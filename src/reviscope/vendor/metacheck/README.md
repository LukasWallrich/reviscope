# Vendored metacheck skill files

Copied from the metacheck agent skill, commit `911f800` ("Add metacheck manuscript review
skill"): `scripts/`, `references/`, `schemas/`, `assets/` and `CONTRACT.md`. One local change:
`mc_load()` in `scripts/_common.R` sets metacheck's contact email from `METACHECK_EMAIL`. They wrap the metacheck R package (tested with 0.1.0,
<https://github.com/scienceverse/metacheck>).

ReviScope's metacheck stage (`src/reviscope/metacheck.py`) runs `scripts/mc_import.R` and
`scripts/mc_run.R` and passes compact module rows and excerpts of the matching
`references/*.md` rubrics to the review modules as unverified leads. The other scripts are kept so the folder stays a
complete, runnable copy of the skill's R layer.

To update, copy the same folders from a newer skill commit and record that commit here.
