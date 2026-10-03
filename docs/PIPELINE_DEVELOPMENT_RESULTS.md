# Broad review, verification and independent audit: development results

The broad-first candidate matches the saved one-call baseline on strict planted-error
retrieval and retrieves seven of eight audited demonstrable errors. Verification has a
concrete filtering benefit: it opens linked analysis code, reproduces results, and rejects
a criticism whose premise is that the code is inaccessible. On two submitted manuscripts,
the independent audit improves the broad-first report, but the plain review remains the
preferred report under the primary judge. The audit's extra time is substantial.

The practical direction is broad discovery with source and calculation scrutiny, with
the independent audit kept optional. These development results justify a small untouched
check and human calibration. They do not justify a full campaign or a claim of superiority.

## Implemented candidate

Engine 0.4.3a1 supports `--strategy holistic` and optional `--evidence-audit`. The broad
read produces candidates and a descriptive manuscript map in one tool-enabled call.
The separate audit reads the manuscript and every retained metacheck lead, without the
broad findings or overview. It records operations, inputs, assumptions, code and results.

Slim discovery records distinguish defects, specification conflicts and clarification
requests. Model-owned discovery text cannot set administrative verification or editorial
fields. Reporting requests receive guidance toward proportionate severity before
verification. Every candidate receives verification in batches of ten; ten is capacity
per call, rather than a finding quota. Required-source holds can receive one complete
verification follow-up with its own recorded tool calls. Failed follow-up preserves the
initial gated outcome. The source-task ledger retains both attempts.

The pilot uses Sol/high discovery and editorial, and Opus 5.5/high verification.
Both review backends pass live sandbox checks: home canary and login data unreadable,
outside writes blocked, working-directory writes permitted, shell networking blocked,
and SciPy and R available. CLI versions are Codex 0.160.0 and Claude Code 2.1.280.
The root Codex update timer is restored after the series.

The specialist path remains available. The factual/publication gates, immutable editorial
text and severity, contamination rules, profile family and metacheck fine-row filters are
shared. No finding cap or lead truncation is introduced. Models and default effort follow
the owner constraints. CLI versions are provenance rather than model-stage cache keys.

Opus architectural and implementation feedback informs the source follow-up, slim schema,
scope distinctions, independent audit input, operation/trace matching, and evaluation
design. Suggested severity rewriting, a new publication route for pipeline-executed
calculations, and tighter fetch-only gates remain owner decisions. A suggestion to pin
every source dependency as required conflicts with the approved optional-source policy:
a bounded claim can stand on manuscript evidence and established knowledge, with unchecked
external items removed.

## Error retrieval on papers 5 and 9

| Configuration | Candidate matches | Published matches | Published demonstrable errors |
| --- | ---: | ---: | ---: |
| Broad-first Sol, Opus verifier | 13/20 | 12/20 | 7/8 |
| Saved one-call Sol | 12/20 | 12/20 | 6/8 |
| Saved one-call Sol without category list | 12/20 | 12/20 | 6/8 |

All six paper/configuration records are clean under the unchanged audit, and the input
hashes match. The two baseline conditions are saved outputs from the benchmark series,
rather than fresh concurrent controls. The candidate has one run per paper. These papers
are shaped by development feedback, and retrieval judgments come from Opus. The baseline's
strict matches include weak/invalid annotations; those matches are not a correctness key.

Paper 5 publishes four strict matches and paper 9 eight. The sole missed demonstrable
error is 5-05, the prose/table geographical inconsistency, which discovery never raises.
The pipeline publishes all six demonstrable errors on paper 9, including the scoring
operation-order issue (9-02) and centering issue (9-09). The trace records two additional
uncertain matches, which are excluded from strict detections.

For 5-01, discovery claims that the synthesis cannot be reproduced without an inaccessible
script. Verification opens the manuscript's OSF project and reads `Meta.R` and `Goal4-5.R`.
The recorded source specifies `rma(ri=r, ni=N, method="REML", measure="ZCOR")`, confidence
and prediction operations and the difference-interval calculation. Its successful shell
reconstruction returns Express r = .077, CI [.012, .142], p = .0197, and Connect r = .086,
CI [-.005, .175], p = .0648; the difference intervals also approximately match the report.
The criticism is contradicted and rejected. The main-text reporting gap is an annotation
target, but the stronger complaint about unreproducibility has a defeated premise. This
is an observed benefit of checking the linked evidence, rather than a measured precision
advantage over plain review.

