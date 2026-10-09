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

## Limits

An LLM judge is a measurement under development. The judges may share blind spots with
the reviewers, in particular when the same model family generated a review; run both
families and read the disagreements. Calibration probes show how a judge behaves on
known cases, not its accuracy on new criticism. Clustering without the manuscript can
merge or split issues wrongly; check cluster boundaries on a sample before relying on
issue-level counts. Stable improvements across runs and papers justify human assessment;
they do not replace it. The [validation plan](PIPELINE_VALIDATION_PLAN.md) describes the
human assessment that decisions require.
