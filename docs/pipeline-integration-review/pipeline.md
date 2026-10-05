I wouldn't merge yet. The reasoning-assessment change needs one small fix, and the evaluation scripts from known-error-benchmark need three before the Meta-Psychology bulk runs.

I worked read-only: I ran no commands or tests and used no API. I did read the archived pilot runs in `coarse-socpsy/runs/pipeline-redesign-20261003` to check exposure. `pipeline.diff` (main→a977767) only touches `eval/` and `tests/`. So the holistic strategy, evidence audit, verification and editorial code already exist on main, and the only `src/` changes come from reasoning-assessment.

## Must-fix before merge

**1. Pilot contamination audit misses Meta-Psychology reviewer material** (`eval/audit_tool_use.py:44-47, 87-95, 164-166`)
- **Curated manifest not loaded:** `open_peer_review_curated.v1.json` isn't in `DEFAULT_MANIFESTS`. Hash matching also fails: the pilot reviews ran on extracted text (source sha `bf652e…`), while the manifest stores the DOCX hash (`323503…`). Without an explicit `--paper`, the audit only applies generic checks and still returns `clean`.
- **Reviewer URLs not blocked:** even with the right manifest, `URL_FIELDS` leaves out `editorial_archive` (e.g. `osf.io/vxqj5/`, which holds the reports and decision letters) and every `human_reviews[].url` except the primary `review_url`. For bonetto, that leaves Rahal's `osf.io/download/unjf5/` unblocked.
- **Published (revised) articles not blocked:** the `open.lnu.se/.../article/{view,download}/<id>` pages aren't in the blocklist either. `REVIEW_PATHS` doesn't match any of these URLs, and Codex has no domain deny-list. So these would pass as clean, which conflicts with "human reports stay out of generation".
- **Fix:**
  - Add the curated manifest to `DEFAULT_MANIFESTS`.
  - Add `"editorial_archive"` to `URL_FIELDS`, and extend `blocks` in `load_papers` with every `human_reviews[].url`.
  - Add the journal's article view/download prefixes to each manifest entry.
  - In `compare_development_reviews.py:89-90`, require `audit[0]["paper"] == prepared["paper_id"]` and the matching run path. Otherwise an "unidentified" audit can count as clean.
- **Historical pilot is unaffected:** the six pilot reviews never touched those OSF IDs. The published Meta-Psychology article pages appear only as unopened search-result listings, which the documented rule exempts. The recorded `clean` verdicts therefore still hold.

**2. A failed run can be archived as the wrong arm** (`eval/run_development_review.py:27, 45`)
- Both arms share `working/`, and `returncode in {0, 2}` is treated as "review written". argparse usage errors also exit 2. If the audit arm hits one, the holistic arm's `review.json` is copied into `reviews/audit/<case>`.
- **Fix:** delete `working/review.json` before each arm. Before archiving, check that `metadata.evidence_audit` matches the arm.

**3. Unverified audit conclusions appear in the author-visible report** (`src/reviscope/pipeline.py:339`, rendered at `render.py:65`)
- The new `EVIDENCE_AUDIT` text asks the model to write verdicts like "false premise" or "circular support" into `operation.result`. That text goes verbatim into the "Coverage and audit" section of `review.md`, bypassing verification and anchoring.
- The channel already existed, but this change turns it into a criticism channel.
- **Fix:** label the line, e.g. `"evidence operation (unverified discovery record; …)"`, or leave `result` out of the markdown and keep it in JSON. The anchor-count format stays, so the tests keep passing.

## Should fix (not blocking)

- **Audit rules relaxed without a record** (`audit_tool_use.py:128-149`): relative to main, listed search results are no longer flagged, and near-title searches for planted papers only produce warnings. `PIPELINE_VALIDATION_PLAN.md` says "keep … contamination rules unchanged", and the results doc calls the audit "unchanged". Either record the owner's approval, or emit listed own-paper/review-site URLs as warnings (verdicts unchanged) so they stay visible.
- **Scoring can mix judge versions:** `score_known_errors.py:62-77` doesn't check that all adjudications share the same adjudicator sha, annotation sha and judge identity/effort. `run_known_errors.py:170` re-scores only when `review.json` changes. Group by these values or refuse to mix them.
- **Hardcoded conclusions:** `check_development_numerics.py` emits fixed conclusion strings (e.g. line 42) whatever the computed values are. Assert the condition (e.g. `abs(t - .81) > tol`) before emitting.
- **Verifier gets discovery-only wording:** it receives the full reasoning guidance through `CLAIM_SCOPE` (`pipeline.py:115`), including lines like "retain … in external_evidence for any resulting finding". This is harmless but noisy; consider sending it only the argument and relation-checking parts.
- **Prompt conflict in the broad read:** "Record successful and unresolved checks where the response contract permits" (`reasoning.py:10-12`) sits next to the broad read's `checks=[]`. Any check entries the broad read returns get logged as "unfinished work". Reword it to refer to the operations ledger.
- **Minor:**
  - `adjudicate_known_errors.py:117`: `--paper` silently defaults to `"8"`; make it required.
  - `trace_known_errors.py:58`: the trace returns "published" even when the judge's published verdict is `not_detected`.
  - `run_development_review.py` doesn't record a code digest.

## Checked and found sound

- **Publication gate:** a finding still needs an anchored manuscript quotation. The verifier's external-source rules are unchanged, including optional-source dropping and refuted sources blocking support.
- **Audit records can't publish:** operation records never become findings. `source_evidence` has no `check` field, so it can't confirm a source.
- **Editorial:** it still can't change severity or text; remedies are still assessed separately.
- **No quotas:** none are introduced.
- **Caching:** cache keys pick up the prompt and schema changes. Old artifacts still load because the new fields default to null.
- **Inputs:** human reports reach only the tool-free judges, and every model call goes through the Codex or Claude CLI.

## Scientific validation needed later (not merge blockers)

- **New condition:** reasoning guidance changes every verification cache key, so new runs are a different condition from the frozen pilot. Don't pool them.
- **Offline probes:** the probes use scripted judgments. They show that records are preserved and gates hold, not reasoning quality. Expert adjudication and matched baseline comparisons remain the plan, as the docs already say.
- **Representation asymmetry:** criticism-only AI text compared with full human prose is a known limit of the judge comparisons. Keep reporting it.
- **Development data only:** all Meta-Psychology results are development evidence. Independent validation is still pending.

**Recommendation:** approve both changes once the three must-fixes are in. Fix 1 has to land before any Meta-Psychology bulk run.
