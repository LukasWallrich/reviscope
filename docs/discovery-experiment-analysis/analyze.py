"""Summarize saved discovery experiments without model calls or external lookups."""

from collections import Counter
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "runs/discovery-exploration-0.4.2"
AUDIT_PATH = REPO / "docs/benchmark-validity-audit/audit-100.json"
AUDIT = {row["id"]: row["verdict"] for row in json.loads(AUDIT_PATH.read_text())["rows"]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(mode, paper):
    directory = ROOT / "reviews" / mode / f"paper-{paper:02d}"
    review_path = directory / "review.json"
    judge_path = directory / "planted-error-adjudication.claude-opus-5-5.json"
    review = json.loads(review_path.read_text())
    judgment = json.loads(judge_path.read_text())
    assert judgment["review"]["sha256"] == digest(review_path)
    assert not review["partial"]
    assert judgment["judge"]["tools"] is False
    assert len(judgment["judgments"]) == 10
    tool_audit = json.loads((directory / "tool-audit.json").read_text())
    stages = [s for s in review["stages"] if s["status"] == "completed" and s["name"] != "metacheck"]
    findings = {f["id"]: f for f in review["findings"]}
    rows = []
    for row in judgment["judgments"]:
        ordinal = int(row["error_id"].split("-")[1])
        rows.append({"error_id": row["error_id"], "validity": AUDIT[f"{paper:02d}-{ordinal:02d}"],
                     **{scope: {"verdict": row[scope]["verdict"], "matched_ids": row[scope]["matched_finding_ids"]}
                        for scope in ("candidate", "published")}})
    categories = sorted({row["validity"] for row in rows})
    counts = {category: {"denominator": sum(r["validity"] == category for r in rows),
                         **{scope: sum(r["validity"] == category and r[scope]["verdict"] == "detected" for r in rows)
                            for scope in ("candidate", "published")}}
              for category in categories}
    held = []
    for f in findings.values():
        if f["editorial_disposition"] != "needs_review":
            continue
        reason = ("supported_claim_editorial" if f["status"] == "llm_supported" else
                  "required_external_unchecked" if f["verifier_status"] == "supported" and
                  "no external item was confirmed" in (f.get("verification") or "") else
                  "verifier_unresolved")
        held.append({"id": f["id"], "reason": reason, "severity": f["severity"]})
    return {"mode": mode, "paper": paper, "review_sha256": digest(review_path),
            "judgment_sha256": digest(judge_path), "judge": judgment["judge"],
            "audit_verdicts": [a["verdict"] for a in tool_audit], "partial": review["partial"],
            "candidates": len(review["candidates"]),
            "editorial": dict(Counter(f["editorial_disposition"] for f in findings.values())),
            "verification": dict(Counter(f["verifier_status"] for f in findings.values())),
            "new_model_calls": len(stages), "new_stage_minutes": sum(s["duration_seconds"] for s in stages) / 60,
            "new_stage_versions": sorted({s["backend_version"] for s in stages}),
            "by_validity": counts, "candidate_summary": judgment["candidate_summary"],
            "published_summary": judgment["published_summary"], "held": held, "targets": rows}


def main():
    results = [summarize(mode, paper) for mode in ("replay", "holistic") for paper in (5, 9)]
    totals = {}
    for mode in ("replay", "holistic"):
        selected = [r for r in results if r["mode"] == mode]
        totals[mode] = {"candidates": sum(r["candidates"] for r in selected),
                        "published_findings": sum(r["editorial"].get("publish", 0) for r in selected),
                        "new_model_calls": sum(r["new_model_calls"] for r in selected),
                        "new_stage_minutes": sum(r["new_stage_minutes"] for r in selected),
                        **{scope: sum(r[f"{scope}_summary"]["counts"]["detected"] for r in selected)
                           for scope in ("candidate", "published")}}
    payload = {"label": "Four exploratory Sol/high reviews; single-run diagnostic, not an accuracy estimate",
               "snapshot": json.loads((ROOT / "snapshot.json").read_text()),
               "validity_audit_sha256": digest(AUDIT_PATH), "runs": results, "totals": totals}
    Path(__file__).with_name("analysis.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
