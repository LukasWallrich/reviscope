"""Aggregate planted-error adjudications per configuration into strict recall.

Reads `reviews/<label>/paper-NN/planted-error-adjudication.<judge>.json` for every
configuration and reports recall over all annotated targets, over the
benchmark-validity audit's `valid_demonstrable_error` subset, and by audit
verdict. A comparison table restricts every configuration to the papers that all
of them scored. Recall is model-judged against the annotations and is a
development diagnostic, not a validated accuracy estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "benchmark-validity-audit" / "audit-100.json"
SCOPES = ("candidate", "published")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_id(error_id: str) -> str:
    paper, index = error_id.split("-")
    return f"{int(paper):02d}-{index}"


def load_configuration(directory: Path, judge_model: str, audit: dict[str, str], inputs: Path) -> tuple[list[dict], dict[str, dict]]:
    papers, verdicts = [], {}
    for path in sorted(directory.glob(f"paper-*/planted-error-adjudication.{judge_model}.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        review = path.parent / "review.json"
        if ":tools-" in data["judge"]["identity"]:
            raise ValueError(f"{path}: judge ran with tools; it must read only the supplied review and annotations")
        if sha256(review) != data["review"]["sha256"]:
            raise ValueError(f"{review} changed after it was scored")
        content = json.loads(review.read_text(encoding="utf-8"))
        if "metadata" in content:
            metadata = content["metadata"]
            generator = {key: metadata[key] for key in ("backend", "model", "effort", "profile", "profile_hash")}
            verifier = {key: metadata[key] for key in ("verifier_backend", "verifier_model", "verifier_effort", "verification_relationship")}
        else:
            generator, verifier = content.get("generator", "external"), None
        source = json.loads((inputs / path.parent.name / "provenance.json").read_text(encoding="utf-8"))
        rows = data["judgments"]
        if len(rows) != 10:
            raise ValueError(f"{path}: expected 10 judgments, found {len(rows)}")
        papers.append({"paper": data["ground_truth"]["paper"], "partial": data["review"]["partial"],
                       "candidate_count": data["review"]["candidate_count"],
                       "published_count": data["review"]["published_count"],
                       "candidate_detected": data["candidate_summary"]["counts"]["detected"],
                       "published_detected": data["published_summary"]["counts"]["detected"],
                       "generator": generator, "verifier": verifier, "judge": data["judge"]["identity"],
                       "input_sha256": source["review_input_sha256"],
                       "artifacts": {str(review.relative_to(ROOT)): data["review"]["sha256"],
                                     str(path.relative_to(ROOT)): sha256(path)},
                       "annotations_sha256": data["ground_truth"]["sha256"],
                       "adjudicator_sha256": data["adjudicator_script"]["sha256"]})
        for row in rows:
            key = audit_id(row["error_id"])
            verdicts[key] = {"candidate": row["candidate"]["verdict"], "published": row["published"]["verdict"],
                             "audit": audit[key]}
    return sorted(papers, key=lambda row: int(row["paper"])), dict(sorted(verdicts.items()))


def recall(verdicts: dict[str, dict], ids: set[str], scope: str) -> dict[str, object]:
    scored = ids & verdicts.keys()
    hits = sum(verdicts[key][scope] == "detected" for key in scored)
    uncertain = sum(verdicts[key][scope] == "uncertain" for key in scored)
    return {"detected": hits, "uncertain": uncertain, "denominator": len(scored),
            "recall": hits / len(scored) if scored else None}


def summarise(verdicts: dict[str, dict], audit: dict[str, str], ids: set[str]) -> dict[str, object]:
    subset = {key for key in ids if audit[key] == "valid_demonstrable_error"}
    return {"all_targets": {scope: recall(verdicts, ids, scope) for scope in SCOPES},
            "demonstrable_subset": {scope: recall(verdicts, subset, scope) for scope in SCOPES},
            "by_audit_verdict": {verdict: {scope: recall(verdicts, {k for k in ids if audit[k] == verdict}, scope) for scope in SCOPES}
                                 for verdict in sorted(set(audit.values()))}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "runs" / "known-errors-all")
    parser.add_argument("--judge-model", default="claude-opus-5-5")
    parser.add_argument("--output", type=Path, default=ROOT / "eval" / "results" / "known-errors-all.json")
    args = parser.parse_args()

    audit = {row["id"]: row["verdict"] for row in json.loads(AUDIT.read_text(encoding="utf-8"))["rows"]}
    configurations = {}
    for directory in sorted(path for path in (args.root / "reviews").iterdir() if path.is_dir()):
        papers, verdicts = load_configuration(directory, args.judge_model, audit, args.root / "inputs")
        if papers:
            configurations[directory.name] = {"papers": papers, "verdicts": verdicts,
                                              **summarise(verdicts, audit, set(verdicts))}
    common = set.intersection(*(set(config["verdicts"]) for config in configurations.values()))
    common_papers = sorted({int(key.split("-")[0]) for key in common})
    result = {
        "label": "model-judged strict recall against Dawes annotations; development diagnostic",
        "judge_model": args.judge_model,
        "audit_sha256": sha256(AUDIT),
        "comparison": {"papers": common_papers,
                       "configurations": {name: summarise(config["verdicts"], audit, common)
                                          for name, config in configurations.items()}},
        "configurations": configurations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"common papers: {common_papers}")
    for name, config in configurations.items():
        shared = result["comparison"]["configurations"][name]
        print(f"{name}: {len(config['papers'])} papers | all {config['all_targets']['candidate']['detected']}/"
              f"{config['all_targets']['candidate']['denominator']} cand, {config['all_targets']['published']['detected']} pub | "
              f"common: cand {shared['all_targets']['candidate']['detected']}/{shared['all_targets']['candidate']['denominator']}, "
              f"demonstrable {shared['demonstrable_subset']['candidate']['detected']}/{shared['demonstrable_subset']['candidate']['denominator']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
