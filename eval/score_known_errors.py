"""Aggregate planted-error adjudications per configuration into strict recall.

Reads `reviews/<label>/paper-NN/planted-error-adjudication.<judge>.json` for every
configuration. Each paper is placed in one group:
- `clean`, `flagged`, `incomplete`: the verdict in the paper's `tool-audit.json`
  (written by eval/run_known_errors.py) for a review with recorded tool calls. A
  partial review is `incomplete` whatever its audit verdict;
- `not_audited`: a review with recorded tool calls but no tool audit;
- `external`: a stored review without tool-call provenance (the benchmark authors'
  reviews), which the audit cannot check.

Recall is reported per group and never pooled across groups. The headline for a
configuration is its `clean` or `external` papers; flagged, incomplete and
unaudited papers are reported beside it. Each summary gives recall over all
annotated targets, over the benchmark-validity audit's `valid_demonstrable_error`
subset, and by audit verdict, for candidate and published findings. The comparison
restricts every configuration to the papers that are headline papers in all of
them; a configuration without headline papers is listed as excluded. Recall is model-judged against the annotations and is a development
diagnostic, not a validated accuracy estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "benchmark-validity-audit" / "audit-100.json"
SCOPES = ("candidate", "published")
GROUPS = ("clean", "external", "flagged", "incomplete", "not_audited")
HEADLINE = {"clean", "external"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_id(error_id: str) -> str:
    paper, index = error_id.split("-")
    return f"{int(paper):02d}-{index}"


def tool_audit_group(directory: Path, review: Path, content: dict) -> str:
    if "stages" not in content:
        return "external"
    path = directory / "tool-audit.json"
    if not path.exists():
        return "not_audited"
    recorded = json.loads(path.read_text(encoding="utf-8"))
    if recorded["review_sha256"] != sha256(review):
        raise ValueError(f"{path} audits an earlier review.json; rerun eval/run_known_errors.py for this paper")
    return recorded["verdict"]


def load_configuration(directory: Path, judge_model: str, root: Path) -> list[dict]:
    papers = []
    for path in sorted(directory.glob(f"paper-*/planted-error-adjudication.{judge_model}.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        review = path.parent / "review.json"
        if data["judge"].get("tools"):
            raise ValueError(f"{path}: judge ran with tools; it must read only the supplied review and annotations")
        if sha256(review) != data["review"]["sha256"]:
            raise ValueError(f"{review} changed after it was scored")
        content = json.loads(review.read_text(encoding="utf-8"))
        if "metadata" in content:
            metadata = content["metadata"]
            generator = {key: metadata[key] for key in ("backend", "model", "effort", "profile", "profile_hash")}
        else:
            generator = content.get("generator") or content.get("model_id") or "external"
        source = json.loads((root / "inputs" / path.parent.name / "provenance.json").read_text(encoding="utf-8"))
        rows = data["judgments"]
        if len(rows) != 10:
            raise ValueError(f"{path}: expected 10 judgments, found {len(rows)}")
        group = "incomplete" if data["review"]["partial"] else tool_audit_group(path.parent, review, content)
        papers.append({"paper": data["ground_truth"]["paper"], "group": group,
                       "partial": data["review"]["partial"],
                       "candidate_count": data["review"]["candidate_count"],
                       "published_count": data["review"]["published_count"],
                       "candidate_detected": data["candidate_summary"]["counts"]["detected"],
                       "published_detected": data["published_summary"]["counts"]["detected"],
                       "generator": generator, "judge": data["judge"]["identity"],
                       "judge_tools": data["judge"].get("tools", "unrecorded"),
                       "input_sha256": source["review_input_sha256"],
                       "artifacts": {str(review.relative_to(root)): data["review"]["sha256"],
                                     str(path.relative_to(root)): sha256(path)},
                       "annotations_sha256": data["ground_truth"]["sha256"],
                       "adjudicator_sha256": data["adjudicator_script"]["sha256"],
                       "verdicts": {audit_id(row["error_id"]): {scope: row[scope]["verdict"] for scope in SCOPES} for row in rows}})
    return sorted(papers, key=lambda row: int(row["paper"]))


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


def verdicts_of(papers: list[dict]) -> dict[str, dict]:
    return {key: value for paper in papers for key, value in paper["verdicts"].items()}


def line(summary: dict) -> str:
    total, subset = summary["all_targets"], summary["demonstrable_subset"]
    return (f"all cand {total['candidate']['detected']}/{total['candidate']['denominator']} "
            f"pub {total['published']['detected']}/{total['published']['denominator']}; "
            f"demonstrable cand {subset['candidate']['detected']}/{subset['candidate']['denominator']} "
            f"pub {subset['published']['detected']}/{subset['published']['denominator']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT / "runs" / "known-errors-all")
    parser.add_argument("--judge-model", default="claude-opus-5-5")
    parser.add_argument("--output", type=Path, help="default: <root>/known-error-scores.json")
    args = parser.parse_args()
    root = args.root.resolve()

    audit = {row["id"]: row["verdict"] for row in json.loads(AUDIT.read_text(encoding="utf-8"))["rows"]}
    configurations = {}
    for directory in sorted(path for path in (root / "reviews").iterdir() if path.is_dir()):
        papers = load_configuration(directory, args.judge_model, root)
        if not papers:
            continue
        groups = {}
        for group in GROUPS:
            members = [paper for paper in papers if paper["group"] == group]
            if members:
                verdicts = verdicts_of(members)
                groups[group] = {"papers": [int(paper["paper"]) for paper in members], **summarise(verdicts, audit, set(verdicts))}
        headline = verdicts_of([paper for paper in papers if paper["group"] in HEADLINE])
        configurations[directory.name] = {"headline": summarise(headline, audit, set(headline)), "groups": groups, "papers": papers}

    headline_ids = {name: set(verdicts_of([p for p in config["papers"] if p["group"] in HEADLINE])) for name, config in configurations.items()}
    compared = [name for name, ids in headline_ids.items() if ids]
    common = set.intersection(*(headline_ids[name] for name in compared)) if compared else set()
    comparison = {name: summarise(verdicts_of(configurations[name]["papers"]), audit, common) for name in compared}
    result = {
        "label": "model-judged strict recall against Dawes annotations; development diagnostic",
        "judge_model": args.judge_model,
        "audit_sha256": sha256(AUDIT),
        "comparison": {"papers": sorted({int(key.split("-")[0]) for key in common}), "configurations": comparison,
                       "excluded_no_headline_papers": [name for name in configurations if name not in compared]},
        "configurations": configurations,
    }
    output = args.output or root / "known-error-scores.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"comparison papers (headline in every compared configuration): {result['comparison']['papers']}")
    if result["comparison"]["excluded_no_headline_papers"]:
        print(f"not compared (no clean or external papers): {result['comparison']['excluded_no_headline_papers']}")
    for name, config in configurations.items():
        print(f"{name}")
        if name in comparison:
            print(f"  comparison: {line(comparison[name])}")
        for group, summary in config["groups"].items():
            print(f"  {group:11} papers {summary['papers']}: {line(summary)}")
    print(f"-> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
