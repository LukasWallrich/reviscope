# Papers9–10 planted-error validity audit

Provisional text-grounded audit, not expert adjudication. All20 targets accounted. Evidence lines refer to the pinned extracted texts. Original source comparison identifies alterations, not necessarily scientific defects.

## 09-01: valid_demonstrable_error (high confidence)

Annotation: Changed SESOI from .11 to .27 (the LARGEST observed effect, not smallest) — makes equivalence tests trivially easy; biases toward confirming moral incongruence is unique to pornography

Resolve the incompatible equivalence bounds: the analytic statement uses .27 while the immediately following rationale explicitly selects .11 and calls it especially small. A wider bound allows more effects to meet equivalence, but the manuscript does not establish that tests become trivially easy.

Valid narrower internal inconsistency; consequence exaggerated.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:78`: SESOI) of δ= .27.
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:79`: setting our equivalence region to δ= |.11|

## 09-02: valid_demonstrable_error (high confidence)

Annotation: Removed standardization before averaging — items use different scales (0-5 vs 0/3/6); raw averaging lets larger-scale items dominate composite, creating measurement artifact

Specify whether ASSIST items are standardized before averaging: the measures paragraph says average raw responses, but the analytic plan still explicitly transforms ASSIST items into standardized variables. Different ranges require a weighting rationale, not an automatic requirement to standardize.

Valid reporting contradiction; does not establish unstandardized implementation or dominant-item artifact.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:55`: Responses to each of the above five items will be averaged
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:76`: SPSS will be used to transform the above-described ASSIST items and measures of religiousness into standardized variables.

## 09-03: valid_demonstrable_error (high confidence)

Annotation: Changed 'frequency of engaging' to 'severity of consequences' — transforms moral incongruence (behavior-value mismatch) into moralized distress about real problems, conflating it with the alternative explanation

Reconcile the isolated severity-of-consequences definition with the frequency-by-disapproval construct used in the abstract, hypotheses, and analytic model. The changed sentence misstates the construct, but the operational analysis remains frequency-based.

Valid contradiction; annotation overstates actual transformed measurement.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:31`: interaction of moral disapproval of an action with severity of consequences from the action.
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:34`: interaction of moral disapproval of pornography use and pornography viewing frequency

## 09-04: weak_or_invalid (medium confidence)

Annotation: Changed 'precluding causal inference' to 'limits temporal ordering' — leaves room for causal interpretation when cross-sectional data fundamentally cannot establish causation

The revised sentence still identifies cross-sectional temporal-ordering limitations. It is less explicit about causality, but deleting the absolute phrase does not independently create a causal result or invalidate a stated associational analysis. A reviewer may request sharper language tied to specific overclaims.

Weak as an independently planted defect; no automatic requirement for this exact disclaimer.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:85`: This sample is cross-sectional, which limits the temporal ordering of variables.
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:78`: moderation analyses using the lm function

## 09-05: valid_demonstrable_error (high confidence)

Annotation: Changed from 10 to 8 analyses, removing parallel NIDA-ASSIST analyses for pornography/gambling — eliminates the measurement-equivalence check essential for fair cross-behavior comparison

Reconcile the eight-analysis statement excluding parallel ASSIST tests for pornography/gambling with the explicit plan to collect them for fully parallel analysis, Table1, and the exploratory comparison still using pornography ASSIST. Cross-behavior comparability needs a coherent analysis plan.

Valid plan inconsistency, not proof all parallel analyses were removed.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:53`: These will be included to allow fully parallel analysis across behaviors and substances
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:83`: we will conduct 8 moderation analyses
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:97`: Brief Pornography Screen Sum Score and modified NIDA-ASSIST items

## 09-06: material_reporting_gap (medium confidence)

Annotation: Deleted entire planned DWLS latent variable sensitivity analysis — removes backup for when OLS assumptions fail (likely for ordinal/skewed addiction measures)

The exact DWLS latent sensitivity model has been deleted, leaving a Stage1 plan with unspecified supplemental analyses when assumptions fail. Request prespecified alternatives and decision criteria to limit analytic discretion. Do not claim that no fallback exists: robustness analyses remain promised.

Material loss of specificity, but annotation incorrectly says backup removed entirely.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:77`: in cases where assumptions are substantially violated, we will conduct supplemental analyses to test the robustness of our models, as appropriate.

## 09-07: material_reporting_gap (medium confidence)

Annotation: Removed census region, race/ethnicity, and income from quota-matching — dramatically weakens representativeness; these variables correlate with moral attitudes and substance use

The continued nationally representative claims need qualification or support given matching is now described only for age and gender. Request other calibration/weighting details and uncertainty about representativeness. Cannot infer actual dramatic bias solely from this change.

