# Vendored metacheck skill files

Copied unchanged from the metacheck agent skill, commit `911f800`
("Add metacheck manuscript review skill"): `scripts/`, `references/`, `schemas/`,
`assets/` and `CONTRACT.md`. They wrap the metacheck R package (tested with 0.1.0,
<https://github.com/scienceverse/metacheck>).

ReviScope's metacheck stage (`src/reviscope/metacheck.py`) runs `scripts/mc_import.R` and
`scripts/mc_run.R` and passes module tables and the matching `references/*.md` rubrics to
the review modules as unverified leads. The other scripts are kept so the folder stays a
complete, runnable copy of the skill's R layer.

To update, copy the same folders from a newer skill commit and record that commit here.
