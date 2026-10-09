"""Experimental, model-judged scoring of reviews against planted errors.

This is a development smoke test, not an estimate of review accuracy. The
completed review is loaded before the held-out annotation file, and neither the
annotations nor this adjudication are inputs to review generation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from reviscope.backend import ClaudeBackend
from reviscope.schemas import ReviewRun


class ScopeJudgment(BaseModel):
    verdict: Literal["detected", "not_detected", "uncertain", "unscorable"]
    matched_finding_ids: list[str] = Field(default_factory=list)
    explanation: str
    finding_evidence: list[str] = Field(default_factory=list)


class ErrorJudgment(BaseModel):
    error_id: str
    candidate: ScopeJudgment
    published: ScopeJudgment


class Adjudication(BaseModel):
    judgments: list[ErrorJudgment] = Field(min_length=10, max_length=10)


CRITERIA = """A planted error is detected only when a finding identifies the specific
planted problem or its methodological/statistical consequence. Lexical overlap,
a broad checklist request, or a generic criticism does not count. A finding may
use different terminology if it clearly identifies the same consequence. Do not
count other plausible manuscript problems. Use uncertain when a finding might
refer to the planted consequence but is too ambiguous to decide. Use unscorable
only when the annotation itself lacks enough information to judge. Every detected
verdict must name at least one exact finding ID and quote the finding language that
establishes the match."""

EXCLUDED_PUBLICATION_STATUSES = {"candidate", "unverified", "contradicted"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(finding: object) -> dict[str, object]:
    row = finding.model_dump()
    keys = ("id", "module", "claim", "rationale", "remedy", "severity", "status", "editorial_disposition")
    return {key: row[key] for key in keys}


def load_review(review_path: Path, *, allow_partial: bool = False) -> tuple[str, bool, list[dict[str, object]], list[dict[str, object]]]:
    """Return run ID, partial flag, candidates and published findings.

    A plain single-call review (`{"issues": [...]}`, the Dawes benchmark format) has
    no verification or editorial stage, so its issues are both candidates and published.
    """
    data = json.loads(review_path.read_text(encoding="utf-8"))
    if "issues" in data:
        issues = [{"id": f"issue-{index:02d}", "claim": item["subcategory"], "rationale": item["description"],
                   "quote": item["quote"], "category": item["category"], "severity": item["severity"]}
                  for index, item in enumerate(data["issues"], 1)]
        partial = bool(data.get("partial"))
        if partial and not allow_partial:
            raise ValueError("Refusing to score a partial review")
        return f"plain:{sha256(review_path)[:12]}", partial, issues, issues
    run = ReviewRun.model_validate(data)
    if run.partial and not allow_partial:
        raise ValueError("Refusing to score a partial review")
    candidates = [compact(item) for item in run.candidates]
    published = [
        compact(item)
        for item in run.findings
        if item.editorial_disposition == "publish" and item.status not in EXCLUDED_PUBLICATION_STATUSES
    ]
    return run.metadata.run_id, run.partial, candidates, published


def load_inputs(review_path: Path, annotations_path: Path, paper: str, *, allow_partial: bool = False) -> tuple[str, bool, list[dict[str, str]], list[dict[str, object]], list[dict[str, object]]]:
    # Preserve the blind boundary: validate the completed output before reading gold.
    run_id, partial, candidates, published = load_review(review_path, allow_partial=allow_partial)
    with annotations_path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = [row for row in csv.DictReader(handle) if row["paper"] == paper]
    if len(source_rows) != 10:
        raise ValueError(f"Expected 10 annotations for paper {paper!r}, found {len(source_rows)}")
    errors = [
        {
            "error_id": f"{paper}-{index:02d}",
            "category": row["category"],
            "subcategory": row["subcategory"],
            "original_snippet": row["original_snippet"],
            "modified_snippet": row["modified_snippet"],
            "description": row["description"],
        }
        for index, row in enumerate(source_rows, 1)
    ]
    return run_id, partial, errors, candidates, published


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental planted-error adjudication with a separate model judge")
    parser.add_argument("review", type=Path, help="Completed review.json produced without access to annotations")
    parser.add_argument("--annotations", required=True, type=Path, help="Dawes error_insertions CSV")
    parser.add_argument("--allow-partial", action="store_true", help="Score an incomplete run for development diagnosis only; preserve its partial status")
    parser.add_argument("--paper", required=True, help="Paper identifier in the annotations CSV")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", choices=["claude-opus-5-5"], default="claude-opus-5-5")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    run_id, partial, errors, candidates, published = load_inputs(args.review, args.annotations, args.paper, allow_partial=args.allow_partial)
    expected = {item["error_id"] for item in errors}
    instruction = f"""Adjudicate a completed peer review against ten planted errors.
