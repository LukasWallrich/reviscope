"""Evaluation primitives for review comparison and factuality auditing.

The functions in this module deliberately do not call a particular model SDK.  A
backend is any callable (or object with ``complete``) accepting a prompt and
returning JSON text or a mapping.  This keeps evaluation independent of the
review pipeline and makes the evaluator configuration explicit and freezeable.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import random
import re
import argparse
import csv
import sys
import math
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping, Protocol, Sequence

from pydantic import BaseModel, Field


class CriterionAssessment(BaseModel):
    criterion: str
    preference: str
    rationale: str


class JudgeOutput(BaseModel):
    winner: str
    confidence: float = Field(ge=0, le=1)
    rationale: str
    criteria: list[CriterionAssessment] = Field(default_factory=list)


class FindingVerificationOutput(BaseModel):
    verdict: str
    confidence: float = Field(ge=0, le=1)
    supporting_evidence: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    reasoning: str


class JudgeBackend(Protocol):
    def __call__(self, prompt: str) -> Mapping[str, Any] | str | Awaitable[Mapping[str, Any] | str]: ...


@dataclass(frozen=True)
class ComparisonCase:
    case_id: str
    paper_id: str
    order: str
    manuscript: str
    review_a: str
    review_b: str
    hidden_labels: Mapping[str, str]


def load_corpus(path: str | Path, *, eligible_only: bool = True) -> list[dict[str, Any]]:
    """Load and minimally validate a frozen corpus manifest."""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported corpus schema_version")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("manifest entries must be a list")
    seen: set[str] = set()
    for entry in entries:
        missing = {"id", "title", "journal", "article_url", "review_url", "version_status"} - set(entry)
        if missing:
            raise ValueError(f"corpus entry missing fields: {sorted(missing)}")
        if entry["id"] in seen:
            raise ValueError(f"duplicate corpus id: {entry['id']}")
        seen.add(entry["id"])
        if entry.get("evaluation_eligible"):
            if entry["version_status"] != "exact_pre_review_version_verified":
                raise ValueError(f"eligible entry {entry['id']} lacks a verified pre-review version")
            if not entry.get("manuscript_under_review_url") or not entry.get("version_evidence"):
                raise ValueError(f"eligible entry {entry['id']} lacks manuscript URL/version evidence")
    return [e for e in entries if e.get("evaluation_eligible")] if eligible_only else entries


def _stable_bit(seed: int, paper_id: str) -> bool:
    digest = hashlib.sha256(f"{seed}:{paper_id}".encode()).digest()
    return bool(digest[0] & 1)


def build_pairwise_cases(
    papers: Sequence[Mapping[str, Any]], *, seed: int = 0, order_swap: bool = True
) -> list[ComparisonCase]:
    """Blind systems and create balanced, optionally order-swapped comparisons.

    Each paper mapping needs ``paper_id``, ``manuscript``, ``candidate_review``,
    and ``reference_review``. Hidden labels are retained only for aggregation.
    """
    cases: list[ComparisonCase] = []
    ids = [str(p["paper_id"]) for p in papers]
    if len(ids) != len(set(ids)):
        raise ValueError("paper_id values must be unique")
    for paper in papers:
        pid = str(paper["paper_id"])
        first_candidate = _stable_bit(seed, pid)
        orders = [first_candidate, not first_candidate] if order_swap else [first_candidate]
        for index, candidate_is_a in enumerate(orders):
            labels = {"A": "candidate" if candidate_is_a else "reference", "B": "reference" if candidate_is_a else "candidate"}
            reviews = {"candidate": strip_review_metadata(str(paper["candidate_review"])),
                       "reference": strip_review_metadata(str(paper["reference_review"]))}
            cases.append(ComparisonCase(
                case_id=f"{pid}:order-{index + 1}", paper_id=pid,
                order="candidate_first" if candidate_is_a else "reference_first",
                manuscript=str(paper["manuscript"]), review_a=reviews[labels["A"]],
                review_b=reviews[labels["B"]], hidden_labels=labels,
            ))
    return cases


def strip_review_metadata(text: str) -> str:
    """Remove known pipeline headers that would reveal a candidate's identity."""
    if re.match(r"^# Peer review \((?:COMPLETE|PARTIAL) REVIEW\)", text, re.I):
        findings = re.search(r"(?ms)^## Findings\s*$\n(.*?)(?=^## Coverage and audit\s*$|\Z)", text)
        if findings:
            text = findings.group(1)
    lines = text.splitlines()
    # Provenance may follow the report title. Restrict removal to the header.
    for index in range(min(15, len(lines))):
        if re.match(r"^\s*(profile|backend|verifier|model|generated by|pipeline|run id)\s*:", lines[index], re.I):
            lines[index] = ""
    lines = [line for line in lines if not re.match(r"^\*\*Verification:\*\*", line, re.I)]
    return "\n".join(lines).strip()


