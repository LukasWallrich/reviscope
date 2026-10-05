# Training diagnostic records

See [the results](../REVIEW_QUALITY_TRAINING_RESULTS.md). These artifacts contain
bounded diagnostics and content hashes, not manuscript, PDF or human-review copies.
Model labels and native item counts are not scientific correctness estimates.

Canonical local artifacts are in
`/home/lukas/Documents/Coding/reviscope-reasoning-assessment/runs/reasoning-quality-20261005`.
The orchestration copies are inspectable records of the executed scripts. They derive
ROOT from their own location; restore them to the canonical run root with retained data
before executing, rather than running these archive copies in place. Generation and
assessment modules are separately frozen at the paths and hashes in the provenance audit.
`offline_finalize.py` uses retained raw calls and refuses model calls. Four negative
provenance checks and two final-render checks test engineering guards only.

All Meta-Psychology data are training/development; an independent corpus and qualified
expert assessment remain to be chosen. Main is checked out separately in
`/home/lukas/Documents/Coding/reviscope-main`; implementation branch/worktree is
`reasoning-assessment` in `/home/lukas/Documents/Coding/reviscope-reasoning-assessment`.
The shared `coarse-socpsy` checkout remains `known-error-benchmark` at `a977767`.
Use explicit PYTHONPATH for isolated code; the shared editable virtual environment
continues to point at the original checkout. Nothing was pushed or publicly published.
