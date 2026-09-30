# Publication and interpretation notes

Checked 2026-09-08. This is preparation for a comment, not a posted communication.

## Publication

Paul Litvak, *How well does AI peer review work? A new evaluation benchmark*, 10 August 2026. Published in his Substack **In One Lifetime**, section Meta Science:
https://www.paullitvak.com/p/how-well-does-ai-peer-review-work

Repository release: 9 August 2026, commit `3d9188343eebd4312d3bfbde6822cfa4eaf32fb4`.
https://github.com/Dawes-Institute/ai-peer-review-benchmark

Tyler Cowen highlighted the findings on 11 August 2026:
https://marginalrevolution.com/marginalrevolution/2026/08/how-well-does-ai-peer-review-work.html

## Author disclosures relevant to a fair comment

The author explicitly describes co-creation with Claude, brainstorming with it, successive modifications after early benchmark saturation, and reliance on AI for research, coding and evaluation. He describes spot-checking errors, asking Claude to explain unfamiliar issues, and does not claim to have thoroughly checked every paper and error himself. He invites a larger team to create fully vetted errors. The comment must acknowledge these disclosures rather than portray the work as claiming comprehensive independent validation.

The author cautions against precise model rankings because models changed after the runs, the target count is small, and the distribution is artificial. He explicitly acknowledges missing precision assessment. Main argument to assess: the data demonstrate difficulty with omissions, and the seven universally missed targets are omissions. Does invalid or ambiguous omission ground truth confound that inference?

## Scope and guardrails for our audit

Assess the pinned modified manuscript actually supplied to reviewers, with captions and tables. Compare originals to establish the textual edit, not to assume originals are methodologically correct. Preserve exact annotations and original scores. Distinguish:
- demonstrable wrong claim, contradiction or computation;
- material missing information justifying clarification;
- a concern requiring additional evidence;
- no defensible defect introduced by the edit.

A valid reporting omission is not evidence of an unperformed analysis, defective design, misconduct or a changed numerical result. Information remaining elsewhere defeats an absence claim. A changed design choice is not intrinsically an error. Benchmark match validity and label validity are separate questions.

This is an AI-assisted diagnostic audit with parent spot-checks and cross-model feedback, not independent human expert validation. Do not replace the answer key by an asserted new gold standard, extrapolate a validity rate to other benchmarks, or revise headline recall without rescoring against a frozen validated rubric. Our selection follows observed pilot failures and is not a blinded validation study.
