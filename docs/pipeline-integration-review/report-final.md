## Verdict: final reporting is approved once two documentation statements are corrected

I used only Read/Glob/Grep. I made no writes, ran no commands and made no model calls. I didn't run the test suite; the 205 and 225 test results are as you reported them.

**Checked against the archived records:**
- **v4 preference table.** All 36 AI cells in `REVIEW_QUALITY_TRAINING_RESULTS.md:214-227` match `summary.json` order by order. That includes Opus Mackinnon audit-vs-broad as A/B, and the Sol audit-vs-broad ties for Sætrevik, Ziano and Heyman.
- **Twelve human comparisons.** All twelve are audit/audit in both orders, as the doc says.
- **The narrative** at lines 229-235 matches the table.
- **Held findings.** The counts of supported but unpublished findings (`needs_review` 3/3, 2/2, 0/0, 1/1, 4/6, 2/2; merged 1/11, 0/18, 0/16, 0/3, 0/10, 0/15) match `supported_not_published_dispositions`.
- **Provenance audit status** is `diagnostic_complete_with_primary_format_failure`, not `complete_verified`.
  - The only missing file is Sol/Niemeyer.
  - The partial is bound to its raw response and packet, lists `item-028`/`item-044` as ungrouped, and is excluded from primary counts.
  - Its labels are re-derived from raw with no invented groups (`retain_partial_niemeyer.py`, and the audit's partial checks).
- **Mackinnon's accepted third response** is linked to the recovery record, the recovery log hash, the raw-call hash and the full cache key. Both rejected responses are retained, one current and one archived.
- **Niemeyer's three responses** are all retained: two archived and one current, with distinct hashes.
- **Offline finalize** records 13 raw cache files unchanged (11 native plus 2 source-only control) and no model calls.
- **Render negative checks:** both final-render mutations are rejected, and the check records hashes of the summary script and of itself.
- **Wording** about the partial, the conditional acceptances and the human-comparison asymmetry is appropriately bounded. I found no claim of scientific superiority.

## Must-fix: two statements are false or stale

**1. The rederivation total is wrong** (`QUALITY_ASSESSMENT_METHOD_REPAIRS.md:40-42`).
- The doc says offline rederivation "restores 14 Bonetto Opus labels and one Sol label".
- The completed-corpus record (`quote-label-rederivation.json`) shows **29 restored labels across 6 judge outputs**:
  - Bonetto: Opus 14, Sol 1
  - Sætrevik: Sol 11
  - Mackinnon: Sol 1
  - Niemeyer: Opus 1, Sol 1
- That sentence is left over from the first impact check. Replace it with the final per-output counts, still described as restored model opinions.

**2. The repeat-label comparison is described as available, but it has already been computed** (`REVIEW_QUALITY_TRAINING_RESULTS.md:246-248`).
- The doc says the rejected responses "remain available for a free within-judge repeat-label comparison". `summary.json` (`native_judge_attempts`) already contains the results:
  - **Sætrevik/Sol:** 3 of 76 raw claim labels differ from the accepted response, in both directions.
  - **Mackinnon/Sol:** 6 of 55 and 5 of 55 differ. Every change goes from `supported` in the rejected response to `unresolved` in the accepted one.
- Report these figures with their limits: this is within-judge repeatability after a grouping failure, not correctness.
- Add the interpretation they support:
  - A single judge sample changes roughly 4–11% of its claim labels on identical input. Single-sample labels and Opus–Sol disagreements therefore include within-judge noise.
  - Accepting a response only once its grouping is complete can shift labels. In Mackinnon the accepted sample was uniformly more conservative.

## Not blocking

- **Unhashed ad hoc script.** `offline-finalize.json` lists `rewrap_niemeyer_opus.py` as a command but doesn't record its hash. Its output is fully re-verified by the audit (derived fields recomputed from raw under `7eaf`), so this doesn't affect validity. Recording the hash would close the record.
- **Broad vs plain is decided by judge family.** All six Opus cells prefer plain and all six Sol cells prefer broad. Saying so outright is clearer than "heterogeneous". It's also worth noting that Opus's pro-plain preference runs opposite to the self-preference risk the doc flags for Opus on pipeline text it verified.
- **Niemeyer repeats.** Niemeyer's three complete partial responses would allow two more free within-judge comparisons. Optional, and outside the primary protocol.

## Open scientific needs (as documented)

- expert adjudication of atomic correctness;
- norms for judging remedies;
- a separate assessment of the excluded unresolved and held strata;
- an equal-compute comparator for the audit;
- repeat generation;
- an independent corpus.
