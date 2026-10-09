# Corpus splits

[`splits.v1.json`](../eval/corpus/splits.v1.json) assigns every inventoried
manuscript to exactly one split. The sampling unit is the paper: repeated runs,
judges or reports of one paper never count as more papers.

| Split | Use | Cases |
|---|---|---:|
| `development` | Iterate freely. Holds every previously exposed case. | 29 |
| `judge_calibration` | Calibrate the judge and judge–human agreement only; do not tune the reviewer on these cases. | 7 |
| `fenced_validation` | Untouched until the single human validation. | 11 |
| `excluded` | Inventoried but unusable; reason recorded per case. | 9 |

The target population is ordinary empirical quantitative social psychology:
experiments, surveys and replications. Report other genres separately.

| Genre | Development | Calibration | Fenced |
|---|---:|---:|---:|
| Ordinary empirical (social/personality, attitudes) | 6 | 2 | 11 |
| Ordinary empirical, adjacent domain | 2 | – | – |
| Methodological, meta-research, psychometric | 5 | 2 | – |
| Tutorials | 2 | – | – |
| Stage 2 registered reports | 3 | 3 | – |
| Dawes planted-error papers | 10 | – | – |
| Owner reanalysis (`owner-negativity`) | 1 | – | – |

Stage 2 registered-report reviews check a completed study against an accepted
protocol. That is a different review task, so these cases are never fenced.

## Inventory and exposure

Each case records its exposure history from `runs/` and git history in the main
checkout. Inventoried on 9 October 2026:

* All ten Dawes papers have Litvak gpt-5.5 reviews. Papers 05 and 09 also have
  plain, pipeline, discovery and retrieval arms; 08 was in the alpha pilot; and
  01, 04, 05, 07 and 10 are in `judge-calibration-20261009`.
* Bonetto and Ziano were used in `pipeline-redesign-20261003` and its
  comparisons, and Bonetto also in `dev-0.5.0`. Both appear in the
  `judge-calibration-20261009` judgments.
* The other four curated Meta-Psychology cases have not been run. The owner
  designated the whole curated corpus as training/development data on 5 October,
  so they are development.
* PeerJ 236 and the two z-curve papers were used in the September alpha pilot.
* `owner-negativity` had a specialist run on 9 October. It is listed by case ID
  only because the repository is public.
* None of the 27 newly verified cases has been run.

## New cases and version correspondence

Twenty-seven new cases have an exact first-round submission and public
first-round reports.

* **Meta-Psychology, 10 cases.** Sources are the journal's OSF editorial archive
  nodes `MP.YYYY.NNNN`, enumerated by OSF title search (261 nodes, including
  rejected and unpublished submissions). A case is admitted only if:
  * the submitted manuscript is a single-version file, uploaded at archive
    creation or held in a `Submission` folder;
  * the revised manuscripts are separately named;
  * round-1 reports are dated after the submitted file;
  * automated matching finds the reports' quotations and statistics in the
    submitted file.

  The matching printed only the review-side strings.
* **PeerJ, 11 cases.** Each case uses the Version 0.1 "Reviewing Manuscript"
  PDF, recovered from Internet Archive captures because the live site returns
  403. Its footer carries the receipt date and revision index 0. Report line
  references and quotations match the PDF. Each report is split from the archived
  review-history page by a deterministic extractor. The extractor's output hashes
  are recorded.
* **PCI Registered Reports Stage 2, 6 cases.** The OSF file revision named by
  the round-1 report is pinned, and quotations and page references match it.
  Four further cases are excluded: three manuscripts lack a licence (two of
  them also have an uncaptured report) and one report set is incomplete.

Each case's `version_evidence` records the evidence, and the manifest's
`unverified_candidates` lists what failed. Common reasons are a submitted
file missing from the archive, streamlined review based on another journal's
reports, reports summarised only by an editor, Stage 1
proposals, preprint-only proxies, and truncated captures.

Licences: Meta-Psychology articles and newer archive nodes are CC BY 4.0, and
PeerJ articles and review histories are CC BY. The PCI reviews and the retained
manuscripts are CC BY. Raw files are used locally for research and are never
committed.

## Fence rule

The rule is recorded in `split_rule` and recomputed by
`.venv/bin/python eval/corpus_splits.py --show`.

1. Before the draw, eligibility and the journal-family stratum were frozen from
   metadata and version checks. A case is eligible if it has a verified exact
   submission and all first-round reports, is ordinary empirical social or
   personality research, and was never run, judged or curated for quality.
2. Within each stratum, order cases by `sha256("reviscope-splits-v1-20261009|" + id)`.
   The first ⌈2n/3⌉ are fenced, and the remainder alternate between
   `judge_calibration` and `development`. This gives 5 of 7 Meta-Psychology cases
   and 6 of 8 PeerJ cases.
3. Cases that are verified but not eligible are ranked the same way within their
   stratum and alternate between `development` and `judge_calibration`.
4. All other assignments are fixed and carry a recorded reason.

## Storage

```sh
.venv/bin/python eval/fetch_split_sources.py                               # development + calibration
.venv/bin/python eval/fetch_split_sources.py --split fenced_validation      # raw files only
```

Development and calibration sources go to
`eval/corpus/cache/corpus-splits-v1/<id>/`. That directory holds `manuscript/`
with the extracted text, `human-reviews/`, anonymized `comparators/` and
`prepared.json`.

Fenced raw files go only to `eval/corpus/fenced/<id>/`, which its own
`.gitignore` keeps out of git. Nothing is extracted beside them. Every download
is checked against its hash.

Curated, Dawes, PeerJ 236 and owner cases keep their existing preparation
scripts and caches.

## Fence guard for run drivers

[`eval/check_fence.py`](../eval/check_fence.py) exits 3 if a manuscript or run
directory touches a fenced case. A match on any of the following always refuses:

* a fenced file or extracted-text hash, as a file or recorded inside one;
* a fenced source URL;
* a fenced case ID.

A fenced DOI or title refuses in a generation input. These are files passed
directly, or files under an `inputs/` or `manuscript/` directory. Elsewhere,
such as a web-search citation in a review, it only warns.

Drivers should call the guard twice:

* before generation, on each manuscript:
  `from check_fence import assert_not_fenced; assert_not_fenced(manuscript)`, or
  `.venv/bin/python eval/check_fence.py <manuscript>`;
* before judging, on the run root.

The guard ignores copies of `splits.v*.json` and itself in code snapshots. OSF
listing dumps such as `runs/open-review-discovery-20261002` name fenced archive
nodes and are correctly refused. They are discovery metadata, not runs.

The single validation run is the only process that may read
`eval/corpus/fenced/`. It should skip the guard, and only that run. Record the
`splits.v1.json` hash in its provenance.
