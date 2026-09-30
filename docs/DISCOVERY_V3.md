# Coverage-first discovery v3

Status: implemented development profile; scientific benefit not yet established.
Activate with `--profile social_psychology_v3` or
`--profile quantitative_social_science_v3`. Baseline v1/v2 profiles remain available.

The five-finding specialist cap is replaced by a 20-item execution ceiling in v3.
Prompts request all distinct, justified findings after an audit, rather than a
top-five selection. Twenty is a resource guard, not a target. Reaching it, reporting
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
shows). Every finding also needs an anchored manuscript quotation. The verifier re-opens
external sources and returns only the items it confirmed; only those reach the report.

Each stage records its tool calls (search queries, fetched URLs, shell commands and
truncated outputs) in `review.json` and in a sidecar next to the cached stage artifact,
so provenance survives cache reuse. The report ends with a Tool use summary.
`eval/audit_tool_use.py` flags calls that could expose the human reviews of a benchmark
paper. The backend's tool configuration is part of the cache identity.

## Additional benchmark paper

Paper 7, *Seeing Ɔ, remembering C: Illusions in short-term memory*, is the next
prepared case. Its manuscript contains four reported experiments and results,
rather than a proposal awaiting data. It is cognitive psychology, so it broadens
this methods diagnostic rather than supplying a representative social-psychology
sample. Specific error annotations have not been inspected or supplied to a model.

Paper 2 was initially selected from the upstream title/design inventory. Its
study map and a check of the manuscript revealed explicit randomized Qualtrics
placeholder data in methods/results. Both the initial banner-exposed attempt and
the subsequent clean-input intake attempt were stopped, retained and marked
ineligible. Neither produced a scored review. Selection of paper 7 occurred before
reading either paper's specific error labels; the inventory's broad suggested
error categories were visible. Do not count these intake decisions as random
sampling or exclude a paper retrospectively based on its achieved score.

The tracked [diagnostic manifest](../eval/corpus/known_error_diagnostics.v1.json)
records both decisions, pinned URLs, hashes and transformations. Sources and
provenance are cached under `runs/known-errors/paper-07/`. Generation should receive
only `manuscript.review-input.txt`, extracted from the modified DOCX with the
opening benchmark banner removed. The original derivative is retained unchanged;
annotations remain under `ground_truth/`. The banner removal prevents disclosure
of the presence/count of planted errors; it cannot remove training contamination.

Source: [pinned upstream manuscript](https://github.com/Dawes-Institute/ai-peer-review-benchmark/blob/3d9188343eebd4312d3bfbde6822cfa4eaf32fb4/modified%20papers/7.docx).

Paper 7 has now been run and scored as a partial development diagnostic:
4/10 strict candidate recall and 3/10 published recall. See
[the result and failure trace](PAPER_07_V3_DIAGNOSTIC.md). To reproduce the run:

```bash
uv run reviscope review runs/known-errors/paper-07/manuscript.review-input.txt \
  --profile quantitative_social_science_v3 --model gpt-6-luna --effort max \
  --out runs/luna-known-error-07-v3
```

The quantitative profile fits the cognitive-psychology paper without adding an
unnecessary social-psychology module. For a within-paper baseline comparison,
use the identical clean input, model and effort with `quantitative_social_science_v2`
and a separate output directory. Do not interpret a different paper's score as
an estimate of improvement from v2 to v3.

Tests cover more than five specialist findings, blind-spot access to prior findings,
external evidence reaching the report after verification, tool-call provenance across
cache reuse, separate publication capping, honest incomplete-coverage marking without
candidate loss, and cache reuse.
