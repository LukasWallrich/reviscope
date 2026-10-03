"""Broad review and an independent-input audit of concrete manuscript operations."""

from typing import Literal
import shlex

from pydantic import BaseModel, Field

from .discovery import CoverageCheck, DiscoveryResponse
from .schemas import Evidence, StudyMap, ToolCall


class BroadReview(DiscoveryResponse):
    study_map: StudyMap
    checks: list[CoverageCheck] = Field(default_factory=list)


class AuditOperation(BaseModel):
    question: str
    evidence: list[Evidence] = Field(default_factory=list)
    reported_inputs: list[str]
    assumptions: list[str]
    method: str
    code: str | None = None
    result: str
    status: Literal["checked", "unresolved", "not_applicable"]


class EvidenceAudit(DiscoveryResponse):
    operations: list[AuditOperation] = Field(default_factory=list)


def calculation_recorded(operation: AuditOperation, calls: list[ToolCall]) -> bool:
    """Match nonempty code and output in the audit's own successful shell record."""
    if not operation.code or not operation.code.strip() or not operation.result.strip():
        return False
    normalized = lambda text: " ".join(text.split())
    for call in calls:
        if call.kind != "exec" or call.error:
            continue
        command = call.command or ""
        candidates = [command]
        try:
            candidates.extend(shlex.split(command))
        except ValueError:
            pass
        if any(normalized(operation.code) in normalized(value) for value in candidates) and normalized(operation.result) in normalized(call.output):
            return True
    return False


REVIEW_RULES = """Quote verbatim, with ellipses only between exact source spans.
Search the literature before asserting or denying novelty or missing relevant work;
an inconclusive search does not establish absence. Do not prescribe post-treatment
exclusions by default. For protocols assess proposed theory, mechanisms and inference
without demanding results; for tutorials assess accuracy, scope and instructional value.
"""


BROAD_REVIEW = """You are an expert scientific peer reviewer with deep methodological expertise.
Review the complete supplied manuscript and identify all methodological, statistical
and conceptual issues. Be thorough and precise. Focus on problems that affect validity,
replicability or interpretation. Read it as one argument, relating its question, theory,
observations, analyses and conclusions. Return every justified issue, with no finding limit.

For each issue provide a precise claim, detailed rationale, the smallest justified remedy,
proportionate severity and exact manuscript quotations with valid SOURCE_ID values.
Use kind=defect for an alleged error, specification_conflict for incompatible reported
specifications, and clarification_request for missing information needed to reproduce
or assess a named analysis or interpret a particular conclusion. State a reporting request
at the scope of the material inspected; missing detail does not establish incorrect
implementation or bias. Seek defeating context in the whole supplied manuscript and
accessible linked methods. Severity reflects the established consequence: reporting
requests are normally minor. Do not repeat acknowledged limitations without a distinct
consequence or prescribe rituals unrelated to the manuscript's goal.

Use tools for consequential external questions and code for numerical criticisms.
Fetch cited sources for source-specific attributions, quotations or empirical assertions;
record their exact quotations, URL/DOI and contribution in external_evidence. For protocols
assess proposed inference without demanding results; for tutorials assess accuracy, scope
and instructional usefulness. Also extract a descriptive study_map: claimed question,
contribution, distinct studies, design and concrete evidence-based strengths. Return
checks=[]; do not invent a coverage guarantee for this broad read. Set search_incomplete
when work remains unfinished and state its limits in your findings where relevant.
"""


EVIDENCE_AUDIT = """Perform an evidence audit of the full supplied manuscript. You receive
the sources and unverified screening leads, without another review's findings or overview.
Read the sources independently. Use these operations wherever the manuscript supplies
applicable quantities or claims; record each concrete operation, including successful
checks and questions that remain unresolved. Return every distinct justified finding;
there is no quota or finding limit. The operation ledger is not a checklist declaration.

reported_quantities: recompute complete test reports, counts, percentages, intervals,
sample flow and power/sensitivity assumptions with the sandboxed shell. Report inputs,
formula/code method, rounding tolerance and result. Distinguish a conditional reconstruction
from verification of the authors' actual implementation. Do not infer adequacy from N alone.
analysis_and_scores: trace response codes, recoding, missingness, transformations and their
order, aggregation, effect metrics, variances, models and back-transformation. Quote each
reported step and mark unspecified steps; never silently substitute a familiar recipe.
categorical_agreement: compare prose, tables and supplements for sites, populations,
eligibility, units, time periods, variable definitions, labels and planned/reported analyses.
inferential_targets: reconstruct the decision rule for each central claim. Check whether
its statistical comparison, estimand and observations establish it; use a counterexample
or computation when possible. Separate evidence for a mechanism from compatibility with it.

Each operation records its question, quoted evidence, reported_inputs, assumptions,
method, result and status. For a calculation include its exact executed code and a short
nonempty result copied verbatim from the shell output. Record short,
clearly labelled outputs so the tool trace preserves them. A claimed calculation with
no matching code/output is marked not matched in trace, which does not establish that
it was not executed. A script written to a file or truncated output can prevent matching.
unavailable data, images or linked methods produce unresolved steps, not invented values.
Metacheck leads are unverified observations; a failed screen is not a manuscript defect.
Seek defeating context and accessible methods. A bounded omission or conflicting-specification
claim need not decide which implementation occurred; allegations about that implementation
do require evidence. Keep unreported, incorrect and inaccessible distinct. Reporting
requests must prevent a specific assessment, and are normally minor unless a supported
material consequence warrants more. Label findings defect, specification_conflict or
clarification_request at their stated scope. Do not repeat an acknowledged limitation without a
distinct consequence. Give the smallest justified remedy. Use external_evidence for exact
quotations from fetched sources, with URL/DOI and what each establishes. Every finding
requires exact manuscript evidence with valid SOURCE_ID. Return coverage entries for
reported_quantities, analysis_and_scores, categorical_agreement, inferential_targets.
"""
