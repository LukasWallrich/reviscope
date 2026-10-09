# Open-review comparisons for pipeline development

## Selected submitted manuscripts and reports

The [curated manifest](../eval/corpus/open_peer_review_curated.v1.json) contains
six Meta-Psychology submissions and twelve first-round expert reports. Each
submitted file is downloaded and hash-pinned. Review quality screening consists
of reading the reports, identifying substantive and actionable criticism, and
checking their connection to the supplied submission. It is not a certification
that every criticism is correct. These purposively selected cases support
development comparisons rather than population estimates of review quality.

| Submitted paper | Genre / profile | Selected reviewers | Useful assessment dimensions |
|---|---|---|---|
| [Group membership and deviance punishment](https://doi.org/10.15626/MP.2021.2764) | Six experimental studies / `social_psychology` | Rima-Maria Rahal; Deliah Sarah Bolesta | Construct interpretation, group identification, scoring, within-subject analysis and incomplete analysis reporting |
| [Mortality salience](https://doi.org/10.15626/MP.2020.2628) | Two experiments / `social_psychology` | Adrien Fillon; Artur Nilsson | Theory-to-design alignment, distraction timing, preregistration, interaction analysis and interpretation of null results |
| [Direct versus indirect harm](https://doi.org/10.15626/MP.2019.2134) | Two replication experiments / `social_psychology` | Arvid Erlandsson; Daniël Lakens | Response recoding, numerical comparisons, sample-size justification, replication fidelity and reproducibility |
| [Multiverse analyses in the classroom](https://doi.org/10.15626/MP.2020.2718) | Education tutorial / `education` | Julia Rohrer; Thomas Nordström | Calibrated feedback, the relationship of model choices to moderators, instructional audience and actionable teaching design |
| [Longitudinal measurement invariance and CLPM](https://doi.org/10.15626/MP.2020.2595) | Statistical tutorial / `quantitative_social_science` | Sacha Epskamp; Ulrich Schimmack | Invariance interpretation, within/between-person inference, model representation and instructional scope |
| [Publication bias in PTSD meta-analyses](https://doi.org/10.15626/MP.2018.884) | Empirical meta-research / `quantitative_social_science` | Katie Coburn; Felix Schönbrodt | Assumptions and power of bias diagnostics, selection models, effect magnitude and sensitivity-analysis feasibility |

The primary report IDs in the manifest are `bolesta`, `nilsson`, `lakens`,
`nordstrom`, `epskamp` and `schonbrodt`, respectively. The other report remains
available as an additional comparator. Retain each report separately and aggregate
comparisons by paper; two reviewers of one manuscript do not supply two
independent papers.

Meta-Psychology's [publication policy](https://open.lnu.se/index.php/metapsychology/about)
describes its public editorial workflow and expert peer review. The archive is
particularly useful because it distinguishes submitted files, reports, responses
and revisions. Open reviews attached to a published article are insufficient by
themselves: the source under review must also be identifiable.

All six cases are development data. [Corpus splits](CORPUS_SPLITS.md) assigns
these and the newer cases to development, judge-calibration, fenced-validation
and excluded splits.

## Version correspondence

The manifest records archive locations, raw-file SHA-256 values and explicit
version evidence. These are submitted manuscripts, not the articles linked by
DOI in the table.

* Bonetto's original DOCX is dated 21 January 2021; the two reports are dated
  16 February and 29 March. The archive separately names revised manuscripts.
  Its `2674-Manuscript.docx` filename differs from journal identifier 2764;
  document title and archive project establish the correspondence.
* Sætrevik's initial PDF is dated 30 September 2020, before Nilsson's dated
  9 November report. The archive names a separate revised-after-review file,
  and both reports are labelled Review 1. Their hypothesis and power-analysis
  references match the submitted pages.
* Ziano's archive has separate Submission and Review round 1 components.
  Both reports match the submitted response-recoding passage; Lakens identifies
  the table's `t(45) = 0.00` comparison. The reports share a PDF but are separated
  into two comparator texts.
* Heyman's original PDF is dated 10 December 2020. The reports match the original
  page-specific statements about moderators, course structure and evaluation.
  The additional Zigerell open comment is not included because its round is not
  assigned in this curation.
* Mackinnon's original PDF is dated 22 July 2020 and is separate from the revision.
  The reviews quote its scalar-invariance explanation and invariant-facets
  statement. Diagram criticisms refer to this tutorial version.
* Niemeyer's archive separates Submission, Review Round 1 and Review Round 2.
  The original DOCX is dated 7 June 2018. Its first-round review bundle contains
  an editor letter and two expert reports; only the expert reports are selected.
  Their quoted selection-model rationale and dataset descriptions match the
  submitted text.

Names, dates and editorial recommendations are removed from comparator headers;
declared signature lines are removed. Substantive comments, praise, caveats,
references and optional suggestions are retained. Report boundaries in combined
files are explicit and validated, rather than inferred by a model.

The source files are public downloads. The journal article pages state CC BY 4.0;
separate redistribution terms for raw submissions and reports are not established
here. The repository publishes metadata and preparation code. Raw files and
extracted review texts remain in the ignored local cache.

## Preparation

```sh
.venv/bin/python eval/prepare_open_reviews.py
```

This verifies every raw-file hash before use, extracts the submitted manuscript,
separates bundled reports and writes anonymized comparator texts plus parser
versions and text hashes. `fonttools` supports the embedded CFF font encodings
used by some PDFs. Files are under
`eval/corpus/cache/open-review-curation-20261002/<cache_key>/`:

* `manuscript/original.pdf` or `original.docx`: the generation input;
* `manuscript/original.txt`: extracted source for text inspection;
* `human-reviews/`: downloaded reports, including combined source files;
* `comparators/<review_id>.txt`: individual, anonymized judge references;
* `prepared.json`: exact local inputs and hashes.

Only the manuscript, with separately version-checked supplements if available,
goes to review generation. Do not supply human reports, quality notes, editor
letters, responses or revised manuscripts to reviewers. A curator can inspect
these materials without transmitting them to a review-model session.

## Comparison design

Start with the Bonetto, Sætrevik and Ziano cases for experimental social psychology.
Use Mackinnon and Niemeyer to test technical depth and Heyman to test genre
adaptation and restraint. The supplied submission is the common reference for
every comparison.

Compare a plain tool-enabled Sol review and the candidate pipeline against each
selected human report, rather than only comparing the AI systems with each other.
Use the existing pairwise comparison command, which strips application metadata,
swaps presentation order, permits ties and judges correctness, importance,
specificity, source grounding and actionability. Judges run without tools.
`claude-opus-5-5` at high effort supplies the primary different-family judgment;
`gpt-6.1-sol` at high effort can check sensitivity to judge family. Neither repeated
orders nor additional reports count as independent papers.

For the Bonetto case, after a candidate review is complete:

```sh
.venv/bin/python -m reviscope.cli evaluate compare \
  --paper-id metapsych-bonetto-2764-round1 \
  --manuscript eval/corpus/cache/open-review-curation-20261002/bonetto/manuscript/original.txt \
  --candidate runs/bonetto/review.json \
  --reference eval/corpus/cache/open-review-curation-20261002/bonetto/comparators/bolesta.txt \
  --reference-kind human_review \
  --backend claude --model claude-opus-5-5 --effort high \
  --output runs/bonetto/comparison-bolesta-opus.json
```

The existing comparison reader includes published findings. Record unconfirmed
author-visible concerns separately, rather than adding them to that condition's
score. A separate complete-report condition can test whether well-labelled
unresolved concerns are useful. Original and audited normalized conditions can
check representation effects; normalization preserves every substantive issue
and has no finding limit.

Human reports are comparators, not an answer key. For example, categorical claims
about t-tests on recoded outcomes, generic difference-score prohibitions and
unverified advice about pooling heterogeneous datasets deserve the same scrutiny
as model advice. A judge should not reward a criticism merely because it also
appears in a human report, or reward length and number of issues. Claims requiring
external material may remain uncertain when the judge only has the manuscript.

PDF diagrams also impose a practical limit: Mackinnon's arrow-direction comments
cannot be established from extracted text alone. Preserve the PDFs and distinguish
diagram-dependent judgments from text-grounded ones. A small tool-enabled
verification of disputed criticisms can investigate correctness separately from
the tool-free preference judgments.
