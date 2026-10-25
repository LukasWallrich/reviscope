# Branches

The repository uses two ongoing branches:

- `main` contains the current specialist pipeline, including the expert-critique
  brief, whole-paper overview, editorial severity and folded findings from
  `specialist-iter4`, plus the reasoning guidance and DOCX/PDF extraction fixes.
- `test` is available for further experiments. Its specialist development history
  was merged into `main` on 25 October 2026; it no longer defines a separate product.

Use `test` for further experiments and merge selected, verified changes into `main`.
Passing software tests does not establish review quality or scientific validity. The
specialist development results, first author ratings and remaining decisions are
recorded in [SPECIALIST_DEVELOPMENT.md](SPECIALIST_DEVELOPMENT.md).

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

Local inputs and run artifacts are not part of the archive tags. Files from removed
worktrees are preserved in private cloud storage under
`reviscope/worktree-archive/2026-10-25/`, with file checksums and original commit IDs
in `manifest.json`. Worktrees serving active previews are retained at their original
paths.
