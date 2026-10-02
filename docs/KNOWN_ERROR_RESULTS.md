# Planted-error benchmark: papers 5 and 9

## Engine 0.4.1 pilot (2 October 2026)

All four reviews are complete and adjudicated. The tool audit is clean for both Sol
papers and Luna's paper 9. Luna's paper 5 is flagged for a manuscript-title search
by `statistical_inference`, and is excluded from headline recall. No model stage or
verification batch failed. Metacheck screening is partial in each review:
`stat_effect_size` fails in both papers; paper 9 also has failed reference accuracy
and partial reference summary.

Strict recall, with `uncertain` excluded:

| Configuration | Paper | Candidate | Published | Demonstrable published | Findings (candidate / published) | Tool audit |
|---|---|---|---|---|---|---|
| pipeline `gpt-6-luna` | 5 | 2/10 | 2/10 | 1/2 | 20 / 9 | flagged |
| pipeline `gpt-6-luna` | 9 | 3/10 | 3/10 | 3/6 | 25 / 13 | clean |
| pipeline `gpt-6.1-sol` | 5 | 2/10 (+1 uncertain) | 2/10 | 1/2 | 52 / 18 | clean |
| pipeline `gpt-6.1-sol` | 9 | 6/10 (+1 uncertain) | 5/10 (+1 uncertain) | 5/6 | 63 / 32 | clean |

On the same clean papers, Sol publishes **7/20**, against **12/20** for its plain
baseline and **4/20** for the 0.4.0 pipeline. On the eight demonstrable targets,
Sol publishes **6/8**, matching the plain baseline's **6/8** and the same six error
IDs: 5-02, 9-01, 9-03, 9-05, 9-09 and 9-10. Both miss 5-05 and 9-02. Luna publishes
**3/10** on its sole clean paper (paper 9), matching its plain baseline's **3/10**;
demonstrable recall is **3/6** for the pipeline and **2/6** for the plain baseline.
The 0.4.0 Luna pipeline publishes 5/10 on that paper. One run per paper and
configuration cannot attribute these differences to the implementation changes.

### Verification and editorial losses

There are 36 verification batches: Luna 6 and 8, Sol 11 and 11 for papers 5 and 9.
All complete successfully. Verifier-supported findings held by unconfirmed required
external evidence are Sol 7 and 4, compared with 13 and 23 in the 0.4.0 series, and
Luna 0 and 2, compared with 5 and 6. Unchecked optional external items are removed
from 4 and 8 Sol findings and 0 and 2 Luna findings. These are diagnostic finding
counts; they include Luna's flagged paper and are not benchmark headline scores.

No planted error in the 0.4.1 trace is lost to the external-source gate or to
editorial selection. Sol publishes 5-02, 5-08 and 9-09. Its one strictly detected
candidate that is not published is **9-02**: verification treats the order of
standardization and averaging as unresolved information, rather than a demonstrated
scoring error. The verifier requests a scoring formula or processing syntax to
resolve it. **5-09** has an uncertain candidate match and stays unresolved.

For **9-04**, Sol publishes a supported minor finding about causal language and
merges a supported design duplicate into it. The judge marks both its candidate and
published match `uncertain`, so it contributes no strict recall. The invalid merge
into an unresolved target documented in the 0.4.0 audit does not occur in this run.

Luna's misses are all discovery misses, including 9-01 and 9-09. Sol has ten targets
with no candidate match. Thus, discovery is the principal remaining loss in this
pilot; the remaining overall gap to the Sol plain baseline consists of weak or
reporting-gap annotations, while demonstrable-target recall matches it.

### Artifacts and scope

The frozen pipeline snapshot is `8e5fc939dcfbbcf7`, engine 0.4.1a1, with Codex CLI
0.160.0. Scores, the full loss trace and the baseline comparison are in
`runs/known-errors-0.4.1/known-error-scores.json`, `known-error-trace.json`,
`known-error-trace.md` and `pilot-summary.md`. Both driver services and the analysis
service complete successfully. The Codex update timer is active after analysis.
The pilot has two papers and one run per configuration; the plain baselines use
macOS and the pipeline uses Linux. A full campaign is not scheduled.

