# Pipeline integration review, 5 October 2026

Two subscription-backed, read-only Opus review sessions assessed the reasoning change
and all branch work relative to main. Both completed successfully with no permission
denials. Each session received a self-contained prompt and concrete source/diff paths;
no source edits or model APIs were permitted. Follow-up reviews checked the repairs.
The [final integration review](pipeline-integration-review/final-gate.md) approves merge
and the Meta-Psychology development assessment, with no remaining must-fixes. Model
identities, session IDs, usage metadata and the complete review texts are retained in
`docs/pipeline-integration-review/`. CLI usage metadata is not an API billing invoice.

## Repairs made before integration

* Preserve the evidence audit's coverage of each central claim, generalize the production
  mechanism example, add support/unspecified literature relations, include material
  restraint in context modules, and keep broad `checks=[]` unambiguous. Audit conclusions
  now appear as explicitly unverified records. Source follow-up receives the same
  reasoning criteria as ordinary verification.
* Identify curated papers from pinned extracted-text hashes. Block all reviewer URLs,
  editorial archives, submitted/other-version OSF GUIDs/file IDs and their short-link,
  download, storage and renderer-query aliases, plus both Linnaeus journal hosts.
  Unopened search listings remain non-flagging warnings under the existing policy.
* Bind each source audit to its exact review hash/path and complete rule identity,
  including manifests, review-site policy and manual overrides. Primary comparisons
  require matching paper/input/profile and current complete clean audits.
* Require explicit case profiles, validate arm/profile before archiving, remove stale
  report/log files before a call, preserve arm history and reject resumes with mismatched
  or missing frozen code/input provenance. A CLI usage failure cannot archive the
  previous arm as a new audit report.
* Refuse pooled planted-error judgments from different judge, annotation or adjudicator
  conditions. Reuse checks all these identities from the frozen code copy. Require
  the paper ID, distinguish an uncredited published candidate from retrieval, and
  check numerical conclusion strings against actual computations.
* Designate all existing Meta-Psychology corpus entries training/development, including
  entries outside the six curated comparison cases. Independent validation remains
  unselected. The six-case broad assessment is specified separately in
  [REVIEW_QUALITY_TRAINING_PLAN.md](REVIEW_QUALITY_TRAINING_PLAN.md).

## Verification

The regression suite passed 200 tests with one SciPy-only test skipped in the project
virtual environment. System Python, which has SciPy installed, independently ran all
seven selected numerical checks and rejected seven contrary-computation controls.
Positive/negative regressions cover claim records, supplementary evidence, unavailable
sources, quote anchoring, cached work, contamination aliases, audit identity, profile and
arm mismatch, stale/usage-failed outputs, resume provenance and mixed judging conditions.
The six historical pilot outputs were re-audited separately with exact paper identity;
all remain clean, with unopened-listing warnings. Original pilot artifacts were retained.

These are engineering/provenance and selected arithmetic checks, not proof of improved
scientific review quality. The reasoning probes use scripted backend judgments. Opus
code-review approval is not expert adjudication of manuscript criticisms. Current source,
verification, remedy, severity and publication contracts remain in force; independent
scientific validation still needs a separately chosen corpus and qualified assessors.

## Integration scope

The implementation branch `reasoning-assessment` starts at `known-error-benchmark`
`a977767`, already containing main `c98e67b`. All accumulated pipeline evaluation,
benchmark diagnostics and documentation on that branch are included in local-main
integration, along with the reviewed reasoning and harness repairs. The shared
`coarse-socpsy` checkout remains on `known-error-benchmark`, with its original untracked
report and `work/` directory untouched. Main is checked out in a separate worktree,
`/home/lukas/Documents/Coding/reviscope-main`. No remote push or public deployment is
part of this integration.

## Training-assessment follow-up

The frozen six-case run exposed metacheck 0.1.0's empty-table join failure when
extracted equations contain no t/F candidates. A narrow adapter repair calls the
package first, classifies only that known failure as `skipped_missing_input`, retains
the original error, and never emits a green light or a finding. Unknown extraction,
other errors and an unsupported F-test format remain failed; coherent/incoherent
t-test calculations still come from the package. A final defensive handler preserves
the original failure if classification itself errors. No shared R package was edited.

Opus approved the initial and package-first versions with no must-fixes; complete
reviews are [retained here](pipeline-integration-review/metacheck-followup.md). The
regression suite passed **205 tests, one skipped** before the final defensive handler;
its focused five tests were rerun after that change. Real-package tests use local
fixtures and no model or reference-lookup calls, although the adapter's existing
`online()` check can probe connectivity. The retained Mackinnon parse now yields
`skipped_missing_input`, no traffic light, and the original join error. Frozen campaign
outputs retain their earlier failure and code identity. This is failure reporting,
not evidence of improved scientific accuracy.

## Numeric anchoring and assessment-provenance follow-up

The training assessment's Opus method review identified false rejection of exact quotes
ending in numbers before sentence/list punctuation. The matcher now accepts those ends
while preserving decimal, grouping, sign, exponent and superscript boundaries. The
external-source, full-rationale, remedy, severity and publication gates are unchanged.
Opus approved this fix and the visual/genre-aware comparison prompt; successive
follow-ups checked immutable packet provenance, nested-arm deduplication, quote
rederivation, distinct comparison directories, raw-call caches and startup guards.
The [merge approval](pipeline-integration-review/assessment-followup3.md) required a
no-call mode for rewrapping; `--offline` now refuses missing raw caches, with a
negative regression. Comparison cache reuse preserves original provenance in history
and appends reuse checks.

The final suite passed **225 tests, one skipped**. The 61 focused quote/assessment
regressions include successful punctuation anchoring, numerical truncation rejection,
immutable packets and origins, excluded-arm handling, preserved raw judgments across
method changes, cache history, old-policy rejection and offline no-call enforcement.
Selected post-hoc arithmetic and anchoring-impact scripts are retained separately.
The complete six-case scientific diagnostic remains a separate report: code review,
fixture success and restored model labels do not establish improved review quality.
