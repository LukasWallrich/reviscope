"""Coverage-first discovery: module prompts, response schema and coverage-ledger validation."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .schemas import Evidence, Finding, SourceDocument
from .verification import verify_quote


TOPICS = {
    'contribution': ['question_and_claims', 'theoretical_argument', 'design_addresses_question'],
    'design': ['sampling_and_assignment', 'timing_and_dependence', 'exclusions_and_missingness'],
    'measurement': ['construct_operationalization', 'scoring_and_denominators', 'comparability_and_validity'],
    'statistical_inference': ['hypothesis_test_alignment', 'numerical_and_power_claims', 'uncertainty_and_analytic_choices'],
    'interpretation': ['theory_and_mechanism_claims', 'causal_and_population_scope', 'claim_evidence_consistency'],
    'social_psychology_context': ['demand_expectancy_and_social_mechanisms', 'people_and_stimuli', 'manipulation_and_alternative_explanations'],
    'blind_spots': ['unexamined_claims_and_sections', 'omissions_with_consequences', 'unresolved_numerical_questions'],
}


class CoverageCheck(BaseModel):
    check: str
    status: Literal['assessed', 'not_applicable', 'insufficient_evidence', 'not_checked']
    rationale: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)


class DiscoveryResponse(BaseModel):
    # Resource ceiling, not an instruction to prioritize before coverage.
    findings: list[Finding] = Field(max_length=20)
    checks: list[CoverageCheck] = Field(min_length=1)
    search_incomplete: bool


def discovery_instruction(module: str, base: str) -> str:
    topics = TOPICS.get(module, ['module_inferences', 'source_consistency', 'information_limits'])
    return base + '''\nThese discovery rules override earlier requests for only a few prioritized findings.
Audit the entire supplied manuscript within your assigned responsibility before selecting findings.
Keep each issue grounded in an exact quotation, a concrete consequence, and the strongest plausible
alternative explanation or defeating context. An omission needs an inferential consequence, not merely
a missing checklist item. Distinguish unreported from incorrect. For proposals/protocols evaluate theory,
mechanisms and planned inference without requiring results. Do not prescribe post-treatment exclusions
by default. Return all distinct justified issues within your responsibility; do not fill a quota.
The schema's twenty-finding ceiling is a resource guard, not a target or publication limit. Set
search_incomplete=true if that ceiling or another limit prevents a complete audit.
Return exactly one checks entry for each of: ''' + ', '.join(topics) + '''.
For assessed checks, explain what you compared and cite source evidence; empty findings do not imply
coverage. Mark not_applicable, insufficient_evidence or not_checked with a reason when appropriate.
Use your tools where they can settle a consequential question. Recompute reported statistics,
power and sample-size claims, percentages and sample flow with code, and state the inputs and
assumptions you used. Open cited sources when the manuscript's use of them carries an inference, and
search the literature before asserting or denying novelty or a missing body of work. Put what an
external source shows in external_evidence with its URL or DOI and an exact quotation from that
source. Every finding also needs at least one exact manuscript quotation in evidence. When a search is
inconclusive, say so rather than asserting an omission.
Stay within the assigned module; do not repeat a cross-section contradiction outside your remit unless
you identify a distinct consequence. Editorial selection happens after discovery and verification.'''


def validate_discovery(result: DiscoveryResponse, module: str, sources: list[SourceDocument]):
    """Repair the coverage ledger without throwing away independent findings.

    A defective coverage claim is not evidence that a candidate criticism is false.
    The raw model response is retained by the caller before this normalization.
    """
    expected = TOPICS.get(module, ['module_inferences', 'source_consistency', 'information_limits'])
    by_name = {}
    for row in result.checks:
        by_name.setdefault(row.check, []).append(row)
    incomplete = result.search_incomplete or bool(set(by_name) - set(expected))
    checks = []
    source_rows = [s.model_dump() for s in sources]
    for name in expected:
        rows = by_name.get(name, [])
        if len(rows) != 1:
            checks.append(CoverageCheck(check=name, status='not_checked',
                                       rationale='Coverage entry missing or duplicated in model output.'))
            incomplete = True
            continue
        row = rows[0]
        if row.status == 'assessed' and (not row.evidence or any(
            verify_quote(e.quote, source_rows, e.source_id).status != 'supported'
            for e in row.evidence
        )):
            row = row.model_copy(update={'status': 'not_checked',
                'rationale': 'Coverage evidence could not be anchored; original account: ' + row.rationale})
            incomplete = True
        checks.append(row)
    return result.model_copy(update={'checks': checks, 'search_incomplete': incomplete})
