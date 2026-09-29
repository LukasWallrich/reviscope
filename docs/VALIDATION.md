# Validation plan

The alpha evaluation asks two bounded questions: whether blinded judges prefer its reviews to human or model baselines on the same manuscript, and whether individual published criticisms are supported by the supplied source. It does not claim that a small open-review sample establishes human-level peer review.

## Version-matched corpus

`eval/corpus/open_peer_review.v1.json` is frozen source metadata. An entry is eligible only when the exact manuscript seen by the reviewers is public and independently checked. A final published article is not a substitute: author revisions can remove the very problem named by a review.

Meta-Psychology is the primary curation source because the journal states that all submission histories are public in its OSF archive. Communications Psychology supplies prominent transparent-review bundles, but the seed entries remain deliberately ineligible until their pre-review manuscripts are located. Royal Society Open Science is a further candidate. PCI is not the primary corpus.

For every admitted paper, record the manuscript URL, immutable identifier or hash, review-round label, review URL, curator, and date checked. Keep development and frozen test paper IDs separate. Human review text should exclude editor decisions and author rebuttals.

## Competitive review comparison

Compare the candidate pipeline with (a) individual public human reviews, (b) a strong single-pass social-science prompt, and (c) coarse where runnable. `build_pairwise_cases` blinds labels and creates an order-swapped pair. Judges receive the manuscript, both reviews, a fixed rubric, and permission to tie. Use at least two judge model families and freeze their prompts and settings.

Aggregate the two order swaps within each paper and judge first, and then aggregate judges within paper. A win requires agreement across both swaps; disagreement or a tie in either order produces a tie. Across judge families, only a unanimous outcome is retained as a win. Missing order pairs are excluded and reported. Order swaps and multiple judges are repeated measurements, not extra papers. Report candidate/reference/tie counts, order and judge discordance, paper-level intervals, runtime, and cost. Also compare candidate reviews with the combined human-review set as a separate coverage analysis; never describe overlap with human comments as truth or completeness.

### Normalized-review sensitivity analysis

The implemented sensitivity workflow tests whether differences in writing and organization affect the original-review comparison. It applies the same blinded normalization model and frozen schema separately to each candidate and human review, using only that review as input. Each atomic assessment records its type, evaluation, rationale, review-supplied evidence, remedy, qualifications, and exact spans from the source review. This includes substantive strengths and endorsements as well as criticisms. The normalizer must preserve equations, reported errors, uncertainty, and missing fields; it must not add evidence, repair reasoning, or fill omissions. Deterministic checks reject unmatched spans, duplicate content, duplicate IDs, and inventories that reach the assessment cap. A separate-family model then audits completeness and faithfulness. One audit-guided revision is allowed; another failure makes that normalized condition ineligible.

Do not impose an equal total-length cap that could erase a real difference in issue coverage. The comparison judge receives the manuscript and the two normalized outputs, evaluates both presentation orders, and uses the same rubric, response schema, and two model families as the full-review comparison. Report normalized and full-review results separately. A changed outcome is evidence that representation affected this evaluation; it does not by itself show that either judge was biased or identify the direction of bias.

The bounded initial run used GLM-5.3-Flash for normalization and Fable at high effort for the audit. Three of six tested inventories passed the final gate. Both Z-curve comparison inputs failed, so a normalized Z-curve comparison was not estimable. In the PeerJ pool, three of four human inventories passed, leaving the seven-review normalized condition ineligible before the three AI reviews were added. Failures included inferred remedies absent from the source review, duplicate summary assessments, and loss of an exact mathematical span. These are diagnostic failures of strict representation fidelity, not outcomes about review quality. Full details and artifact hashes are in `eval/results/normalized-review-diagnostic.v1.json`.

The original-format multi-review workflow uses `rank-reviews` with three seeded blinded presentations per judge. It accepts tied rank groups, validates all six criterion rankings, and reports mean ranks, fractional Borda scores, and implied pairwise counts. The presentations and judges remain repeated measurements of one paper.

