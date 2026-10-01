"""Trace where each planted error was lost in a pipeline review.

For every pipeline configuration under `<root>/reviews/` and each judged paper, reads the
judge's candidate and published verdicts and the matched candidates' verification and
editorial record in `review.json`. A planted error that the published review misses is
placed at the first stage that lost it:

- `never raised`: no candidate matched;
- `contradicted by verification` / `unresolved by verification`: every matched candidate
  failed verification, with the best verifier outcome named;
- `set aside by editorial`: a matched candidate passed verification but was not published;
- `published`: a matched candidate was published.

The prefix `uncertain match;` marks errors whose candidate verdict was `uncertain`.

Prints one Markdown table per configuration and writes the rows as JSON.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "benchmark-validity-audit" / "audit-100.json"
JUDGE = "claude-opus-5-5"


def where_lost(judgment: dict, findings: dict[str, dict]) -> str:
    if judgment["published"]["verdict"] == "detected":
        return "published"
    candidate = judgment["candidate"]
    matched = [findings[i] for i in candidate["matched_finding_ids"] if i in findings]
    if candidate["verdict"] == "not_detected" or not matched:
        return "never raised"
    prefix = "uncertain match; " if candidate["verdict"] == "uncertain" else ""
    verified = [f for f in matched if f.get("verifier_status") == "supported" and f.get("status") != "unresolved"]
    if not verified:
        outcomes = {f.get("verifier_status") or f.get("status") for f in matched}
        return prefix + ("unresolved by verification" if "unresolved" in outcomes else "contradicted by verification")
    if not any(f.get("editorial_disposition") == "publish" for f in verified):
        return prefix + "set aside by editorial (" + ", ".join(sorted({f.get("editorial_disposition") or "?" for f in verified})) + ")"
    return prefix + "published"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT / "runs" / "known-errors-all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with (args.root / "ground_truth" / "error_insertions.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    annotations = {}
    for paper in {row["paper"] for row in rows}:
        for index, row in enumerate((r for r in rows if r["paper"] == paper), 1):
            annotations[f"{paper}-{index:02d}"] = row
    audit = {row["id"]: row["verdict"] for row in json.loads(AUDIT.read_text(encoding="utf-8"))["rows"]}
    traced = []
    for config in sorted((args.root / "reviews").glob("pipeline_*")):
        print(f"\n### {config.name}\n\n| Error | Category | Validity audit | Candidate | Published | Matched candidates (module: verifier / editorial) | Lost at |\n|---|---|---|---|---|---|---|")
        for paper_dir in sorted(config.glob("paper-*")):
            scored = paper_dir / f"planted-error-adjudication.{JUDGE}.json"
            if not scored.exists():
                continue
            review = json.loads((paper_dir / "review.json").read_text(encoding="utf-8"))
            findings = {f["id"]: f for f in review.get("findings", [])}
            for judgment in json.loads(scored.read_text(encoding="utf-8"))["judgments"]:
                error_id = judgment["error_id"]
                matched = [findings.get(i, {"id": i}) for i in judgment["candidate"]["matched_finding_ids"]]
                row = {"configuration": config.name, "error_id": error_id, "category": annotations[error_id]["category"],
                       "validity_audit": audit[f"{int(error_id.split('-')[0]):02d}-{error_id.split('-')[1]}"], "candidate": judgment["candidate"]["verdict"],
                       "published": judgment["published"]["verdict"],
                       "matched": [{"id": f["id"], "module": f.get("module"), "verifier_status": f.get("verifier_status"),
                                    "status": f.get("status"), "editorial_disposition": f.get("editorial_disposition")} for f in matched],
                       "lost_at": where_lost(judgment, findings)}
                traced.append(row)
                described = "; ".join(f"{m['module']}: {m['verifier_status']} / {m['editorial_disposition']}" for m in row["matched"]) or "none"
                print(f"| {error_id} | {row['category']} | {row['validity_audit']} | {row['candidate']} | "
                      f"{row['published']} | {described} | {row['lost_at']} |")
    if args.output:
        args.output.write_text(json.dumps(traced, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
