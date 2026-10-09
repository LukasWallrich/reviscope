# Criticism-level judge

Status: development instrument. Its labels come from language models and have not been
checked against expert adjudication. Use it to compare pipeline versions with a plain
baseline while developing; it does not validate any configuration.

Whole-report preference rewards length, structure and polish. This judge assesses each
criticism separately, without its origin, severity label or verification badge, and
counts supported, material and harmful criticism per run.

## Usage

One invocation judges one paper. Repeat `--arm` with the same name for several runs of
one arm:

```bash
uv run reviscope judge-criticisms --paper-id ziano \
  --manuscript eval/corpus/cache/open-review-curation-20261002/ziano/manuscript/original.txt \
  --arm specialist=runs/a/ziano/review.json --arm specialist=runs/b/ziano/review.json \
  --arm plain=runs/plain-1/ziano/review.json --arm plain=runs/plain-2/ziano/review.json \
  --out runs/criticism-judge/ziano

uv run reviscope judge-summary runs/criticism-judge/*/result.json \
  --output runs/criticism-judge/summary.json
```

The defaults are two tool-enabled judges, `codex:gpt-6.1-sol:high` and
`claude:claude-opus-5-5:high` (`--judge BACKEND:MODEL:EFFORT`, repeatable), a tool-free
Sol clusterer and a tool-free Opus normalizer for free-text reports. Each paper writes
`result.json` and `summary.md`; `judge-summary` writes JSON and Markdown across papers.
Exit status 2 marks a partial result.

`judge-calibrate --probes eval/probes/criticism_probes.v1.json` judges labelled probes
and prints a confusion matrix per judge family. Persuasion sensitivity is the share of
`variant_of` pairs whose correctness label changes when only the rationale's
persuasiveness changes; pairs with manipulation `none` are neutral-rewrite controls.
Members of one variant family are never judged in the same call.

## Stages

**Extraction.** A pipeline `review.json` contributes what the report shows the author:
published findings and the concerns the verifier could not confirm. Remedies follow the
report: a withheld remedy, and every unresolved concern's remedy, is omitted. A plain
review contributes every issue, in the Dawes or the general format; a remedy is used when
present. A free-text report is normalized into atomic issues with the normalization
prompt, and strengths are excluded. Each variant receives an opaque content-hashed id;
arm, run, module, display status, severity and the anchoring of its own quotations are
stored separately and never reach a model.

**Clustering.** One tool-free call groups the pooled variants of all arms and runs,
shuffled with a fixed seed. Variants belong together only when they raise the same
underlying defect and the same consequence. The clusterer sees claims, rationales and
quoted passages, not the manuscript. Every variant must be assigned exactly once: a
violation gets one retry that names it; a second violation is repaired deterministically
(singletons for missing ids) and marks the result partial. Pools above
`--cluster-batch-size` are clustered in batches and merged in one further call.

**Judging.** Each judge receives the full manuscript and supplements with their
SOURCE_IDs and batches of about seven variants in random order, presented as untrusted
claims, rationales, remedies and quotations. Judges run with the review stages' sandboxed
tools and are told not to look for reviews or other versions of the manuscript. For each
variant they return separate verdicts on the factual premise, the inference and the
stated consequence; materiality 0–3; remedy necessity, proportionality and validity;
concrete benefit for suggestions that allege no error; and flags for generic criticism
and for restating a limitation the manuscript already acknowledges. Correctness is
derived from the three parts: supported only if every stated part holds, contradicted if
any part is shown false. The judge's own overall label is kept as `stated_correctness`.
Judge quotations are anchor-checked and recorded; anchoring does not change the verdict.

Every model call is cached on its complete instruction, inputs, schema and backend
identity, with tool calls in a sidecar. Judgments are also indexed by the variant's
rendered content, so adding a run judges only its new variants. A failed judge batch is
recorded and its variants are retried once; variants still without a judgment make the
result partial and are counted as `not_judged`.

## Metrics

Each judge family is reported separately. With two or more families, the combined view
is conservative: supported only if every judge says supported, contradicted if any does,
the lowest materiality for benefit counts and the highest for harm.

Per paper, arm and run, for author-visible output and for published findings only:

* `supported_rate`: supported / judged variants; `supported_of_resolved`: supported /
  (supported + contradicted); `unresolved_rate`; contradicted count. Not-assessable
  variants stay in the denominator. Never read `supported_of_resolved` alone: deferring
  hard criticisms raises it.
* `supported_material`: supported with materiality ≥ 2.
* `supported_beneficial_suggestions`: supported, alleging no error, with concrete benefit.
* `serious_harms`: contradicted, or a disproportionate or invalid remedy, where the stated
  severity is major or critical or the materiality is at least 2.
* `generic` and `restates_own_limitation` counts.
* `output_words`: words of the author-visible criticism text (claim, rationale, shown
  remedy, quotations) for structured outputs; the whole report for free-text reports.

Issue level, from the clusters: clusters with at least one supported variant per arm and
run; unique supported material issues per arm (a supported material variant from that arm
and none from any other arm), with a stricter count requiring no variant at all from
other arms; and, for pipeline arms, which modules produced those unique issues.
Stability gives, for every cluster and arm, the share of runs that raised it.