The candidate uses eleven model calls and 78.81 sequential model-stage minutes across the
two papers; the saved category-list plain baseline uses two calls and 23.70 minutes.
Metacheck has partial screening records on both papers and is excluded from those minutes.
Timing reflects different run schedules and network conditions, rather than monetary cost.

## Submitted manuscripts and expert comparators

The two cases are:

* **Group membership and deviance punishment:** six experiments and an internal synthesis,
  with separate first-round reports by Rahal and Bolesta.
* **Preference for indirect harm replications:** two experiments, with separate first-round
  reports by Erlandsson and Lakens.

The [curated manifest](../eval/corpus/open_peer_review_curated.v1.json) pins submitted
manuscript versions and report hashes. The [curation notes](OPEN_REVIEW_COMPARISONS.md)
explain version correspondence. The full development pool has six submitted manuscripts
and twelve expert reports; four cases remain unused by this pilot. Reviewers receive
the submitted text and metacheck leads. Human reports are judge-only inputs.

| Manuscript | Arm | Candidates | Published/issued criticisms | Model calls | Sequential stage minutes |
| --- | --- | ---: | ---: | ---: | ---: |
| Group membership | Plain | 34 | 34 | 1 | 11.24 |
| Group membership | Broad-first | 20 | 20 | 4 | 46.55 |
| Group membership | Broad + audit | 40 | 23 | 7 | 85.61 |
| Indirect harm | Plain | 33 | 33 | 1 | 23.97 |
| Indirect harm | Broad-first | 25 | 20 | 5 | 32.14 |
| Indirect harm | Broad + audit | 48 | 24 | 9 | 68.73 |

All six reviews are complete and clean. Plain criticisms have no separate verification
or editorial pass. Broad and audit counts distinguish discovery from publication; a
merged candidate is not automatically a lost criticism. Both nested arms share broad
and verification artifacts. Audit-arm minutes include those reused stages at their
recorded original durations, exclude the discarded broad-arm editorial call, and exclude
metacheck and judging. Extending the two shared runs takes 81.73 fresh model-stage minutes.
Concurrent work and source latency limit interpretation of the time differences.

## Judge results and their limits

The primary judge is Opus 5.5/high, with tools disabled, model/stage/support metadata
removed, and both presentation orders. Sol/high supplies the AI-versus-AI sensitivity
check. The 24 paired paper/contrast judgments contain 48 individual order judgments;
there are two independent manuscripts, not 24 papers.

| Contrast | Opus: group membership | Opus: indirect harm | Sol: group membership | Sol: indirect harm |
| --- | --- | --- | --- | --- |
| Broad-first versus plain | Plain | Plain | Order-discordant tie | Plain |
| Broad + audit versus broad-first | Audit | Audit | Audit | Audit |
| Broad + audit versus plain | Plain | Plain | Tie / audit across orders | Plain |

Opus consistently prefers each AI arm to both expert reports on both manuscripts.
These are repeated comparisons on the same two submissions. Their frequent preference
for AI coverage is not proof that AI reviewers are more correct than the experts.
The AI representation contains published criticism only, while the anonymized human
prose includes praise and discussion. Native style, severity labels, report length,
historical context and the judge's confidence in plausible claims remain confounds.

The plain review's advantage includes conceptual and design coverage: outcome selection,
construct comparability and synthesis scope in the group-membership paper; original-study
benchmark comparability, replication fidelity, ordering and priming in the harm paper.
Some are never raised by the candidate and some are held because the verifier cannot
establish an external premise. Those are different losses. The source-specific
original-study claims receive 403 responses in verification.

The audit has tangible incremental effects. It recovers the harm paper's incorrect count
of negative correlations and supplies a bounded aggregation criticism supported from the
manuscript's combined-versus-scenario-specific estimates, with its unchecked external
quotation removed. It contributes three net published findings in the group-membership
paper and four in the harm paper, with substantial overlap and several bibliography
corrections. Net count is not unique material value; much of the recovery is already
present in the plain baseline. The data do not support an always-on audit.

## Independent checks and a verification coverage boundary

[Seven selected numerical checks](pipeline-development-analysis/numerical-checks.json)
use direct source assertions and independent arithmetic. They establish reported
inconsistencies, conditional on the specified inputs, rather than raw-data truth:

* The group paper's thermometer summaries imply |t| = 4.48 and |d| = .517, against the
  displayed .81 and .10. Its blame t = .52 with df = 298 implies p = .603, against .96.
* Its displayed pooled age and male percentage match unweighted study averages. Under
  recruitment Ns as demographic denominators, weighted summaries are 24.63 years and
  32.37%, against 23.83 years and 27.27%. Missing demographic responses need clarification.
