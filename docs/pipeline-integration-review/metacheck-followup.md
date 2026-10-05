**Approval: no must-fix changes.** The package now runs first, and it can no longer produce a false clean result. I read the four files you named and ran nothing.

## What I checked

- **The reclassification is narrow.** Two things must both be true before `stat_effect_size` becomes `skipped_missing_input`:
  - the package raised its "Join columns … must be present in the data" error (`mc_run.R:147`), and
  - `mc_missing_module_input` sees that the package's own `extract_eq` returned a non-empty, well-formed result with no `t`/`F` `lhs`.

  Those two together match the root cause in `stat_effect_size.R:518-530`: every `build_rows` call returns `NULL`, so the join runs on an empty table.
- **Everything else stays `failed`:**
  - a join error when `t`/`F` is present, such as the `F(1, 37.4)` case;
  - any other error;
  - other modules, because the helper returns `NULL` for them;
  - unknown or failed extraction.

  If a dplyr or locale change alters the error text, the case also falls back to `failed`.
- **The original error is kept.** It is appended after "Package error:" (line 158). With a status other than `ok`, the light and summary are NA, the table is empty, and any `.rds` is removed (line 176).
- **An upstream fix would pass straight through.** A successful package run never enters the handler, and the zero-equation `ok`/`na` path is not touched.
- **Accumulated state resets per module:**
  - `missing_input` is set to `NULL` before each module (line 136), so nothing carries over.
  - `<<-` in the handlers finds the global `missing_input`/`warns`, the same mechanism as the existing warning handler.
  - The new top-level names (`module_status`, `error`) don't collide with `status`, the `_common.R` helpers or metacheck exports (I checked `NAMESPACE`). The earlier shadowing bug doesn't return.
  - `status[[m]]` and the counts use `res$status`, and `skipped_missing_input` is already a counted level.
- **Output and warnings:** the second extraction runs while stdout is still redirected to stderr, so stdout stays pure JSON. The test checks this with `json.loads(result.stdout)`. Repeated extraction warnings are removed by `unique()` in `result_json`.
- **Cache behaviour is unchanged in effect:**
  - A skipped result leaves no `.rds`, so it is never reused and the package runs again next time.
  - Reuse still requires an `ok` result from the package.
  - At the Python level, the scripts hash covers both changed `.R` files.
- **Test coverage is adequate.** The tests run the installed module for:
  - the skip, including that the "Package error:" text is kept, no `.rds` remains, `run_status` counts it, and leads say "could not check";
  - green and red coherence cases;
  - the remaining `F(1, 37.4)` case staying `failed` with the join error.

  The unit test covers extraction results the guard doesn't recognise.

## Optional improvements

1. **Harden the error handler.** If `mc_missing_module_input` ever raised an error inside the handler, it would escape with stdout still redirected, and the run's JSON would go to stderr. I see no current path where that happens (extraction is wrapped in `tryCatch` and the rest is base checks). Wrapping the classification in `tryCatch(..., error = function(e2) NULL)` would keep the original `failed` result if it ever did.
2. **Name the dependency on dplyr's message text.** The match relies on dplyr's English message. A short note in `CONTRACT.md` next to the "metacheck 0.1.0" sentence would explain why a future version might show `failed` again. That is the safe direction, so this is documentation only.
3. **Possible extra test.** A real-package run on a paper with no equations, checking it stays `ok`/`na` without interception, would pin down the contract's last sentence.
4. **Test caveats from last round still apply.** `mc_run.R` calls `online()`, so these "offline" tests may still make a network probe. The 30 s timeout includes loading the package.

The caution from last time still applies: the changed scripts hash means a rerun into an existing output directory deletes and rebuilds its metacheck folder. Use new directories to keep the frozen six-case results untouched.