Agreement between judge families: raw agreement and Cohen's kappa on correctness,
linear-weighted kappa on materiality, and a list of disagreements (different correctness
or materiality differing by two or more).

`judge-summary` averages runs within a paper and then papers, so the paper is the unit,
and lists every paper's row. It reports no significance tests.

## Owner validation packet

The author of a judged manuscript can label its criticisms blind; his labels calibrate the
judges and give a first human estimate per arm.

```bash
uv run python eval/owner_packet.py build runs/criticism-judge/p/result.json --out packet.html \
  [--seed N] [--max-variants 80]
uv run python eval/owner_packet.py score runs/criticism-judge/p/result.json owner-labels-ID.json \
  --out runs/criticism-judge/p/owner-report.json
```

`build` writes one self-contained HTML file: no network requests, autosave in the browser's
local storage, export and import of labels as JSON. Issues (clusters) and the criticisms within
them appear in seeded random order as "Issue 7, criticism B", with claim, reasoning, remedy,
quoted passages and cited outside sources. The packet contains no origin (arm, run, module,
status, severity, verification), no judge output and no cluster label; the build refuses to
write a file in which any of these strings occurs outside the criticism text itself and the
fixed template. Style still differs between formats (plain issues have no separate reasoning,
pipeline findings may cite outside sources), so blinding is to labels, not to style. The packet
embeds the SHA-256 of `result.json`, the variant ids and, when sampled, each cluster's inclusion
probability. With `--max-variants`, a larger pool is sampled by whole clusters: strata are the
sets of arms present in a cluster, each stratum keeps at least one cluster, and one sampling
fraction is chosen so that the expected number of criticisms stays within the target (cluster
sizes vary, so the realized number can exceed it).

Per criticism the owner records correctness (correct; partly correct, a substantive part is
wrong; incorrect; cannot tell), materiality if true (0 cosmetic to 3 undermines a primary claim,
the judge's scale), the requested action (essential, would strengthen, extension beyond scope,
wrong or harmful, none given), whether he would act on it (yes, no, already addressed) and an
optional note; per multi-criticism issue, whether the criticisms raise the same issue.

`score` checks that the labels belong to this `result.json` and to a rebuild of the same packet,
then maps the owner's correctness onto the judge's scale. Strict (the complete-criticism rule):
correct is supported, partly correct and incorrect are contradicted, cannot tell is unresolved.
Lenient counts partly correct as supported. Per judge family and the combined view it reports a
judge-by-owner confusion matrix, raw agreement and Cohen's kappa (strict and lenient), agreement
and linear-weighted kappa on materiality, and every disagreement with its text and the owner's
note. Per arm and run it reports the owner-labelled supported rate (strict and lenient),
contradicted, partly correct and cannot-tell counts, supported material criticisms (materiality
≥ 2), would-act and already-addressed counts and wrong-or-harmful remedies. Sampled packets are
weighted by inverse inclusion probability, so counts estimate pool totals; only fully labelled
criticisms count. The cluster check gives the share of multi-criticism clusters the owner would
split. One rater on his own manuscript is a first estimate with an interested rater, not a
validated accuracy; agreement is computed on the packet's criticisms without weights.

## Calibration, 9 October 2026

Both default judges were run on the 48 probes in `eval/probes/criticism_probes.v1.json`
(40 base probes and 8 persuasion variants; labels from documented project verification,
not independent experts). Archive: [`docs/judge-calibration/calibration-20261009.json`](judge-calibration/calibration-20261009.json).

| Judge | Accuracy | False criticisms supported | Persuasion: labels changed |
| --- | ---: | ---: | ---: |
| Sol (`codex:gpt-6.1-sol:high`) | 44/48 | 0 of 21 | 1 of 8 |
| Opus (`claude:claude-opus-5-5:high`) | 41/48 | 1 of 21 | 0 of 8 |

The judges err in opposite directions. Sol is conservative: it left two documented
numerical inconsistencies and one availability problem unresolved. Opus is lenient: it
supported three probes that need an external source the probe set treats as unsettled,
and it supported a true headline whose supporting calculation is wrong, the failure the
complete-criticism rule targets. Both settled a source-specific assertion that the probe
labels unresolved. The conservative combined view (supported only when both judges
agree) therefore suits development comparisons; read Sol's unresolved labels as possible
misses rather than as evidence against a criticism. Forty-eight probes from eight
manuscripts, several drawn from the same audit, give only a coarse picture.

## Limits

An LLM judge is a measurement under development. The judges may share blind spots with
the reviewers, in particular when the same model family generated a review; run both
families and read the disagreements. Calibration probes show how a judge behaves on
known cases, not its accuracy on new criticism. Clustering without the manuscript can
merge or split issues wrongly; check cluster boundaries on a sample before relying on
issue-level counts. Stable improvements across runs and papers justify human assessment;
they do not replace it. The [validation plan](PIPELINE_VALIDATION_PLAN.md) describes the
human assessment that decisions require.
