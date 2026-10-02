# Pilot diagnosis and development priorities

## What the comparison establishes

The Sol pipeline matches the plain Sol review on the eight demonstrable targets:
both publish six, and they are the same six. The overall 7/20 versus 12/20 gap
comes from reporting gaps and a weak causal-language annotation. The pipeline
does not earn its discovery overhead on these two papers. It does supply useful
audit records and at least one consequential numerical correction beyond the
planted-error list.

This is a descriptive comparison of one run per paper, not a controlled estimate
of configuration effects. The pipeline runs on Linux and the plain baseline on
macOS, with different CLI versions. Both use `gpt-6.1-sol`, high effort and tools.
The validity classifications come from the separate benchmark-validity audit;
they identify the strongest defensible criticism, rather than endorsing every
claim in an annotation. The audit and headline scoring rules remain unchanged.

| Target classification | Targets | Pipeline published | Plain published |
|---|---:|---:|---:|
| Demonstrable error | 8 | 6 | 6 |
| Material reporting gap | 6 | 0 | 4 |
| Weak or invalid annotation | 6 | 1 | 2 |
| All annotations | 20 | 7 | 12 |

Strict scores exclude uncertain matches. Luna's sole clean pilot paper, paper 9,
scores 3/10 against its plain baseline's 3/10; its demonstrable score is 3/6
against 2/6. Its paper-5 review searches for the manuscript title and is flagged.
That review cannot supply clean comparative evidence.

## Where the losses occur

The pilot's verification batches complete without failures. No planted error is
held by the external-source gate or lost to editorial selection. Among Sol's 20
targets, ten have no candidate match, eight have a strict candidate match and two
have an uncertain match. Seven strict matches publish; 9-02 stays unresolved.
The uncertain 9-04 match publishes; 5-09 stays unresolved. These are different
failure modes and need different interventions.

The five targets found strictly by the plain baseline but not published as strict
pipeline matches are:

| Target | Pipeline evidence | Diagnosis |
|---|---|---|
| 5-01: pooling transformation | No matched candidate; reviewers use Fisher-z assumptions in their own reconstruction | Discovery checks the calculation under an assumed recipe but does not flag that the manuscript leaves the recipe unspecified. This is a reproducibility gap, not proof of incorrect pooling. |
| 5-07: Facebook-use eligibility | Broader exclusion and population concerns, without the specific eligibility criticism | Missing eligibility detail is absorbed into acknowledged exclusion uncertainty. The plain review asks whether ownership/current use is required or measured. Neither review can establish that nonusers are included or that bias occurs. |
| 5-09: estimator choice | An uncertain candidate match; verifier-unresolved; visible in the report's unconfirmed-concerns section | The criticism concerns undocumented comparison and an undefined selection criterion. Verification treats inaccessible linked analysis material as preventing confirmation; the analytical-flexibility check also seeks a conclusion-changing choice. This is narrower than proving an invalid estimator or p-hacking. |
| 9-04: causal language | Supported, published causal-overreach finding; uncertain judge match | The finding addresses surviving causal claims, rather than specifically the edited limitation sentence. This contributes no strict score despite providing an author-visible criticism. The annotation itself is classified weak or invalid. |
| 9-07: representativeness | Published sports-oversampling concern, without the specific age/gender-only calibration criticism | Discovery identifies the enriched combined sample but misses the separate unsupported nationally representative claim. The bounded criticism is to document calibration or qualify representativeness, not to assert actual bias. |

Two demonstrable targets are missed by both published outputs:

* **5-05, geographical coverage:** the supplied text describes eastern/western
  coverage, while Table 1 names Chicago, Illinois, and East Lansing, Michigan.
  Both passages survive ingestion. The pipeline assesses cross-section agreement
  and finds numerous arithmetic discrepancies, but misses this categorical one.
  This is an attention or checking failure, not a missing-input explanation.
  The annotation's additional rural classification is not demonstrated by the table.
* **9-02, scoring order:** the pipeline explicitly finds that averaging raw ASSIST
  responses and standardizing items before averaging are different recipes. The
  verifier requests the actual formula or syntax and classifies the finding
  unresolved. Its claim already says the specification is unclear, rather than
  that a particular incorrect recipe was implemented. Both specifications are in
  the ingested manuscript. An ambiguity claim can be established without knowing
  which implementation is correct: verification is asking a different question
  from the bounded criticism. The author sees this concern in the rendered report,
  but the published-findings score excludes it. The plain review has no matched
  criticism of this specific discrepancy.

The reporting omissions in 5-06 and 9-06 are also missed. Neither a deleted
adaptation sentence nor a deleted DWLS fallback can be recognized as a deletion
without the original manuscript. A review can still ask for the specified
effect-difference formula or prespecified robustness alternatives and decision
criteria. It cannot legitimately demand the exact deleted method as the only
acceptable choice.

