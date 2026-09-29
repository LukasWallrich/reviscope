"""Review-only normalization for pairwise evaluation sensitivity analyses."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Any, Mapping

from pydantic import BaseModel, Field, StringConstraints

from .backend import Backend, ClaudeBackend, CodexBackend
from .verification import verify_quote


PROMPT_VERSION = "review-normalization-v2"
AUDIT_PROMPT_VERSION = "review-normalization-audit-v3"


NonEmptySpan = Annotated[str, StringConstraints(min_length=1)]


class AtomicIssue(BaseModel):
    issue_id: str
    assessment_type: str
    evaluation: str
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    remedy: str
    qualifications: list[str] = Field(default_factory=list)
    source_review_spans: list[NonEmptySpan] = Field(min_length=1)


class ReviewInventory(BaseModel):
    issues: list[AtomicIssue]


class MissingIssue(BaseModel):
    description: str
    source_review_spans: list[NonEmptySpan] = Field(min_length=1)


class InventoryAudit(BaseModel):
    faithful: bool
    complete: bool
    missing_issues: list[MissingIssue] = Field(default_factory=list)
    unsupported_issue_ids: list[str] = Field(default_factory=list)
    duplicate_issue_ids: list[str] = Field(default_factory=list)
    rationale: str


def _instruction(max_issues: int) -> str:
    return f"""Convert one peer review into a neutral inventory of at most {max_issues} atomic substantive assessments.
Use only the review. Do not consult or infer from the manuscript. Preserve mathematical notation, alleged errors,
qualifications, uncertainty, and missing evaluation/rationale/evidence/remedy fields. Include criticisms, strengths,
endorsements, and substantive overall assessments; label assessment_type accordingly. Use an empty string or empty
list when the review omits a field; never add or repair content. Split distinct assessments and do not duplicate them.
Every assessment must include one or more exact, contiguous source-review spans supporting the inventory entry.
Do not use ellipses or stitch non-contiguous text into one span. Ignore greetings, identity, and editorial boilerplate."""


def _audit_instruction() -> str:
    return """Audit a normalized issue inventory against its source peer review. Use only these supplied materials.
