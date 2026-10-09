## Verdict: matcher fix and v4 prompt approved; five must-fixes elsewhere

I made no edits and no model calls. I read the matcher and its tests, the new criticism script and its tests, the whole-report prompt, the comparison script and the three control result files.

**Approved:**
- **Numeric matcher** (`src/reviscope/verification.py:61-80`). A trailing `.` or `,` now extends a number only when a digit follows it. I traced the boundary cases: "p = .88." matches, and the earlier Bonetto quotes ("Studies 2 and 3.", "$1000.", the "η2p = .36" form) now match. Partial decimals, grouping, signs, exponents and superscripts are still rejected. The tests cover each of these. A few false negatives remain but err on the safe side ("2 and 3" inside "1,2 and 3", "2020" in "pre-2020", "50" without its "%"); add tests that pin that behaviour. The same function anchors evidence in generation, so any new generation run is a new condition. You've already said so.
- **Whole-report prompt** (`src/reviscope/evaluation.py:197-202`). It now covers visual abstention, genre, remedy proportionality and generic-requirement restraint. Moving to protocol v4 correctly invalidates the old cache.

## Must-fix

**1. v4 comparisons write into the same files as the frozen v3 runner.** `compare_development_reviews.py:70` still writes to `comparisons/<model>/<case>/…json`. The frozen `assess_campaign.py` is still processing four pending cases with the frozen comparison script. That script re-runs and overwrites any file whose key doesn't match, with no history. So:
- the v3 runner would silently destroy v4 results and spend calls redoing them;
- v4 would archive v3 results into history and replace them;
- the summary's `comparisons/*/*/*.json` glob would mix the two protocols across cases.

Fix: give v4 its own directory (e.g. `comparisons-v4/`), and have the summary filter on the `protocol` field.

**2. The new script can silently pick up the frozen, buggy matcher.** `assess_criticisms.py` imports `reviscope` from whatever is on the path. The campaign environment sets `PYTHONPATH` to the frozen code (`assess_campaign.py:14`). `method_hash()` would record the frozen file's hash, but labels would still be produced by the bug. Fix:
- add a startup check, e.g. `verify_quote("p = .88", ["p = .88."]).status == "supported"`;
- refuse to run if `verification.__file__` is under `runs/*/code/`;
- record the module path in the output.

**3. Assessments aren't tied to the packet they were judged on.**
- `packet()` overwrites `criticism-packets-v2/<case>.json` and `.origins.json` on every run, without archiving (`:169-170`).
- The assessment output stores neither the packet hash nor the origin map.
- If a call then fails or is skipped, the old assessment's item IDs get joined to the new origin map. That can still happen when the source hashes are unchanged, e.g. when the dedup or filter logic changes.

Fix: archive packets by hash, store `packet_sha256` and the origins in each assessment, and have the summary verify both.

**4. The "dropped" list is wrong whenever the audit arm is excluded.** `holistic_only_ids` (`:165`) becomes every holistic ID. Only compute inherited/new/dropped when both nested arms are included; otherwise write `null` with the reason. Better still, label these as "not published in the audit arm" and include the audit's disposition or reason for each, because a merge isn't a drop.

**5. The planned v1 rederivation would carry a stale failure note.** `checked_labels` copies the v1 row as is. v1 rows have "Deterministic check: missing relevant exact manuscript evidence." appended to `limits`, so the note survives even when the new check passes. Keep the original `limits` separately or strip that suffix, and write rederived labels to their own directory with the matcher hash. Add a test for this.

## Controls: the revised probe has the same design flaw

`judge_controls_followup.py` item-001 still pairs the external count with a claim the manuscript itself can defeat: that Steegen's exclusions transfer to "the classroom analysis". Opus said `contradicted` (raw and checked agree), and its reasoning is right: the classroom analysis uses a different dataset, so the transfer fails regardless of the count. Sol said `unresolved`. So the expected label is wrong a second time.

- Keep both failed expectations and report them as probe-design errors, not judge errors.
- The rationale again announces that the source is unavailable, which hands the judge the answer (as with the original item-004).
- A revision designed after seeing judge outputs is weaker evidence. Design an external-abstention probe whose only checkable content is the external fact.
- All the control scripts still run through the v1 script with the frozen matcher. Raw and checked labels happen to agree in the extended and follow-up results, but future controls should go through the v2 path and be scored on raw labels too.

## Should-fix

- **Cache coupling:** the v2 cache key includes the hash of `verification.py` (`:211`). Any edit to that file, including external-source logic, triggers new model calls, which mixes sampling variation with matcher changes. Cache the judge call on the judge's inputs only, store the raw output, and recompute the checked labels deterministically on every run.
- **Current schema applied to frozen reviews:** `ReviewRun.model_validate` and `unconfirmed_concerns` use the current `schemas.py` and `render.py`. A validation error would crash the whole packet run. Catch failures per arm and record them in provenance, along with which render/schema version was used.
- **Remedy rule:** both eval scripts now show a remedy only when it is `supported`. `render.py:49` and `evaluation.read_review:176` still show it when the status is `None`. That case doesn't occur in this data, but assert or count it so the eval can't silently differ from the author-visible report.
- **Near-duplicates:** dedup only merges exact presentations. List same-ID holistic/audit pairs that weren't merged (e.g. the verifier added evidence), because the judge can still cross-reference them.
- **Stale invalid files:** a `.invalid.json` stays in place after a later valid run. The summary must ignore it or mark it superseded.
- **Test gaps:**
  - `packet()` provenance: unconfirmed counts, inherited/new/dropped, the excluded-arm case;
  - the method hash entering the cache key;
  - comparison history and the separate v4 directory;
  - prompt content;
  - the stale `limits` note.

## Final reporting needs (once the summary repairs land)

- Keep v1 (frozen and offline-rederived), v2 and v4 separate. Differences between v1 and v2 mix dedup, prompt, matcher and sampling changes, so they can't be read as a repair effect.
- Report per case and per judge:
  - raw vs checked labels, and the `quote_check_only_disagreement` count;
  - native vs unique item counts;
  - unconfirmed author-visible exclusions;
  - inherited/new/not-published IDs with dispositions;
  - excluded arms and invalid outputs.
- Report the controls with probe-design errors kept distinct from judge errors.
