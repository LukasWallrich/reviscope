# Evaluation disposition for Fable integration review 03

Reviewed against `docs/design_reviews/03_integration.md` on 2026-09-07.

| Item | Disposition | Verification |
|---|---|---|
| 1, candidate provenance leaks | Fixed | Evaluation prefers canonical `review.json` and renders findings only. Pipeline-rendered Markdown is reduced to its Findings section, with verification labels removed. A test passes an actual `to_markdown` result through this path. |
| 2, rules supplied as untrusted evidence | Fixed | The shared `Backend.generate` path now sends the fixed judge rubric as `instruction`; manuscript and blinded reviews alone are `evidence`. The test backend asserts the separation. |
| 3, prior verifier decision leaks | Fixed | Independent verification receives only finding ID, claim, evidence, and study ID. Returned quotations are deterministically checked against the manuscript and failures are downgraded to unresolved. |
| 6, audit schema mismatch | Fixed | Canonical `review.json` wrappers and `id` are normalized; targeted selection falls back from `verification_status` to `status`; every sampled row carries `stratum`. A sample-to-summary round-trip is tested. |
| 7, lenient or incomplete pair aggregation | Fixed | A paper is a candidate/reference win only when both order swaps agree. Candidate-plus-tie and disagreement become ties. Missing or duplicate orders are excluded and listed under `incomplete_papers`; command failures return nonzero. |
| 9, implicit judge model | Fixed | Evaluation `compare` and `verify` require an explicit `--model`; backend identity, effort, prompt version, content hash, and seed are stored in the cache key. |

Follow-up integration fixes preserve a separate outcome for each judge family before aggregating at paper level. Opposite family outcomes become a paper tie and do not create extra paper observations. Canonical comparison reviews and default precision samples now include only findings whose `editorial_disposition` is `publish`; `--include-set-aside` enables an explicit false-negative audit.

Items 4, 5, and 8 concern core pipeline ownership and were handled there. Item 10 concerns backend CLI smoke checks and is recorded with the integration work rather than changed in the evaluator.
