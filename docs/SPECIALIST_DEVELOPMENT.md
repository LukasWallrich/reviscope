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

What this shows:

* The changes moved the specialist pipeline from clearly behind plain review to roughly
  level with it, mainly under Opus (8.6 to 11.0, against 12.3 for plain). They did not put
  it ahead: plain still has more material criticism on four of six papers.
* Iter2 and iter3 use the same prompts; their differences of up to six per paper are
  run-to-run variation. Single runs cannot rank versions this close.
* Pooling does not favour the pipeline either. On the two papers with two plain runs, the
  material coverage of plain plus pipeline equals that of two plain runs (Bonetto 19.6 vs
  19 under Sol, 14.2 vs 15 under Opus; Ziano 20.8 vs 21 and 13.4 vs 13). The pipeline
  adds no more distinct material issues than another plain run.
* The pipeline costs about 70–90 minutes of model time per paper with two concurrent
  stages, against 10–20 minutes for one plain call.

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
so the owner's labels are the deciding evidence here.

**Where the pipeline loses.** On PeerJ 16147 every material issue raised only by plain
review falls within a module's remit (composite measures, differences in significance
read as significant differences, selection of countries by significance, attrition,
untested change over time, a misrepresented citation). Iter2 discovered most of them; the
external-verdict bug then withheld many. Remaining losses look like run-to-run variation
more than systematic blind spots.

## Decisions for the owner

* **Whether the specialist design should stay the product.** On this evidence it matches,
  but does not beat, a well-prompted single call at about five times the cost, and it adds
  no more distinct material coverage than a second plain run. Possible directions: keep
  developing modules (for example deeper per-module tool use, or modules that take a plain
  review's issues as leads and test them); use specialists for checks a single call does
  badly (numerical recomputation, source verification) on top of a broad review; or accept
  the single call as the core and present the pipeline's verification and report structure
  as the added value. These are product decisions, not settled by the judges.
* **Label the owner-paper packet** (`runs/owner-paper-20261009/validation-packet.html`,
  44 criticisms in 17 issues, about an hour): it shows whether either judge's materiality
  matches the author's, which the comparisons above depend on.
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

More runs per paper before further prompt changes: with differences of up to six material
criticisms between runs of one version, comparisons need at least three runs per arm on
these six papers. If the specialist design stays, the most promising test is a version in
which each module receives the plain review's candidate issues as leads, so that the
specialists deepen and verify rather than rediscover.
