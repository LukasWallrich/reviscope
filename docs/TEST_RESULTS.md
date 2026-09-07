# Observed alpha checks

Date: 7 September 2026. Engineering acceptance and a small model-judged pilot are separate results. The compact evaluation record is in `eval/results/alpha-pilot.v1.json`; interpretation and provenance are in `PILOT_EVALUATION.md`.

## Implementation and review

GPT-5.6 Sol subagents implemented the independent pipeline, discipline profiles, and evaluation harness. Authenticated `claude -p --model fable` requests reviewed architecture, numerical/evidence checks, integration, scientific restraint, and concrete failure contracts. Prompts, responses, and dispositions are retained in `design_reviews`. These bounded checks found defects and informed fixes; they are not certification of scientific review quality.

All initial manuscript generation used authenticated Codex CLI `gpt-5.6-luna`, reasoning effort `max`. The final methods case uses Fable for product verification; the empirical case uses Luna in a separate call. Reports distinguish these relationships. CLI model aliases/settings are recorded, without treating an alias as proof of an immutable model version.

## Real-paper execution

The first implementation was called complete prematurely after a tiny demonstration and an incomplete methods-paper run. Those are historical diagnostics, not acceptance evidence. The revised alpha uses a 1,800-second deadline per model call and records progress and durations. Full max-effort reviews took tens of minutes; one baseline verification pass took 852.6 seconds. The methods V2 Fable-max verification took 1,269.3 seconds. After evidence-anchoring corrections invalidated its inputs, the final refresh used Fable high while retaining cached Luna-max generation.

Three development baselines completed with `partial=false`:

| Input | Profile | Candidates | Published | Published model-supported / unresolved | Local output |
|---|---|---:|---:|---:|---|
| Original Zcurve manuscript | quantitative_social_science v1 | 23 | 12 | 8 / 4 | `runs/luna-zcurve-complete` |
| Zcurve2 original submission | quantitative_social_science v1 | 25 | 12 | 6 / 6 | `runs/luna-zcurve2-complete` |
| Empirical psychology, benchmark paper 8 | social_psychology v1 | 30 | 12 | 9 / 3 | `runs/luna-known-error-08` |

These retained development outputs predate the final V2 engine and profiles. They are not mislabeled as V2 results. Both final V2 acceptance runs completed with `partial=false`:

| Input | Verification | Candidates | Published | Other dispositions | Local output |
|---|---|---:|---:|---|---|
| Zcurve2 | Fable high, different family | 21 | 5: 3 Major, 2 Minor | 8 merged, 8 needs review | `runs/luna-zcurve2-v2-fable` |
| Empirical benchmark paper 8 | Luna max, same model separate call | 22 | 5: 4 Major, 1 Minor | 17 merged | `runs/luna-known-error-08-v2` |

All ten published findings were model-supported with supported remedies. This is the product verifier's assessment, not ten ground-truth correct claims. The methods refresh used cached Luna generation, 337.5 seconds for Fable verification, and 314.1 seconds for final editorial synthesis. Empirical generation and verification remained cached during its 165-second editorial reconciliation repair. Detailed evaluations are recorded in the pilot summary.

The two methods manuscripts match the original public human-review versions, with binary and extracted-text hashes. The empirical manuscript is the modified DOCX from Dawes benchmark commit `3d9188343eebd4312d3bfbde6822cfa4eaf32fb4`. Review subprocesses received only manuscript sources and frozen profiles, not human reviews or planted-error annotations. Public benchmark contamination cannot be excluded.

## Integrity checks

The regression suite covers extraction order/coverage, profile inheritance, numerical assumptions and rounding, original-source quotation offsets, forged finding status, cache invalidation, editorial target integrity, publication quarantine, remedy withholding, HTML escaping, input triage, blinded order swaps, per-paper aggregation, and audit strata. Packaging checks install the wheel outside the repository and exercise bundled profile resources and a fixture review. The current suite passes 80 tests, including normalization fidelity, blinded listwise ranking, complete judge aggregation, and resumable presentation checkpoints. Source distribution and wheel builds succeeded. An isolated installation outside the repository completed the bundled V2 fixture review (`runs/wheel-release-demo`); a fresh installation of the expanded wheel also loaded the `evaluate`, `normalize-review`, `rank-reviews`, and `aggregate-review-ranks` commands successfully.

A fresh model-backed run of the insufficient demonstration manuscript produces one Minor intake limitation, skips substantive reviewing, exits partial, and records verification as `not_run`: `runs/luna-insufficient-material-v2`. Fixture outputs are explicitly demonstrations. A final empirical rerun reused all generation and verification stages; the editorial-only repair reconciles overview/strengths with supported findings while preserving the preliminary study map.

Candidate/unverified findings cannot publish even when the editor selects them. Contradicted findings are rejected. A failed editorial stage quarantines findings rather than publishing an uncapped fallback. Supported criticisms and proposed remedies are assessed separately; overreaching or unresolved remedies are withheld. Semantic consolidation preserves the original candidates and merge targets.

The conservative quote normalizer has a known safe failure mode: a PDF line-wrap hyphen can fail to match a model quotation retaining a lexical hyphen (for example, `p-` followed by a newline and `curve`). Four evidence occurrences in the methods V2 case lost earlier anchors after numeric-integrity fixes. This changed the actual verification inputs and correctly invalidated the old cache; those findings require unresolved treatment unless adequate evidence is supplied. Structured PDF table reconstruction and comprehensive typography repair remain outside this alpha.

## What the pilot can establish

The two human-comparison papers are related statistical-methods cases. Presentation orders, judge families, and pipeline variants are repeated measurements, not additional papers. The empirical known-error case measures detection of ten planted errors, separately before and after publication selection; it does not estimate false-positive rates.

Fable finding assessments and deterministic quotation checks are recorded separately. An exact quotation establishes source provenance, not truth. Unresolved judgments and failed calls are not counted as supported. No representative human-equivalence result or measured low false-claim rate is established. Broader discipline testing and sampled human adjudication remain necessary before such claims.

Downloaded sources and full reports remain local under ignored `runs/` and `eval/corpus/cache/`; compact non-source results and provenance are committed.

## Empirical multi-review workflow follow-up

The original PeerJ 236 manuscript subsequently completed three maximum-effort full-pipeline runs: Luna (24 candidates, 8 published), Sol (22, 6), and Opus (25, 10). All ten substantive/intake stages completed in each run, `partial=false`, and every published finding had model-supported status, a supported remedy, and source offsets for every quotation. Fable high verified all three; Opus shares its model family while Luna and Sol do not. Runtime summed across recorded stages was approximately 57, 59, and 66 minutes respectively; runs executed concurrently.

All four first-round human reports were retained in the original-format ranking pool. The final judges are Codex Sol high and agy Gemini 3.8 Flash (High), replacing the unavailable Claude judge. Per-judge and combined results remain a one-paper workflow diagnostic, documented in PILOT_EVALUATION.md. The strict normalized condition remains ineligible; failed or unavailable audits are not passed or discarded to produce a smaller ranking pool.
