# Specialist pipeline development: status and loop

Status on 9 October 2026. The specialist pipeline is the only review strategy. This file
records how it is now developed before a single human validation, what the development
evidence shows so far, and the decisions that belong to the owner. Numbers here come
from LLM judges on development papers; they guide development and validate nothing.

## What changed

**Product.**

* The broad-review strategy and evidence audit are retired (tag `pre-specialist-only-0.4.3`).
  Their operations already belonged to modules; decision-rule reconstruction for central
  claims moved into `interpretation`. Metacheck leads without an owning module now reach
  the blind-spot pass; before, specialist runs dropped them.
* Independent modules and verification batches run concurrently (`--parallel`, default 4);
  outputs and cache keys do not depend on it.
* Discovery labels each remedy essential, strengthening or extending (COPE), the verifier
  checks the label, and reports show it. Reports open with a summary of major and critical
  findings; `review.html` is real HTML.
* `social_psychology_context` checks replications against their original study and the
  order of measures and manipulations.
* Modules are asked to critique as experts, not only check for errors: conclusions that
  depend on a contestable modelling choice, competing explanations, counterevidence and
  headline claims stated more strongly than the evidence. An acknowledged limitation no
  longer excuses an unqualified headline claim. `statistical_inference` gained a
  `robustness_of_central_conclusions` check; `contribution` searches for counterevidence.
* Claims are stated at the level of the underlying problem and its consequence; the
  remedy can still be a small wording change.
* `main`'s shared reasoning guidance (from the ScientificSlop assessment) is merged.

**Evaluation.**

* `eval/plain_review.py --prompt general` is the comparator: the review a careful user
  could get from one call to the same model, with supplements and remedy labels.
* The [criticism-level judge](CRITICISM_JUDGE.md) clusters criticisms from all arms
  without their origin and has two judge families assess each one against the manuscript.
  It replaces whole-report preference for development decisions.
* Judge calibration on 48 labelled probes: Sol 44/48, never supporting a false criticism;
  Opus 41/48, lenient on source-dependent claims and once accepting a true headline with a
  wrong calculation. Neither changed labels when only a rationale's persuasiveness changed
  (1 of 16 pairs). Details in the judge documentation.
* [Corpus splits](CORPUS_SPLITS.md): 29 development, 7 judge-calibration and 11 fenced
  validation cases, none of the fenced ones run before. `eval/run_dev_arms.py` refuses
  fenced manuscripts and records code commit, input hashes and timing for every run.
* `eval/owner_packet.py` builds an origin-blind labelling page for the owner's own paper
  and scores the owner's labels against each judge.
* Probes and outputs that quote the owner's unpublished manuscript stay in gitignored
  paths; this repository is public.

## The development loop

1. Run the frozen specialist version and the plain baseline on development papers
   (`eval/run_dev_arms.py`), several papers before several runs.
2. Judge all arms of each paper together (`reviscope judge-criticisms`), then summarise
   with the paper as the unit (`reviscope judge-summary`).
3. Read the clusters, not only the counts: which material issues one arm raises that the
   other does not, how each arm frames the same issue, and which criticisms are
   contradicted.
4. Change one thing in a separate worktree, rerun on the same papers, and compare.
5. Recalibrate the judge when its instructions change; use the owner's labels to decide
   which judge to trust on materiality.

A change counts as an improvement when it raises supported material criticism under both
judges on most development papers without adding contradicted criticism or harmful
remedies. Run-to-run variation is large, so a gain on one paper is a lead, not a result.

## Evidence so far

Six development papers: five ordinary empirical Meta-Psychology and PeerJ submissions and
the owner's reanalysis. Counts are supported criticisms with materiality ≥ 2 per run,
averaged over runs, under each judge (judge protocol v3 clustering). Plain is the general
one-call baseline; baseline is the frozen 0.5.0a1 specialist pipeline; iter2 adds the
expert-critique scope, replication check and problem-level claims; iter3 is a fresh run of
iter2's prompts with two fixes (external-verdict matching and metacheck control
characters). One run per arm unless noted.