Apply these criteria strictly:\n{CRITERIA}\nReturn exactly one judgment for every
error_id. Score CANDIDATES before verification/editorial and PUBLISHED after
editorial separately. A published match must use an ID present in PUBLISHED.
The annotation is ground truth for this task; do not assess unrelated errors."""
    evidence = json.dumps({"errors": errors, "candidates": candidates, "published": published}, ensure_ascii=False)
    backend = ClaudeBackend(args.model, args.timeout, args.effort, tools=False)  # the judge reads only the supplied review and annotations
    result = backend.generate(instruction, evidence, Adjudication)

    returned = [item.error_id for item in result.judgments]
    if len(returned) != len(expected) or len(returned) != len(set(returned)) or set(returned) != expected:
        raise ValueError("Judge returned duplicate, missing, or unknown error IDs")
    candidate_ids = {str(item["id"]) for item in candidates}
    published_ids = {str(item["id"]) for item in published}
    for judgment in result.judgments:
        if not set(judgment.candidate.matched_finding_ids) <= candidate_ids:
            raise ValueError(f"Unknown candidate finding ID for {judgment.error_id}")
        if not set(judgment.published.matched_finding_ids) <= published_ids:
            raise ValueError(f"Unknown published finding ID for {judgment.error_id}")
        for scope in (judgment.candidate, judgment.published):
            if scope.verdict == "detected" and (not scope.matched_finding_ids or not scope.finding_evidence):
                raise ValueError(f"Detected verdict lacks finding evidence for {judgment.error_id}")

    def summary(scope: str) -> dict[str, object]:
        counts = {verdict: sum(getattr(row, scope).verdict == verdict for row in result.judgments)
                  for verdict in ("detected", "not_detected", "uncertain", "unscorable")}
        return {"counts": counts, "strict_recall": counts["detected"] / len(errors),
                "detected_error_ids": [row.error_id for row in result.judgments if getattr(row, scope).verdict == "detected"]}

    script_path = Path(__file__).resolve()
    payload = {
        "schema_version": 1,
        "experimental_label": "development known-error smoke test; model-judged; not an accuracy estimate",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "judge": {"backend": backend.name, "model": backend.model, "effort": backend.effort, "tools": backend.tools,
                  "identity": backend.identity, "version": backend.version},
        "review": {"path": str(args.review.resolve()), "sha256": sha256(args.review), "run_id": run_id,
                   "candidate_count": len(candidates), "published_count": len(published), "partial": partial,
                   "partial_diagnostic_authorized": bool(partial and args.allow_partial)},
        "ground_truth": {"path": str(args.annotations.resolve()), "sha256": sha256(args.annotations),
                         "paper": args.paper, "error_count": len(errors)},
        "adjudicator_script": {"path": str(script_path), "sha256": sha256(script_path)},
        "criteria": CRITERIA,
        "candidate_summary": summary("candidate"),
        "published_summary": summary("published"),
        "judgments": [row.model_dump() for row in result.judgments],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"candidate": payload["candidate_summary"], "published": payload["published_summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
