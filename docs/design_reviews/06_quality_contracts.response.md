# Fable quality-contract review

Model: `claude -p --model fable --effort high`, tools disabled, strict MCP configuration, safe mode, no session persistence.

## Verdict: SHIP on the six stated contracts

One adjacent safety gap remains: after a verifier exception, the pipeline marks findings `unverified` and continues to editorial. An editor can return `keep`, producing `editorial_disposition="publish"`. The renderer excludes only `contradicted` findings, so an unverified finding can appear under a substantive severity heading with its remedy. This is the same unsafe-output class that the editorial-exception contract prevents. A regression assertion that the verifier-failure report contains no `### Major:` heading would currently fail.

## Contract results

1. **Verifier exception:** satisfied. Artifact state is initialized before the verification `try`; failure sets `not_run`, marks the run partial, records a failed stage, and rendering proceeds.
2. **Editorial exception:** satisfied. Every finding becomes `needs_review`, merge targets clear, and the renderer excludes them.
3. **Guidance propagation:** satisfied in code. Every module receives canonical severity guidance and incomplete-material zero-finding guidance; editorial receives severity guidance too.
4. **Merge validity:** satisfied. Targets must exist, differ from the source, have `keep`, have equal-or-higher epistemic rank, and remain canonical and publishable after the cap.
5. **Cap priority:** satisfied. Protected targets come first, followed by epistemic strength, severity, and id.
6. **Statistical lead:** satisfied. Deterministic screening creates a Minor candidate and severity is immutable editorially.

A supported claim with an overreaching or unresolved remedy remains eligible while rendering withholds the remedy. Contradicted findings are rejected and excluded from the substantive findings section.

## Test blind spots

- Verifier and editorial failure tests raise before cache artifact writing; malformed post-write joins and cap overflow are covered elsewhere only partially.
- The guidance test should inspect every generation module and editorial input, not only joined generation text.
- Merge tests do not cover every non-kept target and protected-target cap interaction.
- Remedy withholding and contradicted-to-set-aside rendering lack direct tests.
- The verifier-failure test does not assert that unverified findings remain absent from the substantive review.

Non-blocking: rejected exact-duplicate winners can still enter `protected_targets` before post-cap repair. The behavior fails closed.
