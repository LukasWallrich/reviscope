# Discovery and finalization experiments

## Outcome

Neither experiment closes the plain-review gap. Replaying the plain candidates
through verification and editorial publishes 7/20 strict planted-error matches;
single-call discovery with operation-based checks publishes 6/20. The saved plain
baseline scores 12/20. The single-call path does publish all six demonstrable
targets on paper 9, including the scoring-order discrepancy, with substantially
fewer calls than the specialist pipeline. Its paper-5 reporting-gap discovery is
poor. These results support further targeted development, not a default switch or
a full ten-paper campaign.

All four reviews complete, and the unchanged tool-use audit classifies them clean.
Title-search prevention is not a development priority for this exploratory series;
the audit rules and flags remain intact. Scores are tool-free Opus judgments of
completed outputs, not estimates of scientific accuracy.

| Configuration | Paper 5 published | Paper 9 published | Total | Demonstrable targets published |
|---|---:|---:|---:|---:|
| Saved plain Sol | 5/10 | 7/10 | 12/20 | 6/8 |
| Specialist Sol pilot, engine 0.4.1 | 2/10 | 5/10 | 7/20 | 6/8 |
| Replay: plain candidates + finalization | 2/10 | 5/10 | 7/20 | 4/8 |
| Single-call operation-based discovery + finalization | 0/10 | 6/10 | 6/20 | 6/8 |

The demonstrable subset uses the independent
[benchmark-validity audit](benchmark-validity-audit/audit-100.md). It represents
the strongest defensible criticism, rather than endorsing every annotation's
explanation. The single-call path's eleven published paper-5 findings include
numerical and interpretive corrections outside the planted list; a zero planted
score does not mean its review contains no useful findings.

## Experimental inputs

Both paths use `gpt-6.1-sol`, high effort, with tools in discovery, verification and
editorial. The frozen source is `8acef5147f918714`, engine 0.4.2a1, Codex CLI
0.160.0. The descriptive study map and metacheck records are imported from the
0.4.1 pilot. Prior pipeline candidates, findings and editorial overview are
excluded. The same manuscript bytes are checked before importing plain issues.
Human reports and planted-error annotations are absent from reviewer inputs.

Replay imports every plain issue: 34 for paper 5 and 43 for paper 9. Complete
descriptions become claims and rationales; moderate severity maps to minor. The
plain schema contains neither a separate remedy nor structured external-evidence
items. These adapter limitations make replay a factual-retention diagnostic,
rather than a fair comparison of prose, remedies or external-evidence handling.

Single-call discovery uses four named operations: analysis-recipe reconstruction,
categorical-fact comparison, score/population tracing, and claim/inference checking.
All metacheck leads are supplied without truncation. It uses a descriptive seed,
additional leads and stricter materiality instructions than the saved plain prompt,
so this is not a controlled ablation of specialist fan-out alone. Every candidate
receives verification in batches of ten and editorial treatment; there is no
finding quota.

## What finalization retains and loses

| Path / paper | Candidates | Verifier supported | Verifier unresolved | Contradicted | Published | Needs review | Merged | Rejected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Replay / 5 | 34 | 23 | 10 | 1 | 18 | 12 | 3 | 1 |
| Replay / 9 | 43 | 38 | 5 | 0 | 28 | 14 | 1 | 0 |
| Single call / 5 | 14 | 13 | 1 | 0 | 11 | 3 | 0 | 0 |
| Single call / 9 | 17 | 16 | 1 | 0 | 16 | 1 | 0 | 0 |

Replay has 13 strict candidate matches and seven published matches. The saved
plain review has twelve strict matches under its own judgment. The extra replay
candidate match is 5-10, an acknowledged missing-data limitation that the separate
validity audit classifies weak or invalid. The same underlying descriptions with
different structured presentation receive separate judgments; this illustrates
judge/representation sensitivity, not discovery of an additional error.

Three mechanisms explain the important downstream losses:

* **Reporting scope becomes a broader verification question.** Replay `plain:19`
  identifies unspecified correlation transformation, variances and
  back-transformation in the supplied manuscript (5-01). Verification acknowledges
  the omission but holds the claim because inaccessible linked syntax might
  supply the details. `plain:26` identifies unspecified Facebook-use eligibility
  (5-07) and receives analogous treatment. Neither criticism establishes an
  incorrect implementation or actual inclusion of nonusers. The unresolved
  rationale is useful author-facing information, but it is excluded from the
  published-finding score. This distinction needs assessment against expert
  feedback, rather than automatic promotion of every omission.
* **Severity prevents supported claims from publishing.** Replay has eleven
  `llm_supported` findings marked `needs_review`: two on paper 5 and nine on paper 9.
  All carry immutable major severity. Editorial finds the demonstrated consequence
  insufficient for that rating. This loses the sample-size reporting inconsistency
  (5-02, `plain:01`), the consequence-severity wording conflict (9-03, `plain:32`)
  and the age/gender-only representativeness qualification (9-07, `plain:33`). It
  distinguishes a sound bounded criticism from an overstrong rating, but does not
  produce a published finding with a lower rating. This is a concrete explanation
  of `needs_review`, rather than a finding-count limit.