Some misses are desirable. Centering a sole linear predictor does not change its
slope or correlation (5-03); exchanging two predictors' roles in a product does
not create a statistical interaction error (9-08). The historical-platform
qualification and missing-data acknowledgment survive elsewhere in the supplied
paper (5-04 and 5-10). Optimizing recall against these annotations would reward
incorrect or redundant criticism.

## Why the architecture may produce this pattern

The profile explicitly filters measurement concerns for material consequences,
filters acknowledged limitations for overreaching conclusions, and asks the
analytical-flexibility check for undisclosed or conclusion-changing choices.
These are sensible constraints against generic criticism. Applied broadly, they
can also suppress useful requests to specify an analysis recipe or population.
The observed 0/6 reporting-gap score is consistent with that pattern.

The measurement prompt gives a concrete instruction for `construct_validity`,
but scoring is chiefly an introductory topic. The consistency prompt says to
compare every repeated number and statement; its coverage assessment does not
show an enumerated ledger of categorical facts or analysis operations. An
`assessed` check is therefore not evidence that each relevant pair was compared.
The numerical work is extensive while a simple site-description mismatch is
missed.

Several modules reproduce the same criticism. In these Sol runs, all four
social-psychology-context candidates merge into findings from other modules.
The design module contributes one published finding across the two papers,
which the plain review also raises. The blind-spots module supplies useful
criticism, but three of its four published paper-9 findings also appear in the
plain review, including its equivalence-test counterexample. Module labels alone
do not establish extra discovery value.

These observations support hypotheses about attention, scope filters and
duplicated work. They do not identify a causal effect of prompt wording or module
partitioning. The plain prompt's category-list ablation also retains 12/20 for
Sol, so adding a category checklist is not an evidenced solution.

## Value beyond planted-error recall

A manual semantic comparison finds a related plain-review criticism for **43 of
the 50 published pipeline findings**. Seven lack a clear counterpart in this
reading. This is an unblinded desk comparison, not an independent assessment of
precision or novelty; related findings can differ substantially in depth. The
complete mapping and scope notes are in
[overlap.json](benchmark-pilot-analysis/overlap.json).

The strongest extra depth is paper 5's safety prediction interval. Plain issue 8
identifies the substitution of the pooled confidence interval for a prediction
interval in the Discussion. Pipeline finding `interpretation:2:CE3` also identifies
a likely negative upper-bound sign in Results. An independent reconstruction
from Table 1 gives:

| Quantity | Reconstruction |
|---|---:|
| Pooled correlation | −0.27654 |
| Between-study variance on Fisher-z scale | 0.02156 |
| Pooled 95% confidence interval | [−0.39277, −0.15161] |
| 95% prediction interval | **[−0.53719, +0.03232]** |
| Manuscript's Results prediction interval | [−0.54, −0.03] |

