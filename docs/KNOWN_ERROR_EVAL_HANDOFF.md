# Planted-error benchmark: runbook

## What is scored

The benchmark is the Dawes Institute planted-error set (annotations by Litvak):
10 psychology papers with 10 planted errors each, repository commit `3d91883`.
A judge (`claude-opus-5-5`, effort `high`, no tools) decides for each planted error
whether the review identified it. Scoring reports strict recall (`detected` only;
`uncertain` is counted beside it):

- over all 100 targets;
- over the 42 targets that `docs/benchmark-validity-audit/audit-100.json` classifies
  as `valid_demonstrable_error`;
- for candidate findings (before verification and editorial) and for published
  findings, separately. A plain review has no verification or editorial stage, so
  both scopes score the same list.

Every review runs with web search, fetching and a sandboxed shell. The published
originals and the benchmark repository are the answer key, so every run is audited
with `eval/audit_tool_use.py --planted-errors`. Scoring groups each paper by its
audit verdict. Headline recall uses `clean` papers only. `flagged`, `incomplete` and
unaudited papers are reported as separate groups and are never pooled with clean
ones. The benchmark authors' stored reviews (`reviews/litvak_*`) have no tool-call
record and form the `external` group.

## Configurations

| Label | Mode | Reviewer |
|---|---|---|
| `pipeline_gpt-6-luna_high_social_psychology` | `reviscope review` | codex `gpt-6-luna`, effort `high` |
| `pipeline_gpt-6.1-sol_high_social_psychology` | `reviscope review` | codex `gpt-6.1-sol`, effort `high` |
| `plain_gpt-6-luna_high`, `plain_gpt-6.1-sol_high` | one call with the benchmark's `REVIEW_PROMPT` | codex, effort `high` |
| `plain-nolist_gpt-6-luna_high`, `plain-nolist_gpt-6.1-sol_high` | one call with `REVIEW_PROMPT` minus its "Look carefully for:" list | codex, effort `high` |
| `pipeline_claude-opus-5-5_high_social_psychology` (optional) | `reviscope review` | claude `claude-opus-5-5`, effort `high` |

The benchmark planted one error per category in each paper, and the "Look carefully
for:" list names exactly those ten categories. `plain-nolist` removes the list and keeps
the output format, including the category field, so the difference between `plain` and
`plain-nolist` measures what the list itself is worth.

The allowed models are `gpt-6-luna`, `gpt-6.1-sol` and `claude-opus-5-5`. The
per-call timeout is 3600 s.

## Files

- `eval/prepare_known_errors.py`: downloads the benchmark and writes
  `runs/known-errors-all/inputs/paper-NN/manuscript.review-input.txt` (banner removed),
  `provenance.json` and `ground_truth/error_insertions.csv`.
- `eval/corpus/known_errors.v1.json`: identity of each paper: title, published DOI,
  the original's article, preprint and OSF URLs, the benchmark repository URLs and the
  review-input sha256. The audit reads it by default.
