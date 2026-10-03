"""Review benchmark papers, audit each run's tool use, then score it blind to generation.

Each configuration writes to `<root>/reviews/<label>/paper-NN/`:
- `review.json`: `--mode pipeline` runs `reviscope review`; `--mode plain` runs the
  one-call baseline `eval/plain_review.py`; `--mode plain-nolist` runs that baseline
  without the prompt's category list. All run with tools.
- `tool-audit.json`: `eval/audit_tool_use.py --planted-errors` verdict for that paper
  (`clean`, `flagged` or `incomplete`), bound to the review's and the code's sha256.
- `planted-error-adjudication.<judge>.json`: `eval/adjudicate_known_errors.py`.
- `run.json`: every review attempt (command, code snapshot, times, exit code).

Every subprocess runs from a frozen copy of the code: `src/reviscope` (with its
vendored metacheck files), the three eval scripts and `eval/corpus/*.json`, copied
to `<root>/code/<sha256 prefix>/` and put first on PYTHONPATH. Edits to the working
tree during a run do not reach it.

Safe to rerun: `reviscope review` reuses cached successful stages, a complete
review is not regenerated, the audit is redone when the review or the code changed,
and the adjudication only when the review changed. A partial pipeline review is scored with --allow-partial and
stays labelled; a failed plain review is not scored. `--backend fixture` runs the
pipeline with the deterministic demo backend and skips the judge, to check the
chain without model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = {"gpt-6-luna": "codex", "gpt-6.1-sol": "codex", "claude-opus-5-5": "claude"}
MANIFEST = "eval/corpus/known_errors.v1.json"
EVAL_SCRIPTS = ("eval/plain_review.py", "eval/adjudicate_known_errors.py", "eval/audit_tool_use.py", "eval/experiment_discovery.py", "eval/run_development_review.py", "eval/compare_development_reviews.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def code_files(base: Path) -> list[Path]:
    package = [path for path in (base / "src" / "reviscope").rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    return sorted([*package, *(base / name for name in EVAL_SCRIPTS), *(base / "eval" / "corpus").glob("*.json")])


def code_digest(base: Path) -> str:
    lines = "".join(f"{path.relative_to(base)}:{sha256(path)}\n" for path in code_files(base))
    return hashlib.sha256(lines.encode()).hexdigest()


def snapshot(root: Path) -> tuple[Path, str]:
    """Copy the code into a content-addressed directory and check that it is what runs."""
    digest = code_digest(ROOT)
    target = root / "code" / digest[:16]
    if not target.exists():
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        shutil.rmtree(temporary, ignore_errors=True)
        for path in code_files(ROOT):
            copy = temporary / path.relative_to(ROOT)
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, copy)
        try:
            temporary.rename(target)
        except OSError:  # another driver created the same snapshot first
            shutil.rmtree(temporary)
    if code_digest(target) != digest:
        raise SystemExit(f"Snapshot {target} does not match its digest; delete it and rerun")
    probe = "import reviscope, reviscope.metacheck as m; print(reviscope.__file__); print(len(list((m.VENDOR / 'scripts').glob('*.R'))))"
    output = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True,
                            cwd=target, env={**os.environ, "PYTHONPATH": str(target / "src")}).stdout.split()
    if not Path(output[0]).is_relative_to(target) or int(output[1]) == 0:
        raise SystemExit(f"Snapshot {target} is not the imported package or lacks the vendored metacheck scripts: {output}")
    return target, digest


def check_inputs(root: Path, papers: list[int], code: Path) -> None:
    """Refuse to run when an input differs from the manifest the audit uses to identify it."""
    entries = {entry["paper"]: entry for entry in json.loads((code / MANIFEST).read_text(encoding="utf-8"))["entries"]}
    for paper in papers:
        source = root / "inputs" / f"paper-{paper:02d}" / "manuscript.review-input.txt"
        if sha256(source) != entries[str(paper)]["review_input_sha256"]:
            raise SystemExit(f"{source} does not match review_input_sha256 in {MANIFEST}")


def review_command(paper: int, source: Path, out: Path, args: argparse.Namespace) -> list[str]:
    python = sys.executable
    if args.mode != "pipeline":
        command = [python, str(args.code / "eval" / "plain_review.py"), str(source), "--model", args.model,
                   "--effort", args.effort, "--timeout", str(args.timeout), "--output", str(out / "review.json")]
        return command + ["--no-category-list"] if args.mode == "plain-nolist" else command
    command = [python, "-m", "reviscope.cli", "review", str(source), "--profile", args.profile, "--backend", args.backend,
               "--effort", args.effort, "--timeout", str(args.timeout), "--out", str(out), "--quiet"]
    if args.backend != "fixture":
        command += ["--model", args.model]
    if args.no_metacheck:
        command.append("--no-metacheck")
    return command


def run(command: list[str], log, args: argparse.Namespace) -> int:
    log.write(f"$ {' '.join(command)}\n")
    log.flush()
    return subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=args.code, env=args.env).returncode


def audit(paper: int, review: Path, out: Path, log, args: argparse.Namespace) -> str:
    path = out / "tool-audit.json"
    digest = sha256(review)
    if path.exists():
        recorded = json.loads(path.read_text(encoding="utf-8"))
        if recorded["review_sha256"] == digest and recorded["code_sha256"] == args.digest:
            return recorded["verdict"]
    raw = out / "tool-audit.raw.json"
    run([sys.executable, str(args.code / "eval" / "audit_tool_use.py"), str(review), "--paper", f"known-error-{paper}",
         "--planted-errors", "--json", str(raw)], log, args)  # exit 1 means "not clean"
    result = json.loads(raw.read_text(encoding="utf-8"))[0]
    raw.unlink()
    write_json(path, {"review_sha256": digest, "code_sha256": args.digest, "created_at": now(), **result})
    return result["verdict"]


def run_paper(paper: int, args: argparse.Namespace) -> str:
    source = args.root / "inputs" / f"paper-{paper:02d}" / "manuscript.review-input.txt"
    out = args.root / "reviews" / args.label / f"paper-{paper:02d}"
    out.mkdir(parents=True, exist_ok=True)
    review = out / "review.json"
    name = f"{args.label} paper {paper}"
    with (out / "driver.log").open("a", encoding="utf-8") as log:
        # Never start a second review into an output directory that another process is writing.
        while subprocess.run(["pgrep", "-f", f"(reviscope.cli review|plain_review.py) .*{out}"], capture_output=True).returncode == 0:
            time.sleep(30)

        if not (review.exists() and not json.loads(review.read_text(encoding="utf-8")).get("partial")):
            command = review_command(paper, source, out, args)
            attempt = {"command": command, "code": str(args.code), "code_sha256": args.digest, "started_at": now()}
            attempt["exit_code"] = run(command, log, args)
            attempt["finished_at"] = now()
            record = out / "run.json"
            history = json.loads(record.read_text(encoding="utf-8")) if record.exists() else {"attempts": []}
            history["attempts"].append(attempt)
            write_json(record, history)
            if not review.exists():
                return f"{name}: review failed (exit {attempt['exit_code']}), no review.json"
        partial = bool(json.loads(review.read_text(encoding="utf-8")).get("partial"))
        verdict = audit(paper, review, out, log, args)
        status = f"partial={partial}, tool audit {verdict}"
        if args.backend == "fixture":
            return f"{name}: fixture review, not scored ({status})"
        if partial and args.mode != "pipeline":
            return f"{name}: plain review failed, not scored ({status})"

        scored = out / f"planted-error-adjudication.{args.judge_model}.json"
        if scored.exists() and json.loads(scored.read_text(encoding="utf-8"))["review"]["sha256"] == sha256(review):
            return f"{name}: already scored ({status})"
        command = [sys.executable, str(args.code / "eval" / "adjudicate_known_errors.py"), str(review),
                   "--annotations", str(args.root / "ground_truth" / "error_insertions.csv"),
                   "--paper", str(paper), "--output", str(scored), "--model", args.judge_model,
                   "--effort", args.judge_effort, "--timeout", str(args.timeout)]
        if partial:
            command.append("--allow-partial")
        code = run(command, log, args)
        return f"{name}: scored exit {code} ({status})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT / "runs" / "known-errors-all")
    parser.add_argument("--papers", type=int, nargs="+", choices=range(1, 11), default=list(range(1, 11)))
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--mode", choices=["pipeline", "plain", "plain-nolist"], default="pipeline")
    parser.add_argument("--profile", default="social_psychology")
    parser.add_argument("--model", choices=sorted(MODELS), default="gpt-6-luna", help="Reviewer model; sets the backend")
    parser.add_argument("--backend", choices=["fixture"], help="Pipeline with the deterministic demo backend; no model calls, no judge")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="high")
    parser.add_argument("--timeout", type=int, default=3600, help="per-model-call timeout in seconds")
    parser.add_argument("--no-metacheck", action="store_true", help="Skip the pipeline's metacheck screening stage")
    parser.add_argument("--label", help="Configuration directory name (default: <mode>_<model>_<effort>[_<profile>])")
    parser.add_argument("--judge-model", choices=["claude-opus-5-5"], default="claude-opus-5-5")
    parser.add_argument("--judge-effort", default="high")
    args = parser.parse_args()
    if args.backend == "fixture" and args.mode != "pipeline":
        parser.error("--backend fixture applies only to --mode pipeline")
    args.backend = args.backend or MODELS[args.model]
    args.root = args.root.resolve()
    if not args.label:
        reviewer = "fixture" if args.backend == "fixture" else f"{args.model}_{args.effort}"
        args.label = f"pipeline_{reviewer}_{args.profile}" if args.mode == "pipeline" else f"{args.mode}_{reviewer}"
    args.code, args.digest = snapshot(args.root)
    check_inputs(args.root, args.papers, args.code)
    args.env = {**os.environ, "PYTHONPATH": str(args.code / "src")}
    print(f"{now()} {args.label}: code snapshot {args.code} sha256 {args.digest}", flush=True)
    with ThreadPoolExecutor(args.concurrency) as pool:
        for message in pool.map(lambda paper: run_paper(paper, args), args.papers):
            print(f"{now()} {message}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