The reconstruction uses the seven rounded correlations and Ns, Fisher-z effects,
variances `1/(N−3)`, intercept-only REML and normal critical values. A separate
NumPy/SciPy optimization agrees with the standard-library implementation in the
analysis script. The normal-interval convention follows
[metafor's prediction documentation](https://wviechtb.github.io/metafor/reference/predict.rma.html).
These assumptions approximately reproduce the pooled estimate and confidence
interval. Exact corrected bounds require the original output. The change in sign
matters because the prediction interval admits a positive true association even
when the pooled confidence interval remains negative. This is a useful additional
correction, not merely more findings.

The pipeline also provides an explicit PGSI ranking-reversal example: three
highest-category endorsements versus four next-highest endorsements score 9
versus 8 under conventional coding, but 15 versus 16 under the supplemental
coding. The plain review identifies the same nonlinear recoding problem without
that example. This illustrates auditable consequences rather than unique discovery.

Findings without a clear plain counterpart include the incomplete expression
effect range, the account-versus-person denominator in the introductory Facebook
percentage, a categorical diagnostic claim, and a German-study citation-outcome
mismatch. The latter is supported by the
[study's abstract](https://pubmed.ncbi.nlm.nih.gov/33945359/), which describes
perceived impact on sex life, not the addiction outcome attributed collectively
to the cited studies. The available abstract does not establish that the full
article contains no additional relevant outcomes. The remaining three unmatched
findings are small sample-total, effect-size and rounding inconsistencies.
There is some useful breadth, but seven unmatched findings are not seven proven
high-value additions.

The structured pipeline supplies deterministic quote anchors, per-stage tool
records, explicit support/unresolved distinctions, remedy assessments and merge
provenance. Those are real product features. The runs do **not** demonstrate
effective false-positive filtering: the same-family verifier supports **111/115**
candidates, leaves four unresolved and contradicts none. Eleven supported
findings remain unresolved under the required-external-evidence gate, leaving
100 with final `llm_supported` status. Editorial publishes 50 and merges 50; 15
are `needs_review`, consisting of those eleven and the four verifier-unresolved
findings. Every published remedy is supported, so these outputs do not show a
remedy being withheld while its finding publishes.

The pipeline publishes eight major and 42 minor findings; the plain review labels
41 of its 77 issues major. This establishes different severity treatment, not
better calibration. A blinded consequence assessment is needed before treating
either distribution as a benefit. Metacheck screening is partial and its net
contribution is not isolated by this comparison.

## Work required for that value

| Descriptive measure, Sol papers 5 and 9 | Pipeline | Plain |
|---|---:|---:|
| Model calls | 42 | 2 |
| Accumulated model-stage duration | 267.9 minutes | 23.7 minutes |
| Recorded tool calls | 703 | 59 |
| Original candidates/issues | 115 | 77 |
| Published findings/issues | 50 | 77 |

Each pipeline paper has one study-map call, eight discovery calls, eleven
verification calls and one editorial call. The 21-fold call count and 11.3-fold
stage-duration ratio are descriptive, not a monetary-cost estimate or elapsed
campaign time. Metacheck duration is not included, and machine/CLI differences
limit interpretation. Duplicate candidates also undergo verification before
editorial merging, with repeated source fetches. No finding count limit is needed
to address this overhead.

## Development sequence

1. **Test holistic discovery with the pipeline's verification and reporting
   layer.** Convert the saved 34 and 43 plain Sol issues into anchored candidates,
   preserving their wording and provenance, then pass every candidate through
   the existing tool-enabled batches and editorial stage. Keep the same Sol/high
   settings and publication rules. This fixed-candidate experiment tests which
   baseline criticisms verification retains or loses without paying for another
   discovery run. It tests the downstream path, not the end-to-end quality or
   latency of a complete hybrid configuration.
2. **Make verification answer the stated claim.** For 9-02, distinguish a
   demonstrated inconsistency in two scoring specifications from an assertion
   that the implemented scoring is wrong. For 5-09, distinguish missing comparison
   information in the supplied manuscript from claims about inaccessible syntax
   or invalid estimator selection. Correct scope and prompt interpretation while
   preserving the owner-approved evidential and publication requirements. Do not
   promote scientific-error claims merely because clarification would be useful.
3. **Add a small number of operational checks where evidence is missing.**
   Candidate examples are analysis-recipe reconstruction (transformations,
   variance formulas, averaging order and back-transformation), categorical
   text/table comparisons (sites, eligibility, counts and units), and population
   calibration claims. A check should record the compared passages or operations
   and unresolved steps. Named actions address the observed failures more
   directly than a general category list. Checks must be manuscript-general;
   planted-error descriptions and answer keys stay outside reviewers' inputs.
4. **Measure precision and usefulness before preserving specialist overhead.**
   Form criticism clusters from shared, plain-only and pipeline-only outputs.
   Blind configuration labels and evaluate factual support, consequence,
   actionability and redundancy. Source verification remains tool-enabled;
   ranking/adjudication remains tool-free. Track substantive corrections per
   review and accumulated stage time. The verifier's support rate cannot stand
   in for this assessment. Report author-visible unresolved concerns as a separate
   diagnostic, without altering the established headline score.
5. **Use version-matched expert reports for development comparisons.** The
   [curated comparison set](OPEN_REVIEW_COMPARISONS.md) supplies six submitted
   manuscripts and twelve substantive first-round reports. Assess usefulness and
   correctness against the submitted source rather than rewarding agreement with
   a human reviewer. Title-search prevention is not a priority for this exploratory
   benchmark; preserve audit flags and keep flagged runs separate from clean ones.

The preferred architectural hypothesis is **holistic tool-enabled discovery,
targeted numerical/recipe checks, then batched verification and editorial**.
The specialist fan-out should earn its place through useful additional findings
on unseen manuscripts. The four pilot runs and the
[four discovery/finalization experiments](DISCOVERY_EXPERIMENT_RESULTS.md) are
complete. The exploratory results do not close the plain-review gap. The single-call
path publishes the scoring-order discrepancy and uses substantially fewer calls,
but its paper-5 reporting-gap discovery is poor. A small comparison on unseen
manuscripts should precede any replicated ten-paper campaign.

## Evidence and reproduction

* [Completed scores and trace summary](KNOWN_ERROR_RESULTS.md)
* [Benchmark-validity audit](benchmark-validity-audit/audit-100.md)
* [Derived counts and numerical reconstruction](benchmark-pilot-analysis/analysis.json)
* [Complete manual overlap mapping](benchmark-pilot-analysis/overlap.json)
* [Analysis script](benchmark-pilot-analysis/analyze.py)

The script reads the local saved reviews under `runs/known-errors-0.4.1` and
`runs/known-errors-all`. Run from the repository:

```sh
.venv/bin/python docs/benchmark-pilot-analysis/analyze.py
```

It validates complete mapping coverage and valid plain-issue indices, computes
the descriptive counts, and reconstructs the safety interval without new model
calls or external lookups. The public artifacts contain derived measures and
finding identifiers; the full review/tool records remain in the run directories.
