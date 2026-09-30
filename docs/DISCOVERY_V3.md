# Coverage-first discovery v3

Status: implemented development profile; scientific benefit not yet established.
Activate with `--profile social_psychology_v3` or
`--profile quantitative_social_science_v3`. Baseline v1/v2 profiles remain available.

v2 specialists return at most five prioritized findings. v3 specialists work to a
20-item execution ceiling: prompts request every distinct, justified finding after
a full audit of the module's responsibility. Twenty is a resource guard, not a target. Reaching it, reporting
an incomplete search, or leaving a check unperformed makes the run partial. The
existing `--max-findings` controls the published review only (default 12); all
candidates and dispositions remain in the JSON audit.

Each specialist must return exactly its assigned coverage checks with an explicit
status and reason. “Assessed” requires anchored quotations; it is still a model's
claim of coverage, not proof of a sound analysis. Missing, duplicated or unanchored coverage is recorded as not checked and marks
the run partial. Raw discovery responses and candidate findings are retained;
candidates still undergo verification. Not-applicable and insufficient-evidence states are retained,
including when no criticism is generated. The full structured evidence is in
stage JSON; the report displays the coverage explanations.

Interpretation explicitly includes theory and mechanism claims in introductions
and protocols, where results are not expected. Statistics explicitly audits
hypothesis/test/power alignment and numerical assumptions. Field context focuses
on psychological mechanisms and concrete alternative explanations.

One blind-spot pass receives the full manuscript, candidate inventory and coverage
ledger before verification. It searches for substantively new concerns and may
return none. It is a gap audit informed by prior work, not an independent blinded
review. All new findings undergo the same verification and editorial gates.

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
a finding whose external items are all unchecked or refuted cannot be supported.

Each stage records its tool calls (search queries, fetched URLs, shell commands and
truncated outputs) in `review.json` and in a sidecar next to the cached stage artifact,
so provenance survives cache reuse. The report ends with a Tool use summary.
`eval/audit_tool_use.py` flags calls that could expose the human reviews of a benchmark
paper. The backend's tool configuration is part of the cache identity.

Tests cover more than five specialist findings, blind-spot access to prior findings,
external evidence reaching the report after verification, tool-call provenance across
cache reuse, separate publication capping, honest incomplete-coverage marking without
candidate loss, and cache reuse.