The first seven-review workflow diagnostic used four public PeerJ reviews and three complete pipeline reviews generated by Luna, Sol, and Opus. Sol and Gemini 3.8 Flash High each ranked all seven reviews in three seeded orders. Both judges placed the Opus review first in all three presentations. Across the six repeated judgments, the descriptive mean ranks were Opus 1.00, Sol 2.33, Luna 2.67, human review 2 at 4.42, human review 3 at 5.25, human review 1 at 5.33, and human review 4 at 7.00. These are repeated measurements of one paper with an unusually weak and uneven public review set. They demonstrate the ranking workflow and do not establish competitiveness with human peer review. Full provenance, dependencies, and artifact hashes are recorded in `eval/results/peerj236-workflow-diagnostic.v1.json`.

## Factuality and restraint

Product verification should retrieve source context, seek counterevidence, recompute checkable numerical claims, and distinguish `llm_supported`, `contradicted`, and `unresolved` findings. Verification runs as a separate pass without the generator's rationale or verdict. It is independent-model evidence only when a different model family is configured and recorded; the default same-model separate call is not described as independent.

For an external estimate, human-audit a seeded random sample of published substantive findings. Separately audit a targeted sample of major findings, verifier disagreements, and unresolved cases. `sample_finding_audit` keeps these strata disjoint and `audit_summary` reports them separately; the targeted sample must not be pooled into a prevalence estimate. Findings set aside by the editorial stage are excluded by default. Use `--include-set-aside` for a separate analysis of verifier or editorial false negatives, rather than mixing them into the published-finding precision estimate.

## Sensitivity to known errors

Use the [Dawes Institute psychology benchmark](https://github.com/Dawes-Institute/ai-peer-review-benchmark) as a development smoke test for planted-error recall, after inspecting its annotations. It does not estimate false-positive rates. The importer supports the repository's `error_insertions.csv` at commit `3d9188343eebd4312d3bfbde6822cfa4eaf32fb4`; generated IDs take the form `paper-row`. `planted_error_recall` scores explicit adjudicated error IDs. ERROR reports and CLAIMCHECK can supply additional case studies or verifier stress tests, subject to licensing and domain-fit checks.

For the experimental model-judged smoke test, first complete the review without exposing the annotation file to any generation stage. Then run:

```bash
uv run python eval/adjudicate_known_errors.py runs/REVIEW/review.json \
  --annotations /path/to/pinned/error_insertions.csv --paper 8 \
  --output runs/REVIEW/planted-error-adjudication.json
```

The helper records hashes for the review, annotations, and adjudication script. It reports candidate recall before verification/editorial and published recall after the same publication filter used by the report renderer. The result remains a model judgment against one planted-error case, not a human-equivalence or false-positive result.

Release reports must state corpus size, eligibility rules, exclusions, judge configurations, human-audit sampling, uncertainty, and known dependencies between model reviewer, verifier, and model judge. Fully automated results may be described as “preferred by the configured LLM judges” and “supported by the configured verification pass.” The phrase “independent model verification” requires a recorded different-family verifier. None of these descriptions establishes human equivalence or a measured false-claim rate.

## Reproducible commands

Materialize the eligible pairs and verify their recorded hashes:

```bash
python -m reviscope.evaluation fetch-corpus \
  eval/corpus/open_peer_review.v1.json eval/corpus/cache \
  --output runs/eval/corpus-fetch.json
```

After extracting the exact manuscript and public review to text, compare it with a candidate pipeline `review.json`. The command always evaluates both presentation orders and caches only a complete successful result:

```bash
python -m reviscope.evaluation compare --paper-id PAPER_ID \
  --manuscript manuscript.txt --candidate review.json --reference human-review.txt --reference-kind human_review \
  --backend claude --model MODEL --effort max --output runs/eval/comparison.json
```

Run independent claim checks or draw the two human-audit strata with `verify` and `audit-sample`. Automated verifier outcomes remain model assessments; deterministic quote checks can downgrade them, but cannot turn them into human ground truth.
