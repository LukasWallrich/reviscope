# Programmatic near-submission preprint matches outside the initial journal set

Checked 7 September 2026. These are discovery candidates, not automatically eligible evaluation cases. Dates use the public PsyArXiv record date and the immutable primary-file revision date separately. Gap is the public-artifact date minus the journal-reported received date.

## Bounded search

[`eval/discover_submission_preprints.py`](../../eval/discover_submission_preprints.py) implements the reproducible search. It queries a bounded Crossref journal sample, queries Crossref for title-similar PsyArXiv records, requires at least one overlapping author surname, resolves the OSF primary file and every page of its revision history, and extracts the journal receipt date and transparent-review link from Nature HTML. It caches responses under ignored `eval/corpus/cache/discovery/` and writes compact JSON and CSV ledgers.

The completed runs were:

- **Communications Psychology:** ISSN `2731-9121`, 120 most recent articles, 120 checked, 67 candidate rows before collapsing multiple PsyArXiv record versions, and **0 surfaced request failures**. Four clean, manually inspected records fall within seven days; a fifth same-day record was inspected but retained only as a transferred-review caution.
- **Nature Communications:** ISSN `2041-1723`, bibliographic query `misinformation`, 8 relevance-ranked articles returned and checked, 7 candidate rows before version collapsing, and **0 surfaced request failures**. One meta-analytic psychology record falls within seven days.

The completed run predates explicit logging of the OSF `no_data` branch, so “0 surfaced request failures” must not be read as proof that every upstream request succeeded. The checked denominator is exact; the current script additionally records OSF resolution failures rather than treating them as ordinary no-matches.

No-match and request-failure states are distinct in the JSON. A title/author match remains `unconfirmed_title_author_match` until the historical file and review bundle are inspected. This is not an OSF DOI-filter workflow: the OSF preprint API does not support the presumed DOI filter.

## Manually inspected candidates

