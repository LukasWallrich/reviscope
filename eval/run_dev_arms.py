"""Run the specialist pipeline and the general one-call baseline on a development case.

Each arm and run writes to ROOT/ARM/CASE/run-N with a provenance record: code commit,
input hashes, command, return code and wall time. A completed, non-partial run is kept
and skipped on rerun. Runs of one case execute in sequence; the pipeline parallelizes
its own stages. Cases in the fenced validation set are refused when eval/check_fence.py
exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
SPECIALIST = ["--backend", "codex", "--model", "gpt-6.1-sol", "--effort", "high",
              "--verifier-backend", "claude", "--verifier-model", "claude-opus-5-5", "--verifier-effort", "high"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commit() -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=CODE, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "eval"], cwd=CODE, capture_output=True, text=True).stdout.strip()
    return head + ("+dirty" if dirty else "")


def command(arm: str, manuscript: Path, supplements: list[Path], out: Path, args: argparse.Namespace) -> list[str]:
    supplement_args = [part for path in supplements for part in ("--supplement", str(path))]
    if arm == "specialist":
        return [sys.executable, "-m", "reviscope.cli", "review", str(manuscript), *supplement_args,
                "--profile", args.profile, "--parallel", str(args.parallel), *SPECIALIST, "--out", str(out),
                *(["--no-metacheck"] if args.no_metacheck else [])]
    if arm == "plain":
        return [sys.executable, str(CODE / "eval" / "plain_review.py"), str(manuscript), *supplement_args,
                "--prompt", "general", "--model", "gpt-6.1-sol", "--effort", "high", "--output", str(out / "review.json")]
    raise ValueError(arm)


def complete(out: Path) -> bool:
    path = out / "review.json"
    return path.is_file() and not json.loads(path.read_text(encoding="utf-8")).get("partial", True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--supplement", action="append", type=Path, default=[])
    parser.add_argument("--arms", nargs="+", choices=["specialist", "plain"], default=["specialist", "plain"])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--profile", default="social_psychology")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--no-metacheck", action="store_true", help="for unpublished manuscripts without a local GROBID server")
    args = parser.parse_args()

    inputs = [args.manuscript.resolve(), *(path.resolve() for path in args.supplement)]
    fence = CODE / "eval" / "check_fence.py"
    if fence.is_file():
        for path in inputs:
            if subprocess.run([sys.executable, str(fence), str(path)]).returncode:
                print(f"refused: {path} is in the fenced validation set", file=sys.stderr)
                return 2
    env = {**os.environ, "PYTHONPATH": str(CODE / "src")}
    failures = 0
    for run in range(1, args.runs + 1):
        for arm in args.arms:
            out = (args.root / arm / args.case / f"run-{run}").resolve()
            if complete(out):
                print(f"{arm}/{args.case}/run-{run}: complete, kept", flush=True)
                continue
            out.mkdir(parents=True, exist_ok=True)
            cmd = command(arm, inputs[0], inputs[1:], out, args)
            started = time.monotonic()
            with (out / "driver.log").open("a", encoding="utf-8") as log:
                result = subprocess.run(cmd, cwd=CODE, env=env, stdout=log, stderr=subprocess.STDOUT)
            record = {"arm": arm, "case": args.case, "run": run, "command": cmd, "returncode": result.returncode,
                      "wall_seconds": round(time.monotonic() - started, 1), "code_commit": commit(),
                      "inputs": [{"path": str(path), "sha256": sha256(path)} for path in inputs],
                      "complete": complete(out)}
            (out / "provenance.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            failures += not record["complete"]
            print(f"{arm}/{args.case}/run-{run}: {'complete' if record['complete'] else 'INCOMPLETE'} "
                  f"in {record['wall_seconds'] / 60:.1f} min", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