def read_review(path: Path, *, allow_legacy_partial: bool = False) -> str:
    """Read prose, or render the canonical findings from a pipeline JSON output."""
    if path.suffix.lower() != ".json":
        return strip_review_metadata(path.read_text(encoding="utf-8"))
    data = json.loads(path.read_text(encoding="utf-8"))
    findings = data.get("findings") if isinstance(data, Mapping) else None
    if not isinstance(findings, list):
        raise ValueError(f"review JSON {path} has no findings list")
    study_map = data.get("study_map", {}) if isinstance(data.get("study_map"), Mapping) else {}
    rendered = ["STUDY OVERVIEW", str(study_map.get("design_summary") or "No study overview was available."),
                "", "CLAIMED CONTRIBUTION", str(study_map.get("contribution_summary") or "No contribution summary was available."),
                "", "STRENGTHS"]
    strengths = study_map.get("strengths") or []
    rendered.extend(f"- {strength}" for strength in strengths)
    if not strengths:
        rendered.append("No specific strengths summary was available.")
    rendered.extend(["", "FINDINGS"])
    for row in findings:
        disposition = row.get("editorial_disposition")
        if disposition != "publish" and not (allow_legacy_partial and disposition is None):
            continue
        if row.get("status") in {"candidate", "unverified", "rejected", "contradicted", "merged"}:
            continue
        item = (f"{row.get('severity', 'unspecified').upper()}: {row.get('claim', '')}\n"
                f"Reason: {row.get('rationale', '')}")
        if row.get("status") == "unresolved":
            item += "\nAssessment: Unresolved concern; the available evidence did not establish or contradict it."
        if row.get("remedy_status") not in {"overreaching", "unresolved"}:
            item += f"\nSuggested response: {row.get('remedy', '')}"
        for source in row.get("evidence", []):
            location = source.get("location") or (f"page {source['page']}" if source.get("page") else "location unavailable")
            item += f"\nEvidence: “{source.get('quote', '')}” — {source.get('source_id', '')}, {location}"
        rendered.append(item)
    return "\n\n".join(rendered)


def comparison_prompt(case: ComparisonCase) -> str:
    instruction, evidence = comparison_parts(case)
    return f"{instruction}\n\n{evidence}"


def comparison_parts(case: ComparisonCase) -> tuple[str, str]:
    instruction = """You are evaluating two peer reviews against the manuscript they assess.
Judge only substantive usefulness, correctness, importance, specificity, source grounding,
and actionability. Do not reward length or polish. Permit a tie. Treat A and B symmetrically.
Return JSON with keys winner (A, B, or tie), confidence (0..1), rationale, and criteria
(a list of objects with criterion, preference (A, B, or tie), and rationale). Cite short
manuscript evidence in the overall rationale."""
    evidence = f"MANUSCRIPT\n{case.manuscript}\n\nREVIEW A\n{case.review_a}\n\nREVIEW B\n{case.review_b}"
    return instruction, evidence


async def _call_backend(backend: JudgeBackend | Any, prompt: str) -> Mapping[str, Any]:
    call = backend.complete if hasattr(backend, "complete") else backend
    result = call(prompt)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, Mapping):
        raise TypeError("judge backend must return a mapping or JSON object string")
    return result


