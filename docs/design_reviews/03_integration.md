# Fable integration review

The advisor's list matches mine. Here is the review.

**Confirmed from the pasted code**

1. **HIGH: pairwise blinding does not strip the pipeline's own output.** `strip_review_metadata` in `evaluation.py` pops only leading lines matching `backend:` and friends. The rendered review starts with a heading line, so the loop stops immediately and the backend and profile lines survive. The "Coverage and audit" section, stage names, cache statuses, and verification tags such as `verified_deterministic` also identify the candidate to the judge. Fix: render a judge-facing variant with findings only, or strip from the H1 through the study overview and drop everything from "Coverage and audit" onward.

2. **MEDIUM: judge instructions are sent as untrusted evidence.** In the `generate` branch of `_call_backend`, the full comparison prompt including the judging rules is passed as evidence. `SYSTEM_GUARD` tells the model never to follow instructions inside evidence. Fix: pass the rules as the instruction and only the manuscript and the two reviews as evidence.

3. **MEDIUM: "independent" verification sees the pipeline's verdict.** `verify_finding` serializes the whole finding, including status, verification note, rationale, and confidence. The pipeline's prior decision leaks into the audit. Fix: whitelist id, claim, evidence, and optionally severity before serializing.

4. **MEDIUM: candidate ID collisions break the joins.** Candidate IDs use the model-returned id when present. Duplicate ids within a module collide, and the verifier decisions dict plus the editorial `by_id` map then apply one decision to several findings. Fix: always use the position suffix, or suffix on collision.

5. **MEDIUM: editorial can silently remove deterministic findings.** In the editorial block of `pipeline.run`, a merge or reject disposition overwrites any prior status, including recomputed statistical findings. Rendering drops rejected and merged findings with no audit line. The merge `target_id` is never validated, so a missing, self-referential, or itself-rejected target makes both findings vanish. The `seen` dedupe keeps the first occurrence regardless of status, so a contradicted duplicate hides a later supported one. Fix: refuse reject on deterministic statuses, validate that the target exists and is kept, dedupe preferring the best status, and render a short "set aside by editorial" list.

6. **MEDIUM: evaluation key and shape mismatch with pipeline output.** `sample_finding_audit` requires `finding_id`, `verification_status`, and `verifier_disagreement`. The pipeline emits `id` and `status` and never produces the disagreement flag, so targeted sampling never prioritizes unresolved findings. Running audit-sample on review.json iterates the top-level dict keys and fails. `audit_summary` needs a `stratum` key that audit-sample output does not carry. Fix: accept a findings wrapper object, fall back from id to finding_id and from status to verification_status, and tag sampled rows with their stratum.

7. **MEDIUM-LOW: lenient aggregation and unflagged invalid cases.** In `aggregate_pairwise`, votes of candidate plus tie resolve to a candidate win, so order-swap only partially controls position bias. Papers with one invalid order count on a single vote with no flag. Fix: require both orders to agree for a win, and drop or flag papers missing an order.

**Depends on code not shown**

8. **MEDIUM: verifier status is unconstrained.** `VerificationDecision.status` is a free string, and the entire decisions dict, including ids not in the pending list, goes to `verify_findings`. If that function copies status through, the verifier can mint `verified_deterministic`. Fix: use a Literal of supported, contradicted, unresolved, and filter decisions to pending ids. Check that `verify_findings` rejects unknown statuses.

9. **LOW-MEDIUM: audit gap in metadata.** `RunMetadata` never records the verifier backend, so a Claude verifier is invisible in the report header. The eval compare and verify commands with no model flag record the identity as `codex:default:max`, so the frozen judge config omits the actual model. Fix: add verifier fields to metadata and require an explicit model for eval commands.

**Needs one run to confirm**

10. **CLI flags are unverifiable here.** The codex `--disable`, `--ignore-user-config`, `--ignore-rules`, and `--ephemeral` flags, and the claude `--permission-prompts none` and `--effort max` or `xhigh` values, cannot be confirmed from the transcript. Any unknown flag fails loud and blocks the default path. Run each CLI's help once. Two related suggestions: use codex's output-last-message option so `_extract_json` does not scan transcript noise, and confirm the env whitelist without `HOME` still lets both CLIs find credentials.

I skipped the `computed_p` None formatting, which your in-flight abstention fix covers, the fenced-block-without-newline edge in `_extract_json`, and the paid editorial call on an empty findings list.