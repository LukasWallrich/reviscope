# Programmatic Royal Society preprint matches

Checked 7 September 2026. The reproducible discovery script is [`eval/discover_royalsociety_preprints.py`](../../eval/discover_royalsociety_preprints.py). It uses Europe PMC article/full-text XML and Crossref posted-content metadata; it does not read human reviews or call a model.

## Search denominator

The bounded 2021–2024 run retrieved 75 records each for Royal Society Open Science and Proceedings B: **150 papers screened**. A broad title/abstract heuristic retained **87** social, cultural, behavioural or cognitive records. Crossref title search produced **16** posted-content matches at similarity ≥0.86. After correcting a date-parser defect and recomputing all 16 dates from Europe PMC XML, five fell within ±30 days and three within ±7 days. Two of the three close matches were biological or archaeological. **One target-domain match was within ±7 days.**

This is a reproducible discovery screen, not a complete census. Europe PMC ordering limits the sampled slice; title heuristics can miss relevant work; Crossref may omit preprints or dates; and title similarity alone can produce false matches. Authors were manually checked for the two candidates below. The retained historical result predates the script's explicit `query_failures` counter, so its exact failure count is unavailable; subsequent runs record HTTP failures and slow Crossref requests to reduce shared-pool rate pressure. Retrieval failures and unmatched records are not evidence that no preprint exists.

## Candidate 1: classroom neuroscience-explanation replication (0 days)

Väth et al., *Replicating the ‘seductive allure of neuroscience explanations’ effect in a classroom experiment and an online study*, Royal Society Open Science, DOI [10.1098/rsos.241120](https://doi.org/10.1098/rsos.241120).

- Europe PMC full-text history reports **received 2 July 2024**.
- PsyArXiv [j74mw v1](https://api.osf.io/v2/preprints/j74mw_v1/) reports publication on **2 July 2024 at 17:48 UTC**: gap **0 calendar days**.
- The sole primary-file revision was created 2 July at 17:07 UTC. Pinned download: [revision 1](https://osf.io/download/2knvx/?revision=1).
- Cached only under ignored `eval/corpus/cache/royalsociety-preprints/sane-j74mw-v1.docx`: 248,716 bytes; SHA-256 `04083b6708a4bfe4073c43e5251d4600446db42863ba0244e891b015089e60f5`.
- Article title and preprint title match after punctuation/case normalization; the author record was manually confirmed.
- The current Royal Society policy makes publication of RSOS peer-review information mandatory. The article's review-history gateway is [indexed here](https://www.webofscience.com/api/gateway/wos/peer-review/10.1098/rsos.241120), but anonymous HTTP retrieval redirected to a generic Web of Science record rather than returning the review payload. Review-file accessibility therefore remains **indexed/access-blocked**, not locally verified.

This is a strong ordinary empirical psychology candidate: a classroom experiment and online study, with same-day public preprint provenance. It remains unadmitted until the review history is retrieved and the selected round is substantively matched.

## Rejected date match: adolescent social isolation and threat learning (+195 days)

Towner et al., *Increased threat learning after social isolation in human adolescents*, Royal Society Open Science, DOI [10.1098/rsos.240101](https://doi.org/10.1098/rsos.240101).

- The publisher-derived Europe PMC history reports **received 17 January 2024**, revised 12 July, and accepted 27 August. An earlier regex crossed XML date-element boundaries and incorrectly combined the revision month with the acceptance day to produce 27 July; the parser now reads the `date-type="received"` element structurally and has a regression test.
- PsyArXiv [hsx2q v1](https://api.osf.io/v2/preprints/hsx2q_v1/) reports publication on **30 July 2024 at 19:40 UTC**: gap **+195 calendar days**, so this paper is not a near-submission candidate.
- The mutable OSF primary file now points to an October revision. File revision 1 was created 30 July at 19:33 UTC and must be pinned: [revision 1](https://osf.io/download/9dynm/?revision=1).
- Cached only under ignored `eval/corpus/cache/royalsociety-preprints/threat-learning-hsx2q-v1.pdf`: 2,512,519 bytes; SHA-256 `19bbe3d37f63e820f9496bcb91cb22c8172581be222661cfbce49acc803dcf4a`.
- Titles match exactly after punctuation normalization and the author record was manually confirmed.
- RSOS mandatory-review policy applies. The [article review-history gateway](https://www.webofscience.com/api/gateway/wos/peer-review/10.1098/rsos.240101) was indexed, but anonymous retrieval redirected to a generic Web of Science record. Treat review contents as **indexed/access-blocked** until directly recovered.

This otherwise relevant empirical developmental/cognitive paper is excluded from the near-submission shortlist. It still illustrates why `_v1` in an OSF preprint URL is insufficient: the underlying primary file has four revisions, and an unpinned download returns a post-review replacement.

## Other near-date results

After structural date reparsing, the RSOS methods-paper lead *The Systematic Multiverse Analysis Registration Tool* is −19 days rather than −7. Proceedings B supplied the other close matches, including Atlantic cod trade (−7), mosquito ecology (−4), and bat hearing (+17). They validate the discovery method but do not meet the requested priority for ordinary empirical human social/personality/cognitive studies, so they were not promoted as pilot candidates.

No AI reviews were generated. Before either candidate enters evaluation, retrieve every human report, freeze the target review round, compare the pinned preprint against report-referenced studies and values, and keep review files isolated from generation.
