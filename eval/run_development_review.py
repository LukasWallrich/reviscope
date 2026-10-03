"""Archive nested discovery arms while sharing each paper's content-keyed stages."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    working = args.root / "reviews" / "working" / args.case
    working.mkdir(parents=True, exist_ok=True)
    code = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(code / "src")}
    records = []
    for arm, extra in (("holistic", []), ("audit", ["--evidence-audit"])):
        archived = args.root / "reviews" / arm / args.case
        if (archived / "review.json").exists():
            prior = json.loads((archived / "review.json").read_text())
            if not prior["partial"]:
                print(f"{arm}/{args.case}: complete archive retained", flush=True)
                continue
        command = [sys.executable, "-m", "reviscope.cli", "review", str(args.manuscript.resolve()),
                   "--strategy", "holistic", *extra, "--backend", "codex", "--model", "gpt-6.1-sol",
                   "--effort", "high", "--verifier-backend", "claude", "--verifier-model", "claude-opus-5-5",
                   "--verifier-effort", "high", "--out", str(working.resolve())]
        started = time.monotonic()
        result = subprocess.run(command, cwd=code, env=env)
        record = {"arm": arm, "case": args.case, "command": command, "returncode": result.returncode,
                  "wall_seconds": time.monotonic() - started, "code": str(code),
                  "manuscript_sha256": hashlib.sha256(args.manuscript.read_bytes()).hexdigest()}
        if (working / "review.json").exists() and result.returncode in {0, 2}:
            archived.mkdir(parents=True, exist_ok=True)
            for name in ("review.json", "review.md", "review.html", "run.log"):
                shutil.copy2(working / name, archived / name)
            record["review_sha256"] = hashlib.sha256((archived / "review.json").read_bytes()).hexdigest()
            record["archive"] = str(archived)
        records.append(record)
        (working / "arms.json").write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        if result.returncode not in {0, 2}:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
