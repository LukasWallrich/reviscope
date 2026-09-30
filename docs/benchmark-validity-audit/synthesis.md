# Provisional validity audit: all ten papers

**Status:** frozen pre-feedback synthesis. Read [feedback-resolution.md](feedback-resolution.md) for disagreements and qualifications; the [comment outline](comment-outline.md) was prepared after both external-model critiques.

The dataset contains useful error targets, but its annotation key is not a defensible homogeneous set of 100 demonstrated scientific defects. Whole-document inspection repeatedly distinguishes a real reporting contradiction from the more serious methodological consequence asserted in the key. Some deleted information survives in captions, appendices, tables, or nearby prose; other targets make debatable analysis choices mandatory. These are sufficient grounds for a constructive, narrowly evidenced comment, without claiming that this AI-assisted audit establishes a replacement gold standard.

All 100 targets have a per-row annotation, verdict, confidence, defensible criticism, and checked source quotations in [audit-100.json](audit-100.json). [The readable audit](audit-100.md) links the three detailed batches. Inputs comprise all 20 original/modified DOCX files pinned to commit `3d9188343eebd4312d3bfbde6822cfa4eaf32fb4`, with hashes in `runs/benchmark-validity-audit/inputs/provenance.json`. Source text line numbers include the benchmark banner and retain table cells, captions, headers and notes. Figures were inspected selectively; original numerical data, linked supplements and cited theories were not exhaustively checked.

## Provisional category totals

| Strongest defensible assessment of the edited manuscript | Count |
|---|---:|
| Demonstrable error, often a narrower internal contradiction |42|
| Material reporting/evidential gap, not proof a procedure was omitted |24|
| Needs data, code, source or equipment verification |9|
| Weak or invalid as a mandatory planted-error target |25|

These are not counts of fully validated ground-truth labels. For example,09-09 does create contradictory raw-versus-centered reporting, so it is in the first category, but the annotation's claim that lack of centering invalidates moderation is not accepted. The strongest defensible criticism often differs materially from the gold rationale. Do not recalculate recall using these category totals or claim that only 42 targets are real errors.

## Strongest counterexamples

1. **10-02: supposedly absent counterbalancing is explicitly documented in Appendix D.** Modified paper 10 line 2492 states that List 2 reverses congruent/incongruent assignment relative to List 1. The main-method deletion does not justify asserting perfect item–condition confounding. This is a direct documentary counterexample requiring no contested statistical convention.
2. **10-05: the annotation's balance arithmetic is wrong.** Appendix D has 120 stimulus rows with 40 noun, 40 adjective and 40 verb contexts (modified lines 2498–3097). Eighty experimental items comprise two categories; 40 verb fillers supply the third. Omitting filler trials from outcome analyses does not undo balance in presented sentence contexts.
3. **07-02 and07-04: the allegedly missing information remains.** The equal real/pseudo composition survives in Figure 1's caption; the temporal-inference rationale survives repeatedly. Criticizing an unbalanced display or a severed logical argument therefore goes beyond the modified artifact.
4. **05-03: centering a sole predictor is not required for comparable regression effects.** In a linear model with an intercept it leaves slope, standardized beta, t statistic and correlation unchanged. The manuscript's footnote identifies simple regressions and its table identifies standardized betas. Treating the deleted centering phrase as a required methodological safeguard misstates the relevant algebra.
5. **09-08: moderator/focal-predictor naming is statistically symmetric.** Both verbal conditional relationships arise from the same interaction model; the surrounding paragraph retains the originally intended interpretation. This is not a different analysis. Related centering targets 06-09 and 09-09 require the same distinction between interpretation and model validity.

Useful counterbalance: the audit also confirms unequivocal targets such as 04-01 (chi-square statistic, df and p disagree),07-10 (40 participants cannot reconcile with 23 retained plus 5 excluded), and10-03 (the stated conditional-probability denominator contradicts its own definition/example). The comment should acknowledge that benchmark development is worthwhile and that many targets are useful.

## The seven universally unmatched targets

The original pinned `writeup_numbers.py` functions reproduce 14 primary configurations and a 93/100 union. [The reproduction manifest](original-union-reproduction.json) records exact saved-match file paths and SHA256 hashes for all 140 decisions files plus source scripts; [the standalone checker](reproduce_original_union.py) recomputes the union without model calls. A stable copy of the pinned inputs is retained under `runs/benchmark-validity-audit/inputs/original-benchmark-scores/`. The unmatched IDs and this audit's provisional assessments are:

| ID | Assessment | Why |
|---|---|---|
|02-10|Weak/invalid|Deleting blanket disclosure does not establish concealed exclusions; other disclosure and preregistration information survives.|
|04-04|Weak/invalid|Slope comparisons do not require flat comparison trajectories.|
|05-03|Weak/invalid|Centering does not alter the relevant regression effects.|
|05-05|Demonstrable, narrower|Eastern/western-only geography contradicts Midwest locations; annotation's rural-classification rationale is overstated.|
|05-06|Material reporting gap|Effect-size-difference adaptation is no longer specified, while a method citation and syntax link survive.|
|07-04|Weak/invalid|Temporal rationale survives elsewhere.|
|10-10|Needs verification|An800ms fixation cutoff warrants robustness checks, but no condition-specific losses establish asymmetric truncation or attenuation.|

Thus the claim that these seven establish an intrinsic inability to find important omissions is not supported by the annotation key alone. In addition,10-10 is an explicit 1500→800ms numerical replacement, not literally an absent reporting detail. Preserve the distinction between the repository's difficulty tier and actual edit type. This audit does not establish that the original automated matching decisions were correct, and it does not reassess all model findings.

## Other systematic limitations

- **Protocol versus completed study:** Paper 2 is explicitly a preregistration draft with simulated Qualtrics data; papers 8–9 are prospective reports. Planned choices are not undocumented deviations merely because they differ from the original artifact.
- **Unreported versus not done:** Deleted coefficient estimates do not show model paths were omitted (01-04,06-02); deleted checks do not show checks failed or were not run (03-06,06-06).
- **Altered plausibility versus demonstrable wrongness:** Different credible intervals, stimulus sizes, trimming thresholds and regression weights may warrant checks. Privileged access to the original proves alteration, not the specific defect claimed.
- **Unwarranted causal consequences:** Many annotations jump from changed reporting to biased results, inflated error rates or invalid conclusions without supporting data. The appropriate review finding may be a clarification or sensitivity analysis.
- **Interacting edits:** One planted change can remove evidence needed to assess another (02-01 versus02-06), or generate an internal contradiction that makes a target easier to identify than its intended methodological issue.

## Recommended scope of a comment

Lead with two or three documentary counterexamples and qualify the inference drawn from the seven misses. Ask for independent expert adjudication of targets, explicit separation of reporting gaps from verified analytic defects, whole-document redundancy checks, and acceptable alternative criticisms. Retain official scores as agreement with the published key; do not replace them with favorable ad hoc scores after inspecting reviewer outputs. Request precision/unsupported-finding assessment alongside recall. Disclose that our audit is AI-assisted, unblinded, and provisional. Fable and agy feedback should precede the final outline and determine which marginal examples to omit.