## Engine 0.4.0 benchmark (1 October 2026)

Two papers with ten planted errors each. The results are indicative only. One run per
configuration and paper, model-judged recall, and 20 targets (8 of them
`valid_demonstrable_error` in the benchmark-validity audit: 5-02, 5-05, 9-01, 9-02,
9-03, 9-05, 9-09, 9-10) cannot separate configurations reliably. A difference of one or
two errors is within run-to-run variation.

Setup: engine 0.4.0a1 (`consistency` module, `power_and_sensitivity` and
`analytic_flexibility` checks, no deterministic statistical-checks stage), profile
`social_psychology`, effort `high`, every review with web search, fetching and a sandboxed
shell. Judge `claude-opus-5-5`, effort `high`, no tools. Pipeline and `plain-nolist` runs
used code snapshot `7b53d4a9f59a3b39` and `6741730212d46dd2` on Linux (1 October 2026). The
`plain` runs are the existing macOS runs of the same prompt (30 September and 1 October
2026). Metacheck ran under R 4.5.1 with metacheck 0.1.0 at commit `35033be`. Its
`ref_accuracy` module could not run because the CrossRef labs API returned HTTP 502/503,
and `stat_effect_size` failed inside the package, so screening was partial in all four
pipeline reviews.

## Planted errors found

Detected / 10 planted errors, strict (`uncertain` not counted; uncertain in brackets when
present). For the one-call baselines, candidates and published findings are the same list.
"Findings" gives candidate / published counts.

| Configuration | Paper | Candidate | Published | Demonstrable published | Findings | Tool audit |
|---|---|---|---|---|---|---|
| pipeline `gpt-6-luna` | 5 | 2 | 2 | 1/2 | 22 / 7 | flagged |
| pipeline `gpt-6-luna` | 9 | 5 | 5 | 4/6 | 26 / 12 | clean |
| pipeline `gpt-6.1-sol` | 5 | 2 (+1) | 0 | 0/2 | 53 / 16 | clean |
| pipeline `gpt-6.1-sol` | 9 | 6 (+1) | 4 | 4/6 | 58 / 15 | clean |
| plain `gpt-6-luna` | 5 | 4 (+1) | 4 | 1/2 | 15 | clean |
| plain `gpt-6-luna` | 9 | 3 (+2) | 3 | 2/6 | 21 | clean |
| plain `gpt-6.1-sol` | 5 | 5 (+2) | 5 | 1/2 | 34 | clean |
| plain `gpt-6.1-sol` | 9 | 7 (+1) | 7 | 5/6 | 43 | clean |
| plain-nolist `gpt-6-luna` | 5 | 1 | 1 | 1/2 | 14 | clean |
| plain-nolist `gpt-6-luna` | 9 | 5 (+2) | 5 | 4/6 | 17 | clean |
| plain-nolist `gpt-6.1-sol` | 5 | 5 (+1) | 5 | 1/2 | 34 | clean |
| plain-nolist `gpt-6.1-sol` | 9 | 7 (+1) | 7 | 5/6 | 44 | clean |
| external: benchmark GPT-5.5 reviews (no tools) | 5 | 7 | 7 | | | external |
| external: benchmark GPT-5.5 reviews (no tools) | 9 | 9 | 9 | | | external |
| external: reviews of the unmodified papers | 5 | 2 (+2) | 2 | | | external |
| external: reviews of the unmodified papers | 9 | 0 | 0 | | | external |

Clean papers only, published: pipeline Luna 5/10 (paper 9 only), pipeline Sol 4/20,
plain Luna 7/20, plain Sol 12/20, plain-nolist Luna 6/20, plain-nolist Sol 12/20. The
pipeline Luna review of paper 5 is flagged: `review-statistical_inference` searched for the
manuscript's own title, and the results of an earlier search listed the published
article's DOI (not opened). It is reported separately and not pooled.

