# Criticism calibration probes (eval only)

`criticism_probes.v1.json` is the verifier calibration set called for in
[the validation plan](../../docs/PIPELINE_VALIDATION_PLAN.md). Each probe is one
reviewer-style criticism of a real manuscript with an expected judgment of its
correctness, materiality and remedy necessity. The probes calibrate judges that assess
individual criticisms. **Never place them in review reports, reviewer prompts or
discovery inputs.**

## Format

```
{"version": 1, "probes": [{"id", "case", "sources": [{"path", "kind"}],
  "criticism": {"claim", "rationale", "remedy", "quotes"},
  "expected": {"correctness", "materiality", "remedy_necessity"},
  "label_basis", "label_source", "variant_of", "manipulation"}]}
```

- `correctness` covers the complete criticism: claim, rationale, calculations and
  stated consequences. A true headline with a wrong supporting calculation or rationale
  is `contradicted`. `unresolved` means the probe sources alone cannot settle it; it needs
  data, code, display equipment or an external publication.
- `materiality` (3 undermines a primary claim; 2 weakens a primary claim or affects a
  secondary claim; 1 local or reporting issue without inferential effect; 0 cosmetic) and
  `remedy_necessity` are labelled only for `supported` probes; they are `null` otherwise.
  They are also `null` for a supported probe where no defensible value could be given
  (`d07-participant-flow` materiality; `zia-comparison-p` remedy).
- `quotes` are verbatim passages from the listed sources. Every quote anchors with
  `reviscope.verification.verify_quote` against `reviscope.ingest.ingest` text. Quotes
  may come from passages that the criticism misreads.
- Persuasion variants (`variant_of` set) copy the base probe's claim, remedy, quotes
  and expected label. They change only the rationale's presentation: added confidence
  (`confident_rationale`), an unverifiable expert endorsement (`authority_appeal`), or
  accurate but irrelevant manuscript details (`irrelevant_detail`).

## Sources

Manuscripts are licensed, under review, or unpublished. The repository therefore stores
only their paths and SHA-256 digests. Materialize the sources before using the probes:

```
.venv/bin/python eval/probes/materialize_sources.py   # optional: --root MAIN_CHECKOUT
```

This copies byte-identical files from the main checkout's gitignored `runs/` and
`eval/corpus/cache/` into the gitignored `eval/probes/sources/`. It also writes
`manifest.json` and aborts on any digest mismatch. The Dawes sources are the
modified-paper review inputs, with the benchmark banner removed, from
`runs/known-errors-all/inputs/paper-NN/`. Their DOCX footnotes are not extracted. The
owner sources are the submitted PDFs. `tests/test_probes.py` checks the schema, ids,
variants and label counts. When sources are present, it also checks the hashes and that
every quote anchors.

## Where the labels come from

The labels come from documented project verification. **No independent expert assigned
them.** An AI agent (Claude) wrote the probes and checked each label against the cited
evidence:

- **Dawes planted-error papers (`dawes-*`, 17 base probes plus 5 variants).** These rest
  on the provisional, AI-assisted, unblinded benchmark audit
  (`docs/benchmark-validity-audit/audit-100.json`, `synthesis.md`,
  `feedback-resolution.md`). Labels follow the audit's narrower defensible criticism, not
  the benchmark annotation. Probes are limited to high-confidence audit rows, plus
  medium-confidence `needs_external_verification` rows used as unresolved probes. They
  still need expert adjudication. The planted alteration itself is privileged knowledge
  and is not used as evidence a reviewer could see.
- **Development numerical checks (`bonetto`, `ziano`).** These rest on deterministic
  recomputation from reported summaries in
  `docs/pipeline-development-analysis/numerical-checks.json`
  (`eval/check_development_numerics.py`). The recomputation shows that the reports
  cannot all be correct. It does not validate the raw data.
- **Owner manuscript (`owner-negativity`, 13 base probes plus 2 variants).** These were
  built from the submitted manuscript and supplement text and from the owner's
  AI-assisted verification notes
  (`negativity_bias_review_20261003/review/verified-findings.md`, outside this
  repository). The owner has not adjudicated them. The case is kept separable so that it
  can be excluded if the owner later adjudicates the same paper. For two of its
  unresolved probes, the verification notes indicate that the criticism is false.
  `unresolved` assumes a judge that cannot open the cited external source. A judge that
  retrieves the source should reach `contradicted` (`own-schafer-direction`,
  `own-coding-manual`). `own-tiebreak-source` is unresolved even for the project because
  the full original article was not accessible.

Rows were excluded where the documents could not support a label. This covers audit
rows whose classification the feedback round disputed (02-10, 09-08, 03-02, 08-05,
10-01, 09-09, 08-08 and 08-10).

## Probe types

| Type | Probes |
|---|---|
| True error, plain | d04-chisq-p, d10-diagnosticity-denominator, bon-thermometer-stats, zia-correlation-stars, zia-half-negative, zia-replication-label |
| True error with defeating-looking context that does not resolve it | d04-attempt-coverage, d07-participant-flow |
| True headline, incorrect calculation or rationale (contradicted) | d04-chisq-p-miscalc, d07-participant-flow-miscalc, d10-diagnosticity-equals-specificity, bon-thermometer-miscalc, zia-half-negative-miscalc |
| Misquoted number | bon-punishment-misquote, own-positive-gap-misquote |
| Purported conflict between compatible passages | d07-bf-stopping, d10-context-balance, own-sample-count-conflict, own-k1-reproduction-mismatch, own-matched-mean-difference |
| Absence claim defeated elsewhere | d07-interference-composition, d10-counterbalancing, own-matched-converted-effects |
| Mischaracterised method | own-codes-ordinal |
| Generic boilerplate that does not apply | own-preregistration-boilerplate, d05-centering (generic centring advice with a false statistical consequence) |
| Correct but immaterial (materiality 0–1) | bon-blame-p, bon-pooled-demographics, zia-comparison-p, own-code-placeholder, own-abstract-matched-sensitivity |
| Valid criticism, disproportionate remedy (`extending`) | d05-geography-remedy, own-contact-measure-remedy (also restates an acknowledged limitation) |
| Source-specific external assertion (unresolved) | d01-sdt-attribution, own-tiebreak-source, own-schafer-direction, own-coding-manual |
| Needs data, model output or equipment (unresolved) | d01-rwa-ci-width, d07-training-stimulus-size, d10-viewing-geometry |

The persuasion variants are based on d04-chisq-p, bon-thermometer-stats and
d07-participant-flow (supported); d10-counterbalancing, d10-context-balance and
own-codes-ordinal (contradicted); and d01-rwa-ci-width and own-schafer-direction
(unresolved).
