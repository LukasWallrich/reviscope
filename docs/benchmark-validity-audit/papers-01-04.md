# Benchmark validity audit: papers 1–4

Independent manual audit of papers 1–4, CSV ordinal rows 1–10 within paper, pinned input artifact commit 3d918834. No pipeline model runs.

Read every line of each modified text, including captions/tables/notes, then compared all original–modified differences. Exact evidence quotes are validated against line-numbered text. Original differences establish alteration, not scientific invalidity. Supplementary/source-dependent questions are retained as unresolved rather than silently inferred.

Counts: needs_external_verification: 4, material_reporting_gap: 11, valid_demonstrable_error: 18, weak_or_invalid: 7.

- Linked supplements, original cited source papers, datasets and analysis code were not independently retrieved.
- Paper 2 repeatedly identifies the artifact as a preregistration draft using simulated Qualtrics responses; statements about performed real-world studies must be qualified.
- Paper 1 DOCX contains no media or textbox diagram; Figure 1 caption survives but no graphic could be used to recover autoregressive estimates.
- Verdicts assess the strongest defensible consequence of each edit and may differ from its annotation rationale.

## 01-01 — test_parameter_error

**Verdict:** `needs_external_verification`; confidence: medium.

**Annotation claim:** Widened RWA confidence interval lower bound from -.03 to -.05, making RWA effect appear to overlap more with SDO — undermines core claim of differential prediction

**Audit:** The changed interval is suspiciously asymmetric around B=-.02, but SD is labelled SD, precision is heavily rounded, and the interval method is unspecified. It cannot be disproved solely by an SE-width calculation. The annotation’s overlap rationale is wrong: [-.05,-.01] still does not overlap SDO [-.13,-.09]. Verify the numerical interval against model output; do not count wider intervals or overlapping marginal CIs as proof of an erroneous contrast.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:88`: “SDO was a stronger predictor of change in environmental sacrifice (B = -.11, SD = .01, p < .001, 95% CI [-.13, -.09]) than RWA (B = -.02, SD = .01, p = .001, 95% CI [-.05, -.01])”

## 01-02 — measurement_invariance_removed

**Verdict:** `material_reporting_gap`; confidence: high.

**Annotation claim:** Removed metric and scalar invariance testing (equal factor loadings and intercepts) — without these, latent constructs could mean different things at different time points, making cross-lagged comparisons meaningless

**Audit:** The specific loading/intercept constraints are no longer reported, leaving longitudinal measurement comparability unclear. However “all parameters” time-invariant and residual equality survive. Deleting a description does not establish that invariance was neither imposed nor tested. The original describes imposing constraints, not a sequence of invariance tests; its factor means/intercepts wording is itself ambiguous. “Meaningless” and blanket scalar-invariance prerequisites overstate what is demonstrated.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:47`: “a stationary cross-lagged model where all parameters are set as time-invariant”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:47`: “We started by constraining the cross-lagged associations between the constructs”

- `runs/benchmark-validity-audit/inputs/paper-01.original.txt:46`: “ensure factor loadings were invariant across measurement points”

## 01-03 — measure_construct_mismatch

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Replaced behavioral intention DV (willingness to sacrifice) with attitude measure (environmental concern) — paper's theoretical contribution about ideology predicting behavioral willingness is now unsupported by the DV

**Audit:** Concern/exaggeration questions do not ask willingness to sacrifice. The results and conclusions nevertheless retain that outcome label and behavioral-intention interpretation. This is a directly visible measurement–claim mismatch, irrespective of whether the source scale attribution is accurate.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:44`: “Environmentalism was measured as participants’ concern about environmental problems.”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:109`: “both SDO and RWA predict lower willingness to make sacrifices for the environment over time”

## 01-04 — autoregressive_paths_removed

**Verdict:** `material_reporting_gap`; confidence: high.

**Annotation claim:** Removed autoregressive path coefficients — these control for prior levels in CLPM, essential for interpreting cross-lagged paths as predicting change

**Audit:** The numerical stability estimates have been removed from the prose, so the stability claim loses quantitative support in this supplied artifact. But the heading explicitly retains autoregressive paths; removal of coefficients from reporting does not remove them from the model. Figure 1 is referenced but the DOCX has no embedded media or text-box path diagram, so a surviving graphic cannot rescue the missing coefficients here. The annotation’s causal-control diagnosis is not established.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:85`: “Stability over time: Autoregressive paths”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:86`: “SDO, RWA, and willingness to sacrifice were all relatively stable over time”

- `runs/benchmark-validity-audit/inputs/paper-01.original.txt:85`: “the autoregressive path for willingness to sacrifice was strong (B = .83, SD = .01”

## 01-05 — model_results_contradiction

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed chi-square from significant (50.98, p<.001) to non-significant (2.34, p=.126) — formal test now says SDO and RWA effects are NOT different, but text still claims SDO is stronger

**Audit:** The edited sentence is explicitly descriptive and a nonsignificant contrast does not prove equal effects. Nevertheless the Discussion still claims SDO is significantly stronger. That surviving inferential claim is unsupported by the reported equality test p=.126. Score the overclaim, not the false proposition that nonsignificance establishes no difference.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:88`: “comparable fit to the data 2(1) = 2.34, p = .126”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:94`: “SDO is a significantly stronger prospective predictor than RWA.”

## 01-06 — model_specification_removed

**Verdict:** `material_reporting_gap`; confidence: high.

**Annotation claim:** Removed: latent variable specification, cross-lagged structure, FIML for missing data — reader cannot evaluate measurement model, model type, or missing data handling

**Audit:** Latent versus observed variable construction and the complete path specification are inadequately specified. The annotation overstates the deletion: the next paragraph explicitly names a stationary cross-lagged model, and missing-data handling is explicitly listwise deletion (another planted row). The justified criticism concerns the measurement model and full paths, not absence of model type or missing-data method.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:46`: “The model included three variables across five measurement points”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:46`: “Analyses were conducted using listwise deletion.”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:47`: “a stationary cross-lagged model”

