"""Review every prepared benchmark paper, then score each review blind to generation.

Each configuration writes to `reviews/<label>/paper-NN/`. `--mode pipeline` runs
`reviscope review`; `--mode plain` runs the single-call baseline in
`eval/plain_review.py`. A `review.json` placed in a paper directory by other means
(for example a stored benchmark review) is scored without regeneration.

Safe to rerun: `reviscope review` reuses cached successful stages, a complete
review is not regenerated, and an adjudication is redone only when its review
file changed. Partial reviews are scored with --allow-partial and stay labelled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".venv" / "bin"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_paper(paper: int, args: argparse.Namespace) -> str:
    source = args.root / "inputs" / f"paper-{paper:02d}" / "manuscript.review-input.txt"
    out = args.root / "reviews" / args.label / f"paper-{paper:02d}"
    out.mkdir(parents=True, exist_ok=True)
    review = out / "review.json"
    log = (out / "driver.log").open("a", encoding="utf-8")

    # Never start a second review into an output directory that another process is writing.
    while subprocess.run(["pgrep", "-f", f"(reviscope review|plain_review.py) .* {out}"], capture_output=True).returncode == 0:
        time.sleep(30)

    complete = review.exists() and not json.loads(review.read_text(encoding="utf-8")).get("partial")
    if not complete:
        common = ["--backend", args.backend, "--model", args.model, "--effort", args.effort, "--timeout", str(args.timeout)]
        if args.mode == "pipeline":
            command = [str(BIN / "reviscope"), "review", str(source), "--profile", args.profile, *common, "--out", str(out), "--quiet"]
        else:
            command = [str(BIN / "python"), str(ROOT / "eval" / "plain_review.py"), str(source), *common, "--output", str(review)]
        log.write(f"$ {' '.join(command)}\n")
        log.flush()
        code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=args.env).returncode
        if not review.exists():
            return f"{args.label} paper {paper}: review failed (exit {code}), no review.json"
    partial = bool(json.loads(review.read_text(encoding="utf-8")).get("partial"))

    scored = out / f"planted-error-adjudication.{args.judge_model}.json"
    if scored.exists() and json.loads(scored.read_text(encoding="utf-8"))["review"]["sha256"] == sha256(review):
        return f"{args.label} paper {paper}: already scored (partial={partial})"
    command = [str(BIN / "python"), str(ROOT / "eval" / "adjudicate_known_errors.py"), str(review),
               "--annotations", str(args.root / "ground_truth" / "error_insertions.csv"),
               "--paper", str(paper), "--output", str(scored),
               "--model", args.judge_model, "--effort", args.judge_effort]
    if partial:
        command.append("--allow-partial")
    log.write(f"$ {' '.join(command)}\n")
    log.flush()
    code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=args.env).returncode
    return f"{args.label} paper {paper}: scored exit {code} (partial={partial})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "runs" / "known-errors-all")
    parser.add_argument("--papers", type=int, nargs="+", default=list(range(1, 11)))
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--mode", choices=["pipeline", "plain"], default="pipeline")
    parser.add_argument("--profile", default="social_psychology_v2")
    parser.add_argument("--backend", choices=["codex", "claude"], default="codex")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--effort", default="max")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--label", help="Configuration directory name (default: <mode>_<model>[_<profile>])")
    parser.add_argument("--judge-model", default="claude-opus-5-5")
    parser.add_argument("--judge-effort", default="high")
    parser.add_argument("--code", type=Path, help="Directory holding a frozen `reviscope` package copy to import instead of src/")
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.env = dict(os.environ)
    if args.code:
        args.code = args.code.resolve()
        args.env["PYTHONPATH"] = str(args.code)
        files = sorted(path for path in (args.code / "reviscope").rglob("*") if path.is_file() and "__pycache__" not in path.parts)
        digest = hashlib.sha256("".join(f"{path.relative_to(args.code)}:{sha256(path)}\n" for path in files).encode()).hexdigest()
        print(f"code snapshot {args.code} sha256 {digest}", flush=True)
    if not args.label:
        args.label = f"pipeline_{args.model}_{args.profile}" if args.mode == "pipeline" else f"plain_{args.model}"
    with ThreadPoolExecutor(args.concurrency) as pool:
        for message in pool.map(lambda paper: run_paper(paper, args), args.papers):
            print(message, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
