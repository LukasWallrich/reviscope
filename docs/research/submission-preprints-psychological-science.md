# Psychological Science submission–preprint matches

## Scope and result

This is a bounded, purposive search for empirical *Psychological Science* papers whose first identifiable preprint version was posted near the journal's reported receipt date. It is not a complete census. The search used DOI relations as leads, then checked the publisher-reported received date against the creation time of a specific historical preprint file. A date match is only a discovery screen: it does not establish that the preprint and submitted manuscript are substantively identical.

The search produced **one same-day candidate**, one candidate within the protocol's **±30-day sensitivity window**, and one wider-window lead. Thus it contributes one candidate to the requested ±7-day set, not two or three. *Psychological Science* does not generally supply public peer-review reports through its article pages, so these candidates address manuscript acquisition only. They are not a human-review comparison set.

## Candidate pairs

| Article | Journal receipt | Historical preprint file | Calendar-day gap | Classification and next check |
|---|---:|---:|---:|---|
| Salvador et al., “Relational Mobility Predicts Faster Spread of COVID-19: A 39-Country Study” ([article DOI](https://doi.org/10.1177/0956797620958118); [PsyArXiv DOI](https://doi.org/10.31234/osf.io/gwpj3)) | 2020-04-13 ([publisher article](https://journals.sagepub.com/doi/10.1177/0956797620958118)) | Publicly posted 2020-04-13 22:21 UTC; file created 22:18 UTC ([OSF preprint record](https://api.osf.io/v2/preprints/gwpj3/); [OSF v1 metadata](https://api.osf.io/v2/files/5e94e54cf1353503ded53077/versions/1/); [pinned v1 PDF](https://osf.io/download/52seu/?revision=1)) | **0 days** | `temporal_proxy_unconfirmed`. The timing evidence is strong. V1 says “37 country study” while the published paper says 39-country study, an expected kind of review-stage change that should be recorded in a frozen difference map rather than treated as an exclusion by itself. |
| Pfattheicher et al., “The Emotional Path to Action: Empathy Promotes Physical Distancing and Wearing of Face Masks During the COVID-19 Pandemic” ([article DOI](https://doi.org/10.1177/0956797620964422); [PsyArXiv DOI](https://doi.org/10.31234/osf.io/y2cg5)) | 2020-04-15 ([publisher article](https://journals.sagepub.com/doi/10.1177/0956797620964422)) | Publicly posted 2020-03-23 10:44 UTC; file created 10:39 UTC ([OSF preprint record](https://api.osf.io/v2/preprints/y2cg5/); [OSF v1 metadata](https://api.osf.io/v2/files/5e7891cb0cd06c06ac002638/versions/1/); [pinned v1 PDF](https://osf.io/download/zqymd/?revision=1)) | **−23 days** | ±30-day sensitivity candidate. The v1 title and apparent scope concern physical distancing; the final title also covers mask wearing. It requires a substantive concordance audit before inclusion. |
| Nussenbaum et al., “Sensitivity to the Instrumental Value of Choice Increases Across Development” ([article DOI](https://doi.org/10.1177/09567976241256961); [PsyArXiv DOI](https://doi.org/10.31234/osf.io/exps6)) | 2023-09-13 ([publisher article](https://journals.sagepub.com/doi/10.1177/09567976241256961)) | 2023-06-27 16:02 UTC ([OSF v1 metadata](https://api.osf.io/v2/files/649b080e3809110c143c2ccd/versions/1/); [pinned v1 PDF](https://osf.io/download/2tguz/?revision=1)) | **−78 days** | Wider-window lead only. It is outside both ±7 and ±30 screens and should remain separately labelled unless stronger provenance links v1 to the submitted version. |

Negative checks were informative. DOI-linked preprints for “Behavioral Immune Trade-Offs,” “Do People Prescribe Optimism?,” “Behavioral Consistency,” and “Exact Number Concepts” were posted well after receipt or around acceptance, or beyond the sensitivity window. A DOI relation therefore cannot substitute for version and timing checks.

## Reproducible provenance rules

OSF's preprint record can retain its original publication date while its `primary_file` relationship points to a later upload. For each candidate above, the evidence is therefore the file-version endpoint and a revision-pinned download (`?revision=1`), not the current primary-file download or the preprint landing-page date alone. The local research copies were retained only in the ignored evaluation cache, with these SHA-256 hashes:

- `gwpj3` revision 1: `9518597d974bde5f7eb5a5222534770e0cefff54a0b107dad076579ba35613fe`
- `y2cg5` revision 1: `b02e282ad8655115cefa32bba8233d9518d220a00aa1bdf2836a3d9ef131a9cd`
- `exps6` revision 1: `ee13db48186172132aae4e3c7ea4a96f4856e7a4a4ebdd587f14d101ea741b4e`

These are manuscript-source discovery results. The appropriate next step is to freeze a version-difference map before generation so expected review-stage changes can be handled symmetrically during scoring. Contemporaneous human reports were not located for these papers; any future human comparison would need reports obtained separately and matched to the relevant review round. The journal's [submission guidance](https://www.psychologicalscience.org/publications/psychological_science/ps-submissions) should not be read as providing such a public report corpus.
