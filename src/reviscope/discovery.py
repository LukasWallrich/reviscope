"""Coverage-first discovery: module prompts, response schema and coverage-ledger validation."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from .schemas import CandidateFinding, Evidence, SourceDocument
from .verification import verify_quote
from .reasoning import ARGUMENT_ASSESSMENT, LITERATURE_ASSESSMENT, MATERIAL_ASSESSMENT


TOPICS = {
    'overview': ['central_claims_and_evidence', 'alternative_explanations_and_scope', 'consequential_gaps'],
    'contribution': ['question_and_claims', 'theoretical_argument', 'design_addresses_question'],
    'design': ['confounds_and_controls', 'sampling_and_assignment', 'timing_and_dependence', 'attrition_and_missing_data'],
    'measurement': ['construct_validity', 'scoring_and_denominators', 'comparability_and_validity'],
    'statistical_inference': ['hypothesis_test_alignment', 'statistical_errors', 'power_and_sensitivity', 'analytic_flexibility',
                              'robustness_of_central_conclusions', 'uncertainty_and_estimates'],
    'interpretation': ['causal_inference', 'generalizability', 'theory_and_mechanism_claims', 'claim_evidence_consistency'],
    'consistency': ['cross_section_agreement', 'sample_counts_through_stages', 'planned_versus_reported_analyses'],
    'social_psychology_context': ['demand_expectancy_and_social_mechanisms', 'people_and_stimuli', 'manipulation_and_alternative_explanations',
                                  'replication_and_original_comparison'],
    'blind_spots': ['unexamined_claims_and_sections', 'omissions_with_consequences', 'unresolved_numerical_questions'],
}
DEFAULT_TOPICS = ['module_inferences', 'source_consistency', 'information_limits']

# The blind-spot pass runs after every profile module, before verification.
BLIND_SPOTS = 'blind_spots'
BLIND_SPOT_PROMPT = ('Perform one blind-spot audit of the full manuscript against the existing candidate inventory '
                     'and coverage ledger. Treat earlier findings as unverified leads, not facts. Search for overlooked '
                     'claims, mechanisms, numerical assumptions and consequential omissions. Return only substantively '
                     'new findings; do not paraphrase existing issues. Do not manufacture problems to fill gaps.')

_CHECKS_LINE = 'Return exactly one checks entry for each of: '


class CoverageCheck(BaseModel):
    check: str
    status: Literal['assessed', 'not_applicable', 'insufficient_evidence', 'not_checked']
    rationale: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)


class DiscoveryResponse(BaseModel):
    findings: list[CandidateFinding]
    checks: list[CoverageCheck] = Field(min_length=1)
    search_incomplete: bool


def discovery_instruction(module: str, base: str) -> str:
    topics = TOPICS.get(module, DEFAULT_TOPICS)
    base += '\n' + ARGUMENT_ASSESSMENT
    if module == 'contribution':
        base += LITERATURE_ASSESSMENT
    if module in {'overview', 'measurement', 'interpretation', 'consistency', 'blind_spots',
                  'social_psychology_context', 'education_context'}:
        base += MATERIAL_ASSESSMENT
    return base + '''\nAudit the entire supplied manuscript within your assigned responsibility and return every
distinct, justified issue you find. There is no quota and no limit on the number of findings.
Review as a critical expert in your remit, not only as an error checker. Besides errors, raise what
such a reviewer would expect the authors to address: a central conclusion that depends on a modelling
or design choice when a reasonable alternative gives a materially different answer; a competing
explanation the evidence does not distinguish; directly relevant prior or newer evidence, including
counterevidence, that changes how a claim should be read; and a headline claim stated more strongly
than the evidence allows. A limitation acknowledged in one passage does not settle a claim that the
abstract, results or conclusions still state without that qualification, or a limitation that
undermines the main result itself.
Keep each issue grounded in an exact quotation, a concrete consequence, and the strongest plausible
alternative explanation or defeating context. An omission needs an inferential consequence, not merely
a missing checklist item. Use kind=defect for an alleged error, specification_conflict for incompatible
reported specifications, and clarification_request for missing information needed to assess a named
analysis or conclusion. State each claim at the level of the underlying problem and its consequence for the paper's
conclusions, not as the edit that would fix it: write that the design cannot separate the claimed
cause from a named alternative, rather than that a sentence in the discussion is unclear. Give the
smallest remedy that resolves the issue, which may well be a wording change, and set remedy_necessity:
essential when the claims as stated cannot stand without it, strengthening when it would improve
support or clarity without being required, extending when it goes beyond the manuscript's scope. Distinguish unreported from incorrect. For proposals/protocols evaluate theory,
mechanisms and planned inference without requiring results. Do not prescribe post-treatment exclusions
by default. Missing information is major only when a central claim cannot be assessed without it.
Severity here is provisional; editorial assigns final severity with all findings in view.
Set search_incomplete=true if you could not complete the audit of your responsibility.
''' + _CHECKS_LINE + ', '.join(topics) + '''.
For assessed checks, explain what you compared and cite source evidence; empty findings do not imply
coverage. Mark not_applicable, insufficient_evidence or not_checked with a reason when appropriate.
Use your tools where they can settle a consequential question. Recompute reported statistics,
power and sample-size claims, percentages and sample flow with code, and state the inputs and
assumptions you used. Open cited sources when the manuscript's use of them carries an inference, and
search the literature before asserting or denying novelty or a missing body of work. Put what an
external source shows in external_evidence with its URL or DOI and an exact quotation from that
source. Every finding also needs at least one exact manuscript quotation in evidence, with a valid
SOURCE_ID. Quote verbatim; mark an omission inside a quotation with an ellipsis (...). When a search is
inconclusive, say so rather than asserting an omission.
Stay within the assigned module; do not repeat a cross-section contradiction outside your remit unless
you identify a distinct consequence. Editorial selection happens after discovery and verification.'''


def requested_checks(instruction: str) -> list[str]:
    """Coverage check names that a discovery instruction asks for (used by offline backends)."""
    match = re.search(re.escape(_CHECKS_LINE) + r'([^\n]*)\.\n', instruction)
    return [name.strip() for name in match.group(1).split(',')] if match else DEFAULT_TOPICS


def validate_discovery(result: DiscoveryResponse, module: str, sources: list[SourceDocument]):
    """Repair the coverage ledger without throwing away independent findings.

    A defective coverage claim is not evidence that a candidate criticism is false.
    The raw model response is retained by the caller before this normalization.
    """
    expected = TOPICS.get(module, DEFAULT_TOPICS)
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
        if row.status == 'assessed':
            anchored = [e for e in row.evidence if verify_quote(e.quote, source_rows, e.source_id).status == 'supported']
            if len(anchored) < len(row.evidence):
                note = 'no cited quotation could be anchored' if not anchored else f'{len(row.evidence) - len(anchored)} cited quotation(s) could not be anchored and were dropped'
                row = row.model_copy(update={'evidence': anchored, 'rationale': f'{row.rationale} [{note}]'})
        checks.append(row)
    return result.model_copy(update={'checks': checks, 'search_incomplete': incomplete})
