# Fable v2 contract review

Model: `claude -p --model fable --effort high`, tools disabled, strict MCP configuration, safe mode, no session persistence.

## Verdict: BLOCK

The prompts are contract-consistent on nearly every requested scientific point, but two engine failure paths can crash the run or publish an unfiltered dump.

## Blockers

1. **Verifier failure can crash instead of degrading.** `run()` reads `verification_artifact` in its exception handler, but initialization was inside `_cached`. A verifier/backend/schema exception can therefore cause `UnboundLocalError` and prevent rendering. Initialize it in `run()` immediately before the verification `try` and remove the dead local.

2. **Editorial failure can publish every finding uncapped.** If editorial processing raises, verification-stage findings retain `editorial_disposition="publish"`. Rendering then includes unresolved and unverified duplicates. On editorial failure, findings must become `needs_review`/set aside with an audit reason. Invalid individual merge instructions should set aside the offending source rather than aborting the whole stage where feasible.

## Material contract issues

3. Severity guidance exists only in profile metadata and is not passed to generation. Because `Finding.severity` defaults to Major and editorial severity is immutable, absence-only findings can remain Major. Supply severity guidance to generators and editor; require absence-only Major/Critical candidates to be set aside if no appropriately calibrated canonical candidate exists.

4. Merge validation blocks merge/reject targets but does not prevent a stronger-supported source from merging into a lower-support target. Require the target to be kept and to have equal or stronger epistemic status.

5. The cap sorts severity before verification strength, allowing an unresolved Major to displace an `llm_supported` Minor. Sort by epistemic support first and visibly separate unresolved material in rendering.

6. Deterministic statistical-screening leads are hardcoded Major even though the claim says values “may be” inconsistent and still requires independent verification. Default these leads to Minor until consequence and correctness are established.

7. Triage guidance appears chiefly in contribution. A thin manuscript just above the deterministic length threshold can still make every other module emit absence findings. The shared generation instruction should tell non-contribution modules to return zero when material is insufficient for their assessment.

8. Verification provenance is computed before verification and remains a model relationship if the stage fails or is skipped. Set it to `not_run` on failure/skip and compare resolved model identities.

## Checks passed

- V2 asks for few, genre-appropriate issues and treats the maximum as a ceiling.
- It distinguishes absence from demonstrated failure.
- It requires a conclusion-scope mismatch before elevating acknowledged limitations.
- It prohibits retrospective preregistration.
- Numerical prose/table consistency guidance is generic and contains no known-paper answer.
- Claim and remedy outcomes use separate typed fields.
- A supported claim with an overreaching remedy can remain publishable and the renderer can suppress advice.

## Smaller issues

- Do not concatenate remedy assessment into claim rationale when it already has a typed field.
- `verifier_prompt()` and `combine_verification()` diverge from the live pipeline instruction and should be wired in or removed.
- Contradicted findings should carry a rejected editorial disposition in the audit record.
- Clarify in the v2 editorial prompt that remedy withholding is automatic and is not an editorial operation.