## 01-07 — sample_description_changed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed nationally representative sample (N=22974) to convenience student sample (N=374) — paper's own discussion explains SDO-environment link is weaker in student samples

**Audit:** A student convenience sample can be legitimate, but it contradicts the national probability/representativeness claims and the discussion’s explanation that sample type distinguishes this study from student research. The robust defect is contradictory population description and unjustified population generalization, not the bare choice of students or small N.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:40`: “introductory psychology participant pool at Victoria University of Wellington”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:40`: “Of the 374 participants included in this study”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:107`: “Our research uses a nationally representative sample”

## 01-08 — theoretical_framework_misattributed

**Verdict:** `needs_external_verification`; confidence: medium.

**Annotation claim:** Replaced Duckitt's dual-process model (explains BOTH SDO and RWA via different worldviews) with SDT (focuses on SDO/hierarchy only) — SDT alone doesn't predict RWA effects

**Audit:** The framework attribution changed, and the same dual-pathway account is later attributed to Duckitt. This makes a source-verification request reasonable. However the supplied manuscript does not establish exactly what Sidanius and Pratto’s book permits one to claim about RWA; proving categorical misattribution requires checking that primary source. Do not equate SDT’s emphasis on SDO with proof it cannot discuss RWA.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:23`: “Sidanius and Pratto’s [1] social dominance theory proposes that SDO and RWA are separate but interrelated”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:102`: “Duckitt’s [3] dual-process model predicts a pathway where ultimately SDO and RWA are causes of prejudice”

## 01-09 — analysis_specification_changed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Switched from unstandardized (time-invariant) to standardized (time-varying) parameters — creates inconsistency with single reported coefficients; relaxed alpha from .01 to .05 removing large-N safeguard

**Audit:** The analysis text says standardized time-varying coefficients and alpha .05, while Figure 1’s caption says unstandardized and .01, and the results describe unstandardized coefficients. This is a direct reporting contradiction. Changing alpha to .05 is not inherently erroneous; reporting one coefficient for a stationary unstandardized model is not itself erroneous either.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:48`: “We present standardized parameters, which vary across time points”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:84`: “Figure 1. Unstandardized parameters”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:84`: “threshold for significance of p < .01”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:48`: “threshold of p < .05”

## 01-10 — missing_data_handling_changed

**Verdict:** `material_reporting_gap`; confidence: medium.

**Annotation claim:** Changed FIML to listwise deletion — in 5-wave panel study, listwise deletion would dramatically reduce N and produce biased estimates if dropout is non-random

**Audit:** Listwise deletion is explicitly disclosed, not inherently biased. The manuscript also says one RWA item was not assessed at Time 2 but is included otherwise; with item-level listwise deletion this creates an important unresolved question about retained cases and variables. Report the operational definition, retained sample and missingness/attrition assessment. The annotation’s dramatic loss and biased-estimate claims are conditional, not demonstrated.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:46`: “Analyses were conducted using listwise deletion.”