* **A verifier can assert a source check without performing it.** The single-call
  paper-5 review has two verifier-supported findings held by required external
  evidence: `holistic:09` cites the prediction-interval documentation and
  `holistic:14` cites Eşkisu's full text. The verifier describes having checked the
  sources, but its batch has no fetch or search of their URL/DOI. The deterministic
  gate correctly withholds them. Batches of ten do not guarantee source coverage.
  Replay imports no structured external items, so its absence of this loss is not
  evidence that the gate is unnecessary.

There is a concrete filtering benefit: replay `plain:06` is contradicted and
rejected. It accuses the manuscript of using nonsignificance as equivalence despite
the manuscript expressly excluding that goal and qualifying the comparison. The
verifier also retains the bounded estimator-selection reporting criticism
(5-09, `plain:20`) without establishing an invalid estimator or p-hacking.
One rejected criticism is useful evidence of a working check; it is not a measured
false-positive rate.

The single-call path supplies a useful positive case. Paper-9 `holistic:11` quotes
the conflicting ASSIST aggregation descriptions and explains the item-weighting
consequence without alleging which implementation occurred. It is supported and
published (9-02). Its other five demonstrable targets publish as well. On paper 5,
the recipe check reconstructs calculations under Fisher-z assumptions but does not
raise the manuscript's unspecified recipe as a finding. The categorical check
also misses the geographical mismatch (5-05). Recording an assessed operation does
not establish exhaustive checking.

## Work required

| Path, two papers | Fresh model calls | Accumulated model-stage minutes | Candidates | Published findings |
|---|---:|---:|---:|---:|
| Saved plain baseline | 2 | 23.7 | 77 | 77 |
| Specialist pilot | 42 | 267.9 | 115 | 50 |
| Replay finalization only | 11 | 75.3 | 77 | 46 |
| Single-call discovery + finalization | 8 | 67.9 | 31 | 27 |

Imported study-map and metacheck work is excluded from fresh-call and duration
counts. Replay excludes its saved discovery cost. These are summed stage durations,
not elapsed campaign time or billing estimates. Four reviews run concurrently.
The saved baseline uses a different machine and CLI version. Single-call discovery
uses about one quarter of the specialist pilot's stage time, but remains roughly
three times the saved plain baseline's time before charging its imported seed.

## Development path

1. **Keep a plain tool-enabled review as the reference configuration.** The
   current evidence does not justify paying for eight specialist discovery calls
   by default. Preserve the specialist path as a comparison until its added
   corrections and usable feedback earn that work on unseen manuscripts.
2. **Test a plain review plus targeted evidence work.** Give numerical
   reconstruction and score/analysis tracing responsibility for explicit quantities
   and passage pairs. The operation checks need inspectable ledgers of reported
   steps versus reviewer assumptions, not an additional category checklist or an
   assertion that coverage is complete. The current single-call variant remains
   experimental because its paper-5 omission discovery is poor.
3. **Make required-source coverage observable before accepting a verification
   batch.** A useful next implementation is a source-task ledger with fetch/search
   outcomes and a focused follow-up for unfinished required items. Continue processing
   every candidate and retain source-specific verification requirements. Treat
   a verifier's claimed lookup as insufficient without a tool record. This is a
   scheduling improvement; relaxing the publication gate is not needed.
4. **Assess bounded reporting feedback and severity separately.** Expert reports
   can establish whether the held clarification requests are useful and correctly
   qualified. Candidate wording and severity should reflect the established
   consequence before editorial. Permitting editorial to revise severity would
   require an explicit change to the publication contract; this experiment leaves
   that contract intact. Keep author-visible unresolved concerns distinct from
   established errors in both reports and evaluation.
5. **Use the version-matched human reports for the next small comparison.** The
   [comparison guide](OPEN_REVIEW_COMPARISONS.md) supplies six submissions and twelve
   screened reports, with three experimental social-psychology cases first. Compare
   plain and candidate reviews with each human report using blinded, order-swapped
   tool-free judgments of correctness, importance and actionability. Judge disputed
   human advice as critically as model advice. Aggregate by paper. Do not optimize
   agreement with reviewers or issue count.

The human-review inputs are prepared; generation and preference judging on those
six manuscripts are separate work. A small quality comparison precedes additional
replicated planted-error runs.

## Reproduction and artifacts

The local root is `runs/discovery-exploration-0.4.2`. It contains `snapshot.json`,
`launch.json`, four review directories, tool audits, Opus adjudications and logs.
The collector's first invocation lacks the user-local Claude executable on PATH;
`rs-exp-analysis-retry` supplies `/home/lukas/.local/bin` and completes all four
adjudications. The Codex update timer is active after collection. Review and judge
artifacts retain backend versions; cache identity excludes CLI version.

Public [derived results](discovery-experiment-analysis/analysis.json) contain
counts, target verdicts, finding IDs, held-reason classes and source hashes. Full
review and tool records remain local. Recompute without model calls:

```sh
.venv/bin/python docs/discovery-experiment-analysis/analyze.py
```

The script checks judgment/review hashes, complete ten-target judgments, completed
reviews and tool-free judges. Experimental generation is implemented in
`eval/experiment_discovery.py`, with frozen invocation arguments in `launch.json`.
