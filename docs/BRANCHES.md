# Branches

The repository uses two ongoing branches:

- `main` retains the broad-review and optional evidence-audit pipeline, including the
  reasoning-assessment work and the DOCX extraction fix.
- `test` continues the specialist pipeline from `specialist-iter4`, including its
  overview module, editorial severity and folded findings. It also includes `main`.

Use `test` for further experiments and merge selected, verified changes into `main`.
Passing software tests does not establish review quality or scientific validity. The
specialist development results and remaining decisions are recorded in
`docs/SPECIALIST_DEVELOPMENT.md` on `test`.

## Archived work

On 25 October 2026, the previous branch tips were preserved as annotated tags under
`archive/2026-10-25/` before retiring their branch names. These tags are pushed to
GitHub and preserve the original commits for inspection or recovery.

- `specialist-foundation`, `specialist-only`, `specialist-iter`, `specialist-iter2`,
  `specialist-iter3`, `specialist-iter4`, `judge-clustering` and
  `validation-workspace` are development steps incorporated into `test`.
- `fix-docx-nested-tables` is incorporated into both ongoing branches.
- `known-error-benchmark`, `reasoning-assessment`, `report-clarity` and
  `worktree-agent-a8e13da82a9190575` are incorporated into `main` and `test`.
- `argument-coherence` remains a separate archived experiment. Its additional module
  and point-level judging were not incorporated into either ongoing branch. See
  `docs/ARGUMENT_COHERENCE_RESULTS.md` at its archive tag for the results.

For example, inspect that experiment with:

```bash
git show archive/2026-10-25/argument-coherence:docs/ARGUMENT_COHERENCE_RESULTS.md
```

Retired worktrees containing local inputs or run artifacts are retained at their
original paths with detached HEADs. Their untracked and ignored files are local
artifacts, not part of the archive tags.