async def judge_case(case: ComparisonCase, backend: JudgeBackend | Any) -> dict[str, Any]:
    if hasattr(backend, "generate"):
        instruction, evidence = comparison_parts(case)
        raw = backend.generate(instruction, evidence, JudgeOutput).model_dump()
    else:
        raw = dict(await _call_backend(backend, comparison_prompt(case)))
    winner = raw.get("winner")
    if winner not in {"A", "B", "tie"}:
        raise ValueError("judge winner must be A, B, or tie")
    system_winner = "tie" if winner == "tie" else case.hidden_labels[winner]
    identity = getattr(backend, "identity", None) or getattr(backend, "name", None) or type(backend).__name__
    return {"case_id": case.case_id, "paper_id": case.paper_id, "judge": str(identity), "order": case.order,
            "winner": system_winner, "blind_winner": winner, "judgment": raw}


async def verify_finding(
    manuscript: str, finding: Mapping[str, Any], backend: JudgeBackend | Any
) -> dict[str, Any]:
    """Independently test a criticism against source, including counterevidence."""
    instruction = (
        "Assess the criticism against the manuscript. Seek evidence that supports and defeats it; "
        "do not merely confirm the rationale. Return verdict supported, contradicted, or unresolved, "
        "confidence, short verbatim supporting_evidence and counterevidence lists, and reasoning. "
        "Every evidence item must be one exact contiguous excerpt from the manuscript: never use "
        "ellipses, bracketed omissions, paraphrases, or text stitched from separate table cells."
    )
    criticism = {key: finding.get(key) for key in ("finding_id", "id", "claim", "evidence", "study_id") if finding.get(key) is not None}
    evidence = f"MANUSCRIPT\n{manuscript}\n\nCRITICISM\n{json.dumps(criticism, ensure_ascii=False)}"
    raw = await _generate_verification(backend, instruction, evidence)
    raw_model_verdict = raw.get("verdict")
    if raw.get("verdict") not in {"supported", "contradicted", "unresolved"}:
        raise ValueError("verification verdict must be supported, contradicted, or unresolved")
    matched_support, matched_counter, unmatched = _audit_verification_quotes(raw, manuscript)
    repaired_model_verdict = None
    if unmatched:
        repair_instruction = (
            "Reassess the criticism because at least one evidence excerpt from the prior assessment "
            "could not be matched. Return a complete corrected assessment. Quote only exact contiguous "
            "manuscript spans, with separate list items for separate table cells or passages; do not use "
            "ellipses or paraphrase. Do not merely delete contrary evidence to preserve the prior verdict."
        )
        repair_evidence = (f"{evidence}\n\nPRIOR ASSESSMENT\n{json.dumps(raw, ensure_ascii=False)}"
                           f"\n\nUNMATCHED EXCERPTS\n{json.dumps(unmatched, ensure_ascii=False)}")
        raw = await _generate_verification(backend, repair_instruction, repair_evidence)
        repaired_model_verdict = raw.get("verdict")
        if repaired_model_verdict not in {"supported", "contradicted", "unresolved"}:
            raise ValueError("repaired verification verdict must be supported, contradicted, or unresolved")
        matched_support, matched_counter, unmatched = _audit_verification_quotes(raw, manuscript)
    relevant_matches = matched_support if raw.get("verdict") == "supported" else matched_counter if raw.get("verdict") == "contradicted" else matched_support + matched_counter
    raw["matched_supporting_evidence"] = matched_support
    raw["matched_counterevidence"] = matched_counter
    raw["unmatched_evidence"] = unmatched
    if unmatched or not relevant_matches:
        raw["verdict"] = "unresolved"
        raw["confidence"] = min(float(raw.get("confidence", 0)), .5)
        raw["evidence_check"] = "unmatched_after_repair" if unmatched else "no_exact_verdict_relevant_quote"
    else:
        raw["evidence_check"] = "passed_after_repair" if repaired_model_verdict is not None else "passed"
    return {"finding_id": finding.get("finding_id", finding.get("id")), "assessment_method": "llm_assessed",
            "raw_model_verdict": raw_model_verdict, "repaired_model_verdict": repaired_model_verdict, **raw}