Mark faithful false if an inventory item adds, repairs, strengthens, or materially changes the review. Mark complete
false if any substantive criticism, strength, endorsement, overall evaluation, remedy, qualification, equation, or
alleged error is omitted. Identify duplicates.
An obvious or reasonable implicit remedy that the reviewer did not state is still an addition and requires faithful=false.
Every missing issue must cite exact contiguous spans from the source review. Do not evaluate whether the review is
correct about the manuscript."""


def _exact_source_span(span: str, review: str) -> tuple[str | None, str | None]:
    """Return an exact raw span, correcting only an explicit PDF line-wrap artifact."""
    direct = verify_quote(span, [review])
    if direct.status == "supported":
        if direct.source_char_start is None or direct.source_char_end is None:
            return None, None
        exact = review[direct.source_char_start:direct.source_char_end]
        return exact, None if exact == span else "exact_raw_source_slice"
    dehyphenated = re.sub(r"(?<=[^\W\d_])-\s+(?=[^\W\d_])", "", span)
    if dehyphenated == span:
        return None, None
    recovered = verify_quote(dehyphenated, [review])
    if recovered.status != "supported" or recovered.source_char_start is None or recovered.source_char_end is None:
        return None, None
    return review[recovered.source_char_start:recovered.source_char_end], "pdf_linewrap_dehyphenation"


def _assemble_inventory(review: str, inventory: ReviewInventory, backend: Backend, max_issues: int) -> dict[str, Any]:
    ids = [item.issue_id for item in inventory.issues]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    seen_content: dict[tuple[str, tuple[str, ...]], str] = {}
    duplicate_content = []
    unmatched, span_corrections = [], []
    for issue in inventory.issues:
        key = (" ".join(issue.evaluation.casefold().split()), tuple(sorted(" ".join(s.casefold().split()) for s in issue.source_review_spans)))
        if key in seen_content:
            duplicate_content.append([seen_content[key], issue.issue_id])
        else:
            seen_content[key] = issue.issue_id
        for index, span in enumerate(issue.source_review_spans):
            exact, correction = _exact_source_span(span, review)
            if exact is None:
                unmatched.append({"issue_id": issue.issue_id, "span": span})
            elif correction:
                issue.source_review_spans[index] = exact
                span_corrections.append({"issue_id": issue.issue_id, "kind": correction})
    result = {
        "normalization_schema_version": 1,
        "prompt_version": PROMPT_VERSION,
        "backend": backend.identity,
        "source_review_sha256": hashlib.sha256(review.encode()).hexdigest(),
        "max_issues": max_issues,
        "inventory": inventory.model_dump(),
        "deterministic_checks": {
            "all_source_spans_matched": not unmatched,
            "unmatched_spans": unmatched,
            "source_span_corrections": span_corrections,
            "duplicate_issue_ids": duplicate_ids,
            "duplicate_content": duplicate_content,
            "issue_cap_reached": len(inventory.issues) >= max_issues,
        },
    }
    if hasattr(backend, "calls"):
        result["model_calls"] = list(backend.calls)
    return result


def normalize_review(review: str, backend: Backend, *, max_issues: int = 40) -> dict[str, Any]:
    if max_issues < 1:
        raise ValueError("max_issues must be positive")
    inventory = backend.generate(_instruction(max_issues), review, ReviewInventory)
    return _assemble_inventory(review, inventory, backend, max_issues)


def revise_inventory(review: str, prior: Mapping[str, Any], audit: Mapping[str, Any], backend: Backend) -> dict[str, Any]:
    """One model revision using a failed audit as a completeness checklist."""
    if audit.get("comparison_eligible"):
        raise ValueError("revision is only available for a failed inventory audit")
    expected = hashlib.sha256(review.encode()).hexdigest()
    if prior.get("source_review_sha256") != expected or audit.get("source_review_sha256") != expected:
        raise ValueError("revision inputs do not match the source review")
    max_issues = int(prior["max_issues"])
    instruction = (_instruction(max_issues) + "\nThis is the single bounded revision. Correct every omission, strengthening, "
                   "unsupported field, or duplicate identified by the audit. The source review remains the only ground truth.")
    evidence = ("SOURCE REVIEW\n" + review + "\n\nPRIOR INVENTORY\n" + json.dumps(prior["inventory"], ensure_ascii=False)
                + "\n\nFAILED AUDIT\n" + json.dumps(audit["audit"], ensure_ascii=False))
    inventory = backend.generate(instruction, evidence, ReviewInventory)
    result = _assemble_inventory(review, inventory, backend, max_issues)
    result["revision"] = {"bounded_revision": 1,
                          "prior_sha256": hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest(),
                          "audit_sha256": hashlib.sha256(json.dumps(audit, sort_keys=True).encode()).hexdigest()}
    return result


def audit_inventory(review: str, normalized: Mapping[str, Any], backend: Backend) -> dict[str, Any]:
    expected = hashlib.sha256(review.encode()).hexdigest()
    if normalized.get("source_review_sha256") != expected:
        raise ValueError("normalized inventory was created from a different review")
    if str(backend.identity).split(":", 1)[0] == str(normalized.get("backend")).split(":", 1)[0]:
        raise ValueError("inventory audit must use a different model family from normalization")
    evidence = "SOURCE REVIEW\n" + review + "\n\nNORMALIZED INVENTORY\n" + json.dumps(normalized["inventory"], ensure_ascii=False)
    audit = backend.generate(_audit_instruction(), evidence, InventoryAudit)
    invalid_missing_spans = [
        {"description": item.description, "span": span}
        for item in audit.missing_issues for span in item.source_review_spans
        if verify_quote(span, [review]).status != "supported"
    ]
    issue_ids = {row["issue_id"] for row in normalized["inventory"]["issues"]}
    unknown_ids = sorted((set(audit.unsupported_issue_ids) | set(audit.duplicate_issue_ids)) - issue_ids)
    # Never trust persisted checks: recompute from the hash-bound review.
    spans = [(row["issue_id"], span) for row in normalized["inventory"]["issues"] for span in row["source_review_spans"]]
    unmatched = [{"issue_id": issue_id, "span": span} for issue_id, span in spans
                 if verify_quote(span, [review]).status != "supported"]
    inventory_rows = normalized["inventory"]["issues"]
    ids = [row["issue_id"] for row in inventory_rows]
    duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
    content_keys = [(" ".join(row["evaluation"].casefold().split()),
                     tuple(sorted(" ".join(span.casefold().split()) for span in row["source_review_spans"])))
                    for row in inventory_rows]
    duplicate_content = len(content_keys) != len(set(content_keys))
    issue_cap_reached = len(inventory_rows) >= int(normalized["max_issues"])
    eligible = bool(
        audit.faithful and audit.complete
        and not audit.missing_issues and not audit.unsupported_issue_ids and not audit.duplicate_issue_ids
        and not duplicate_ids and not duplicate_content and not issue_cap_reached
        and not unmatched
        and not invalid_missing_spans and not unknown_ids
    )
    result = {
        "audit_schema_version": 1,
        "prompt_version": AUDIT_PROMPT_VERSION,
        "backend": backend.identity,
        "source_review_sha256": expected,
        "normalization_sha256": hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest(),
        "audit": audit.model_dump(),
        "deterministic_checks": {"unmatched_inventory_spans": unmatched,
                                 "duplicate_issue_ids": duplicate_ids, "duplicate_content": duplicate_content,
                                 "issue_cap_reached": issue_cap_reached,
                                 "invalid_missing_spans": invalid_missing_spans, "unknown_issue_ids": unknown_ids},
        "comparison_eligible": eligible,
        "normalization": dict(normalized),
    }
    if hasattr(backend, "calls"):
        result["model_calls"] = list(backend.calls)
    return result




def render_inventory(normalized: Mapping[str, Any]) -> str:
    if normalized.get("audit_schema_version") == 1:
        if not normalized.get("comparison_eligible"):
            raise ValueError("normalized inventory failed completeness or faithfulness audit")
        normalized = normalized["normalization"]
    checks = normalized.get("deterministic_checks", {})
    if (not checks.get("all_source_spans_matched") or checks.get("duplicate_issue_ids")
            or checks.get("duplicate_content") or checks.get("issue_cap_reached")):
        raise ValueError("normalized inventory failed deterministic checks")
    parts: list[str] = []
    for item in normalized["inventory"]["issues"]:
        evidence = "\n".join(f"- {value}" for value in item["evidence"])
        qualifications = "\n".join(f"- {value}" for value in item["qualifications"])
        parts.append(
            f"ASSESSMENT {item['issue_id']} ({item['assessment_type']})\nEvaluation: {item['evaluation']}\nRationale: {item['rationale']}\n"
            f"Evidence supplied by review:\n{evidence}\nRemedy: {item['remedy']}\n"
            f"Qualifications:\n{qualifications}"
        )
    return "\n\n".join(parts)


def validate_normalized_pair(candidate: Mapping[str, Any], reference: Mapping[str, Any]) -> None:
    """Require audited, symmetric normalizations before a sensitivity comparison."""
    for value in (candidate, reference):
        if value.get("audit_schema_version") != 1 or not value.get("comparison_eligible"):
            raise ValueError("normalized comparison inputs must pass their inventory audits")
    left, right = candidate["normalization"], reference["normalization"]
    if (str(candidate.get("backend")).split(":", 1)[0] == str(left.get("backend")).split(":", 1)[0]
            or str(reference.get("backend")).split(":", 1)[0] == str(right.get("backend")).split(":", 1)[0]):
        raise ValueError("inventory audit must use a different model family from normalization")
    if candidate.get("backend") != reference.get("backend"):
        raise ValueError("normalized comparison inputs used different audit models")
    for field in ("normalization_schema_version", "prompt_version", "backend", "max_issues"):
        if left.get(field) != right.get(field):
            raise ValueError(f"normalized comparison inputs differ on {field}")
    left_calls, right_calls = left.get("model_calls", []), right.get("model_calls", [])
    if left_calls and right_calls and left_calls[-1].get("resolved_model") != right_calls[-1].get("resolved_model"):
        raise ValueError("normalized comparison inputs used different resolved models")


def _backend(args: argparse.Namespace) -> Backend:
    if args.backend == "openrouter":
        from .openrouter_backend import OpenRouterBackend
        return OpenRouterBackend(args.model, timeout=args.timeout, max_tokens=args.max_tokens,
                                 max_cost_usd=args.max_cost_usd)
    if args.backend == "claude":
        return ClaudeBackend(args.model, args.timeout, args.effort)
    return CodexBackend(args.model, args.timeout, args.effort)


def _write(payload: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def command(args: argparse.Namespace) -> int:
    # Pipeline JSON is converted to the same provenance-free substantive text
    # used by the original pairwise comparison. Plain human reviews pass through.
    from .evaluation import read_review
    review = read_review(args.review)
    if args.normalization_action == "create":
        payload = normalize_review(review, _backend(args), max_issues=args.max_issues)
        _write(payload, args.output)
        checks = payload["deterministic_checks"]
        return 0 if (checks["all_source_spans_matched"] and not checks["duplicate_issue_ids"]
                     and not checks["duplicate_content"] and not checks["issue_cap_reached"]) else 2
    if args.normalization_action == "revise":
        prior = json.loads(args.inventory.read_text(encoding="utf-8"))
        audit = json.loads(args.audit.read_text(encoding="utf-8"))
        payload = revise_inventory(review, prior, audit, _backend(args))
        _write(payload, args.output)
        checks = payload["deterministic_checks"]
        return 0 if (checks["all_source_spans_matched"] and not checks["duplicate_issue_ids"]
                     and not checks["duplicate_content"] and not checks["issue_cap_reached"]) else 2
    normalized = json.loads(args.inventory.read_text(encoding="utf-8"))
    payload = audit_inventory(review, normalized, _backend(args))
    _write(payload, args.output)
    return 0 if payload["comparison_eligible"] else 2


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("normalize-review", help="normalize reviews for evaluation sensitivity analysis")
    actions = parser.add_subparsers(dest="normalization_action", required=True)
    create = actions.add_parser("create")
    create.add_argument("--review", required=True, type=Path)
    create.add_argument("--output", required=True, type=Path)
    create.add_argument("--max-issues", type=int, default=40)
    audit = actions.add_parser("audit")
    audit.add_argument("--review", required=True, type=Path)
    audit.add_argument("--inventory", required=True, type=Path)
    audit.add_argument("--output", required=True, type=Path)
    revise = actions.add_parser("revise")
    revise.add_argument("--review", required=True, type=Path)
    revise.add_argument("--inventory", required=True, type=Path)
    revise.add_argument("--audit", required=True, type=Path)
    revise.add_argument("--output", required=True, type=Path)
    for child in (create, audit, revise):
        child.add_argument("--backend", choices=["codex", "claude", "openrouter"], required=True)
        child.add_argument("--model", required=True)
        child.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="high")
        child.add_argument("--timeout", type=int, default=900)
        child.add_argument("--max-tokens", type=int, default=6000)
        child.add_argument("--max-cost-usd", type=float, default=0.025)
        child.set_defaults(func=command)