Defensible scope/reporting concern; magnitude and direction of bias unverified.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:45`: match nationally representative norms for age and gender.
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:85`: nationally representative sample, pre-registered design

## 09-08: weak_or_invalid (high confidence)

Annotation: Swapped moderator and focal predictor — though statistically symmetric, conceptually different: PPMI says disapproval changes the use-addiction link, not that use changes the disapproval-addiction link

No distinct statistical error follows from exchanging the verbal roles of two continuous predictors in their product interaction. The surrounding paragraph still gives the originally intended conditional explanation. For y=b0+b1x+b2z+b3xz, both derivatives vary with the other variable. Conceptual emphasis can be clarified without treating symmetry as a wrong analysis.

Weak/invalid as scored defect; same interaction hypothesis.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:21`: use frequency moderates links between moral disapproval and self-reported feelings of addiction
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:21`: moral disapproval of pornography likely amplifies the links between pornography use and self-reported feelings of compulsivity or addiction.

## 09-09: valid_demonstrable_error (high confidence)

Annotation: Removed centering — main effects evaluated at raw zero (outside scale range for 1-7 disapproval scale); inflates multicollinearity with interaction term

Resolve raw-versus-centered inconsistency between preprocessing paragraphs. Centering changes lower-order coefficient reference points, but with intercept, both main effects and interaction included it does not change fitted values or the interaction coefficient/test; raw zero outside the scale affects interpretation, not mathematical validity.

Valid reporting contradiction; asserted intrinsic multicollinearity/inference defect unsupported.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:76`: focal predictors (behavioral frequency measures) and moderators (moral disapproval questions) will be centered
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:78`: key variables will be entered in their raw form

## 09-10: valid_demonstrable_error (high confidence)

Annotation: Removed restriction to behavior-engagers — includes non-users who have zero frequency AND zero problems, creating massive floor effects that trivially inflate frequency-addiction correlations

Resolve inconsistent eligibility/skip logic: all-participant administration conflicts with the surviving past-year-user restrictions in substance and pornography measures and the expectation of varying subset sizes. Asking nonusers questions is not by itself proof of inflated correlations or equal-zero outcomes.

Valid contradiction; asserted floor-effect magnitude/direction not established.

- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:74`: key measures will be administered to all participants regardless of their engagement
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:54`: Only participants who endorse past-year use will complete further measures of problematic use.
- `runs/benchmark-validity-audit/inputs/paper-09.modified.txt:60`: only participants who report viewing pornography at least once in the past 12 months

## 10-01: valid_demonstrable_error (medium confidence)

Annotation: Removed random intercept for suffixes — 'language as fixed effect fallacy' (Clark, 1973); ignores suffix-level clustering, inflating Type I error

Repeated observations share20 suffixes, and suffix condition is defined at that level, yet the stated model now includes only subject intercepts. Request suffix/item dependence to be modeled or justified before generalizing beyond stimuli. Inflation direction and magnitude require reanalysis.

Substantive model-specification concern; not proof of changed p-values.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:67`: Twenty suffixes diagnostic for the noun or adjective category were selected
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:72`: each suffix occurred twice only.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:75`: glmer (response ~ condition + (1|subject), data, family = "binomial")

## 10-02: weak_or_invalid (high confidence)

Annotation: Removed Latin-square counterbalancing — without it, item properties are perfectly confounded with condition in within-subject design

Counterbalancing was deleted from the main method paragraph but remains explicitly described in AppendixD. The manuscript does not support the claim that item assignments were never counterbalanced or perfectly confounded. Cross-reference the appendix if clarification is wanted.

Invalid omission claim: information survives.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:119`: List 1 is presented in Appendix D.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:2492`: List 2 was identical, but nonwords that were presented in congruent contexts in List 1 were presented in their corresponding incongruent contexts, and vice versa.

## 10-03: valid_demonstrable_error (high confidence)

Annotation: Changed denominator from P(category|suffix) to P(suffix|category) — this IS specificity, not diagnosticity; collapses the paper's central theoretical distinction

Correct the diagnosticity denominator: dividing suffix/category intersection by all words in category does not implement the stated category-given-suffix conditional probability or the example TUDE=1. However the altered formula is not exactly the paper's specificity, which additionally conditions on a sound sequence.

Valid formula error; annotation conflates changed denominator with full sound-conditioned specificity.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:46`: by the total number of words falling into this category.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:46`: –TUDE unambiguously signals a noun (diagnosticity is 1).
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:47`: the total number of words of this lexical category with any spelling of the sound sequence.

## 10-04: material_reporting_gap (high confidence)

Annotation: Deleted entire pre-target word count confound check — the paper acknowledged this confound (significant p<.05 condition difference) and explicitly ruled it out; now the confound is unaddressed