| Paper | Plain | Baseline | Iter2 | Iter3 |
| --- | --- | --- | --- | --- |
| Bonetto (2 plain, 2 baseline runs) | 17 / 13 | 12.5 / 10 | 19 / 9 | 15 / 13 |
| Brohmer | 17 / 14 | 17 / 10 | 15 / 10 | 11 / 8 |
| PeerJ 16147 | 25 / 18 | 15 / 9 | 16 / 9 | 20 / 13 |
| Satrevik | 25 / 18 | 20 / 10 | 20 / 16 | 22 / 15 |
| Ziano (2 plain, 2 baseline runs) | 16.5 / 10.5 | 22.5 / 12.5 | 27 / 22 | 21 / 17 |
| Owner paper (2 plain runs) | 4.5 / 0 | 1 / 0 | 5 / 0 | 5 / 0 |
| **Mean** | **17.5 / 12.3** | **14.7 / 8.6** | **17.0 / 11.0** | **15.7 / 11.0** |

Cells are Sol / Opus. Contradicted criticisms are rare in every arm (at most one per run).

What this shows (revised after a review by GPT 6.1 Sol, which recomputed these numbers
from the judge outputs; see `research/llm-reviewer-sources/sol-review-of-development-results.md`):

* **Plain review is ahead on distinct material issues.** Counting each issue once, rather
  than each criticism, the means are:

  | Arm | Material criticisms | Distinct material issues | Published findings only |
  | --- | --- | --- | --- |
  | Plain | 17.5 / 12.3 | 17.4 / 12.3 | 17.5 / 12.3 |
  | Baseline | 14.7 / 8.6 | 12.5 / 7.4 | — |
  | Iter2 | 17.0 / 11.0 | 13.8 / 8.5 | 12.8 / 8.3 |
  | Iter3 | 15.7 / 11.0 | 13.7 / 9.3 | 12.7 / 8.7 |

  The specialist modules repeat issues across modules (on Ziano, iter2's 27 / 22
  material criticisms are 18 / 13 issues), so criticism counts flatter the pipeline. On
  distinct issues iter3 is about 22–24% below plain under both judges. The changes
  narrowed the gap from the baseline; they did not close it. Six papers with mostly single
  runs establish neither superiority nor equivalence.
* **Pooling shows some complementarity, not a consistent advantage.** On the two papers
  with two plain runs, plain plus iter3 covers about as many material issues as two plain
  runs; plain plus iter2 covers somewhat more (Ziano 22 vs 21 under Sol, 15.5 vs 13 under
  Opus). Iter3 raises a few material issues neither plain run raised.
* **Version differences are confounded.** Iter3 differs from iter2 by two fixes as well as
  by fresh generation; the owner-paper iter3 reused iter2's model outputs and is not a
  replication. Single runs cannot rank these versions.
* **Burden.** The pipeline shows authors about 6,700 words of criticism per paper against
  about 2,900 for plain, and takes 70–95 minutes elapsed (120–165 minutes of summed stage
  time at two concurrent stages) against 10–20 minutes. Whether verification prevents
  enough harmful advice to justify this is unmeasured; contradicted criticisms are rare in
  every arm.
* **Measurement caveats.** Results depend on the materiality threshold (at ≥ 1 the
  pipeline has more supported criticisms than plain) and on cluster boundaries set without
  the manuscript. Judge calibration covers correctness on selected probes, not materiality;
  materiality agreement between judges is moderate (weighted kappa about 0.4–0.6) on the
  empirical papers and nil on the owner paper.

Two measurement and product bugs found along the way changed these numbers and are fixed:

* **Judge clustering** required the same consequence as well as the same problem, which
  split equivalent criticisms. Issue-level overlap computed with protocol v1 made the arms
  look complementary (Jaccard 0.11–0.29); with protocol v3 the specialist arm overlaps
  plain about as much as plain overlaps itself.
* **External-verdict matching**: the verifier reported checked sources by DOI, while the
  gate looked verdicts up by URL, so opened and confirmed sources counted as unchecked.
  This held back 21 verifier-supported findings on Satrevik and 14 on PeerJ 16147 in iter2,
  falling hardest on the literature-based critique iter2 encouraged. The fix is cherry-picked
  from the `argument-coherence` branch (cf3068a).

**Owner paper.** The baseline modules audited thoroughly but raised nothing on model
specification, theory or counterevidence; plain did. Iter1 raised those issues framed as
wording fixes, rated less material; iter2's problem-level framing brought the pipeline to
plain's level on this paper under Sol. Opus rates no criticism on this paper as material,
so the owner's labels are an important diagnostic here, though one author's view of an
atypical reanalysis is not an independent standard.

**Where the pipeline loses.** On PeerJ 16147 every material issue raised only by plain
review falls within a module's remit (composite measures, differences in significance
read as significant differences, selection of countries by significance, attrition,
untested change over time, a misrepresented citation). Iter2 discovered most of them and
the external-verdict bug withheld many, yet after the fix iter3 still misses nine of
plain's material issues entirely. Being within a module's remit is intended coverage, not
reliable detection; whether these misses come from stochastic discovery, partitioning that
discourages cross-cutting reasoning, or downstream filtering needs a stage-by-stage trace.

## Decisions for the owner

* **Whether the specialist design should stay the product.** On this evidence it finds
  fewer distinct material issues than a well-prompted single call, at several times the
  latency and more than twice the reading load, and its extra coverage over a second plain
  run is inconsistent. Retain it as the default only if independent assessment shows enough
  distinct material benefit, deeper actionable analysis or harm prevention to justify that. Possible directions: keep
  developing modules (for example deeper per-module tool use, or modules that take a plain
  review's issues as leads and test them); use specialists for checks a single call does
  badly (numerical recomputation, source verification) on top of a broad review; or accept
  the single call as the core and present the pipeline's verification and report structure
  as the added value. These are product decisions, not settled by the judges.
* **Label the owner-paper packet** (`runs/owner-paper-20261009/validation-packet.html`,
  44 criticisms in 17 issues, about an hour; score it against `judge-v4/result.json`, which
  it was built from): it gives an author-utility check and a materiality diagnostic for
  the judges.
* **Fenced set membership:** two fenced PeerJ cases are attitude surveys at the edge of
  social psychology (16338, 15835). Changing that means changing the rule and redrawing
  before anyone looks at them.
* **Public metadata:** `eval/corpus/splits.v1.json` lists reviewer names and short
  verification snippets from CC BY sources.
* **The `argument-coherence` branch** has the external-verdict fix used here and an
  `argument_coherence` module; its point-level judging overlaps with the criticism judge.
* **Severity:** every finding on the owner paper was rated minor, including challenges to
  headline claims.

## Next steps

1. Trace each of plain's material issues that the pipeline misses through discovery,
   verification and editorial on the existing outputs, and replay the old and repaired
   external-source gates on fixed candidates, to separate discovery losses from filtering.
2. Compare, with independent caches and matched inputs on several development papers: the
   repaired specialist pipeline, plain, plain with a second plain run, and plain followed
   by the pipeline's verification (`eval/experiment_discovery.py --mode replay`). The last
   arm tests whether verification and report structure add value without specialist
   discovery.
3. If the specialist design stays, test modules that receive plain's candidate issues as
   leads, so they deepen and check rather than rediscover.
4. Before the fenced validation, prespecify the acceptable coverage deficit and the safety
   or utility benefit the pipeline must show, and use human assessment of unique material
   issues, judge disagreements, gate losses and potentially harmful remedies.
