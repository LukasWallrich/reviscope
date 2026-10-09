## Verdict: the core provenance is sound; two reporting-code must-fixes remain

I used only Read/Glob/Grep. I made no writes, ran no commands or tests, and made no model calls. I'm not approving any results, because none of the final outcomes exist yet.

**Confirmed against the code:**
- **Native rows must be rewrapped.** The final status requires every native row to have been rewrapped under `7eaf`. For those rows, the derived fields must equal `checked_labels` recomputed from the raw output, and the quote flags and `present_in_audit` must be present (`provenance_audit.py:51-54, 122`).
- **v1 rederivation is fully re-checked:** the original v1 file's hash, the matcher and method, all model metadata and groups, and every raw and derived row (`:101-115`).
- **The comparison set is derived, not hard-coded.** It comes from `launch.json` and each case's human reviewers, and completion requires an exact match (`:91-99, 122`).
- **The 18 report identity rows** each re-run the recorded-source audit gate (`:116-121`).
- **Source-only controls** are bound to their packet, raw call and the archived `09dd60` derivation, and labelled as a separate trial.
- **The three reporting scripts** are hashed at the start and re-checked at the end of the audit. The summary checks them against both the audit and `offline-finalize.json` (`summarize.py:20-21`).
- **The final render** refuses a missing judge and refuses to mix v1 into v2 cases (`summarize.py:56, 67`).
- **Other fixes are in place:** comparison history is listed with a note that an archive isn't necessarily a new call; the numerical-checks artifact appears under its real filename; the draft text states its limits.
- **The methods doc's impact statement** now matches its artifact: candidate evidence only, 3 occurrences across arms, 2 unique quotes, including the merged one.

## Must-fix

**1. Native retries are undercounted, and the accepted attempt isn't identified.**
- `summarize.py:163-166` only finds the *current* `<case>.invalid.json` files.
- `assess()` archives each earlier invalid attempt to `<model>/history/<case>.invalid-<sha>.json` before overwriting it. Sol Mackinnon's first failed attempt, for example, sits only in history, so the error list understates the attempts.
- Fix: include `criticism-assessments-v2/*/history/*.invalid-*.json`. Report, per case and model:
  - the number of invalid attempts, in order;
  - whether the accepted raw call came from the frozen campaign or from the logged additional recovery;
  - the accepted `raw_judge_sha256`, matched against the recovery record.
- The matching cache key already proves the prompt, schema, packet and backend identity were unchanged. What's missing is which attempt was accepted.
- The report must also say that the accepted labels are a later sample, accepted only once the grouping passed validation. Earlier attempts contain complete, valid assessment sets that the analysis doesn't use.

**2. "Finished" can be shown over artifacts the audit never saw.**
- `final_ready` (`summarize.py:21`) compares script hashes. It doesn't compare the artifacts the summary actually reads against those the audit verified.
- The frozen v2 campaign and the recovery attempts are still writing. Any later write, followed by a standalone `summarize.py` run, would render "Finished: verified" over artifacts the audit never checked.
- Fix: when `final_ready`, require each v2 file's `raw_judge_sha256` and `packet_sha256` to equal the audit's `native_assessments` entry. Require each `comparisons-v4` file's hash to equal its `artifact_sha256` in the audit. Fail if either doesn't match.

## Scientific follow-up (new)

The invalid Sol Mackinnon and Niemeyer attempts have every assessment ID valid. Comparing their claim labels with the accepted attempt would give a small, free check of whether one judge gives the same labels when asked again with identical inputs. If you don't run that comparison, say so in the report.

All other limitations and follow-ups stand as already documented.