- `runs/benchmark-validity-audit/inputs/paper-01.modified.txt:43`: “was not assessed at time two, but included in all other time points”

## 02-01 — effect_size_misreported

**Verdict:** `needs_external_verification`; confidence: high.

**Annotation claim:** Changed Study 3 d from 0.55 to 0.23 — makes power analysis based on d=-0.36 no longer the most conservative estimate; study may be underpowered for this smaller effect

**Audit:** The number differs from the original manuscript, but d=.23 and its CI are not internally impossible. The claimed inconsistency with planning at d=-.36 cannot be observed in the modified artifact because row 02-06 removed that planning paragraph. The remaining table is an omnibus three-group F rather than a uniquely specified pairwise d. Recover the supplementary calculation and intended contrast to establish numerical misreporting or inadequate planned power.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:126`: “d = 0.23, 95% CI [0.01, 0.45]”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:238`: “The full report of power analysis can be found in the supplementary”

- `runs/benchmark-validity-audit/inputs/paper-02.original.txt:237`: “Cohens’d = -0.36, the corresponding sample size to detect such effect was 314”

## 02-02 — design_type_changed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed between-subjects to within-subjects — impossible for this intervention (learning about IVE permanently changes cognition); df in ANOVA tables are inconsistent with within-subjects

**Audit:** The within-subject label is incompatible with the described selection of conditions, disjoint six-cell counts summing to 1000, and the ordinary 2×3 ANOVA residual df=994. A within-subject intervention is not literally impossible, but carryover would need handling. Crucially this paper labels these methods/results as a simulated preregistration draft; the demonstrated defect is the proposed design/analysis reporting inconsistency, not proof that a real experiment was improperly conducted.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:272`: “single within-subject design”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:274`: “Participants selected their preferred intervention and identifiability conditions.”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:502`: “Residual
Original study
115
Replication
994”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:423`: “written using randomized dataset produced by Qualtrics”

## 02-03 — affect_measures_replaced

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Replaced affective measures with cognitive evaluations — IVE theory is explicitly affect-driven (affect heuristic); cognitive measures can't test the proposed emotional mechanism

**Audit:** The alteration is in the narrative about Small et al.’s original Study 1, not the replication’s own measurement procedure. Table 5 still lists the original and replication emotional measures, contradicting the new cognitive-item narrative. The valid error is inconsistent reporting of the original study; it is false to infer that the replication no longer measures affect.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:202`: “questionnaire for different cognitive evaluations”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:332`: “Note: Segregated feelings include being
upset, being touched, being sympathetic, moral responsibility, and donation appropriateness”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:405`: “We will measure affective feelings in the Joint condition”

## 02-04 — random_assignment_removed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Replaced random assignment with self-selection — eliminates internal validity; empathetic people may choose identifiable victim condition

**Audit:** Self-selection prevents condition comparisons from isolating the experimental intervention without additional assumptions or adjustment. This also weakens the stated close-replication design. But “eliminates internal validity” is too absolute, and selection specifically by empathy is only a possible confound. Interpret as a defect in the proposed design: the methods and results are explicitly simulated.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:274`: “Participants selected their preferred intervention and identifiability conditions.”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:123`: “thinking analytically about the value of lives reduces giving to an identifiable victim”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:235`: “Method and results sections were written using randomized dataset produced by Qualtrics”

## 02-05 — effect_direction_reversed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Reversed which condition has higher donations — IVE is now reversed (statistical > identifiable), contradicting the phenomenon being replicated and Table 11 descriptives

