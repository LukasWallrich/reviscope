Review of the pasted normalization and OpenRouter modules. `verify_quote`, `_strict_schema`, `_extract_json`, `SYSTEM_GUARD`, and `Backend.identity` were not read in this session, so findings that depend on them are listed separately as contingent.

**High severity**

- **Truncated output enters a model "repair" that can fabricate content.** The OpenRouter request never reads `finish_reason`. At the default cap of 6000 output tokens, 40 issues with seven fields plus spans is likely to truncate. The cut-off JSON fails validation, and the repair prompt then hands the model its own partial output with no source review and asks it to fix it. The model completes the tail. Spans are re-verified, but invented critique, rationale, or remedy text is not. This violates "preserve without repair". Raise on `finish_reason == "length"` and remove content repair, or at minimum record which entries in `calls` were repair calls.

- **Nothing enforces "same model/schema for human and AI review" or audit independence.** The audit gates one inventory. No code compares two inventories on backend identity, resolved model, prompt version, or `max_issues` before comparison. No check that the audit backend differs from the normalization backend, so a model can audit itself. `render_inventory` reads only the deterministic checks and never the audit's `comparison_eligible`, so an inventory that failed the audit still renders into the comparison. The fail-closed gate lives in a file the comparison path does not read.

- **Cost and provider provenance is never populated.** OpenRouter returns `usage.cost` only when the request includes `"usage": {"include": true}`, so `cost_usd` is always null. The response `provider` and generation `id` are not recorded either. No `provider: {require_parameters: true}` is set, so routing can land on a host that ignores `response_format` and returns free text, which then enters the repair path above.

**Medium severity**

- **Dedup is duplicate-ID detection on model-chosen labels only.** Two issues with different ids but identical spans or identical critique text pass. Nothing is deduplicated, only flagged. A deterministic equality check on span sets or normalized critique text is what the requirement describes.

- **Audit trusts stored deterministic checks instead of recomputing them.** The review is hash-bound, the inventory JSON is not. Recomputing span matches inside `audit_inventory` is one loop and closes the gap.

- **Hitting the issue cap is not flagged.** The prompt instructs truncation at `max_issues`. An inventory with exactly that many issues should fail eligibility deterministically instead of relying on the auditor's `complete` flag.

- **"Bounded" calls are weaker than they look.** `reasoning: {"exclude": True}` hides reasoning text but does not disable reasoning. Reasoning tokens still consume the output budget and bill. Set a reasoning effort or budget if bounding is required.

**Low severity**

- **Rendering joins with a pipe.** Evidence and qualifications joined by `' | '` collide with `|` in absolute values and conditional probabilities.
- **Exit codes are inconsistent.** `create` exits 2 on unmatched spans but 0 on duplicate ids, although rendering later raises on duplicates.
- **Unhandled response shapes.** OpenRouter can return HTTP 200 with an `error` body, which raises a bare `KeyError` on `choices`. A refusal yields `content: None`, which feeds the literal string "None" into the repair prompt. `URLError` and timeouts propagate raw. No key leaks, but no sanitized message either.

**Contingent on unread helpers**

- **Empty span may pass verification.** `min_length=1` applies to the list, not the string. If `verify_quote` is substring-based, an empty string is "supported" against any review. The same hole exists in `MissingIssue`.
- **Exactness of spans is unenforced if `verify_quote` is fuzzy.** If it normalizes whitespace or splits on ellipses, the "no stitched spans" instruction has no deterministic backstop.
- **Schema strictness.** `Field(min_length=1)` emits `minItems`, which some strict JSON-schema implementations reject. Check what `_strict_schema` does with it.

Points that hold as written: the review-only boundary holds in both prompts, the review hash binding is correct, the normalization hash is reproducible from the loaded dict, and file writes are atomic.