The category list in the benchmark prompt made no difference for Sol (12/20 with and
without it, with the same errors found on paper 5) and one error for Luna (7 against 6).
Without the list, Sol found 9-06 (deleted DWLS sensitivity analysis), which no other
tool-enabled configuration found.

## Where the pipeline lost each missed error

From `eval/trace_known_errors.py` (rows in `runs/known-errors-all/known-error-trace.json`).
"Never raised" means no candidate matched in the judge's candidate-level assessment.

| Error | Category | Validity audit | Luna (paper 5 flagged) | Sol |
|---|---|---|---|---|
| 5-01 | statistical errors | reporting gap | never raised | never raised |
| 5-02 | methodological design | demonstrable | published | unresolved by verification |
| 5-03 | construct validity | weak | never raised | never raised |
| 5-04 | causal inference | weak | never raised | never raised |
| 5-05 | internal consistency | demonstrable | never raised | never raised |
| 5-06 | reporting completeness | reporting gap | never raised | never raised |
| 5-07 | generalizability | reporting gap | never raised | never raised |
| 5-08 | theoretical/conceptual | weak | published | unresolved: cited external source not confirmed |
| 5-09 | analytic flexibility | reporting gap | never raised | uncertain match; unresolved by verification |
| 5-10 | attrition/missing data | weak | never raised | never raised |
| 9-01 | statistical errors | demonstrable | published | published |
| 9-02 | methodological design | demonstrable | never raised | never raised |
| 9-03 | construct validity | demonstrable | published | published |
| 9-04 | causal inference | weak | published | set aside by editorial (`needs_review`) |
| 9-05 | internal consistency | demonstrable | published | published |
| 9-06 | reporting completeness | reporting gap | never raised | never raised |
| 9-07 | generalizability | reporting gap | never raised | uncertain match; unresolved by verification |
| 9-08 | theoretical/conceptual | weak | never raised | never raised |
| 9-09 | analytic flexibility | demonstrable | never raised | unresolved: cited external source not confirmed |
| 9-10 | attrition/missing data | demonstrable | published | published |