**Audit:** The prose swaps the group labels attached to the means. Table 7, not Table 11, provides the decisive descriptives: identifiable cells 2.58 and 2.50 exceed statistical cells 2.46 and 2.01, with the stated sample sizes yielding marginal means about 2.54 versus 2.25. A replication may reverse a target phenomenon without error; the error here is contradiction with its own simulated table.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:578`: “a statistical victim (M=2.54, SD=1.76)”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:429`: “Identifiable victim condition
Statistical victim condition
Joint condition
Intervention condition
2.58 [1.77] (159)
2.46 [1.69] (175)”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:436`: “No intervention condition
2.50 [1.75] (175)
2.01 [1.61] (159)”

## 02-06 — power_analysis_removed

**Verdict:** `material_reporting_gap`; confidence: medium.

**Annotation claim:** Removed specific power parameters (power=.95, alpha=.05, d=-.36, N=314) — reader cannot evaluate power adequacy or whether target effect size is appropriate

**Audit:** The supplied main text no longer specifies target effect, test, power, alpha, and planned N. It still explicitly directs readers to a full supplementary power report. This is a main-artifact reporting gap, not proof no adequate power analysis exists. Supplement access could resolve it, and simulated N=1000 should not be mistaken for the planned real sample.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:238`: “sample size for this study was determined to ensure adequate statistical power”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:238`: “full report of power analysis can be found in the supplementary”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:237`: “1000 responses were generated from the Qualtrics for pre-registration”

## 02-07 — exclusion_criteria_added

**Verdict:** `material_reporting_gap`; confidence: medium.

**Annotation claim:** Added non-preregistered exclusions — prior-knowledge exclusion biases toward IVE-naive participants; contradicts 'no exclusion' claim earlier

**Audit:** The inserted exclusions lack counts, operational definitions and a clear relationship to the simulated-data draft. The old “no exclusion” sentence was replaced, not retained, so the claimed internal contradiction is absent. Neither non-preregistration nor actual selection bias can be inferred from adding these legitimate possible eligibility/quality criteria. Their timing and effect on N need clarification.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:237`: “Participants who indicated they had prior knowledge of the identifiable victim effect were excluded, as well as those who failed the attention check.”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:235`: “Method and results sections were written using randomized dataset produced by Qualtrics”

- `runs/benchmark-validity-audit/inputs/paper-02.original.txt:236`: “There was no exclusion of samples in this study.”

## 02-08 — mechanism_replaced

**Verdict:** `material_reporting_gap`; confidence: medium.

**Annotation claim:** Replaced affect heuristic (emotional arousal) with availability heuristic (memory retrieval) — changes the theoretical mechanism; intervention design and feeling measures no longer match the theory

**Audit:** The paragraph names retrieval ease but explains the effect entirely via emotional arousal, and later predictions explicitly invoke the affect heuristic. The justified criticism is an unexplained theoretical link and terminology shift, not proof an availability-based explanation is impossible. The rest of the affect rationale survives, so the whole paper’s mechanism has not simply been replaced.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:118`: “which relies on the ease of retrieving relevant instances from memory”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:118`: “As such, affective feelings do play a role in the identifiable victim effect.”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:124`: “override the affective heuristic”

## 02-09 — preregistration_removed

**Verdict:** `weak_or_invalid`; confidence: high.

**Annotation claim:** Removed pre-registration on OSF — eliminates the constraint on analytic flexibility that gives replication studies credibility

**Audit:** Preregistration was not removed from the manuscript as a whole. A dedicated OSF preregistration link, author contributions, abstract and study rationale all survive. Deleting one redundant statement cannot establish absence of preregistration or freedom from constraints. The artifact is itself explicitly a preregistration draft with simulated results.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:95`: “Pre-registration on the Open Science Framework
<https://osf.io/n4jkh/?view_only=d52771c7540a4a8f8051c8b430a6f15d>”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:107`: “In this pre-registered study”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:121`: “well-powered pre-registered close to very close replication”

## 02-10 — transparency_statement_removed

**Verdict:** `weak_or_invalid`; confidence: high.

**Annotation claim:** Removed 21-word solution disclosure (Simmons et al 2012): 'exclusions...reported' and pre-registration claim — hides whether unreported exclusions or measures exist

