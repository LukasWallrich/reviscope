# Proposed comment outline

Prepared after feedback from Fable/high and Gemini 3.8 Flash (High) through agy. **Not posted.**

## Venue and scope

Paul Litvak, **How well does AI peer review work? A new evaluation benchmark**, published 10 August 2026 in **In One Lifetime** on Substack:
https://www.paullitvak.com/p/how-well-does-ai-peer-review-work

Recommend a constructive reader comment of approximately 350–450 words, with the detailed audit offered as supporting material. An extended note could expand the evidence; a full rebuttal is not needed. The author explicitly discloses Claude co-creation, incomplete human checking and a desire for community vetting.

## Central point

**A known textual edit is not necessarily a known scientific defect. Some targets retain the supposedly missing information elsewhere, and at least one planted statement is supported by the manuscript's own table. This matters especially when interpreting the seven universally unmatched targets as an omission-detection ceiling.**

## Outline for the comment

1. **Acknowledge the useful contribution and invitation to audit** (40–50 words).
   Thank the author for releasing originals, modified manuscripts, annotations and results, and for explicitly acknowledging limited verification. Frame this as a response to the invitation to improve the benchmark. The error-planting approach remains useful.

2. **Give two concrete whole-manuscript checks** (110–140 words).
   - **Paper 10, error 5:** the key treats80 experimental items versus40 fillers as an imbalance across three lexical categories. The 80 experimental items span two categories; Appendix D has 40 noun, 40 adjective and 40 verb contexts. Excluding fillers from outcome analyses does not undo balance of presented contexts. This is the clearest target whose asserted contradiction is false.
   - **Paper 10, error 2:** deletion of a main-text counterbalancing description does not remove Appendix D's statement that List 2 reverses congruent/incongruent assignments from List 1. Allocation of participants to lists may warrant clarification, but perfect item-condition confounding is not established. Use “still described,” not “proved to have been implemented.”

3. **Connect specifically to the seven misses** (90–110 words).
   The two examples above show key-validity problems but are not among the seven universally unmatched targets. For that claim, use **paper 5, error 3**: omitting mean-centering does not make simple-regression slopes, standardized betas or correlations incomparable when the model includes an intercept. The manuscript explicitly identifies simple regressions and standardized betas. Also briefly correct “all seven were omissions”: two are wording/number alterations, including 1500→800ms fixation trimming. If space permits, paper 7,error4 deletes a rationale still stated elsewhere.

4. **State the implication without inventing new performance claims** (40–60 words).
   The seven are not a clean test of missing-information detection. Their interpretation needs target-validity adjudication. These checks do not establish a corrected recall, a new ranking, or that omission detection is easy. Main-text clarification can be legitimate without supporting the stronger defect asserted by an annotation.

5. **Offer a concrete next step and disclose our method** (60–80 words).
   Suggest a frozen, independently adjudicated rubric separating contradictions, material reporting gaps and permissible choices; check the whole document for retained information and specify acceptable criticism boundaries. Assess unsupported findings separately from recall. Disclose that this audit is AI-assisted and provisional, with selected documentary/arithmetic checks, rather than a new expert gold standard.

## Supporting evidence for the user

- 10-05: [modified paper 10,line 117](../../runs/benchmark-validity-audit/inputs/paper-10.modified.txt), Appendix D starts line 2492 ; 120 rows at 2498–3097,40 N / 40 A / 40 V.
- 10-02: same Appendix D caption: “List 2 was identical, but nonwords that were presented in congruent contexts in List 1 were presented in their corresponding incongruent contexts, and vice versa.” Consult source for exact spacing before quotation.
- 05-03: [modified paper5](../../runs/benchmark-validity-audit/inputs/paper-05.modified.txt), table note line 236 and simple-regression footnote line 402.
- 07-02 (reserve example): [modified paper 7](../../runs/benchmark-validity-audit/inputs/paper-07.modified.txt), Figure 1 caption line 38 retains real/pseudo composition.
- Seven-miss provenance: [original-union-reproduction.json](original-union-reproduction.json), [reproduction script](reproduce_original_union.py). This reproduces stored matches, not a validation of judge decisions.
- Exact 100-row record: [audit-100.json](audit-100.json); [readable audit](audit-100.md). These are frozen pre-feedback triage classifications.
- Feedback and qualifications: [feedback-resolution.md](feedback-resolution.md).

For a public comment, use paper/experiment/table identifiers and pinned repository links rather than these local extraction line numbers. The canonical annotated CSV and modified DOCX are at:
https://github.com/Dawes-Institute/ai-peer-review-benchmark/blob/3d9188343eebd4312d3bfbde6822cfa4eaf32fb4/error_insertions.csv
https://github.com/Dawes-Institute/ai-peer-review-benchmark/tree/3d9188343eebd4312d3bfbde6822cfa4eaf32fb4/modified%20papers

## What to leave out

Do not headline provisional category totals or claim 25 percent of errors are invalid. Avoid borderline centering/moderation, random-effects and design-choice examples when cleaner ones suffice. Do not imply misconduct, treat Claude involvement itself as disqualifying, or attribute model silence to deliberate restraint. Do not claim the entire omission finding has been disproved. Keep isolated scoring mismatches in the supporting note unless the author asks about scoring.

## Fair counterargument and response

The author may reasonably say this was an exploratory demonstration, that gaps in the main Methods can warrant clarification, and that rankings might survive a few disputed labels. Agree. The narrower point is that the key should not equate a clarification request with an established confound, and that the specific seven-miss narrative requires valid targets. No revised model ranking is claimed.
