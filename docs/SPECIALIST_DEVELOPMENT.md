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

All numbers are LLM-judge labels on six development papers (five submitted manuscripts
and the owner's paper), with one run per version except where noted. "Material" means a
supported criticism rated 2 or 3 for materiality.

**Supported material criticisms per run.** Sol's count first, Opus's in brackets.

| Paper | Plain | Baseline 0.5.0a1 | Iter2 | Iter3 |
| --- | ---: | ---: | ---: | ---: |
| Bonetto | 17 (13)* | 12.5 (10)* | 19 (9) | 15 (13) |
| Brohmer | 17 (14) | 17 (10) | 15 (10) | 11 (8) |
| PeerJ 16147 | 25 (18) | 15 (9) | 16 (9) | 20 (13) |
| Satrevik | 25 (18) | 20 (10) | 20 (16) | 22 (15) |
| Ziano | 16.5 (10.5)* | 22.5 (12.5)* | 27 (22) | 21 (17) |
| Owner paper | 4.5 (0)* | 1 (0) | 5 (0) | 5 (0) |
| **Mean** | **17.5 (12.2)** | **14.7 (8.6)** | **17.0 (11.0)** | **15.7 (11.0)** |

\* mean of two runs. Iter2 is the expert-critique scope, replication check and claim
framing. Iter3 reruns iter2's prompts with two fixes: verdicts on external sources are
accepted under either the cited URL or DOI, and control characters no longer stop
metacheck. On the owner paper iter3 reused iter2's stages.

What this shows:

* **The baseline was below plain review; the changes brought the pipeline level with it,
  not ahead.** Plain beat the baseline on four of six papers under both judges. Iter2 and
  iter3 are close to plain on average and still behind on three or four papers.
* **Differences between pipeline versions are within run-to-run variation.** Iter3 reran
  iter2's prompts and moved by four to six material criticisms per paper in both directions.
  Two plain runs of one paper share 60–70% of their material issues.
* **A pipeline run adds about as much coverage as a second plain run.** On Bonetto and Ziano,
  one plain run plus one pipeline run covered 18–22 material issues under Sol; two plain runs
  covered 19–21. The pipeline takes four to five times as long as a plain run.
* **Neither arm shows a precision problem the judges can see.** Contradicted criticisms
  average below 0.2 per run in every arm, so verification has no measured precision
  advantage here. The probe calibration shows the judges do catch false criticisms when
  they occur.
* **The external-source gate was discarding supported findings.** The verifier reported
  sources by DOI and the gate looked them up by URL. Iter2 lost 21 verifier-supported
  findings on Satrevik and 14 on PeerJ 16147 this way. Fixed in iter3.
* **Issue-level counts need the corrected clustering.** Clustering protocol v1 split
  equivalent criticisms and made the arms look complementary; v3 does not.

**What the diagnosis of the owner paper showed.** The baseline modules audited thoroughly
(recomputing statistics and sample flow) and raised nothing on model specification, theory
or counterevidence, which plain review did. After the scope change they raised those
issues, but as wording fixes, which the judges rated less material; the claim-framing change
corrected that. Opus rated no criticism of this paper as material in any arm, so the
owner's labels are needed to decide which judge's materiality to trust.

## What the evidence does not show

It does not show that the specialist pipeline is worse than plain review for an author.
The judges count criticisms; they do not assess the report as delivered, the audit trail,
whether a human would trust the "supported" labels, or whether plain review's criticisms
survive expert scrutiny as often as verified ones. Five of the six papers come from two
open-review journals. No human has adjudicated any of these criticisms yet.

## Decisions for the owner

* **What should the pipeline be better at than a plain prompt?** On the count of supported,
  material criticisms it is currently level at four to five times the time. Candidate
  answers that the present evidence cannot settle: precision as judged by experts,
  trustworthy labels and audit trail, recomputation, and stability. If coverage is the
  goal, pooling several cheap broad passes and spending the pipeline's effort on
  verification and prioritisation is the more promising design, and it changes what the
  specialist modules are for.
* **Label the owner-paper packet** (`runs/owner-paper-20261009/validation-packet.html`,
  44 criticisms in 17 issues, about an hour). It gives the first human check of both arms'
  correctness and of the judges' materiality.
* **Fenced set membership:** two fenced PeerJ cases are attitude surveys at the edge of
  social psychology (16338, 15835). Changing that means changing the rule and redrawing
  before anyone looks at them.
* **Public metadata:** `eval/corpus/splits.v1.json` lists reviewer names and short
  verification snippets from CC BY sources.
* **The `argument-coherence` branch** adds an `argument_coherence` module and its own
  point-level judging; it is not merged here. One of the two judging approaches should
  become the standard. Its external-verdict fix is cherry-picked into iter3.
* **Severity:** every finding on the owner paper was rated minor, including challenges to
  headline claims.

## Next steps

Hold further prompt iteration until the owner has labelled the packet and chosen what the
pipeline should earn. Version differences are within noise at one run per paper, so more
single runs will not rank versions; a decision on the target outcome determines which
measurement to scale. Development runs so far cover six of 29 development papers.
