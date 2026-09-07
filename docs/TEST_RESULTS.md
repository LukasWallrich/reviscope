# Observed alpha checks

Date: 7 September 2026. This records engineering tests, not scientific performance validation.

## Implementation and independent review

Implementation was delegated to GPT-5.6 Sol subagents. Three authenticated `claude -p --model fable --effort high` reviews examined architecture, evidence/statistical verification, and integration. Requests, responses, and dispositions are retained in `docs/design_reviews`; the service reported Claude Fable 5.1. Initial manuscript review runs use Codex CLI `gpt-5.6-luna` with `model_reasoning_effort=max`, as requested.

## Deterministic acceptance

- 45 tests passed after the final core integrity fixes. Tests cover extraction order/coverage, profile inheritance, numerical assumptions and rounding, original-source quotation offsets, forged finding status, finding joins, cache invalidation, editorial target integrity, HTML escaping, blinded order swaps, per-paper aggregation, and audit strata.
- Fixture review completed with bundled social-psychology criteria and with the external education profile. Fixture reports visibly identify themselves as demonstrations.
- Source distribution and wheel builds succeeded; bundled profile/rubric resources and both license/credit files were included. An isolated wheel installation, invoked outside the repository, listed all three profiles and completed a fixture review.
- Corpus validation admitted 2 of 5 records. The four manuscript/review artifacts for eligible records downloaded successfully and matched recorded SHA-256 hashes.

## Live CLI checks

Both authenticated Codex and Claude backends returned schema-valid smoke responses. Codex tool and web capabilities were disabled, and output was read from its final-message artifact. The first short Luna review completed generation and verification but its editorial pass exceeded the initial 180-second per-call limit, producing an explicitly partial report. Inspection exposed insufficient verifier evidence; the final typed schema and prompt now require usable source identifiers and quotations for supported findings. A fresh run uses a 600-second limit.

The live Fable evaluator smoke completed both presentation orders with no invalid judgments. Its comparator was an explicitly synthetic, locally written baseline, and the candidate was the earlier partial Luna demonstration. The artifact records this as ineligible for scientific validation. A separate Fable pass assessed two generated findings, returned two supported decisions, and passed deterministic quotation checks. These are integration outcomes, not precision estimates.

The final six-module social-psychology Luna run completed with `partial=false`. It generated 23 candidates; all received source-anchored independent model support, and editorial selection published 12, merged 8, and capped 3. Verification took 171.2 seconds and editorial selection took 262.3 seconds. A repeat invocation completed successfully with cache hits for all nine model stages and no new model calls. Output: `runs/live-luna-final/review.{json,md,html}`. The content remains a reporting-gap-heavy response to a 50-word demonstration, not evidence of good real-paper reviewing.

The longer original Z-curve manuscript trial was started during development. It completed the study map and three specialist modules, then statistical assessment exceeded its 600-second limit. The older process was stopped; completed artifacts were transparently recovered as `runs/luna-zcurve-partial/review.{json,md,html}`. Its 15 findings are all unverified, and the report records the timeout, interruption, skipped stages, and development-snapshot provenance. It is not a completed test of the final pipeline on that paper. `recover.py` records the recovery procedure. No genuine-human-review comparison was run against this incomplete trial.

Local outputs under `runs/` are intentionally excluded from version control.

## Interpretation limits

The tiny demonstration manuscript is deliberately incomplete. It tests orchestration and evidence handling, not the quality of substantive peer review. The two eligible public manuscript/review pairs are Meta-Psychology methods papers, and do not constitute a representative validation corpus. Communications Psychology records remain ineligible until the original reviewed manuscripts are located. No human-equivalence result or measured false-claim rate is established. Model verification is recorded as model support, not ground truth.
