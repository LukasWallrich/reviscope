**Approval: no must-fix changes.** The fix keeps the thin-adapter contract and the cache and failure guarantees. I found no path where it produces a false clean result or hides a failure. I read the code only and ran nothing, so the four passing tests are as you reported them.

## Why it holds

- **It only intercepts a crash the package would hit anyway.** In the installed module, `label_lhs` (`stat_effect_size.R:460-468`) can only label a test when `lhs` is exactly `"t"` or `"F"`. If the paper has equations but none has that `lhs`, `build_rows` returns `NULL` for every sentence. `bind_rows` then gives an empty table with no columns, and the `left_join` at line 530 fails. So the guard never skips a case the package could have checked. Extraction and arithmetic stay in the package; the guard copies just one condition from it.
- **Unknown cases fall through to the package.** A parser error, a non-data-frame result, zero rows, a missing `lhs`, a non-character `lhs` or an `NA` all return `NULL`. The package then runs and fails in the usual way. If `metacheck::extract_eq` were missing from an older package, the error happens inside the `tryCatch`, so that is portable too.
- **A skip can't be read as clean:**
  - `result_json` sets the light and summary to NA for any status other than `ok`.
  - Any stale `.rds` is removed (`mc_run.R:167`) and the result is never reused.
  - `skipped_missing_input` was already part of the contract (`CONTRACT.md:48`) and the run counts.
  - Downstream, Python shows it as "could not check" (`metacheck.py:371,443`), and `light_mapping.json` rule `module_not_ok` maps it to `fail`.
  - The message says coherence was not checked and that extraction can miss tests.
- **Source, verification, remedy and severity rules don't change.** No rows means no candidates and no findings. The unchanged rubric excerpt is attached as for any module that was not checked.
- **Cache keys cover the change.** `reuse_key` hashes `scripts/*.R`, which includes the new `_module_inputs.R` and the edited `mc_run.R`. Old screenings are invalidated rather than silently reused, and the stage fingerprints change as they should.

## Optional improvements (none blocking)

1. **The same crash can still happen.** An `F` that the package won't label, such as `F = 4.2` or a Welch `F(1, 37.4)`, passes the guard, and the module still crashes and is recorded as `failed`. That is honest, not falsely clean, but the frozen failure mode isn't fully gone. A regression test pinning this as `failed` would document it. Don't copy the df regex into the adapter; that would duplicate more package logic.
2. **The guard won't notice an upstream fix.** It runs before the package whatever the version. If metacheck later handles this case (probably returning `ok`/`na`), the adapter would keep overriding it. A better design: run the package first, and record `skipped_missing_input` only when it errors and the condition holds, keeping the package's error in the message. That catches only real failures and adapts to upstream fixes on its own. Otherwise, gate the guard on the package version or commit.
3. **`CONTRACT.md` is unchanged**, but it says "never reimplement package logic". Add a line saying the adapter has this one precondition, which status it produces, and which package version it targets.
4. **The two no-test cases are labelled differently.** A paper with no equations still goes to the package and gets `ok`/`na` ("No t-tests or F-tests were detected"). A paper with equations but no t/F gets `skipped_missing_input`. Neither can become green, but it's worth a sentence in the contract so readers don't think they differ in kind.
5. **Small placement tweak.** `mc_missing_module_input` runs before the reuse check (`mc_run.R:110`), so `extract_eq` runs even when a cached `ok` result is reused. It also runs outside the `sink` and warning handler, so extraction warnings aren't recorded. Stray stdout is harmless because `_json_object` tolerates output before the JSON. Moving the call into the non-reuse branch fixes both.
6. **Test gaps:**
   - `mc_run.R` calls `online()`, which may probe the network (I haven't checked), so the "offline" label may not be strictly true.
   - The 30 s timeout covers loading the package and may be tight on slow machines.
   - The tests read only `modules/stat_effect_size.json`. They could also check `run_status.json` counts (`skipped_missing_input: 1`) and that no `.rds` is left behind.

## Caution about the frozen results

Because the scripts hash changed, running `run_metacheck` again into an existing output directory will delete and rebuild its metacheck folder (`metacheck.py:259-261`). It will also miss the review-stage caches, which means new model calls. To keep the frozen six-case results untouched, run the new code into new output directories.

As you asked, I haven't treated any statistical claims from the assessment report as established. The tests only show that the installed module agrees on the `t(48) = 2.00` cases (green/match for d = .57, red/no match for d = 3.00).
