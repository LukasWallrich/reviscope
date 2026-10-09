## Verdict: approved for the local-main merge, with one guard needed before the offline re-wrap

I read the four files, `EVAL_SCRIPTS` and the running `09dd60` snapshot. I made no edits and no model calls. Merge once the full suite you're running passes.

**Confirmed:**
- **Failed quote checks stay visible.** `quote_check_passed` is false whenever any quote is unmatched, even if the raw label is `unresolved`. The stale note is only stripped when the check passes, in both the assessment and rederivation paths. A test covers a persistent invented quote.
- **Matcher guard.** `require_repaired_matcher(launch)` checks the matcher's behaviour and rejects the original generation code. Both scripts call it and record the module path. Both rejection branches are tested.
- **v4 prompt guard.** The comparison script checks the actual instruction text before any call, and records the prompt module, its hash and the instruction hash. A test shows a legacy prompt is refused with no output written.
- **Packet binding.** The on-disk packet must equal the judged data before and after the call. New raw artifacts record the packet hash and protocol.
- **Rederived outputs** are archived before being overwritten.
- **Remedy listing** now counts only shown IDs, and each not-published entry carries `present_in_audit`.
- **Snapshot coverage.** `EVAL_SCRIPTS` includes both new scripts, so the snapshot digest covers them.
- **Raw-cache reuse will work.** The `09dd60` key is built from the same fields, and its instruction, schema and protocol string match the current code, so the current wrapper will find the `09dd60` raw files.

## Required before the re-wrap run

**Add a no-call mode to `assess_criticisms.py`.** Nothing currently enforces your plan to apply the corrections without new sampling:
- If a raw file is missing, `assess()` calls the model (`:278-280`).
- That happens for any job that failed or came back invalid under `09dd60`.
- It also happens if the packet bytes change before the re-wrap, e.g. an arm's audit status changes.

In each case the "offline" re-wrap would quietly draw new judgments. Add an `--offline` flag that raises when the raw file is missing or the key differs, and use it for the re-wrap. Report any job that needs a real retry separately, as a retry.

## Optional refinements

- **Comparison cache hits overwrite provenance.** On a hit, the script rewrites the prompt module path and hash in place, without archiving first (`compare_development_reviews.py:80-83`). The judgments stay tied to the identical prompt through the key, but the record of which module made the call (e.g. the `09dd60` path) is lost. Keep the original fields and append a reuse record.
- **Pin the prompt.** Checking an exact expected `instruction_sha256` would be stronger than the substring guard.
- **Record the re-wrap code.** Store the re-wrap code's identity next to `09dd60` in `assessment-method-v2.json`. At reporting time, check every output's key, `method_sha256`, matcher path and prompt hash against the recorded snapshots.
- **v1 rederivation may go stale.** The frozen v3 runner is still writing, so a v1 file could change after rederivation. Check each rederived file's `original_sha256` against the current v1 file at reporting time. Run the rederivation from current code, not `09dd60`'s older copy.

## Scientific limitations to carry into the report

- **Judges aren't ground truth.** Opus verified the pipeline items it now judges, and Sol generated both arms. Labels and preferences are model opinions.
- **Unequal filtering.** Pipeline items passed a verifier; plain items didn't. Per-arm label rates can't be compared as quality.
- **Pooled calls and bundled items.** Each case is judged in one pooled call, items can bundle several claims, and there's no atomic inventory, so counts aren't precision or recall.
- **Small design.** One replicate, a nested audit arm and no compute-matched broad read mean no variance estimate and no causal claim about the audit stage.
- **Human comparisons** are Opus-only, and the formats differ: human reports are full prose, AI reports are stripped to criticisms.
- **v1 vs v2/v4 aren't comparable.** Dedup, prompt, matcher and sampling all changed together.
- **Controls** were designed after seeing outputs; two earlier probes had wrong expectations.
- **The quote check** is quote hygiene, not proof of correctness.
- **Targeted checks** were chosen after generation, on training data.
- **Frozen generation (f7) still has the boundary bug** in evidence anchoring. Quantify offline how many generation-time quotes failed only at a number boundary, and state whether any publication decisions were affected.
- **Still needed:** expert adjudication, repeat runs, a compute-matched comparator and an independent corpus.
