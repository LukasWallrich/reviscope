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

## Directed numerical tool

The original no-tools guard separated manuscript evidence from external actions
and prevented retrieval of benchmark answers. Those boundaries remain. V3 adds a
host-mediated numerical tool: a model returns up to 12 structured requests, the
host evaluates them, and results are supplied to specialists and the verifier.
No shell, arbitrary Python, browsing, package installation, file access or
open-ended literature research is enabled for the reviewer.

Each request contains a concrete question, a scalar expression, quoted inputs and
explicit assumptions. Quotes must anchor in the supplied source. The interpreter
accepts arithmetic and a small function allowlist; it never calls eval or exec.
Expressions, AST size, exponents and numerical ranges are bounded. Functions cover
basic arithmetic, t/F/chi-square tail probabilities, normal quantiles, and a
specified repeated-measures interaction power/sample-size calculation. Unsupported
models and missing inputs must be recorded as unavailable. This is deliberately
not a general numerical research environment.

Calculation plans and results are cached with source, request and implementation
provenance. Computed values are not automatically criticisms or verified facts:
the verifier must assess the statistical assumptions and mapping from quoted
inputs. A valid arithmetic expression can still answer the wrong question.

There is currently one request/response round before specialist discovery. A
specialist cannot request a second computation mid-call; remaining numerical
questions go into the coverage ledger and blind-spot audit. More flexible directed
calculation can extend this interface without enabling unrestricted research.

### Deferred agentic checks

Every specialist and the blind-spot pass can return `deferred_tool_checks`:
a manuscript-grounded question, capability, bounded proposed action, required
inputs, expected effect on the review under alternative outcomes, priority and
stopping rule. Zero is valid. Requests for broad research, benchmark answers or
checks already executed by the calculator are excluded by the prompt.

The host stamps the originating module and independently checks source anchors.
The proposals are retained in review JSON and a clearly labelled audit section;
they are not executed, counted as findings, or passed off as verified criticisms.
They remain outside the substantive review text used for evaluation. Their
presence alone does not mark a review partial: substantive coverage statuses
still determine whether an actual required check was left undone.

Use this log to identify recurring, bounded capabilities with available inputs.
Model-assigned priority and predicted benefit are hypotheses. A useful capability
trial should record whether executing the proposed check actually resolves an
uncertainty or changes a verified finding, along with time and cost. Repeated
requests across modules should be grouped before counting demand for a tool.
Combine these self-reported requests with observed failures: an agent may not
recognize the capability it actually lacks. For example, the paper-7 intake of
specialist outputs exposed unanchored, abridged quotations without generating a
request for source-text lookup. Deferred requests alone would miss that problem.

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
  --profile quantitative_social_science_v3 --model gpt-5.6-luna --effort max \
  --out runs/luna-known-error-07-v3
```

The quantitative profile fits the cognitive-psychology paper without adding an
unnecessary social-psychology module. For a within-paper baseline comparison,
use the identical clean input, model and effort with `quantitative_social_science_v2`
and a separate output directory. Do not interpret a different paper's score as
an estimate of improvement from v2 to v3.

Tests cover rejection of arbitrary-code expressions and unanchored inputs,
numerical reference values, more than five specialist findings, blind-spot access
to prior findings and calculations, verification access to calculator results,
separate publication capping, honest incomplete-coverage marking without candidate loss, and cache reuse.
