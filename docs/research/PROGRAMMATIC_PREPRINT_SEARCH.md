# Programmatic preprint discovery across other journals

Checked 7 September 2026. The searches are bounded samples, not a census. They establish discovery provenance, not automatic evaluation eligibility.

## Result

The strongest additional candidates are **parental emotion regulation**, **motivated perception**, and **cognitive conflict** in Communications Psychology. Each has a preprint version public within seven days of journal receipt and an actually retrieved human-review bundle. Interoception is an adjacent psychology example, and the Nature Communications accuracy-prompts paper is a meta-analysis. A same-day Royal Society Open Science preprint adds a further empirical candidate, but its human-review body remains access-blocked.

| Paper (abbreviated) | Journal | Received | Selected public artifact date | Gap | Human reports |
|---|---|---|---|---:|---|
| [Parental emotion regulation](https://doi.org/10.1038/s44271-026-00469-w) | Communications Psychology | 29 Oct 2025 | 30 Oct 2025, record v1 | +1 | Retrieved; initial decision identifies two reviewers |
| [Motivation biases behavior but not perception](https://doi.org/10.1038/s44271-026-00461-4) | Communications Psychology | 21 Aug 2025 | 21 Aug 2025, record v1 | 0 | Retrieved; initial decision identifies three reviewers |
| [Cognitive conflict is intrinsically rewarding](https://doi.org/10.1038/s44271-026-00462-3) | Communications Psychology | 22 Aug 2025 | 29 Aug 2025, record v2 | +7 | Retrieved; initial decision identifies four reviewers |
| [Interoceptive ability across respiratory and cardiac axes](https://doi.org/10.1038/s44271-026-00404-z) | Communications Psychology | 21 Mar 2025 | 19 Mar 2025, record v1 | −2 | Retrieved; adjacent psychophysics |
| [Accuracy prompts are replicable and generalizable](https://doi.org/10.1038/s41467-022-30073-5) | Nature Communications | 14 Oct 2021 | 15 Oct 2021, underlying file revision 6 | +1 | Retrieved; meta-analysis, not a new single empirical study |
| [Seductive allure of neuroscience explanations](https://doi.org/10.1098/rsos.241120) | Royal Society Open Science | 2 Jul 2024 | 2 Jul 2024, record v1 | 0 | Review identifiers located; report body not retrieved |

Full artifact URLs, timestamps, hashes, page counts and qualifications are in the linked source notes below. No new model reviews were run, and these papers have not been automatically admitted to the evaluation corpus.

## What ran

- [Nature-family search](programmatic-nature-matches.md): 120 Communications Psychology papers, plus an 8-paper relevance-ranked Nature Communications misinformation query. A preliminary 120-record Nature Communications broad-query pass was unproductive; it is not counted as 120 additional unique papers here.
- [Royal Society search](programmatic-royalsociety-matches.md): 150 papers in the documented 2021–2024 slice; 87 retained by a broad topic heuristic and 16 title-matched preprints. Only one manually checked target-domain paper met the seven-day screen. Earlier recent-issue exploratory runs are not added to this denominator.
- [Psychology-journal DOI-relation search](programmatic-psychology-matches.md): 100 recent papers across European Journal of Personality, QJEP, Journal of Community Psychology and BMC Psychology. Four EJP articles had explicit preprint DOI relations; no fully qualified pair emerged. Absence of an explicit relation is not evidence of absence of a preprint.

These routes trade coverage against precision. DOI relations provide strong identity leads but miss unlinked preprints. Title-and-author matching recovers more candidates but requires identity checks. Received dates come from publisher HTML or structural full-text XML. OSF record versions and underlying file revisions are separate and must both be pinned.

## Reuse and validation

Scripts:

- `eval/discover_submission_preprints.py`: journal ISSN/query, Crossref title-and-author candidates, OSF version histories, Nature publisher dates and review links, JSON/CSV output.
- `eval/discover_royalsociety_preprints.py`: Europe PMC cohort/full text and Crossref preprint matching.
- `eval/discover_psychology_preprints.py`: explicit DOI-relation matching across the four psychology journals.

Each script exposes `--help`. Successful requests are cached where implemented; requests are throttled/backed off and failed queries are distinguished from negative matches in the documented outputs. See per-route limitations rather than assuming complete retrieval.

The Royal Society date parser initially crossed XML date elements. Independent source checking caught the resulting false Towner match; structural parsing replaced the regex, all 16 matched dates were recomputed, and a regression test passes. Towner's actual received date is 17 January 2024, so its July preprint is excluded (+195 days). This is why the final shortlist uses source-checked records rather than raw date rankings.
