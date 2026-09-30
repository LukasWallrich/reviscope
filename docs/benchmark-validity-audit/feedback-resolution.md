# Feedback and parent adjudication — 2026-09-08

This note accompanies the frozen **pre-feedback** 100-target audit. Raw categories remain an internal triage aid, not a replacement gold standard. No original review, benchmark score, or match has been changed.

## Feedback obtained

- **Fable/high**, authenticated Claude CLI, 677.9 seconds. Read all 100 verdicts and annotation file; reported checking the three lead examples, all seven never-matched targets, and about ten other rows against original/modified texts. Also inspected selected saved matches. Did not inspect linked supplements, embedded images, external sources, or the article itself. Raw response: `runs/benchmark-validity-audit/feedback/fable-feedback.txt`.
- **Gemini 3.8 Flash (High) through agy**, 82.5 seconds on successful retry. Read an inline packet with all 100 readable verdicts, source notes, synthesis, provisional argument and 12 detailed evidence rows. Did not independently reread complete manuscripts. First attempt failed at file-read permissions despite explicit added directories; retry embedded the material without tools. Raw responses and prompts, including failed first attempt, are retained in `runs/benchmark-validity-audit/feedback/`.

These are model critiques of an AI-assisted audit, not independent expert validation. Fable and agy agree on the strongest examples but disagree on several marginal classifications.

## Changes to the proposed argument

1. **Omit aggregate validity totals from the public comment.** Both reviewers recommend this. Categories overlap imperfectly with annotation validity: a text contradiction can be real while the key's asserted scientific harm is unsupported. Our post-hoc audit is not a sufficient basis for new validity or recall percentages.
2. **Lead with10-05 and10-02.** Fable independently confirms the 120-row table and Appendix D caption. Parent also counted40 N / 40 A / 40 V. Phrase10-02 as counterbalancing *remaining documented*; never claim to have verified actual implementation. Participant assignment to lists may still warrant clarification, but that is narrower than perfect item-condition confounding.
3. **Use05-03 to address the seven misses.** The simple-regression footnote and standardized-beta table establish the relevant model. Centering a sole predictor in a model with an intercept does not change slope or correlation. Keep the assumption explicit. Paper7's redundant temporal-rationale deletion is a useful second example if space permits.
4. **Correct literal edit-type claim.** Parent verified the article says all seven were omissions. Both04-04(no expectation→also an expectation) and10-10(1500→800ms) are explicit alterations. The original 93/100 union is reproduced from 140 stored match files. Difficulty labels are not synonymous with deletion operations.
5. **Keep conclusions bounded.** These examples weaken the inference that the seven measure a clean omission-detection ceiling. They do not establish that omission detection is easy, that all models intentionally rejected invalid concerns, or that the aggregate tier ordering reverses. Do not adopt agy's stronger claims that models were demonstrably correct to remain silent or that actual experimental implementation was established.
6. **Keep scoring examples in supporting notes.** Parent verified one credited paper 10 counterbalancing criticism concerns Experiment 2 while the edit concerns Experiment 3; the sole credited paper 7 balance criticism concerns Experiment 3 while the edit concerns Experiment 1. These show specific match concerns, not an estimated judge error rate. Another credited paper 10 criticism correctly recognizes List 2 and asks about participant allocation—a potentially fair, narrower reporting request.

## Borderline disagreements retained rather than silently resolved

| IDs | Feedback | Treatment |
|---|---|---|
|05-06|Fable would downgrade the adaptation gap because the remaining method description/citations/code link still signal it.|Do not use as a lead example or claim a final seven-miss validity tally; linked method/code not independently audited here.|
|02-10|Agy considers the removed exclusions assurance a material gap; Fable agrees the target is weak given surviving disclosures.|Explicit disagreement; avoid as a lead example. A missing assurance is not proof of undisclosed conduct.|
|09-08|Fable sees minor framing inconsistency; agy/audit treat statistical role symmetry as defeating the main criticism.|Avoid in comment; statistical and conceptual symmetry are distinct.|
|03-02,08-05,10-01|Agy challenges classification of potential confounds, directional power assumptions, and random-effects omissions as demonstrable errors.|Keep provisional, requiring narrower expert adjudication. Do not present the initial 42 as an agreed total.|
|09-09|Agy objects to counting a text inconsistency as validation of the stronger centering annotation.|Accept distinction; the audit category only describes a defensible narrower criticism.|
|08-08,08-10|Agy questions consistency of treatment of theoretical overclaim and estimand clarity.|Do not use in comment; ordinary publication frequency does not establish validity, and legitimate intention-to-treat does not resolve every estimand-reporting question.|
|04-04|Fable agrees flat comparison slopes are unnecessary but identifies possible theoretical inconsistency.|Use only its objectively altered wording for edit-type correction, not as a flagship invalidity judgment.|

## Verification

Parent verified 100 unique targets, 10 per paper, and 348 quoted passages at their reported starting lines (including multiline table excerpts). Independently reproduced 93 matched targets across 14 configurations and the seven IDs. Parent spot-checked proposed lead source passages and40/40/40 counts. This verifies provenance and quotation fidelity, not all scientific judgments. Raw audit files are retained to make disagreements visible.