**Audit:** The new disclosure still states all measures/manipulations are reported, collection preceded analysis, and full disclosures are in the supplement; preregistration survives elsewhere and the newly specified exclusions are visible. Removing a blanket assurance about exclusions is not evidence of concealed exclusions or undisclosed measures. Any concrete exclusion-reporting gap belongs to row 02-07.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:233`: “Full open-science details and disclosures are provided in the supplementary. All measures and manipulations conducted for this investigation are reported, and data collection was completed before analyses.”

- `runs/benchmark-validity-audit/inputs/paper-02.modified.txt:237`: “Participants who indicated they had prior knowledge of the identifiable victim effect were excluded”

## 03-01 — confidence_interval_changed

**Verdict:** `needs_external_verification`; confidence: high.

**Annotation claim:** Widened CI lower bound from -0.34 to -0.54 — inconsistent with later-reported HPDI values, changes precision of null result

**Audit:** The interval is changed, but Bayesian credible intervals need not be symmetric around a posterior mean. More importantly, the later HPDIs describe understanding levels at generations 1 and 5, not the generation slope. Their different endpoints therefore are not a numerical contradiction. Check posterior output/Supplementary Table 2 to establish the correct slope interval; merely changing a plausible interval is not a demonstrable methodological defect.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:17`: “Generation 95% CI: (-0.54, 0.25), mean = -0.04”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:17`: “their understanding score was 4.60 (95% HPDI: (3.83, 5.53))”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:58`: “95% credible intervals were used to make inferences”

## 03-02 — procedure_order_changed

**Verdict:** `valid_demonstrable_error`; confidence: medium.

**Annotation claim:** Changed theory-writing from after to before test — act of generating theory could inflate understanding scores in Theory condition (generation effect), confounding the understanding measure

**Audit:** Writing one’s own theory before completing the understanding test introduces an additional treatment-specific activity that could affect measured understanding. Therefore comparisons do not isolate receiving/transmitting another person’s theory from effects of actively formulating one’s own before assessment. The order is explicit, but inflation via a generation effect is only a possibility, not an observed result; “before completed” also leaves exact timing within the test unclear.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:47`: “Participants were asked to write their theory before the test phase was completed.”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:18`: “The cultural transmission of explicit causal theories might affect both the optimization and the understanding”

## 03-03 — understanding_measure_changed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed from comparative judgment (which wheel first) to absolute estimation (how long) — measures different construct; absolute timing requires calibrated knowledge, not relative understanding

**Audit:** The new absolute-time task contradicts both the surviving figure caption and detailed method, which specify relative choice among Wheel 1, Wheel 2, and No difference. The demonstrable error is an incompatible outcome description. Absolute estimates could in principle be ranked into relative predictions, but no such scoring bridge is given.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:14`: “asking them to estimate how long each wheel would take”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:15`: “predict which of two wheels would cover the distance faster”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:45`: “For each pair, participants could submit 3 possible answers: “Wheel 1”, “Wheel 2” or “No difference”.”

## 03-04 — information_constraint_removed

**Verdict:** `weak_or_invalid`; confidence: high.

**Annotation claim:** Changed from last-two to all-previous configurations — breaks information parity with between-generation transmission, confounding cumulative cultural learning with individual data accumulation

**Audit:** Consulting all of one’s own five-trial history is a changed design choice, not an established confound. It applies to all participants/treatments, and the number of trials and two-configuration transmission remain fixed across generations. Individuals already physically observed their earlier trials. There is no stated design requirement that displayed within-person memory equal transmitted information; the edit alone does not make across-generation improvement attributable to unequal individual experience.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:43`: “Each participant had 5 trials”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:43`: “Participants could consult all of their previous configurations between any trials.”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:47`: “the last two configurations and associated scores of the previous participant in the chain were provided to the next participant”

## 03-05 — coder_count_changed

**Verdict:** `weak_or_invalid`; confidence: high.

**Annotation claim:** Changed blind coders from 5 to 3 — undermines reliability of theory coding; reported kappa values may not match 3-rater computation

