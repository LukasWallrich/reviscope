## Verdict: the five fixes are in place; three small must-fixes remain before the main merge

I read the four files you named, the method record (`assessment-method-v2.json`) and the new source-only control (`runs/reasoning-quality-20261005/judge_source_control.py`). I made no edits and no model calls. The full test suite hasn't been run on this state yet, so the merge should also wait for that.

**Approved:**
- **v4 comparisons** now write to their own `comparisons-v4/` directory and keep history there. That removes the collision with the frozen v3 runner.
- **Packets:** immutable snapshots, a byte hash, and the full origin map and provenance embedded in each assessment.
- **Nested-arm reporting:** "not published in audit" is only computed when both arms are included, and it carries the audit status, disposition, reason and merge target. The excluded-arm case is tested. Same-ID unmerged pairs and author-visible unconfirmed exclusions are recorded.
- **Raw judge cache:** keyed on instruction, packet, backend, schema and protocol only. Checked labels are recomputed on every run, and the test shows one call reused across a method change.
- **Source-only control:** now a pure probe of an unavailable source fact, run through the v2 path and scored on raw labels. Earlier mixed-probe failures are retained.

## Must-fix

**1. The stale note is stripped when the quote check still fails** (`assess_criticisms.py:226`, `rederive_criticism_quotes.py:32`).
- v1 appended the "Deterministic check…" note whenever any quote was unmatched, including when the raw label was `unresolved` (old `criticism_audit.py:178`).
- Both new paths strip the note whenever checked equals raw. For a raw-`unresolved` item whose quote is still unmatched (a genuinely fabricated or garbled quote), the note disappears and `quote_check_only_disagreement` is false.
- Only `unmatched_evidence` still records the failure.
- Fix: strip only when `not unmatched and (raw == 'unresolved' or relevant)`. Add an explicit `quote_check_passed` boolean, and a test for raw `unresolved` with a persistent unmatched quote.

**2. The rederivation script has no matcher guard.**
- `rederive_criticism_quotes.py` imports `checked_labels`/`method_hash` but never runs the self-test or the frozen-path rejection. It also doesn't record `matcher_module`.
- Run with the campaign's `PYTHONPATH`, it would silently reproduce the bug. The recorded method hash would show it only after the fact.
- The guard in `assess()` (`:248-252`) reads the module-level `LAUNCH`, which is only set under `__main__`, so it can't simply be reused.
- Fix: factor out a helper such as `require_repaired_matcher(launch)` that returns the module path. Call it in both scripts and store the path in the rederivation record.
- Add tests for both rejection branches. They're currently untested; the fixture just sets `LAUNCH['code']` to a dummy path to get past the guard.

**3. v4 comparisons don't check that the v4 prompt is the one in use.**
- `compare_development_reviews.py` takes `comparison_parts` from whichever `reviscope` is on the path.
- With the frozen code first on the path, it would write v3-prompt judgments labelled `development-criticism-comparison-v4` into `comparisons-v4/`.
- Fix: assert the instruction contains the v4 visual/genre text, or reject an `evaluation.py` under `launch.json`'s `code` path. Either way, record the module path and hash in each output.

## Should-fix (not blocking)

- **Packet binding:** `assess()` takes `packet_sha256` from the file on disk (`:280-283`), not from the `data` it judged. Assert `json.loads(packet_path.read_text()) == data` before recording.
- **Raw artifacts:** store `packet_sha256` and the protocol in the raw judge file as well as the key.
- **Rederived outputs:** they're overwritten without history (`rederive_criticism_quotes.py:40`). Call `archive()` first, as `assess()` does.
- **Remedy listing:** `legacy_unassessed_remedies` (`:146`) includes candidates that are never shown. Restrict it to shown IDs (`arm_ids`).
- **Missing audit entries:** a holistic ID absent from the audit's findings shows up as all-null fields. Add `present_in_audit: false`.
- **Method snapshot not enforced:** nothing checks that native v2/v4 runs use the frozen `assessment-method-v2` snapshot. The source control ran from the live repo `eval/`. Before reporting, confirm each output's `method_sha256` and module paths match the snapshot hashes.
- **Controls share directories:** the control writes into `criticism-packets-v2/` and `criticism-assessments-v2/` next to the native cases. The summary must select cases from `launch.json` or exclude anything marked `control`.

## Remaining reporting needs

- Keep generation f7 and the original v1/v3 results separate from the v1 rederivation and from v2/v4. Differences between v1 and v2 mix dedup, prompt, matcher and sampling changes.
- Per case and judge, report:
  - raw vs checked labels, the quote-check-only disagreements and failed quote checks;
  - native vs unique item counts, and same-ID unmerged pairs;
  - author-visible unconfirmed exclusions;
  - inherited/new/not-published IDs with reasons;
  - excluded arms and invalid outputs.
- Report the controls with the two mixed-probe design errors kept distinct from the source-only result.
