# ReviScope review quality: where we stand

*Status report, 6 October 2026*

## The short version

The engineering work is finished and checked, but we do not yet know whether it makes scientific reviews better. ReviScope's pipeline reviewer is now instructed to spell out how a paper's claims follow from its evidence. Those changes pass the test suite and are merged into local main through `bd4a2a7`, which is not pushed. A six-paper diagnostic then ran to completion, and its two AI judges disagreed. Opus preferred a plain single review to the broad pipeline on all six papers, while Sol preferred the pipeline on all six. Without expert checks we cannot say which judge is right, so the defaults stay unchanged.

The main question is still open. Does the extra pipeline machinery produce more correct and useful scientific criticism than a simpler review, once false accusations, missed issues, burden on authors and compute are counted?

## What changed and what was tested

The patch adds shared reasoning guidance to the pipeline. Reviewers are asked to link each important claim to:

- its premises;
- the inferential step;
- the assumptions it needs;
- any context elsewhere in the paper that qualifies or defeats it.

The optional audit can also record structured reasoning traces and how a claim relates to prior literature. These records are only for inspection. A criticism still has to pass ordinary verification before it is published.

The diagnostic used six curated Meta-Psychology submissions. They cover experimental social psychology, an education research proposal, a statistical tutorial and meta-research. "Training" here means development data used to find and fix problems in prompts and the pipeline, not fitting model weights. All Meta-Psychology entries are designated training data, and no independent validation corpus has been chosen yet. Results on these papers therefore cannot show how the system generalises.

Each of three approaches got one fresh generation run, and retries were kept on record:

- **Plain review:** a single tool-enabled review by Sol. It is a separate baseline without the new pipeline reasoning guidance.
- **Broad pipeline review:** a broad reading by Sol. Opus then verifies each criticism, and an editorial step reconciles the result.
- **Broad pipeline plus optional independent evidence audit:** the broad run extended by a separate audit that does not see the broad findings, then reconciled again.

This was not a before/after test of the patch, because no otherwise identical pipeline run without it exists. It did not test the default specialist strategy. The pipeline arms also used far more compute than the plain review.

All 18 reviews completed. Source audits confirmed that each review is bound to the correct submitted paper and that its source access stayed within the permitted policy. Consulting external literature is allowed.

## What the judges said

Opus and Sol compared the reports in pairs. Model and stage labels were hidden, and each pair was shown in both orders. All 48 whole-report comparisons in the repaired set completed. An earlier round of comparisons is kept separately, and order swaps do not count as independent evidence.

| Comparison (six papers) | Opus prefers | Sol prefers |
|---|---|---|
| Broad pipeline vs plain | Plain on all six | Broad on all six |
| Audit vs plain | Audit on two, plain on four | Audit on all six |
| Audit vs broad | Audit on five; one flips with order | Audit favoured; one order ties on three papers |

The broad-versus-plain verdicts split entirely by judge family. Both families helped produce what they judged: Sol generated the criticisms in every AI arm, and Opus verified and reconciled the pipeline text. That creates a risk of bias toward related output. Opus's preference for plain runs opposite to a possible self-preference, but that does not settle which judge is right.

Adding the audit is the one change both judges tended to favour, so it is worth pursuing. It is not evidence that the audit causes better reviews:

- the audit arm used more compute;
- it builds on the broad report;
- it has not been compared with an equally costly second broad reading;
- no expert has checked whether its criticisms are correct.

Opus also preferred the audit report to twelve selected human reports. Format differences and Opus's verifier role rule out reading that as "better than human".

## What the criticism-level checks show

In a separate blinded pass, the judges labelled each criticism against the manuscript. Eleven of twelve judge outputs passed the formatting and grouping protocol. Sol's last Niemeyer response assessed all 82 items but left two ungrouped, so it is kept as a partial diagnostic outside the main counts.

These labels are not validated counts of correct criticism. Pipeline items had already been filtered by verification and editing, while plain items had not. Items are also bundled differently across arms, and a matched quote does not prove the inference drawn from it. Labels on rationales and remedies remain unchecked model opinions. When a judge was re-asked the same task after a formatting failure, some labels changed. A single judge opinion is therefore unstable and should not be read as a precise verdict.

Targeted post-hoc checks on Sætrevik show what careful checking can separate:

- **Supported:** the reported d = .15 falls outside the ordinary pooled-SD range implied by the rounded means and SDs. The analysis settings are unknown, so this is a defensible statistical question rather than a proven error.
- **Rejected:** the plain review alleged that the heart-rate-variability (RMSSD) calculation omitted averaging, but the manuscript explicitly says "mean".

These checks were chosen after seeing the outputs, so they illustrate the distinction rather than measure an error rate.

## Current state and decision

On the engineering side:

- The full test suite passed 225 tests with one skipped.
- Opus reviewed the code, the integration, the method and the final results report.
- A known missing-input screening-package failure is now labelled as a skipped check; it never receives a clean result.
- The quotation matcher was narrowly repaired.

Execution failures were logged, and most succeeded on retry. Sol's Niemeyer grouping failure remains unresolved and is retained as recorded. The original frozen outputs were never altered.

Decisions:

- Engineering changes are merged into local main through `bd4a2a7` and not pushed. This report is documentation only.
- The default specialist strategy and the optional audit are unchanged.
- The shared checkout on `known-error-benchmark` has been preserved.
- No new runs follow from this report.

## Recommended next steps

These are proposed scientific-validation steps, in priority order. None has been done yet.

1. **Have a qualified expert check a manageable set of single criticisms.** Include disputed and high-impact items, a reproducible sample of the rest, and the unresolved or held-back concerns the pipeline excluded. This is the step most likely to answer the main question.
2. **Assess full rationales and remedies.** The aim is to see whether the reasoning holds and the requested changes are proportionate for authors.
3. **Repeat generation to measure run-to-run variation.** In the same runs, compare the audit with an equally costly second broad reading.
4. **Freeze the pipeline and test it on an independent corpus** chosen after development ends.

For detail, see the [technical record](REVIEW_QUALITY_TRAINING_TECHNICAL_RECORD.md) (full results, retries, label changes and timings), the [implementation record](REASONING_ASSESSMENT_IMPLEMENTATION.md) and the [benchmark plan](REVIEW_QUALITY_TRAINING_PLAN.md).