**Audit:** Three blinded coders can support reliable coding; no minimum of five is established. Agreement coefficients could be computed or summarized from three raters as from five. The manuscript already used the label Cohen’s kappa with five raters in the original, so any ambiguity about pairwise aggregation is pre-existing, not a newly demonstrated numerical impossibility.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:56`: “3 individuals blind to the research question”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:56`: “Cohen’s kappa coefficients reveal almost perfect agreement between raters (0.81 for inertia and 0.85 for centre of mass).”

- `runs/benchmark-validity-audit/inputs/paper-03.original.txt:55`: “5 individuals blind to the research question”

## 03-06 — robustness_check_removed

**Verdict:** `material_reporting_gap`; confidence: high.

**Annotation claim:** Deleted MCMC convergence warning AND robustness checks — hides computational problems with primary model and the verification that alternative specifications confirmed results

**Audit:** Comparison confirms removal of the reported inefficient sampling/low effective sample size and successful sensitivity checks for Analysis 3. That is material diagnostic and robustness-reporting loss, not evidence checks were not run or the primary model failed to converge. The original warning concerned inefficiency/low ESS; a separate nonconvergence disclosure for Analysis 4 survives. Supplementary Table 3 and available code might restore the missing evidence.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:64`: “see Supplementary Table 3 for model output”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:68`: “the preregistered model did not converge so we ran our analysis on aggregated score”

- `runs/benchmark-validity-audit/inputs/paper-03.original.txt:63`: “the chains were inefficient and the effective number of samples for one parameter was low”

- `runs/benchmark-validity-audit/inputs/paper-03.original.txt:63`: “Additional models with more efficient sampling confirmed the reported results”

## 03-07 — mixed_gender_overclaim

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Added mixed-gender generalizability claim when methods state chains were 'exclusively males or exclusively females' — visible contradiction with design

**Audit:** The categorical claim that findings generalize to mixed-gender collaboration is unsupported by a study with exclusively single-sex chains and deliberate prevention of direct interaction. Such generalization could be a hypothesis for future testing, but it is not a finding demonstrated here. This is overreach, not logical proof mixed-gender outcomes must differ.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:24`: “These findings generalize beyond the single-sex chain compositions used here”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:47`: “exclusively males or exclusively females”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:40`: “prevent any form of direct interactions between participants”

## 03-08 — hypothesis_mischaracterized

**Verdict:** `material_reporting_gap`; confidence: medium.

**Annotation claim:** Changed 'poorly understood' to 'well-understood' — fundamentally mischaracterizes the hypothesis; contradicts next sentence about 'absence of explicit understanding'

**Audit:** The substituted “well-understood” premise clashes with the paper’s own account that the hypothesis predicts optimization without individual causal understanding. Local improvements can conceivably be understood without global understanding, so adjacent clauses are not a strict logical contradiction. The justified critique asks the authors to distinguish local versus system understanding and reconcile their hypothesis/test; proving the cited theory is misrepresented requires checking the primary theoretical sources.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:11`: “well-understood improvements made across generations”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:11`: “in the absence of explicit understanding about how these solutions work”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:16`: “participants’ understanding of the system will not improve over generations”

## 03-09 — model_selection_admission

**Verdict:** `material_reporting_gap`; confidence: high.

**Annotation claim:** Added explicit model selection based on data fit, contradicting the pre-registration claim that 'analysis plan took place before any data were collected'