Luna loses errors at discovery: every miss is never raised. Sol raises more (8 of 20 at
candidate level against Luna's 7) but publishes fewer. It loses 6 raised errors, two of
them uncertain matches, after discovery:

- **Verification left the claim unresolved (5-02, 5-09, 9-07).** For 5-02 the verifier
  confirmed with code that six of seven samples are below the stated minimum of 120. It
  judged the conflict unresolved because the minimum concerns recruited participants and
  Table 1 may report analysed participants. That reading is defensible for the edited text.
- **External-source rule (5-08, 9-09).** The verifier supported the claim, but the finding
  cited an external source that the verifier did not confirm with a recorded fetch or search,
  so the finding stayed `unresolved`. This is a large effect across the whole reviews, not
  only planted errors. Verifier-supported candidates left unresolved for this reason: Sol 13
  of 45 (paper 5) and 23 of 52 (paper 9); Luna 5 of 20 and 6 of 26. In Sol's paper 9
  verification (one call, 58 candidates, 10 fetches), 15 external items had a `confirmed`
  verdict without a recorded fetch or search of the URL, and 16 had no verdict at all.
- **Editorial (9-04).** A verified finding (status `llm_supported`) was marked `needs_review`.

## Consistency module and power check

The `consistency` module produced on-target findings in all four reviews. Of its targets:

- 9-05 (analysis count changed from 10 to 8): raised by `consistency` in both pipelines
  ("eight moderation analyses do not map to seven behaviors") and merged into a published
  finding from another module.
- 9-03 (construct definition changed): the published finding comes from `consistency` in
  both pipelines.
- 5-02, 9-10 and, for Sol, 9-01 and 9-09: also raised by `consistency`, alongside other
  modules.
- 5-05 (rural and Midwest removed, contradicting Table 1), 5-06 (adaptation of a d-based
  method hidden) and 9-06 (planned DWLS sensitivity analysis deleted): not raised by any
  pipeline. 9-06 and 5-06 leave no contradiction in the text; they require knowing what is
  missing.

The module also raised further inconsistencies that are not planted errors (for example
fail-safe numbers and prediction intervals that differ between Results and Discussion in
paper 5), most of them verified as supported.

The `power_and_sensitivity` check was recorded as assessed in all four reviews, with
recomputation in code: correlation-test sensitivity for the reported sample sizes in
paper 5, and the noncentral F calculation behind the planned N in paper 9. Its targets:

- 9-01 (SESOI changed from .11 to .27): raised by `statistical_inference` and published in
  both pipelines.
- 5-02 (minimum N of 120 against samples of 80 to 90): published by Luna; raised by Sol in
  four modules but unresolved by verification (see above).

The `analytic_flexibility` check raised 9-09 (centering removed) only in Sol, where the
external-source rule held it back. It raised 5-09 (model selection by interpretability)
in neither pipeline.

## Caveats

- Two papers, one run each, model-judged recall: indicative only.
- The validity audit classifies 12 of the 20 targets as `weak_or_invalid` (6) or
  `material_reporting_gap` (6); recall on the 8 demonstrable errors is the more informative column.
- The `plain` runs ran on macOS; all other runs ran on Linux. The plain baseline does not
  depend on the pipeline code.
- Metacheck reference accuracy was unavailable during these runs (CrossRef labs outage).

## Editorial merge audit

Sol's paper-9 candidate `interpretation:0:CI-1` has severity minor and final status
`llm_supported`. Its editorial model decision is `merge`, with target
`contribution:2:TA-03`. That target's final status is `unresolved`, even though the
editorial model gives it a `keep` decision. The deterministic merge guard requires
at least as much evidential support in the target as in the source, so it records
`needs_review` with reason `Invalid editorial merge target`. The loss of 9-04 is an
invalid merge, not an editorial judgment that the causal-language criticism is too
severe or unsupported.

The editorial protocol requires canonical targets with a publishable final status
(`llm_supported`, `supported`, `recomputed` or `verified_deterministic`). A supported
verifier verdict alone is insufficient. If a proposed target is unresolved, the
editor chooses a supported member as canonical or keeps the supported criticism
separately. The deterministic publication and merge gates enforce the same rules.

## Engine 0.4.1 pilot scope

The pilot consists of papers 5 and 9 for the Luna and Sol pipelines, under
`runs/known-errors-0.4.1`. It tests module-based verification batches, explicit
required-versus-optional external evidence, shared preregistration leads, and the
editorial merge instruction. The code snapshot is `8e5fc939dcfbbcf7`, with Codex CLI
0.160.0. Results require completed reviews, tool audits and adjudications; service
launches and stage completion counts do not establish recall.

A full repeated 10-paper campaign depends on evidence that the pipeline can plausibly
match the one-call baseline. Headline comparisons use clean papers and the same paper
set in both configurations. Demonstrable errors and all annotations are reported
separately, with the trace locating each loss. Four pilot reviews are the authorized
scope; the full campaign is not scheduled.

Discovery diagnostics use the existing named checks. `cross_section_agreement`
already requests text-versus-table comparisons, so the 5-05 miss calls for checking
extraction and the model's recorded comparisons. `scoring_and_denominators` and
`analytic_flexibility` own composite construction and consequential transformations;
the 9-02 and 9-09 misses call for inspecting whether those operations were traced.
A deleted analysis or methodological explanation can leave no internal contradiction.
For 5-06 and 9-06, a reporting gap must be demonstrable from the supplied manuscript,
allowed cited methodological sources or an available registration. The manuscript's
unmodified original remains an answer key and cannot supply that diagnosis.