| Paper | Received | Public preprint record | Pinned file | Gap | Review evidence | Scope |
|---|---:|---:|---|---:|---|---|
| [Motivation biases behavior but not perception](https://doi.org/10.1038/s44271-026-00461-4) | 2025-08-21 | [`cr4tw_v1`, 2025-08-21 08:02 UTC](https://api.osf.io/v2/preprints/cr4tw_v1/) | [revision 1, created 07:32 UTC](https://osf.io/download/u3mw7/?revision=1) | **0** | [15-page review bundle](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs44271-026-00461-4/MediaObjects/44271_2026_461_MOESM1_ESM.pdf); initial decision names the preprint title and three reviewers | Four experiments; motivated perception, at the social/cognitive boundary |
| [Longitudinal profiles of parental self- and child-focused emotion regulation](https://doi.org/10.1038/s44271-026-00469-w) | 2025-10-29 | [`2u6nj_v1`, 2025-10-30 15:13 UTC](https://api.osf.io/v2/preprints/2u6nj_v1/) | [revision 1](https://osf.io/download/7p62w/?revision=1) | **+1** | [38-page review bundle](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs44271-026-00469-w/MediaObjects/44271_2026_469_MOESM1_ESM.pdf); initial decision names the historical title and two reviewers | Longitudinal family/emotion-regulation study |
| [Interoceptive ability is uncorrelated across respiratory and cardiac axes in a large scale psychophysical study](https://doi.org/10.1038/s44271-026-00404-z) | 2025-03-21 | [`s56v4_v1`, 2025-03-19 07:57 UTC](https://api.osf.io/v2/preprints/s56v4_v1/) | [revision 1, created 07:54 UTC](https://osf.io/download/pmbx3/?revision=1) | **−2** | [20-page review bundle](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs44271-026-00404-z/MediaObjects/44271_2026_404_MOESM1_ESM.pdf) | Large psychophysical study; psychology but not social psychology |
| [The experience of cognitive conflict is intrinsically rewarding](https://doi.org/10.1038/s44271-026-00462-3) | 2025-08-22 | [`b83mn_v2`, 2025-08-29 20:42 UTC](https://api.osf.io/v2/preprints/b83mn_v2/) | [revision 1, created 14:25 UTC](https://osf.io/download/xz6bd/?revision=1) | **+7** | [45-page review bundle](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs44271-026-00462-3/MediaObjects/44271_2026_462_MOESM1_ESM.pdf); initial decision names the historical title and four reviewers | Experimental affect and cognitive-conflict study |
| [Accuracy prompts are a replicable and generalizable approach for reducing the spread of misinformation](https://doi.org/10.1038/s41467-022-30073-5) | 2021-10-14 | [`v8ruj_v1`, first public 2021-06-09](https://api.osf.io/v2/preprints/v8ruj_v1/) | [primary-file revision 6, created 2021-10-15](https://osf.io/download/49t2m/?revision=6) | **+1 for revision 6** | [25-page Nature Communications review bundle](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-022-30073-5/MediaObjects/41467_2022_30073_MOESM2_ESM.pdf) | Meta-analysis of accuracy-prompt experiments; relevant but less useful than a single new empirical study |

The Communications Psychology decision bundles do not print a machine-readable first-feedback date, so that field remains unavailable rather than being inferred from acceptance or file metadata. The review text does verify the relevant initial manuscript title and reviewer count for the records stated above.

## File checks

| Paper | Manuscript SHA-256 (bytes; pages/type) | Review SHA-256 (bytes; pages) |
|---|---|---|
| Motivation | `d6523913769750843ba8b3f82bf5859f5ece68dde69d8ff763f729344b1ae642` (3,573,242; 47 PDF pages) | `76535d75bf58165004bcb355897c541f85f39eaf43cb18e8d478243dc5f7bf2a` (200,952; 15) |
| Parental emotion regulation | `1a3e3976af266a2fd79b684d946de8173b9f40fbc12021e36c30ac0572a36d64` (1,330,743; 42 PDF pages) | `30c3ce1ef9fed1c49949e4ec8815ed1b5c58212f5d1b3b2ee9d265ed52bdec49` (514,242; 38) |
| Interoception | `3037cdc4c4e75f4a5f59994bb9ef6c6fbf1c6031a3e0ba2a6a54fc0248944bdd` (6,348,178; 36 PDF pages) | `d0a6931c698f310a82cd73005585a805c9559c7240ec376b31b067da15b5fbab` (3,027,274; 20) |
| Cognitive conflict | `d5161d3f307bb1d8d9144b2f802b01d5f5334e5f1af02378acea61e6e6717ae3` (1,274,766; 23 PDF pages) | `713870c184dbdce705e71ea9f6cb1b44e6735a35b08b8ba7b0a0ca1430e75200` (1,158,083; 45) |
| Accuracy prompts | `e039398a5400dfa9dcec7a3eb47dbab30314c9a89d219601afdc8df3678f0d12` (1,061,491; 30 PDF pages) | `ef917143a882337079076cbc864e56c9d1101715d63e6a9b7731f75e47c6fdaa` (551,713; 25) |

## Important exclusions and cautions

“Neural responses to conflicting self- and partner-directed feedback…” appeared to be a same-day match (`qcj45_v5`, 1 April 2026), but its public bundle says the manuscript was previously reviewed at another Nature Portfolio journal and contains only the versions considered at Communications Psychology. It should not enter a clean submission-to-first-review corpus until the transferred-review chronology is reconstructed.

Later PsyArXiv record versions must not be silently collapsed into version 1. For example, the cognitive-conflict match is `b83mn_v2` at +7 days, while `b83mn_v1` was public 30 days before receipt. Conversely, a bare OSF identifier can resolve to the latest record and create a false near-date match. The script therefore retains record IDs, record-publication dates, primary-file revision timestamps, and download URLs as separate fields.

These candidates add Communications Psychology and Nature Communications to the discovery pool. They should still undergo content-level matching between each pinned manuscript and the initial reports before evaluation admission; date proximity and matching titles are necessary provenance evidence, not proof of byte-identical journal submission.

A wider-window Nature Communications lead is [“Psychological booster shots targeting memory increase long-term resistance against misinformation”](https://doi.org/10.1038/s41467-025-57205-x): received 4 April 2023; PsyArXiv [`6r9as_v1`](https://api.osf.io/v2/preprints/6r9as_v1/) public 17 April 2023, a **+13-day** record-level gap. It is retained as a lead rather than counted among the five records above; later `v2` and `v3` records from 2025 must not be substituted for it.
