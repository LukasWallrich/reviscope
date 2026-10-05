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


def code_digest(code):
    paths = sorted(p for p in (code / "src" / "reviscope").rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts)
    paths.append(Path(__file__).resolve())
    records = "".join(f"{p.relative_to(code)}:{hashlib.sha256(p.read_bytes()).hexdigest()}\n" for p in paths)
    return hashlib.sha256(records.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--profile", required=True,
                        help="Use the corpus case's discipline profile, including tutorials")
    args = parser.parse_args()
    working = args.root / "reviews" / "working" / args.case
    working.mkdir(parents=True, exist_ok=True)
    code = Path(__file__).resolve().parents[1]
    digest = code_digest(code)
    env = {**os.environ, "PYTHONPATH": str(code / "src")}
    records_path = working / "arms.json"
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    for arm, extra in (("holistic", []), ("audit", ["--evidence-audit"])):
        archived = args.root / "reviews" / arm / args.case
        if (archived / "review.json").exists():
            prior = json.loads((archived / "review.json").read_text())
            if not prior["partial"]:
                if (prior.get("metadata", {}).get("profile") != args.profile
                        or prior.get("metadata", {}).get("evidence_audit") is not (arm == "audit")):
                    raise ValueError("Complete archive differs from requested profile or audit arm; use a new root")
                review_hash = hashlib.sha256((archived / "review.json").read_bytes()).hexdigest()
                record = next((r for r in reversed(records) if r.get("arm") == arm
                               and r.get("review_sha256") == review_hash), {})
                if (record.get("code_sha256") != digest
                        or record.get("manuscript_sha256") != hashlib.sha256(args.manuscript.read_bytes()).hexdigest()):
                    raise ValueError("Complete archive has different or missing frozen provenance; use a new root")
                print(f"{arm}/{args.case}: complete archive retained", flush=True)
                continue
        command = [sys.executable, "-m", "reviscope.cli", "review", str(args.manuscript.resolve()),
                   "--profile", args.profile,
                   "--strategy", "holistic", *extra, "--backend", "codex", "--model", "gpt-6.1-sol",
                   "--effort", "high", "--verifier-backend", "claude", "--verifier-model", "claude-opus-5-5",
                   "--verifier-effort", "high", "--out", str(working.resolve())]
        # A usage error may also exit 2. Never mistake the previous arm's report for a new one.
        (working / "review.json").unlink(missing_ok=True)
        (working / "run.log").unlink(missing_ok=True)
        started = time.monotonic()
        result = subprocess.run(command, cwd=code, env=env)
        record = {"arm": arm, "case": args.case, "command": command, "returncode": result.returncode,
                  "profile": args.profile,
                  "wall_seconds": time.monotonic() - started, "code": str(code), "code_sha256": digest,
                  "manuscript_sha256": hashlib.sha256(args.manuscript.read_bytes()).hexdigest()}
        if (working / "review.json").exists() and result.returncode in {0, 2}:
            review = json.loads((working / "review.json").read_text())
            if review.get("metadata", {}).get("evidence_audit") is not (arm == "audit"):
                raise ValueError(f"{arm}/{args.case}: output does not identify the requested audit arm")
            if review.get("metadata", {}).get("profile") != args.profile:
                raise ValueError(f"{arm}/{args.case}: output profile differs from the requested profile")
            archived.mkdir(parents=True, exist_ok=True)
            for name in ("review.json", "review.md", "review.html", "run.log"):
                shutil.copy2(working / name, archived / name)
            record["review_sha256"] = hashlib.sha256((archived / "review.json").read_bytes()).hexdigest()
            record["archive"] = str(archived)
        records.append(record)
        records_path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        if result.returncode not in {0, 2}:
            return result.returncode
        if not (working / "review.json").exists():
            return result.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