- `eval/run_known_errors.py`: the driver. For each paper it writes to
  `runs/known-errors-all/reviews/<label>/paper-NN/`: `review.json`, `tool-audit.json`
  (audit verdict bound to the review's sha256), `planted-error-adjudication.claude-opus-5-5.json`,
  `run.json` (every review attempt) and `driver.log`. It refuses to start when an input
  differs from the manifest hash.
- `eval/plain_review.py`: the one-call baseline (`--no-category-list` for `plain-nolist`).
  Its `review.json` holds the issues, the prompt variant and one `review-plain` stage with
  every tool call.
- `eval/adjudicate_known_errors.py`: the judge.
- `eval/score_known_errors.py`: writes `runs/known-errors-all/known-error-scores.json`.
- `eval/trace_known_errors.py`: for every pipeline configuration, places each planted error
  that the published review misses at the stage that lost it (never raised, verification,
  external-source rule, editorial). `--output` writes the rows as JSON. Results for papers 5
  and 9 are in `docs/KNOWN_ERROR_RESULTS.md`.

The driver copies `src/reviscope` (including `vendor/metacheck`), the three eval
scripts it calls and `eval/corpus/*.json` to `runs/known-errors-all/code/<sha256 prefix>/`
and runs every subprocess from that copy. Edits to the working tree during a run do
not reach it. The snapshot sha256 is printed at start and stored in `run.json` and
`tool-audit.json`.

Reruns are safe. Cached pipeline stages are reused, a complete review is not
regenerated, the audit reruns when `review.json` or the code snapshot changed, and the
judge reruns when `review.json` changed. A partial pipeline review is judged with
`--allow-partial` and scored in the `incomplete` group. A failed plain review is not
judged; rerun the driver to retry it.

## Run

Run from the repository root, on mains power. The drivers survive the end of a
Claude session. Keep Codex concurrency at about 3 to 4 per account.

On Linux, tool-enabled Codex calls need a `codex` binary installed outside the home
directory and on `PATH` (see README), and the shell sees only system-wide Python and R
packages. Metacheck needs R 4.5 or later (see README). Set `REVISCOPE_CONTACT_EMAIL` (see README) in the
environment the drivers start from; user services inherit it from `~/.config/environment.d/`. The commands below use macOS `caffeinate`; on Linux start each driver as a
user service instead, which survives the end of the session when lingering is enabled
(`loginctl enable-linger`). Pass `PATH` so the service finds `codex` and `claude`:

```bash
systemd-run --user --unit=ke-pipeline-luna --working-directory="$PWD" -E PATH="$PATH" -p StandardOutput=append:"$PWD/runs/known-errors-all/driver-pipeline-luna.log" -p StandardError=append:"$PWD/runs/known-errors-all/driver-pipeline-luna.log" .venv/bin/python eval/run_known_errors.py --papers 5 9 --concurrency 2
```

Check the chain without model calls (fixture backend, no judge), in a scratch root:

```bash
mkdir -p /tmp/known-errors-dry/inputs && cp -R runs/known-errors-all/inputs/paper-05 /tmp/known-errors-dry/inputs/ && cp -R runs/known-errors-all/ground_truth /tmp/known-errors-dry/ && .venv/bin/python eval/run_known_errors.py --root /tmp/known-errors-dry --papers 5 --backend fixture --no-metacheck
```

Papers 5 and 9, pipeline and plain baseline:

```bash
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --papers 5 9 --concurrency 2 >> runs/known-errors-all/driver-pipeline-luna.log 2>&1 < /dev/null &
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --mode plain --papers 5 9 --concurrency 2 >> runs/known-errors-all/driver-plain-luna.log 2>&1 < /dev/null &
```

The other configurations add `--model gpt-6.1-sol` and `--mode plain-nolist`, for example:

```bash
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --model gpt-6.1-sol --papers 5 9 --concurrency 2 >> runs/known-errors-all/driver-pipeline-sol.log 2>&1 < /dev/null &
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --mode plain-nolist --model gpt-6.1-sol --papers 5 9 --concurrency 2 >> runs/known-errors-all/driver-plain-nolist-sol.log 2>&1 < /dev/null &
```

A complete review is never regenerated, so a pipeline rerun after a pipeline change
needs the old `reviews/<label>/` folder moved out of `reviews/` first.

All papers: drop `--papers` (default 1 to 10). The optional Opus pipeline:

```bash
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --model claude-opus-5-5 --papers 5 9 --concurrency 2 >> runs/known-errors-all/driver-pipeline-opus.log 2>&1 < /dev/null &
```

Monitor files: `run.log` stage lines in each paper directory, new
`planted-error-adjudication.claude-opus-5-5.json` files, and `Traceback` in
`driver.log`. A stage running well past 60 minutes means the process is stalled,
usually after sleep.

Stop the drivers, then the review processes. Check each PID before killing model
calls; other sessions run their own `codex exec` and `claude -p` processes.

```bash
pkill -f "eval/run_known_errors.py"; pkill -f "reviscope.cli review .*known-errors-all"; pkill -f "plain_review.py .*known-errors-all"
ps -eo pid,ppid,command | grep -E "codex exec|claude -p" | grep -v grep
```

## Audit and score

The driver audits each review. To reread the verdicts and reasons for papers 5 and 9:

```bash
.venv/bin/python eval/audit_tool_use.py --planted-errors runs/known-errors-all/reviews/pipeline_gpt-6-luna_high_social_psychology/paper-05 runs/known-errors-all/reviews/pipeline_gpt-6-luna_high_social_psychology/paper-09 runs/known-errors-all/reviews/plain_gpt-6-luna_high/paper-05 runs/known-errors-all/reviews/plain_gpt-6-luna_high/paper-09
```

Score every configuration:

```bash
.venv/bin/python eval/score_known_errors.py
```

The output gives, per configuration, one summary per audit group and a comparison
restricted to the papers that are clean (or external) in every configuration.

## Caveats

- Recall is model-judged against the annotations: a development diagnostic, not a
  validated accuracy estimate. For the Opus pipeline the reviewer and the judge are
  the same model.
- The paper 5 input begins with the published article's DOI
  (`10.24839/2325-7342.JN23.2.98`); this line is part of the benchmark's modified
  manuscript. A reviewer that opens it fetches the answer key, and the audit flags
  the run.
- The audit matches recorded tool calls only. A search engine's summary of the
  original, or a page not in the manifest that quotes it, can pass unflagged.
- Search results that merely list the published original (title and snippet, not
  opened) are not flagged. Ordinary topic searches list it routinely. A snippet can
  reveal an abstract-level detail, but few planted errors sit at that level.
- Paper 2 is a pre-registration draft. Its method and results sections report a
  dummy dataset of 1000 responses generated by Qualtrics, so its numbers carry no
  empirical result.
- The `external` rows are the benchmark authors' stored reviews, made without tools
  and judged with the same judge. Their adjudication files have no `judge.tools`
  field, so the scores record `judge_tools: "unrecorded"`. The adjudicator builds its
  judge with `tools=False`.
- `reviews/litvak_openai_gpt55_high_reasoning_originals` holds reviews of the
  unmodified papers. Its recall is the rate at which a review of a paper without the
  planted errors is credited with one; report it next to every configuration.

## Engine 0.4.1 pilot series

The 0.4.1 pipeline verifies every candidate in module-based batches of at most ten.
Each batch has an independent cache and tool record; a failed batch leaves its own
candidates unverified and marks the run partial. Other batches retain their results.
External-source confirmation uses only that batch's recorded fetches and searches.

The verifier classifies external evidence as required or optional, with an explicit
explanation. Optional means that anchored manuscript evidence and established knowledge
support the claim as worded without the external items. Unchecked optional items are
removed from the finding and recorded in its verification trace; candidates and stage
artifacts retain them. Unusual empirical assertions and statements about a particular
source require external verification. Refuted external evidence always blocks support.
Preregistration leads reach both consistency and statistical inference in full.
Editorial merge targets must have a publishable final evidential status, rather than
only a supported model verdict.

The pilot root is `runs/known-errors-0.4.1`; the 0.4.0 series is recorded under
`runs/known-errors-all`. The pilot uses Codex CLI 0.160.0, with the root
`codex-update.timer` stopped for the series, and code snapshot `8e5fc939dcfbbcf7`.
Its persistent units are `ke-041-pilot-luna.service` and `ke-041-pilot-sol.service`.
Each runs papers 5 and 9 with concurrency 2. The driver logs are `driver-luna.log`
and `driver-sol.log` under the pilot root.

```bash
systemctl --user status ke-041-pilot-luna ke-041-pilot-sol --no-pager
.venv/bin/python eval/score_known_errors.py --root runs/known-errors-0.4.1
.venv/bin/python eval/trace_known_errors.py --root runs/known-errors-0.4.1 --output runs/known-errors-0.4.1/known-error-trace.json
```

Report clean, flagged and incomplete papers separately. Compare each pilot's clean
paper set to the same papers in the 0.4.0 series. The trace names failed verification
batches separately from contradictions and distinguishes refuted external sources
from sources that were not confirmed.

`ke-041-pilot-analysis.service` waits for both pilot drivers, then runs frozen copies
of the scoring and trace scripts. It writes `known-error-scores.json`,
`known-error-trace.json`, `known-error-trace.md` and `pilot-summary.md` under the pilot
root. The summary compares each pipeline with its plain baseline on the same clean
papers and input hashes, and reports missing adjudications explicitly. The local
collector is `runs/known-errors-0.4.1/finish-pilot.py`; its log is `analysis.log`. A
smoke check against the stored 0.4.0 results verifies the clean-paper denominators,
flagged-run exclusion and all 40 trace rows. After successful analysis, the collector
starts `codex-update.timer` to restore daily CLI updates. A collector failure leaves
the timer stopped and records its exception in `analysis.log`.


The four 0.4.1 pilot reviews and automatic analysis complete successfully on
2 October 2026. Results are recorded at the start of `docs/KNOWN_ERROR_RESULTS.md`.
Sol's clean-paper strict recall is 7/20 against the plain baseline's 12/20;
demonstrable recall is 6/8 for both, on the same six targets. Luna's clean paper 9
has 3/10, matching its plain baseline; paper 5 is flagged. The timer is active.
No full campaign or additional review run is scheduled.