async def _generate_verification(backend: JudgeBackend | Any, instruction: str, evidence: str) -> dict[str, Any]:
    if hasattr(backend, "generate"):
        return backend.generate(instruction, evidence, FindingVerificationOutput).model_dump()
    return dict(await _call_backend(backend, f"{instruction}\n\n{evidence}"))


def _audit_verification_quotes(raw: Mapping[str, Any], manuscript: str) -> tuple[list[str], list[str], list[str]]:
    from .verification import verify_quote
    support = list(raw.get("supporting_evidence", []))
    counter = list(raw.get("counterevidence", []))
    matched_support = [quote for quote in support if verify_quote(quote, [manuscript]).status == "supported"]
    matched_counter = [quote for quote in counter if verify_quote(quote, [manuscript]).status == "supported"]
    unmatched = [quote for quote in support + counter if verify_quote(quote, [manuscript]).status != "supported"]
    return matched_support, matched_counter, unmatched


def _normalize(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def aggregate_pairwise(judgments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Resolve swaps within judge, then judges within paper without pseudo-replication."""
    by_paper_judge: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in judgments:
        key = (str(row["paper_id"]), str(row.get("judge", "unspecified-judge")))
        by_paper_judge.setdefault(key, []).append(row)
    judge_outcomes: dict[str, dict[str, str]] = {}
    incomplete: list[dict[str, str]] = []
    discordant = 0
    for (pid, judge), rows in by_paper_judge.items():
        orders = [str(row.get("order")) for row in rows]
        if len(rows) != 2 or set(orders) != {"candidate_first", "reference_first"}:
            incomplete.append({"paper_id": pid, "judge": judge})
            continue
        votes = [str(row["winner"]) for row in rows]
        if len(set(votes)) > 1:
            judge_outcomes.setdefault(pid, {})[judge] = "tie"
            discordant += 1
        else:
            judge_outcomes.setdefault(pid, {})[judge] = votes[0]
    incomplete_paper_ids = {row["paper_id"] for row in incomplete}
    outcomes: dict[str, str] = {}
    judge_disagreement: list[str] = []
    for pid, per_judge in judge_outcomes.items():
        if pid in incomplete_paper_ids:
            continue
        votes = list(per_judge.values())
        if len(set(votes)) == 1:
            outcomes[pid] = votes[0]
        else:
            outcomes[pid] = "tie"
            judge_disagreement.append(pid)
    counts = {key: sum(v == key for v in outcomes.values()) for key in ("candidate", "reference", "tie")}
    resolved = counts["candidate"] + counts["reference"]
    interval = _wilson(counts["candidate"], resolved) if resolved else None
    papers_seen = {pid for pid, _ in by_paper_judge}
    incomplete_papers = sorted(incomplete_paper_ids)
    return {"paper_count": len(outcomes), "papers_seen": len(papers_seen), "paper_outcomes": outcomes,
            "judge_outcomes": judge_outcomes, "incomplete_judge_pairs": incomplete,
            "incomplete_papers": incomplete_papers,
            "judge_disagreement_papers": sorted(judge_disagreement), "counts": counts,
            "order_discordant_papers": discordant, "candidate_preference_among_resolved":
            counts["candidate"] / resolved if resolved else None, "candidate_preference_wilson_95": interval}


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if total <= 0:
        raise ValueError("total must be positive")
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


async def run_comparisons(cases: Sequence[ComparisonCase], backend: JudgeBackend | Any) -> dict[str, Any]:
    """Run all comparisons while recording model failures as invalid cases."""
    valid, invalid = [], []
    for case in cases:
        try:
            valid.append(await judge_case(case, backend))
        except Exception as exc:
            invalid.append({"case_id": case.case_id, "paper_id": case.paper_id,
                            "error_type": type(exc).__name__, "error": str(exc)})
    return {"judgments": valid, "invalid": invalid, "aggregate": aggregate_pairwise(valid)}


def sample_finding_audit(
    findings: Sequence[Mapping[str, Any]], *, random_n: int, targeted_n: int, seed: int = 0,
    include_set_aside: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Draw disjoint random and targeted audit strata.

    Target priority is explicit: serious severity, then verifier disagreement or
    unresolved status. Rates from these strata must never be pooled implicitly.
    """
    rows = [dict(f) for f in findings if include_set_aside or (
        f.get("editorial_disposition") == "publish"
        and f.get("status") not in {"candidate", "unverified", "rejected", "contradicted", "merged"}
    )]
    if any("finding_id" not in row for row in rows):
        raise ValueError("every finding needs finding_id")
    rng = random.Random(seed)
    shuffled = rows[:]
    rng.shuffle(shuffled)
    random_rows = shuffled[: min(random_n, len(shuffled))]
    used = {r["finding_id"] for r in random_rows}
    remaining = [r for r in rows if r["finding_id"] not in used]
    severity = {"critical": 3, "major": 2, "minor": 1}
    remaining.sort(key=lambda r: (
        severity.get(str(r.get("severity", "")).lower(), 0),
        bool(r.get("verifier_disagreement")),
        str(r.get("verification_status", r.get("status", ""))) == "unresolved",
        str(r["finding_id"]),
    ), reverse=True)
    return {"random": [{**row, "stratum": "random"} for row in random_rows],
            "targeted": [{**row, "stratum": "targeted"} for row in remaining[: min(targeted_n, len(remaining))]]}


def audit_summary(adjudications: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize adjudications separately by sampling stratum."""
    result: dict[str, Any] = {}
    for stratum in ("random", "targeted"):
        rows = [r for r in adjudications if r.get("stratum") == stratum]
        counts = {label: sum(r.get("verdict") == label for r in rows) for label in ("supported", "contradicted", "unresolved")}
        denom = counts["supported"] + counts["contradicted"]
        result[stratum] = {"n": len(rows), "counts": counts,
                           "supported_rate_among_resolved": counts["supported"] / denom if denom else None}
    return result


def revalidate_verification_rows(rows: Sequence[Mapping[str, Any]], manuscript: str) -> list[dict[str, Any]]:
    """Reapply the current deterministic quote matcher without another model call."""
    validated = []
    for value in rows:
        row = dict(value)
        model_verdict = row.get("repaired_model_verdict") or row.get("raw_model_verdict") or row.get("verdict")
        matched_support, matched_counter, unmatched = _audit_verification_quotes(row, manuscript)
        relevant = matched_support if model_verdict == "supported" else matched_counter if model_verdict == "contradicted" else matched_support + matched_counter
        row.update({"matched_supporting_evidence": matched_support, "matched_counterevidence": matched_counter,
                    "unmatched_evidence": unmatched, "verdict": model_verdict,
                    "evidence_normalizer": "verification.verify_quote-current"})
        if unmatched or not relevant:
            row["verdict"] = "unresolved"
            row["confidence"] = min(float(row.get("confidence", 0)), .5)
            row["evidence_check"] = "unmatched_on_revalidation" if unmatched else "no_exact_verdict_relevant_quote"
        else:
            row["evidence_check"] = "passed_on_revalidation"
        validated.append(row)
    return validated


def planted_error_recall(predictions: Sequence[Mapping[str, Any]], gold_error_ids: Iterable[str]) -> dict[str, Any]:
    gold = set(map(str, gold_error_ids))
    matched = {str(eid) for row in predictions for eid in row.get("matched_error_ids", [])} & gold
    return {"gold_count": len(gold), "matched_count": len(matched), "matched_error_ids": sorted(matched),
            "recall": len(matched) / len(gold) if gold else None}


def import_dawes_errors(path: str | Path) -> list[dict[str, Any]]:
    """Import the pinned Dawes ``error_insertions.csv`` (or legacy JSON exports).

    The upstream CSV has no error ID, so stable IDs use ``paper-row`` where row
    is one-based within that paper in file order.
    """
    source = Path(path)
    if source.suffix.lower() == ".csv":
        rows = list(csv.DictReader(source.read_text(encoding="utf-8-sig").splitlines()))
        required = {"paper", "category", "subcategory", "modified_snippet", "description"}
        if not rows or not required.issubset(rows[0]):
            raise ValueError(f"Dawes CSV missing columns: {sorted(required - set(rows[0] if rows else {}))}")
        per_paper: dict[str, int] = {}
        normalized = []
        for row in rows:
            paper = str(row["paper"])
            per_paper[paper] = per_paper.get(paper, 0) + 1
            normalized.append({"error_id": f"{paper}-{per_paper[paper]:02d}", **row})
        return normalized
    data = json.loads(source.read_text(encoding="utf-8"))
    rows = data.get("errors", data) if isinstance(data, Mapping) else data
    if not isinstance(rows, list):
        raise ValueError("Dawes data must be a list or an object containing errors")
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError("each Dawes error must be an object")
        error_id = row.get("error_id", row.get("id", f"error-{index + 1}"))
        normalized.append({"error_id": str(error_id), **dict(row)})
    return normalized


def _write_json(value: Any, output: Path | None) -> None:
    rendered = json.dumps(value, indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        os.replace(temporary, output)
    else:
        print(rendered)


def _command(args: argparse.Namespace) -> int:
    exit_code = 0
    if args.eval_action == "check":
        _write_json({"entries": len(load_corpus(args.manifest, eligible_only=False)),
                     "eligible": len(load_corpus(args.manifest))}, args.output)
    elif args.eval_action == "audit-sample":
        rows = json.loads(args.findings.read_text(encoding="utf-8"))
        if isinstance(rows, Mapping):
            rows = rows.get("findings", [])
        rows = [{"finding_id": row.get("finding_id", row.get("id")), **row} for row in rows]
        _write_json(sample_finding_audit(rows, random_n=args.random_n, targeted_n=args.targeted_n,
                                         seed=args.seed, include_set_aside=args.include_set_aside), args.output)
    elif args.eval_action == "audit-summary":
        _write_json(audit_summary(json.loads(args.adjudications.read_text(encoding="utf-8"))), args.output)
    elif args.eval_action == "planted-recall":
        predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
        errors = import_dawes_errors(args.gold)
        if args.paper is not None:
            errors = [row for row in errors if str(row.get("paper")) == str(args.paper)]
            if not errors:
                raise ValueError(f"No Dawes errors found for paper {args.paper}")
        _write_json(planted_error_recall(predictions, [x["error_id"] for x in errors]), args.output)
    elif args.eval_action == "compare":
        backend = _backend_from_args(args)
        candidate_payload = json.loads(args.candidate.read_text(encoding="utf-8")) if args.candidate.suffix.lower() == ".json" else None
        candidate_partial = bool(candidate_payload.get("partial")) if isinstance(candidate_payload, Mapping) else False
        if candidate_partial and not args.allow_partial:
            raise ValueError("candidate review is partial; pass --allow-partial for a plumbing smoke excluded from validation")
        paper = {"paper_id": args.paper_id, "manuscript": args.manuscript.read_text(encoding="utf-8"),
                 "candidate_review": read_review(args.candidate, allow_legacy_partial=candidate_partial and args.allow_partial),
                 "reference_review": read_review(args.reference)}
        cases = build_pairwise_cases([paper], seed=args.seed, order_swap=True)
        config = {"backend": backend.identity, "seed": args.seed, "prompt_version": "pairwise-v6",
                  "content_sha256": hashlib.sha256(json.dumps(paper, sort_keys=True).encode()).hexdigest()}
        key = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        if args.output.exists():
            prior = json.loads(args.output.read_text(encoding="utf-8"))
            if prior.get("cache_key") == key and not prior.get("invalid") and len(prior.get("judgments", [])) == len(cases):
                return 0
        result = asyncio_run(run_comparisons(cases, backend))
        result.update({"cache_key": key, "judge_config": config,
                       "order_mapping": {c.case_id: dict(c.hidden_labels) for c in cases},
                       "candidate_partial": candidate_partial, "reference_kind": args.reference_kind,
                       "scientific_validation_eligible": not candidate_partial and args.reference_kind != "synthetic_fixture",
                       "eligibility_note": "plumbing smoke only" if candidate_partial or args.reference_kind == "synthetic_fixture" else "eligible subject to corpus protocol"})
        _write_json(result, args.output)
        exit_code = 2 if result["invalid"] else 0
    elif args.eval_action == "verify":
        backend = _backend_from_args(args)
        manuscript = args.manuscript.read_text(encoding="utf-8")
        findings = json.loads(args.findings.read_text(encoding="utf-8"))
        if isinstance(findings, Mapping):
            findings = findings.get("findings", [])
        if not args.include_set_aside:
            findings = [row for row in findings if row.get("editorial_disposition") == "publish"
                        and row.get("status") not in {"candidate", "unverified", "rejected", "contradicted", "merged"}]
        config = {"backend": backend.identity, "prompt_version": "finding-verification-v2",
                  "content_sha256": hashlib.sha256(json.dumps({"manuscript": manuscript, "findings": findings}, sort_keys=True).encode()).hexdigest()}
        prior_rows: dict[str, dict[str, Any]] = {}
        if args.resume_partial and args.output.exists():
            prior = json.loads(args.output.read_text(encoding="utf-8"))
            current_ids = {str(row.get("finding_id", row.get("id"))) for row in findings}
            prior_rows = _validated_resume_rows(prior, config, current_ids)
        rows, invalid = list(prior_rows.values()), []
        for finding in findings:
            finding_id = str(finding.get("finding_id", finding.get("id")))
            if finding_id in prior_rows:
                continue
            try:
                rows.append(asyncio_run(verify_finding(manuscript, finding, backend)))
            except Exception as exc:
                invalid.append({"finding_id": finding.get("finding_id", finding.get("id")),
                                "error_type": type(exc).__name__, "error": str(exc)})
        order = {str(row.get("finding_id", row.get("id"))): index for index, row in enumerate(findings)}
        rows.sort(key=lambda row: order.get(str(row.get("finding_id")), len(order)))
        _write_json({"backend": backend.identity, "verification_config": config,
                     "resumed_assessments": len(prior_rows), "verifications": rows, "invalid": invalid}, args.output)
        exit_code = 2 if invalid else 0
    elif args.eval_action == "fetch-corpus":
        entries = load_corpus(args.manifest)
        args.directory.mkdir(parents=True, exist_ok=True)
        fetched, errors = [], []
        for entry in entries:
            record = {"id": entry["id"], "files": {}, "source": entry["article_url"]}
            for kind, url_key, hash_key in (("manuscript", "manuscript_under_review_url", "manuscript_sha256"),
                                             ("review", "review_url", "review_sha256")):
                url, expected = entry[url_key], entry.get(hash_key)
                try:
                    if not expected:
                        raise ValueError(f"missing {hash_key}")
                    suffix = Path(urlparse(url).path).suffix or (".pdf" if kind == "manuscript" else ".bin")
                    target = args.directory / f"{entry['id']}-{kind}{suffix}"
                    payload = _download_public(url, args.timeout)
                    actual = hashlib.sha256(payload).hexdigest()
                    if actual != expected:
                        raise ValueError(f"hash mismatch: expected {expected}, received {actual}")
                    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
                    temporary.write_bytes(payload)
                    os.replace(temporary, target)
                    record["files"][kind] = {"path": str(target), "url": url, "sha256": actual}
                except Exception as exc:
                    error = {"id": entry["id"], "kind": kind, "url": url,
                             "error_type": type(exc).__name__, "error": str(exc)}
                    errors.append(error)
                    record["files"][kind] = {"url": url, "error": error}
            fetched.append(record)
        _write_json({"fetched": fetched, "errors": errors}, args.output)
        exit_code = 2 if errors else 0
    elif args.eval_action == "revalidate":
        payload = json.loads(args.assessments.read_text(encoding="utf-8"))
        manuscript = args.manuscript.read_text(encoding="utf-8")
        payload["verifications"] = revalidate_verification_rows(payload.get("verifications", []), manuscript)
        payload["deterministic_revalidation"] = "current verification.verify_quote; no model calls"
        _write_json(payload, args.output)
    return exit_code


def _download_public(url: str, timeout: int) -> bytes:
    """Download a public artifact with an explicit research-client identity."""
    request = urllib.request.Request(url, headers={
        "User-Agent": "coarse-socpsy-evaluation/0.1 (+https://github.com/)",
        "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError:
        # Authorization errors are stable and should be reported immediately.
        raise


def asyncio_run(awaitable: Awaitable[Any]) -> Any:
    import asyncio
    return asyncio.run(awaitable)


def _validated_resume_rows(prior: Mapping[str, Any], config: Mapping[str, Any], current_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Accept cached verification rows only for an identical frozen evaluation."""
    if prior.get("verification_config") != config:
        raise ValueError("cannot resume verification: backend, prompt version, or input content changed")
    rows = {str(row.get("finding_id")): dict(row) for row in prior.get("verifications", [])}
    if not set(rows).issubset(current_ids):
        raise ValueError("cannot resume verification: prior output contains finding IDs outside the current input")
    return rows


def _backend_from_args(args: argparse.Namespace) -> Any:
    from .backend import ClaudeBackend, CodexBackend
    if args.backend == "claude":
        return ClaudeBackend(args.model, args.timeout, args.effort)
    return CodexBackend(args.model, args.timeout, args.effort)


def _add_backend_args(parser: Any) -> None:
    parser.add_argument("--backend", choices=["codex", "claude"], default="codex")
    parser.add_argument("--model", required=True, help="explicit judge/verifier model for reproducible evaluation")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="max")
    parser.add_argument("--timeout", type=int, default=300)


def register(subparsers: Any) -> None:
    """Register non-paid evaluation data operations with an argparse CLI."""
    parser = subparsers.add_parser("evaluate", help="evaluation corpus and audit operations")
    actions = parser.add_subparsers(dest="eval_action", required=True)
    check = actions.add_parser("check")
    check.add_argument("manifest", type=Path)
    sample = actions.add_parser("audit-sample")
    sample.add_argument("findings", type=Path)
    sample.add_argument("--random-n", type=int, required=True)
    sample.add_argument("--targeted-n", type=int, required=True)
    sample.add_argument("--seed", type=int, default=0)
    sample.add_argument("--include-set-aside", action="store_true")
    summary = actions.add_parser("audit-summary")
    summary.add_argument("adjudications", type=Path)
    recall = actions.add_parser("planted-recall")
    recall.add_argument("predictions", type=Path)
    recall.add_argument("gold", type=Path)
    recall.add_argument("--paper", help="limit Dawes CSV ground truth to one paper number")
    fetch = actions.add_parser("fetch-corpus")
    fetch.add_argument("manifest", type=Path)
    fetch.add_argument("directory", type=Path)
    fetch.add_argument("--timeout", type=int, default=60)
    revalidate = actions.add_parser("revalidate")
    revalidate.add_argument("--manuscript", required=True, type=Path)
    revalidate.add_argument("--assessments", required=True, type=Path)
    revalidate.add_argument("--output", required=True, type=Path)
    compare = actions.add_parser("compare")
    compare.add_argument("--paper-id", required=True)
    compare.add_argument("--manuscript", required=True, type=Path)
    compare.add_argument("--candidate", required=True, type=Path)
    compare.add_argument("--reference", required=True, type=Path)
    compare.add_argument("--seed", type=int, default=0)
    compare.add_argument("--reference-kind", choices=["human_review", "model_baseline", "synthetic_fixture"], required=True)
    compare.add_argument("--allow-partial", action="store_true")
    compare.add_argument("--output", required=True, type=Path)
    _add_backend_args(compare)
    verify = actions.add_parser("verify")
    verify.add_argument("--manuscript", required=True, type=Path)
    verify.add_argument("--findings", required=True, type=Path)
    verify.add_argument("--output", required=True, type=Path)
    verify.add_argument("--include-set-aside", action="store_true")
    verify.add_argument("--resume-partial", action="store_true", help="retain successful rows in an existing partial output and retry missing/invalid findings")
    _add_backend_args(verify)
    for command in (check, sample, summary, recall, fetch):
        command.add_argument("--output", type=Path)
        command.set_defaults(func=_command)
    for command in (compare, verify):
        command.set_defaults(func=_command)
    revalidate.set_defaults(func=_command)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coarse-socpsy-eval")
    register(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(["evaluate", *(list(argv) if argv is not None else sys.argv[1:])])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
