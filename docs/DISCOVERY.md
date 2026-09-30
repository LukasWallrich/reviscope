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

Interpretation includes theory and mechanism claims in introductions and protocols,
where results are not expected. Statistics audits hypothesis/test/power alignment and
numerical assumptions. The social-psychology module focuses on psychological
mechanisms and concrete alternative explanations.

One blind-spot pass receives the full manuscript, candidate inventory and coverage
ledger before verification. It searches for substantively new concerns and may
return none. It is a gap audit informed by prior work, not an independent blinded
review. All new findings undergo the same verification and editorial gates.

## Verification and publication

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
a finding whose external items are all unchecked, or any of which is refuted, cannot be supported.

Each stage records its tool calls (search queries, fetched URLs, shell commands and
truncated outputs) in `review.json` and in a sidecar next to the cached stage artifact,
so provenance survives cache reuse. The report ends with a Tool use summary.
`eval/audit_tool_use.py` flags calls that could expose the human reviews of a benchmark
paper. The backend's tool configuration is part of the cache identity.