* The harm paper's r = .166 at maximum N = 314 implies p = .00317. Favourable rounding
  cannot reach .001 even for a one-sided test. Its t(313) = -2.03 gives p = .0432,
  outside the displayed .040 even with rounding bounds.
* Four of sixteen nonreason correlations are negative. The MTurk zoo CI [.24, .47]
  excludes the original d = .70, so its consistency label fails the named
  [LeBel criterion](https://ppw.kuleuven.be/okp/_pdf/LeBel2019ABGTE.pdf).

Plain and the audit-extended candidate cover all seven checks; broad-first misses the
negative-correlation count. This is a retrospectively selected development check set,
not a complete error inventory or an estimate of precision.

The verifier receives headline claims, remedies, quotations and external items. Its
instruction excludes reliance on the generating rationale. A supported headline therefore
does not establish every factual assertion in the rationale. In the harm audit, the
published aggregation rationale asserts eight original scenarios while the verifier
cannot open the source and judges the bounded headline independently of that exact count.
That illustrates the coverage boundary. Mandatory verification of factual rationales
requires an explicit owner decision under the verification-rule constraint. Claim-level
support language in the current renderer states the scope precisely.

The frozen pilot judge rubric asks for correctness and grounding, but rationales sometimes
call external assertions verified without supplied source text. The current judge rubric
requires explicit uncertainty and counterevidence in that situation; it is not applied
retroactively to these pilot judgments. Future comparison cache keys include the complete
presented prompts and model settings. Operation code/output matching records execution,
without independently establishing that the code or assumptions are correct.

## Validation and advancement

1. **Cheap retrieval check:** freeze broad-first and plain on two to four untouched
   planted-error papers, with identical inputs. Report strict and demonstrable-subset
   retrieval, source-access losses, editorial holds, extra correct criticisms and
   unsupported advice separately. Do not tune on those outputs before recording results.
2. **Expert review comparison:** use the four reserved submitted manuscripts with at
   least two runs of plain and broad-first. Keep human reports out of generation. Use
   both judge families and presentation orders under the stronger frozen rubric. Compare
   criticism-only and complete author-visible reports as separate conditions.
3. **Correctness calibration:** assess atomic criticism clusters, including every unique
   audit contribution and disputed high-impact claim. Include eval-only true/false probes,
   false absence claims defeated elsewhere, unverified source assertions and a correct
   headline with an incorrect rationale. Two methods-qualified assessors per paper rate
   correctness, importance, necessity and feasibility independently.
4. **Small crowd assessment:** 8–12 methods-trained researchers can assess clarity and
   actionability in short blinded packets. Include abstention and calibration items.
   Technical correctness requires qualified assessors. A reproducible 20% sample of
   remaining clusters records inclusion probabilities and is not pooled unweighted with
   the deliberately selected difficult claims. Recruitment and compensation need a
   separate agreed arrangement; no people are contacted or money spent by this work.
5. **Scale only after promise:** prespecify acceptable retrieval/precision loss and cost
   premium from the small assessment. A replicated ten-paper series then has forty reviews
   for two configurations and two runs. Add unseen manuscripts across the profile family
   to assess generalization. The full series remains on hold.

The [validation plan](PIPELINE_VALIDATION_PLAN.md) details these controls. Default
replacement requires evidence beyond development recall. The useful features with direct
evidence are claim/source scrutiny, source provenance and reproducibility checks. The
independent audit is an optional second opinion whose marginal benefit needs assessment
against both plain review and a second broad read with comparable compute.

## Reproduction

The ignored run root is `runs/pipeline-redesign-20261003`. Reviewer code snapshot is
`5fe44c42b1dcb1bc`; plain snapshot `2cbe2d3120a1385c`; primary comparison snapshot
`88e328faacef66d0`. Exact commands, hashes, archives, source audits and feedback are retained
locally. Raw manuscripts and expert reports are excluded from Git.

```bash
.venv/bin/python docs/pipeline-development-analysis/analyze.py --root runs/pipeline-redesign-20261003
python3 eval/check_development_numerics.py --output docs/pipeline-development-analysis/numerical-checks.json
.venv/bin/python eval/score_known_errors.py --root runs/pipeline-redesign-20261003/retrieval
.venv/bin/python eval/trace_known_errors.py --root runs/pipeline-redesign-20261003/retrieval
```

The numerical command requires SciPy. Derived [comparison data](pipeline-development-analysis/analysis.json),
[retrieval data and trace](pipeline-development-analysis/retrieval.json), and analysis scripts
are public; full source documents, report texts and model traces remain local.