**Audit:** Post-data model selection is explicitly disclosed, but the candidate models, selection rule and preregistered status of that procedure are not. Preregistration can include a model-selection rule, so this is not by itself a contradiction of preregistration. Clarify whether selection was prespecified or a deviation and report the selection process; the existing deviation section discusses a different analysis.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:60`: “The final model specification was selected after comparing several candidate models based on fit to the observed data.”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:71`: “Pre-registration of the study design, hypotheses and analysis plan took place before any data were collected.”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:68`: “In preregistered analysis 4”

## 03-10 — exclusion_criterion_removed

**Verdict:** `material_reporting_gap`; confidence: high.

**Annotation claim:** Deleted specification that failed wheels got speed=0 — without this, reader can't evaluate if increasing speed reflects genuine optimization or just fewer failures

**Audit:** The mapping of non-descending wheels into the analysis outcome is now unspecified. Figure 2 separately plots failure counts and speeds only for non-failures, while model descriptions merely restrict to the final two trials. This is material because a model including zero-speed failures answers a different question from one conditioning on descent. The original confirms removed zero coding; do not infer failures were excluded or misconduct occurred.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:20`: “Vertical bars show the number of wheels that did not descend”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:20`: “Coloured lines show the average speed for non-failure wheels”

- `runs/benchmark-validity-audit/inputs/paper-03.modified.txt:60`: “Data were restricted to participants’ last two trials”

- `runs/benchmark-validity-audit/inputs/paper-03.original.txt:59`: “Wheels that did not go down were attributed a speed of 0.”

## 04-01 — p_value_inconsistent

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed p from .033 to .003 — chi-square(3)=8.74 yields p~.033 not .003; makes marginal finding appear robust

**Audit:** The reported chi-square and df imply p≈.03296, not .003. Table 2 retains .033 for exactly this test, so there is also a direct table–text contradiction. Both values meet .05; the altered value exaggerates evidence rather than changing that threshold decision.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:73`: “2(3)=8.74, p=.003”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:281`: “Sadness (sad)
2=8.74
3
.033”

## 04-02 — comparison_condition_altered

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed positive mood to typical/neutral mood — compresses risk gradient, eliminates theoretical contrast between suicidal states and genuinely positive states

**Audit:** A neutral low-risk comparison is not intrinsically invalid and still permits testing differentiation from lower-risk states. Here, however, the interview definition says typical/neutral mood while procedure, model labels and interpretation repeatedly say positive mood. That makes the actual comparison condition ambiguous and interpretations of positive episodes unsupported.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:47`: “two-week episode of typical mood (i.e., neither particularly positive nor negative mood”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:52`: “two-week episodes of suicide ideation, depressive mood, and positive mood”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:81`: “during periods of positive mood (low/minimal risk)”

## 04-03 — construct_label_changed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed 'self-focus' to 'rumination' — different constructs (Baumeister escape theory vs Nolen-Hoeksema response styles); first-person pronouns index self-referential attention, not repetitive negative thinking

**Audit:** The single new rumination label is unsupported by the operationalization and conflicts with explicit self-focus labels in hypothesis, discussion and table. Counts of first-person pronouns do not by themselves demonstrate the repetitive thought process meant by rumination. The defensible criticism is construct overinterpretation/terminological inconsistency, without requiring any claim that the two constructs cannot correlate.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:29`: “as an indicator of rumination”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:34`: “increased self-focus (i.e., greater singular first-person pronoun usage)”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:85`: “Self-focus. Operationalized by singular first-person pronoun use”

## 04-04 — temporal_logic_altered

**Verdict:** `weak_or_invalid`; confidence: high.

**Annotation claim:** Changed 'no expectation of temporal change' to 'also an expectation' — undermines the slope comparison logic; comparison conditions should be flat baselines

**Audit:** A slope-difference test does not require flat comparison trajectories. Its question is whether trajectories differ, which remains meaningful if multiple episode types change. The edit changes theoretical expectations but does not undermine the mathematics or comparison logic. Requesting a citation for the added expectation would be reasonable, but “comparison conditions should be flat baselines” is not a defensible benchmark requirement.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:62`: “whether communication changed differently during the 14 days leading up to a suicide attempt compared to changes during other two-week periods”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:62`: “there is also a theoretical expectation of temporal change”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:35`: “we did not have hypotheses on whether language differences would be observed for episodes overall (means) but not changes over time (slopes), or vice versa”

## 04-05 — iatrogenic_means_reversed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed post desire-to-die from 0.61 to 1.03 — means now show INCREASE while text says 'decreased'; safety-critical inconsistency in iatrogenic check

**Audit:** The displayed mean rises from .82 to 1.03 while the sentence says it decreased. This directly invalidates the direction statement. The paired t statistic cannot be reconstructed from marginal SDs without within-person covariance, and these summaries do not establish clinical harm or an individual risk event; the demonstrated error is the arithmetic/directional inconsistency.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:70`: “desire to die from pre (M=0.82, SD=1.10) to post (M=1.03, SD=0.90) significantly decreased slightly”

## 04-06 — episode_window_inconsistent

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Changed 'two-week' to 'one-week' in episode definition but all other references say 'two weeks' / '14 days' — cross-section inconsistency

**Audit:** The one-week attempt-episode definition contradicts the same paragraph’s statement that every episode is two weeks and the analysis’s -14-to-0 time range. This is a concrete window-definition inconsistency with consequences for included messages and slopes.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:47`: “using the one-week period prior to the attempt”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:47`: “The decision to set each episode at two weeks long”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:62`: “day of episode (numerical factor ranging from -14 to 0)”

## 04-07 — recruitment_source_hidden

**Verdict:** `weak_or_invalid`; confidence: high.

**Annotation claim:** Removed university participant pool source — hides that sample is mostly college students (94% 'some college', mean age 20.4), making findings appear more generalizable

**Audit:** The participant-pool route was removed only from one summary sentence. The next subsection still explicitly describes semester participant-pool pretests and recruitment; results say college-aged and Table 1 reports age and education. Community and university sources can overlap, so this is at most a less complete recruitment summary, not successful concealment of the student composition or a demonstrable generalizability distortion.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:39`: “recruited from the Charlottesville community”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:42`: “Participant pool participants were selected based on two surveys”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:67`: “Most of the participants were female, White, and college-aged.”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:201`: “Some college
94.0”

## 04-08 — theory_mechanism_changed

**Verdict:** `weak_or_invalid`; confidence: medium.

**Annotation claim:** Changed 'social support' (perceived caring) to 'social engagement' (behavioral frequency) — collapses theory-operationalization gap that's a real limitation; message volume is weak proxy for perceived support

**Audit:** Social engagement is already the named construct throughout the original and modified paper, and proposing engagement might increase connectedness is not itself a theoretical error. The new paragraph immediately says perceived-support research supports the hypothesis only indirectly. Discussion retains social support and acknowledges the message-count operationalization was too basic. The original proxy limitation survives; the word replacement does not establish a newly invalid theory or concealed limitation.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:31`: “Previous research examining between-subjects differences in perceived social support indirectly supports this hypothesis.”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:90`: “In theory, social support should combat such feelings”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:91`: “these particular methods for capturing social engagement were too basic to detect any meaningful signal”

## 04-09 — random_effects_simplified

**Verdict:** `valid_demonstrable_error`; confidence: medium.

**Annotation claim:** Removed all random slopes (kept only intercepts) — fails to account for participant variability in episode effects; inflates Type I error per Barr et al (2013); key p-values near .05 may become false positives

**Audit:** The final slope-analysis model is explicitly intercept-only, but the Discussion still invokes maximal/near-maximal random effects to reassure readers about Type I error. That assurance no longer follows from the reported final model and is a demonstrable reporting/inference defect. Dropping slopes can be problematic depending on variance and design, but nonconvergence can justify simplification; claiming actual Type I inflation or false positives here requires data/code sensitivity analyses.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:62`: “no random slopes were included in the final model.”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:103`: “using the maximal (or near-maximal) random effects in our models likely decreased the chances of Type I error”

## 04-10 — missing_data_pattern_concealed

**Verdict:** `valid_demonstrable_error`; confidence: high.

**Annotation claim:** Concealed that only 15/27 (56%) had attempt SMS data — hides selection bias in who contributes to the critical attempt vs non-attempt comparisons

**Audit:** All 27 participants cannot each have at least one attempt episode with SMS data when the next paragraph reports only 21 such attempts. The original confirms the correct split was 15 versus 12. This both misstates critical coverage and creates an internal counting contradiction. Nonrandom selection bias is a possible consequence to investigate, not demonstrated merely by missingness.

**Evidence:**

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:68`: “Among these 27 participants, all had data from at least one reported suicide attempt.”

- `runs/benchmark-validity-audit/inputs/paper-04.modified.txt:69`: “Among the 21 attempts with corresponding SMS data”

- `runs/benchmark-validity-audit/inputs/paper-04.original.txt:67`: “15 had data from at least one reported suicide attempt; the other 12 participants contributed data from non-suicide attempt episodes”
