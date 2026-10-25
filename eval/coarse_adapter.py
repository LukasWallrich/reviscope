"""Convert a coarse review (markdown from `coarse-review`) into the plain-review JSON format,
so `reviscope judge-criticisms` can judge it as an arm.

Overall-feedback issues become criticisms without a quotation; detailed comments keep their
quotation. coarse prints no per-comment severity, so overall issues are labelled major and
detailed comments moderate; the judge never shows severity to its models. Feedback text,
including coarse's embedded remedy, becomes the description. `--manuscript` names the source
the judge will read; its hash is recorded so the judge can match the arm to the paper, even
when coarse read a markdown conversion of it (recorded as `coarse_input`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def parse(markdown: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    overall = markdown.split("## Overall Feedback", 1)[-1].split("**Recommendation**", 1)[0]
    overall = overall.split("## Detailed Comments", 1)[0]
    for title, body in re.findall(r"^\*\*(.+?)\*\*\s*\n\n(.+?)(?=\n\n\*\*|\Z)", overall, flags=re.M | re.S):
        if title.strip().lower().startswith(("status", "key revision")):
            continue
        issues.append({"category": "overall", "description": f"{title.strip()}. {body.strip()}",
                       "quote": "", "location": "overall", "severity": "major"})
    detailed = markdown.split("## Detailed Comments", 1)[1] if "## Detailed Comments" in markdown else ""
    for block in re.split(r"^### \d+\.\s*", detailed, flags=re.M)[1:]:
        title = block.splitlines()[0].strip()
        quote = re.search(r"\*\*Quote\*\*:\s*\n((?:>.*\n?)+)", block)
        feedback = re.search(r"\*\*Feedback\*\*:\s*\n(.+?)(?=\n---|\Z)", block, flags=re.S)
        quote_text = " ".join(line.lstrip("> ").strip() for line in quote.group(1).splitlines()) if quote else ""
        issues.append({"category": "detailed", "description": f"{title}. {feedback.group(1).strip() if feedback else ''}",
                       "quote": re.sub(r"\s+", " ", quote_text).strip(), "location": "detailed comment",
                       "severity": "moderate"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path, help="coarse review markdown")
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument("--supplement", action="append", type=Path, default=[])
    parser.add_argument("--coarse-input", type=Path, help="the file coarse actually read")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    issues = parse(args.review.read_text(encoding="utf-8"))
    sources = [{"id": "manuscript", "kind": "manuscript", "path": str(args.manuscript.resolve()),
                "sha256": hashlib.sha256(args.manuscript.read_bytes()).hexdigest()}]
    sources += [{"id": f"supplement-{i}", "kind": "supplement", "path": str(p.resolve()),
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for i, p in enumerate(args.supplement)]
    payload = {"generator": "coarse", "prompt": "coarse-review (headless)", "partial": False, "sources": sources,
               "coarse_review": str(args.review.resolve()),
               "coarse_input": str(args.coarse_input.resolve()) if args.coarse_input else None,
               "stages": [{"name": "review-coarse", "status": "completed", "tool_calls": []}], "issues": issues}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(issues)} issues -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
