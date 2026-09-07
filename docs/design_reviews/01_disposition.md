# Response to Fable architecture review

Reviewer: authenticated `claude -p --model fable --effort high`, 2026-09-07. The full request and response are alongside this file.

Adopt: flat effective profiles and content hashes; pure module contracts; source-aware normalized quote anchors with offsets; explicit deterministic/model verification provenance; verification without the generator rationale where practical; editorial cannot upgrade support; rounding-aware statistical checks; chained cache keys; isolated no-tools subprocess calls with timeout and validation; reviewed-version manifests; small pilot before wider evaluation; separate random/targeted human audit. These recommendations were forwarded to the responsible Sol agents.

Adapt: partial runs still render a clearly labelled PARTIAL report with failed-stage coverage and non-success CLI status. Suppressing all output would impair diagnosis and hide useful completed stages. Such reports cannot be treated as complete reviews.

Adapt: observed-power and rote significance mistakes are guarded through applicability rules, examples and tests, not a blind lexical filter. A legitimate criticism can itself mention observed power or an arbitrary threshold.

Keep inexpensive alpha scope: JSON, Markdown and safely escaped static HTML; Claude as well as Codex backend when no-tools operation is available; one minimal education profile to test inheritance. This does not imply validation in education.

Reject the claim that public-data leakage affects systems equally or is solved by a claim audit. Memorization can differ between models; exact-version matching, reference isolation, public-data caveats and fresh cases reduce but do not eliminate contamination.
