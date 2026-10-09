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

**Owner paper (reanalysis; one run per version).**

| Version | Criticisms shown | Supported (both judges) | Material, Sol | Material, Opus |
| --- | ---: | ---: | ---: | ---: |
| Baseline 0.5.0a1 | 6 | 6 | 1 | 0 |
| Expert-critique scope (iter1) | 15 | 14 | 2 | 0 |
| Plain, two runs (mean) | 7 | 6.5 | 4.5 | 0 |

The baseline modules audited thoroughly (recomputing statistics and sample flow) yet raised
nothing on model specification, theory or counterevidence; plain review did. After the
scope change the specialist pipeline raised those same issues, but framed them as wording
fixes ("the abstract leaves … unclear"), which the judges rated less material. The
claim-framing change (iter2) targets that. Opus rates almost no criticism on this paper as
material, so the combined materiality count is uninformative here; the owner's labels will
show which judge's materiality to trust.

**Bonetto (six experiments; one run each).** The baseline specialist and plain arms are
close: 26 and 25 criticisms, all but one supported, with 15 and 17 material under Sol and
9 and 13 under Opus. They overlap little: of about 49 issue clusters, Sol counts 11
material issues unique to the specialist arm and 14 unique to plain. Whether that reflects
complementary coverage or run-to-run variation needs the second runs of each arm.

## Decisions for the owner

* **Label the owner-paper packet** (about an hour): it calibrates the judges, especially on
  materiality, against someone who knows the paper.
* **Fenced set membership:** two fenced PeerJ cases are attitude surveys at the edge of
  social psychology (16338, 15835). Changing that means changing the rule and redrawing
  before anyone looks at them.
* **Public metadata:** `eval/corpus/splits.v1.json` lists reviewer names and short
  verification snippets from CC BY sources.
* **The `argument-coherence` branch** adds an `argument_coherence` module and its own
  point-level judging; it is not merged here. The criticism judge on this branch overlaps
  with that judging, and one of them should become the standard.
* **Severity:** every finding on the owner paper was rated minor, including challenges to
  headline claims. The guidance may be too conservative; the owner's labels should decide.

## Next steps

Complete the interrupted runs (the Opus verifier hit usage limits under concurrent load),
judge all six development papers for baseline, iter1 and iter2 against plain, and add
second runs where the overlap question matters. Then test whether pooling diverse passes,
for example a broad critique as one more module beside the specialists, raises material
coverage beyond what either finds alone.
