**The reasoning-assessment changes are approved; the eval/corpus changes need three fixes before the six-case training assessment runs.** I re-read both diffs and the current files plus the eval scripts they touch. I didn't run anything; the test results are as you reported them.

## Reasoning-assessment fixes: all verified, approved

| Item | Status |
|---|---|
| M1 | `evidence_review.py:162-163` now says "each central claim and other consequential claims inspected". |
| M2 | `interpretation.generation.md:9` now uses "two candidate mediators". The `confounded_mechanism` fixture and `SCIENTIFIC_SLOP_ASSESSMENT.md:18` still use the group-membership scenario, but neither is a generation input. Your provenance note covers them. |
| S1 | `support` and `unspecified` are in the enum (`evidence_review.py:30-31`), in the audit instruction and in `LITERATURE_ASSESSMENT`. |
| S2 | `discovery.py:57-59` now covers both context modules, and a test checks it. |
| S3 | Now refers to "assessments in operation records". |
| S4 | The false-claim label is corrected, and `distributed_support` supplies both premises, which the test checks. |
| O1 | The coverage line says "unverified audit record". No test or eval script parsed the old prefix. |
| O2 | The preface reads correctly. |
| O5 | Every verification call, including the source follow-up when it runs, now asserts the shared guidance. |

**Leaving the stage version unchanged is fine.** The schema, instruction and profile hashes already re-key every affected stage.

**One residual defect: the implementation record is stale.** `REASONING_ASSESSMENT_IMPLEMENTATION.md:19-21` doesn't list the two context modules among those receiving material guidance. Lines 35-36 don't list `support` or `unspecified` among the relations. Fix these when you add the provenance note.

## Eval harness and corpus metadata: fix before running the assessment

**E1. A committed evidence file still makes the claim the code retracted** (`docs/pipeline-development-analysis/numerical-checks.json:161`)
- The file still says "Half applies only to the Hong Kong subset…". `check_development_numerics.py:89` no longer produces that wording, and `PIPELINE_DEVELOPMENT_RESULTS.md:153` links this file as evidence.
- The new test only checks the computed values, not the conclusion text, which is why it passes.
- **Fix:** regenerate the file, or edit that one conclusion to match the script.

**E2. Resuming the runner loses a record and can quietly break the nested comparison** (`eval/run_development_review.py:35, 38-45, 71`)
- `records` starts empty on every run. When a complete holistic archive is kept, `arms.json` gets overwritten with only the audit arm's record, so the holistic arm's `code_sha256` and command are lost.
- Nothing checks that the kept holistic archive was built from the current code. If code changed between arms, the audit arm reruns broad review under the new code. The audit-vs-holistic comparison is then no longer nested, and nothing flags it. This is exactly where "frozen code snapshots identify the condition" fails.
- **Fix:**
  - Load the existing `arms.json` and append to it.
  - Before running the audit arm, require that the kept holistic record's `code_sha256` matches the current digest. Equivalently, require that the two `review.json` files share the same `review-broad` `cache_key`. Otherwise demand a new root.

**E3. Nothing checks that a case was reviewed under its curated profile** (`run_development_review.py:27`, `compare_development_reviews.py:19-34`)
- `--profile` defaults to `social_psychology`, but three of the six cases need `education` or `quantitative_social_science`.
- `prepared.json` already carries `profile` (`prepare_open_reviews.py:80`), but nothing compares it with the review. A run where the flag was forgotten passes the archive check and `checked_audit` and enters the primary comparisons.
- **Fix:** In `checked_audit`, require `review["metadata"]["profile"] == prepared["profile"]`. Also make `--profile` required, or read it from `prepared.json`.

## Should-fix (not blocking)

**E4. The docs contradict the new comparison gate on which file is the generation input** (`docs/OPEN_REVIEW_COMPARISONS.md:93`)
- That line still says the `.pdf`/`.docx` is the generation input.
- `checked_audit` only accepts a review whose manuscript source hash equals `manuscript_text_sha256`, which is only true when the `.txt` is reviewed. The training plan (`REVIEW_QUALITY_TRAINING_PLAN.md:49`) agrees with the gate.
- A run that follows the older doc is rejected only after spending the compute. **Fix:** update line 93.

**E5. The training-data designation has an unclear scope**
- The curated manifest's `independent_validation` text says "all Meta-Psychology cases", and the docs say "all six".
- Other Meta-Psychology entries carry no role:
  - Bartoš–Schimmack and Brunner–Schimmack in `open_peer_review.v1.json:7, 21`.
  - Sætrevik–Sjåstad in `empirical_pilot.v1.json:109-111`, which still says "retained for future evaluation".
- When the independent corpus is chosen later, it won't be clear whether these count as used. **Fix:** say "the six curated cases" in the manifest, or tag the other entries.

**E6. Other files in the OSF editorial archives aren't blocked** (`audit_tool_use.py:125`)
- Blocking now covers the archive project page, the published-version pages and the human report URLs.
- Revised-manuscript, response and decision files in the same OSF archive have their own `osf.io/download/<id>` addresses, which aren't listed. API paths such as `files.osf.io/v1/resources/vxqj5/…` don't start with the blocked prefix. Neither form is flagged.
- This isn't a regression: the curated manifest wasn't audited at all before this change. **Fix:** match the archive's project ID inside any OSF host or path, or list those file IDs.

The other eval changes check out:
- Adjudication reuse now keys on the review, the labels, the adjudicator script and the judge identity, and those fields match what `adjudicate_known_errors.py` writes.
- The scorer refuses mixed judging conditions.
- `--paper` is now required, and `run_known_errors.py` already passes it.
- The audit now records the review's hash and the audit rules' hash, and `checked_audit` rejects the cases it should.
- The trace relabel is correct.

The training plan matches the corpus metadata and the existing contamination and publication rules. One thing to note in it: Heyman uses the `education` profile, which its own metadata marks "not suitable for production claims".

**Bottom line:** the reasoning-assessment changes are approved once the implementation record's two stale lines are updated. The eval/corpus changes are approved for merge, but fix E1–E3 before running the six-case training assessment.