A reported pretarget-word-count difference remains without the deleted sensitivity analysis. Because go-past time includes regressions to earlier words, checking that context-length difference is a material request. Do not infer that confounding actually accounts for the effect.

Defensible material evidential gap, with cautious consequence.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:118`: number of words pre-target was slightly different across conditions (congruent: 4.75, incongruent: 5.23
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:133`: including any fixations made following regressions to earlier words in the sentence.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:136`: These results therefore suggest that the category information conveyed by suffix spelling is used during sentence integration processes.

## 10-05: weak_or_invalid (high confidence)

Annotation: Changed 'more varied' to 'balanced across all three categories' — contradicted by next sentence (fillers not analyzed due to low diagnosticity) and actual numbers (80 experimental vs 40 filler = not balanced)

The assertion of unbalanced three-category contexts is contradicted by the actual120-row AppendixD:40N,40A,40V. Eighty experimental nonwords comprise two categories, with40 verb fillers supplying the third. Excluding fillers from analyses does not contradict balance of presented contexts.

Invalid arithmetic/comparison in annotation.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:117`: Eighty experimental nonwords with suffix spellings diagnostic for adjectives (10 suffixes) or nouns (10 suffixes)
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:117`: Forty filler nonwords whose suffix spellings were diagnostic for verbs
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:2492`: N – noun, A – adjective, V – verb contexts.

## 10-06: needs_external_verification (high confidence)

Annotation: Changed viewing distance from 70cm to 140cm but character width still reported as 0.3° — geometry inconsistent (should be ~0.15° at 140cm)

Verify viewing geometry against actual physical screen size and rendered character width. Doubling viewing distance halves angular extent if physical font width is fixed, but manuscript gives pixel resolution and14pt, not physical display dimensions/rendering scale sufficient to establish exact .15 degrees. The original70cm value is privileged benchmark information.

Plausible typo/check; categorical geometry failure not established from modified text alone.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:120`: viewing distance of 140cm
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:120`: dimensions 1920 x 1080
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:121`: size 14pt, horizontal character width 0.3o

## 10-07: material_reporting_gap (medium confidence)

Annotation: Removed native speaker and no-learning-difficulties screening — non-native speakers and dyslexic participants would have different suffix-category sensitivity, adding noise and potentially attenuating effects

Report sample language proficiency and relevant reading characteristics to interpret skilled-reader generalization. The removal leaves these unspecified; it does not establish nonnative/dyslexic recruitment or require their exclusion in all designs.

Material population reporting gap; asserted composition/effect attenuation unverified.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:66`: Participants were 46 undergraduate students at Royal Holloway, University of London.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:84`: Results suggest that skilled readers extract information about lexical category from written language.

## 10-08: valid_demonstrable_error (high confidence)

Annotation: Swapped diagnosticity/specificity task predictions — diagnosticity should predict reading, specificity should predict spelling; reversed mapping inverts the entire experimental logic

The swapped prediction paragraph contradicts its own feedforward definition and the immediately following specific task predictions. Reconcile the prediction mapping; no claim is needed that every analysis was reversed.

Valid internal theoretical contradiction.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:60`: diagnosticity, a measure of spelling-to-meaning consistency, would impact on tasks that involve the production of spelling
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:62`: in tasks requiring access to grammatical information from printed spellings (lexical category judgment and sentence reading), spellings with higher diagnosticity should yield stronger behavioural effects

## 10-09: needs_external_verification (medium confidence)

Annotation: Removed frequency weighting from entropy regression — rare suffixes with extreme values now dominate equally; finding that spelling > phonology may not hold unweighted

Weighted and unweighted regressions target different summaries. Whether suffix-frequency weighting is preferable depends on whether the intended claim concerns a typical suffix or frequency-weighted exposure. Request rationale and sensitivity analysis; loss of the conclusion cannot be established without corpus data and reanalysis.

Analysis change confirmed; inherent error and claimed consequence unverified.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:153`: lm(Hspelling ~ Hphonology).
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:153`: slope of 0.9 (SE = 0.04, t = 25.32, p < 0.0001)

## 10-10: needs_external_verification (high confidence)

Annotation: Changed upper fixation cutoff from 1500ms to 800ms — asymmetrically trims long fixations from incongruent condition (which has longer processing); attenuates the congruency effect

Ask for justification of800ms fixation trimming, losses by condition, and sensitivity to the cutoff. A common cutoff may select differently across distributions, but no observed exclusion counts establish that here. Go-past-time differences do not imply a longer single-fixation tail: the manuscript reports no first-fixation effect.

Plausible robustness check, not demonstrated asymmetric truncation or attenuation.

- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:124`: more than 800 ms duration.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:131`: There was no effect of congruency on first fixation durations.
- `runs/benchmark-validity-audit/inputs/paper-10.modified.txt:133`: go-past times were longer for incongruent trials than for congruent ones.

