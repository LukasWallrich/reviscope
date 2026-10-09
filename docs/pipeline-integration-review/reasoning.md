I recommend **approving after two small must-fixes**. I couldn't run anything (read-only review), so the 189 passing tests are as you reported. I read the diff, the five new files, and the pipeline, discovery, evidence-review, schema, profile-loading, backend schema, ingest and render code.

## Must-fix

**M1. The audit no longer has to cover every central claim** (`src/reviscope/evidence_review.py:134`)
- **What changed:** `inferential_targets` used to say "reconstruct the decision rule for each central claim". It now says "for consequential claims inspected".
- **Consequence:** "Inspected" means whatever the model chose to look at, so the audit can now skip central claims entirely. This weakens an existing contract, while the implementation record (§Useful subset, "remain in place") says existing contracts are unchanged. The quota concern is already handled at lines 151–152 ("no claim or relation inventory quota").
- **Fix:** "reconstruct the decision rule for each central claim and other consequential claims inspected."

**M2. A bundled prompt contains the criticism of one development case without saying so** (`src/reviscope/profiles/quantitative_social_science/interpretation.generation.md:9`)
- **What changed:** The new example ("A manipulation that changes both group membership and norm violation…") is the main conceptual criticism of the group-membership/deviance-punishment development case (`docs/OPEN_REVIEW_COMPARISONS.md:21`). It now ships in every QSS-derived profile. The same scenario is in the `confounded_mechanism` probe and in `SCIENTIFIC_SLOP_ASSESSMENT.md:18`.
- **Consequence:** Tuning on development data is now allowed. But any later run on that case is primed toward its known criticism. `REASONING_ASSESSMENT_IMPLEMENTATION.md:22` calls these generic "quantitative-social-science examples", which misstates their provenance. I couldn't confirm the example didn't come from the Rahal/Bolesta reports.
- **Fix:** Generalise it, e.g. "A manipulation that changes two candidate mediators cannot identify one as the mechanism from a compatible contrast alone". If you keep it, record in the implementation record that it mirrors that case and that later results there are tuned.

## Should-fix (cheap, not blocking)

**S1. The literature-relation field forces a label, contradicting "do not invent"** (`evidence_review.py:30-31`)
- `relation` is a required six-value enum with no "unspecified" option. The strict schema makes every property required.
- Targets and criteria may be left empty, but the relation itself must be made up. The most common prior-work use in social-science introductions, "prior work shows X" offered as a premise, fits none of the six values well.
- **Fix:** Add `"support"` and `"unspecified"`, explained in `result`.

**S2. Material guidance skips the module that handles stimuli** (`discovery.py:57`)
- `social_psychology_context` (and `education_context`) don't get `MATERIAL_ASSESSMENT`.
- That module explicitly assesses "participant and stimulus scope", and a stimulus-dependent interpretation is the guidance's own example. The specialist most likely to ask for stimuli therefore lacks the "only when it blocks a specific inference" discipline.
- **Fix:** Add both context modules to the set, or apply the material guidance to all modules.

**S3. The word "checks" collides with the `checks` field** (`reasoning.py:11`)
- "Record successful and unresolved checks where the response contract permits" reaches the broad review, which is told `checks=[]` and whose expected topics are `[]`.
- If a model obeys the new sentence and adds any check entry, `validate_discovery` (`discovery.py:100`) sets `search_incomplete`. The coverage section then wrongly reports unfinished work. The same happens in specialist modules if the model adds an unknown check name.
- **Fix:** "Record successful and unresolved assessments in operation records where the schema provides them."

**S4. Two probes are mislabelled for the taxonomy they are meant to test** (`tests/fixtures/reasoning_probes.json`)
- Line 19 calls `false_claim_after_related_prose` a "false premise". The premise ("Assignment was randomized") is true; the claim is a non-sequitur contradicted by the reported count. These packets are meant for later expert adjudication, so the label matters. **Fix:** "does not follow from randomization and is contradicted by the reported count."
- In `distributed_support` (line 27), the step cites Methods but the only premise is the Results quote, so support spread across sections isn't actually exercised. **Fix:** Allow a `premises` list in the fixture and include both quotes.

## Optional

- **O1. Unverified reasoning verdicts appear in the report.** Coverage lines include `operation.result` (`pipeline.py:339`), and `review.md` renders them under "Coverage and audit" (`render.py:65`). The new prompt asks `result` to carry verdicts like "false premise" or "refuted", so more unverified criticism-like text appears there. The path itself is pre-existing, and the audit/publication policy is out of scope. The smallest mitigation is to prefix those lines "unverified audit record".
- **O2. Writing-side guidance also goes to the verifier.** `CLAIM_SCOPE` (`pipeline.py:115`) appends all of `REASONING_ASSESSMENT`, including "Retain … in external_evidence for any resulting finding". The verifier has no such field, and "claims" is ambiguous between manuscript claims and criticisms. Prefacing it with "When a criticism concerns a manuscript inference:" would clarify.
- **O3. One bad optional record can cost the whole audit.** `literature_relation.source_evidence` reuses `ExternalCitation`, which rejects items without a URL or DOI, and `inferential_step` must be non-empty. One malformed optional record triggers a full repair rerun of the tool-enabled audit (`backend.py:415`) or fails the stage. Existing findings carry the same risk, but this adds surface.
- **O4. Runs before and after this change are labelled the same.** `RunMetadata.engine_version` (`schemas.py:196`) is still `0.4.3a1`, so baseline and changed-prompt runs look identical in run metadata. Caching is correct because instruction, schema and profile hashes all change, but matched-baseline comparisons would benefit from a bump.
- **O5. Test gaps.**
  - Nothing asserts the reasoning guidance reaches the verification and `-sources` follow-up instructions, as the record claims (`pipeline.py:386,570`). Only `profile.verification_prompt` is checked.
  - `test_nested_evidence_is_anchored_and_never_promotes_an_operation` is trivially true, because the scripted response for that probe contains no finding.
- **O6. Doc hygiene.** `SCIENTIFIC_SLOP_ASSESSMENT.md:60-62` records LAN/Tailscale access details and is headed "on the OpenClaw box". The implementation record places the work in the local worktree, so the two disagree.

## What I checked and found intact

- **Contamination:** the audit still receives no broad findings or overview. Nothing new enters generation inputs.
- **External sources:** `source_evidence` uses `ExternalCitation`, which has no `check` field. Discovery fetches don't count as verification lookups. The relation probe confirms such a finding ends up `unresolved` / `needs_review`.
- **Evidence:** nested passages are anchored and counted, and raw records are kept.
- **Unchanged contracts:** severity, remedy and editorial contracts are untouched. No new stage, call, score, quota, authorship/PMI classifier or citation-count rule was added.
- **Caching:** cache invalidation follows the instruction, schema and profile hashes. Historical artifacts still load because the new fields default to null.
- **Figures:** ingestion is text-only, so leaving visual questions unresolved is correct, and table values stay usable.
- **Testing claims:** the docs consistently say the scripted probes are not scientific validation.

**Recommendation:** approve once M1 and M2 are fixed. S1–S4 are small and worth doing in the same pass; the optional items can wait.
