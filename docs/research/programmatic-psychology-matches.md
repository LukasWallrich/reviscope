# Programmatic psychology preprint matching

## Result

A bounded precision-first search examined the 25 most recent Crossref journal-article records since 2019 for each of four journals (100 records total). It then queried the PsyArXiv DOI prefix and retained only preprints whose Crossref `is-preprint-of` relation pointed back to the exact article DOI. The reusable discovery code is [`eval/discover_psychology_preprints.py`](../../eval/discover_psychology_preprints.py).

The pass found six version-level relations in the *European Journal of Personality* (EJP), representing four articles. It found no explicit relations in the sampled records from the *Quarterly Journal of Experimental Psychology*, *Journal of Community Psychology*, or *BMC Psychology*. These zeroes describe this recent, relation-dependent sample only. They do not show that those journals have no preprints. No request failed in the completed pass.

No actionable ±7-day manuscript-plus-human-review pair resulted. One EJP empirical preprint was publicly posted during revision, one recent empirical paper lacked an independently verified receipt date, and the other EJP hits were reviews or research resources. EJP offers transparent peer review when authors opt in, but a public review-history link was not located for either empirical candidate.

## Candidate audit

| Candidate | Date and version evidence | Receipt comparison | Public review evidence | Disposition |
|---|---|---|---|---|
| Bauditz et al., “Construal and Contact in Person–Situation Relations” ([article](https://doi.org/10.1177/08902070261449352); [PsyArXiv v1](https://doi.org/10.31234/osf.io/yceph_v1)) | PsyArXiv was publicly posted 2026-04-27 16:43 UTC ([OSF record](https://api.osf.io/v2/preprints/yceph_v1/)); its primary file is identifiable through the record's `primary_file` relationship. | Publisher PDF reports received 2025-10-30, revised 2026-04-23, accepted 2026-04-24 ([publisher PDF](https://journals.sagepub.com/doi/pdf/10.1177/08902070261449352)). The public preprint is **179 days after receipt and four days after revision**, so it is not a pre-review proxy. | EJP's [current instructions](https://journals.sagepub.com/author-instructions/erp) describe optional transparent review. No article-specific public history was located. | Ineligible for this comparison; useful negative control showing that an explicit DOI relation need not identify a pre-review version. |
| “Self-Perceptions on Social Media vs. Offline Contrast With Those Perceived in Generalized but Not Close Others” ([article](https://doi.org/10.1177/08902070261470900); [PsyArXiv v1](https://doi.org/10.31234/osf.io/ts7wq_v1)) | V1 was publicly posted 2026-07-13 13:42 UTC ([OSF record](https://api.osf.io/v2/preprints/ts7wq_v1/)); v2 followed on 2026-08-24 ([OSF record](https://api.osf.io/v2/preprints/ts7wq_v2/)). | A publisher-reported received date was not located in the bounded search. The pair cannot be assigned a date gap from publication dates or DOI suffixes. | No article-specific public history was located. | Unresolved discovery lead, not an eligible match. Retrieve the publisher PDF/history before any further use. |

The remaining EJP relations represented a meta-analysis of personality and alternative-medicine preference and the Living SEB Skills review resource. They were excluded at the empirical-paper screen rather than sent to later acquisition steps.

## Method and limits

The script caches successful Crossref responses, records exhausted request failures separately, and enforces a maximum of 100 examined journal works. It uses exact related DOI equality, so fuzzy title similarity cannot create a retained match. Title similarity is recorded only as an audit aid. The output inventory used for this run is stored in the ignored evaluation cache at `eval/corpus/cache/programmatic-psychology-matches.json`.

For any future match, Crossref establishes only a DOI relationship. Eligibility still requires:

1. the preprint's public posting timestamp, rather than an earlier private file-upload time;
2. traversal of every page of the OSF file-versions endpoint to identify and pin the relevant historical file;
3. a publisher PDF or editorial-history source for the selected review round's receipt date;
4. an article-specific public review link; and
5. a frozen substantive difference map before model generation.

This pass did not make AI review calls. The practical next search should use article-level transparent-review indexes or publisher exports first, then look backward for preprints. Beginning from recent journal articles plus explicit Crossref relations was precise but had low recall and did not expose opt-in review histories.
