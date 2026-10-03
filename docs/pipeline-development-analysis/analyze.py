"""Summarize archived development reviews without publishing manuscript/report text."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


MODEL_STAGE = re.compile(r"^(study_map|review-.+|verification(?:-.+)?|editorial)$")


def summarize(root):
    reviews = []
    for case in ("bonetto", "ziano"):
        historical_durations = {}
        for arm in ("plain", "holistic", "audit"):
            path = root / "reviews" / arm / case / "review.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text())
            stages = [row for row in data["stages"] if MODEL_STAGE.match(row["name"])
                      and row["status"] in {"completed", "cached", "failed"}]
            logical_seconds = 0
            missing_durations = []
            for stage in stages:
                key = stage.get("cache_key")
                if stage["status"] == "cached":
                    duration = historical_durations.get(key)
                else:
                    duration = stage.get("duration_seconds")
                    if key and duration is not None:
                        historical_durations[key] = duration
                if duration is None:
                    missing_durations.append(stage["name"])
                else:
                    logical_seconds += duration
            published = data.get("issues")
            if published is None:
                published = [row for row in data["findings"] if row["editorial_disposition"] == "publish"
                             and row["status"] not in {"candidate", "unverified", "unresolved", "contradicted"}]
            audit = json.loads((path.parent / "tool-audit.json").read_text())[0]
            meta = data.get("metadata", {})
            reviews.append({"case": case, "arm": arm, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "engine_version": meta.get("engine_version"), "partial": data["partial"],
                            "candidate_count": len(data.get("candidates", data.get("issues", []))),
                            "published_count": len(published),
                            "published_severity": dict(Counter(row["severity"] for row in published)),
                            "published_kind": dict(Counter(row.get("kind", "plain_schema") for row in published)),
                            "finding_status": dict(Counter(row["status"] for row in data.get("findings", []))),
                            "editorial_disposition": dict(Counter(row["editorial_disposition"] for row in data.get("findings", []))),
                            "logical_model_calls": len(stages),
                            "fresh_model_calls": sum(row["status"] != "cached" for row in stages),
                            "logical_stage_minutes": None if missing_durations else round(logical_seconds / 60, 2),
                            "unknown_stage_durations": missing_durations,
                            "incremental_stage_minutes": round(sum(row.get("duration_seconds") or 0 for row in stages if row["status"] != "cached")/60, 2),
                            "tool_calls": sum(len(row.get("tool_calls", [])) for row in stages),
                            "audit_verdict": audit["verdict"], "audit_reasons": audit["reasons"],
                            "source_task_count": len(data.get("source_tasks", [])),
                            "source_task_checks": dict(Counter(row["check"] for row in data.get("source_tasks", []))),
                            "backend_versions": sorted({row["backend_version"] for row in stages if row.get("backend_version")})})
    comparisons = []
    for path in sorted((root / "comparisons").rglob("*.json")):
        data = json.loads(path.read_text())
        comparisons.append({"case": data["case"], "left": data["left"], "right": data["right"],
                            "judge": data["model"], "backend_version": data["backend_version"],
                            "cache_key": data["cache_key"], "source_hashes": data["source_hashes"],
                            "audit_groups": data["audit_groups"], "invalid": data["invalid"],
                            "outcome": data["aggregate"]["paper_outcomes"],
                            "order_discordant": data["aggregate"]["order_discordant_papers"],
                            "orders": [{"order": row["order"], "winner": row["winner"],
                                        "confidence": row["judgment"]["confidence"]}
                                       for row in data["judgments"]]})
    return {"scope": "Two development submissions, one run per arm; multiple reports and presentation orders are repeated assessments, not independent papers.",
            "cost_note": "Stage minutes sum sequential model calls. Audit-arm logical cost includes reused broad/verification calls at their archived duration; incremental cost counts calls made to extend the shared run. Metacheck and judge time are excluded.",
            "snapshots": {label: json.loads((root / (label + "-snapshot.json")).read_text())
                          for label in ("baseline", "candidate", "evaluation")},
            "reviews": reviews, "comparisons": comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("analysis.json"))
    args = parser.parse_args()
    data = summarize(args.root)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for row in data["reviews"]:
        print(row["case"], row["arm"], row["candidate_count"], row["published_count"], row["logical_stage_minutes"])


if __name__ == "__main__":
    main()
