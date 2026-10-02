# Coverage-first discovery and verification

Status: implemented for every profile; scientific benefit not yet established.

## Discovery

Each profile module audits the whole manuscript within its responsibility and returns
every distinct, justified finding. No stage limits the number of findings: the discovery
schema has no ceiling, the prompts set no quota, and editorial selection has no
publication cap. The JSON audit keeps all candidates and their dispositions.

Each specialist must return exactly its assigned coverage checks with an explicit
status and reason. “Assessed” requires anchored quotations; it is still a model's
claim of coverage, not proof of a sound analysis. Missing, duplicated or unanchored
coverage is recorded as not checked and marks the run partial, as does a module that
reports an incomplete search. Raw discovery responses and candidate findings are
retained; candidates still undergo verification. Not-applicable and
insufficient-evidence states are retained, including when no criticism is generated.
The full structured evidence is in stage JSON; the report displays the coverage
explanations.

## Modules and coverage checks

Each module's generation prompt asks for its error categories, and each category has a
named coverage check, so the coverage ledger shows whether the owner assessed it.

| Module | Coverage checks | Error categories it owns |
|---|---|---|
| `contribution` | `question_and_claims`, `theoretical_argument`, `design_addresses_question` | theoretical and conceptual problems |
| `design` | `confounds_and_controls`, `sampling_and_assignment`, `timing_and_dependence`, `attrition_and_missing_data` | methodological design; attrition and missing data |
| `measurement` | `construct_validity`, `scoring_and_denominators`, `comparability_and_validity` | construct validity |
| `statistical_inference` | `hypothesis_test_alignment`, `statistical_errors`, `power_and_sensitivity`, `analytic_flexibility`, `uncertainty_and_estimates` | statistical errors; analytic flexibility |
| `interpretation` | `causal_inference`, `generalizability`, `theory_and_mechanism_claims`, `claim_evidence_consistency` | causal inference; generalizability |
| `consistency` | `cross_section_agreement`, `sample_counts_through_stages`, `planned_versus_reported_analyses` | internal consistency; reporting completeness |

`consistency` checks agreement across the whole manuscript: numbers and statements
across sections (abstract against results, text against tables and figures), sample
counts through the stages of the analysis, planned against reported analyses
(including analyses announced, preregistered or described in the methods that the
results do not report), definitions, and limitations stated in one place and
contradicted elsewhere.

`power_and_sensitivity` asks whether a power or sensitivity analysis is reported
completely (target effect size and its justification, alpha, power, test or model, N),
whether it is calculated correctly (recomputed with code), and whether the sample is
adequate for each claimed inference, including interactions, subgroups and equivalence
tests. Adequacy is judged by computing the sensitivity or power for the claimed
inference, never from N alone; observed or post-hoc power is never requested.
`analytic_flexibility` covers undisclosed researcher degrees of freedom, deviations from
a preregistration, and changed transformations, centering, exclusions or covariates.

Test statistics are screened by metacheck's `stat_check` module (the statcheck R
package), whose rows reach `statistical_inference` as leads. With `--no-metacheck`,
`statistical_inference` recomputes every complete test report with code.

Interpretation includes theory and mechanism claims in introductions and protocols,
where results are not expected. The social-psychology module focuses on psychological
mechanisms and concrete alternative explanations.

One blind-spot pass receives the full manuscript, candidate inventory and coverage
ledger before verification. It searches for substantively new concerns and may
return none. It is a gap audit informed by prior work, not an independent blinded
review. All new findings undergo the same verification and editorial gates.

## Verification and publication

Verification processes every candidate in module-based batches of at most ten. This
is a per-call workload, not a finding limit. Each batch is independently cached and
records its backend version and tool calls. A failed batch marks the run partial and
leaves its candidates unverified; successful batches retain their results. An external
confirmation uses only the tool calls from the batch that checked the candidate.

Quotations anchor when they match the named source exactly, modulo whitespace and
common PDF artefacts; numbers must match exactly. A quotation shortened with an
ellipsis (`...`, `…` or `[...]`) anchors when every segment around the ellipsis has at
least three words and all segments occur in the named source, in order. The evidence
location and the verification note mark such a match as elided.

A quotation that does not anchor is dropped from the finding's evidence and listed in
its verification note; it does not block the finding. When the verifier supports a
claim, its own anchored quotations join the finding's evidence. A finding is published
(`llm_supported`) when the verifier supports it and at least one anchored quotation
from the manuscript exists, from the generating model or from the verifier.
Supplements and preregistrations add support but cannot carry a finding alone. A
finding with no anchored manuscript quotation is `unresolved`.

When the verifier judges a claim unresolved on the evidence, and the finding has an
anchored manuscript quotation, the report shows it under “Concerns the verifier could
not confirm” with the verifier's reason. It keeps status `unresolved` and is not part
of the findings list. Contradicted findings, and findings left unresolved by quote
anchoring or external-source checks, are listed only in the set-aside audit.

Editorial selection merges duplicates and sets aside findings that verification does
not support or that no candidate states proportionately. It never sets a finding aside
because of how many there are. Published findings are ordered critical, major, minor.

## Tool use

Specialists, the blind-spot pass, the verifier and the editorial stage run with web
search, web fetching and a sandboxed shell (see `backend.py`). The discovery rules ask
the model to recompute reported statistics, power and sample-size claims and sample flow
with code, to open cited sources whose use carries an inference, and to search the
literature before asserting or denying novelty or missing work. What an external source
shows goes into a finding's `external_evidence` (URL or DOI, exact quotation, what it
shows). Every finding also needs an anchored quotation from the manuscript itself. The
verifier re-opens each external source and returns a verdict per item. An item counts as
confirmed only when the verifier says so and its recorded tool calls touched that URL or DOI;
a finding whose required external items are all unchecked, or any of which is refuted, cannot be supported.
The verifier may classify external evidence as optional with an explicit explanation
of how anchored manuscript evidence and established methodological or disciplinary
knowledge support the claim as worded without it. Unchecked optional items are removed
from the finding, with their locators and the explanation retained in its verification
trace; the original candidates and raw verifier decisions retain the full evidence.
Source-specific quotations, attributions, novelty claims and unusual empirical
assertions require external verification. Familiarity with a source cannot establish
its contents. A claim that depends on an inaccessible source stays unresolved. A
refuted item blocks support even when the verifier labels external evidence optional.

Each stage records its tool calls (search queries, fetched URLs, shell commands and
truncated outputs) in `review.json` and in a sidecar next to the cached stage artifact,
so provenance survives cache reuse. The report ends with a Tool use summary.
`eval/audit_tool_use.py` flags calls that could expose the human reviews of a benchmark
paper. The backend's tool configuration is part of the cache identity.
