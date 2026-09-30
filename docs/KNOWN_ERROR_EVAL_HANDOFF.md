# Planted-error benchmark evaluation: handoff

## Goal

Score ReviScope configurations against the 100 planted errors in the Dawes
benchmark (Litvak, 10 psychology papers, commit `3d91883`). Report strict recall
over all 100 targets and over the 42 targets that
`docs/benchmark-validity-audit/audit-100.json` classifies as
`valid_demonstrable_error`, for candidate findings and for published findings
separately.

Configurations to run once the pipeline code is ready:

| Label | Mode | Reviewer | Papers |
|---|---|---|---|
| `pipeline_gpt-6-luna_social_psychology_v2_<tools>` | pipeline | codex `gpt-6-luna`, effort `max` | all 10 (4, 5, 9 first) |
| `pipeline_claude-opus-5-5_social_psychology_v2_<tools>` | pipeline | claude `claude-opus-5-5`, effort `max` | 4, 5, 9 |
| `plain_gpt-6-luna_<tools>` | plain (one call, Dawes `REVIEW_PROMPT`) | codex `gpt-6-luna`, effort `max` | all 10 |

`<tools>` is `tools` or `notools`; the plain baseline uses the same condition as
the pipelines. Papers 4, 5 and 9 were chosen as paper 5 plus the lowest- and
highest-scoring papers of the Luna 5.6 pipeline; they are a diagnostic spread,
not a sample. For the Opus pipeline the reviewer and the judge are the same
model; report that caveat. Never use GPT-5.6 models.

## Current results

`eval/results/known-errors-all.json` (judge `claude-opus-5-5`, effort `high`, no tools):

| Configuration | All targets (candidate / published) | Demonstrable subset (candidate) |
|---|---|---|
| `pipeline_gpt-5.6-luna_social_psychology_v2` (old code, no tools) | 36 / 29 of 100 | 29 of 42 |
| `litvak_openai_gpt55_high_reasoning` (Litvak's stored reviews) | 71 of 100 | 38 of 42 |
| `litvak_openai_gpt55_high_reasoning_originals` (same model on unmodified papers) | 8 of 100 | 5 of 42 |

Litvak's own Haiku judge gave 71 and 24 for the last two rows. The originals row
is the rate at which a review of the unmodified paper is credited with a planted
error; report pipeline recall next to it. Plain reviews have no verification or
editorial stage, so their candidate and published scores are the same list.

## Files

- `eval/prepare_known_errors.py`: downloads the benchmark, writes
  `runs/known-errors-all/inputs/paper-NN/manuscript.review-input.txt` (banner
  removed) and `ground_truth/error_insertions.csv`. Inputs exist; rerunning is safe.
- `eval/run_known_errors.py`: per configuration, reviews each paper into
  `runs/known-errors-all/reviews/<label>/paper-NN/` and scores it. Rerunning is safe:
  cached stages are reused, complete reviews are not regenerated, a score is redone
  only when its `review.json` changed. A `review.json` placed in a paper directory
  by other means is scored without regeneration.
- `eval/plain_review.py`: the single-call baseline.
- `eval/adjudicate_known_errors.py`: the judge. It always runs with `tools=False`.
- `eval/score_known_errors.py`: writes `eval/results/known-errors-all.json`, with
  per-configuration recall, a comparison on the papers that all configurations
  share, and provenance hashes. It refuses scores from a judge that had tools and
  reviews that changed after scoring.
- `eval/audit_tool_use.py`: flags tool calls that could expose the answer key.
- `runs/known-errors-all/superseded/`: void or aborted runs; not scored.

## Before launching

1. **Freeze the code.** Other sessions edit `src/` while runs are going, and each
   review process imports whatever is on disk when it starts. Snapshot the finished
   code and run from the snapshot:

   ```bash
   rm -rf runs/known-errors-all/code-snapshot && mkdir -p runs/known-errors-all/code-snapshot && cp -R src/reviscope runs/known-errors-all/code-snapshot/ && .venv/bin/python -m pytest -q
   ```

   The driver prints the snapshot's sha256 at start; keep it in the report.
2. **Decide tools on or off.** With tools, a reviewer can find the published
   original, which is the answer key. The pipeline records every tool call and
   `eval/audit_tool_use.py --planted-errors` flags title searches, benchmark-repo
   URLs and the paper's own DOI. Litvak's runs were tool-free.
3. **If tools are on, close two gaps first.**
   - `plain_review.py` does not save tool calls. Store `backend.take_tool_calls()`
     in its output, or plain runs cannot be audited.
   - The 10 benchmark papers are not in the corpus manifests, so the audit cannot
     identify them by input sha256. Add them to a manifest (title, original DOI,
     `review_input_sha256` from `inputs/paper-NN/provenance.json`), or pass
     `--title` and `--block` for each paper.
4. **If tools are off**, check that `reviscope review` exposes a way to construct
   both backends with `tools=False`, and that `plain_review.py` passes the same flag.
5. **Pilot one paper per configuration.** Confirm that `study_map: completed`
   appears in `run.log` and note how long it took. Tools-on stages can be much
   slower than the 3–7 min per stage of tool-free runs; estimate the batch time from
   the pilot before launching the rest.

## Launching

Background tasks die when the Claude session ends, and the Mac idle-sleeps on
battery, which stalls every model call. Launch each driver detached and wrapped in
`caffeinate`, from the repository root, with every argument written out (zsh does
not split an unquoted variable into several arguments):

```bash
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --code runs/known-errors-all/code-snapshot --label pipeline_gpt-6-luna_social_psychology_v2_tools --papers 4 5 9 1 2 3 6 7 8 10 --concurrency 3 >> runs/known-errors-all/driver-luna6-pipeline.log 2>&1 < /dev/null &
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --code runs/known-errors-all/code-snapshot --backend claude --model claude-opus-5-5 --effort max --label pipeline_claude-opus-5-5_social_psychology_v2_tools --papers 4 5 9 --concurrency 3 >> runs/known-errors-all/driver-opus-pipeline.log 2>&1 < /dev/null &
nohup caffeinate -i .venv/bin/python eval/run_known_errors.py --code runs/known-errors-all/code-snapshot --mode plain --label plain_gpt-6-luna_tools --papers 4 5 9 1 2 3 6 7 8 10 --concurrency 2 >> runs/known-errors-all/driver-luna6-plain.log 2>&1 < /dev/null &
```

Replace `_tools` with `_notools` in the labels for a tool-free run. Keep the Mac on
mains power. Keep Codex concurrency at about 3 per account; throttled calls time
out and produce partial reviews.

Monitor through files, not process output: new
`reviews/<label>/paper-NN/planted-error-adjudication.claude-opus-5-5.json` files,
`run.log` stage lines, and `Traceback` in `driver.log`. A stage running well past
the 30-minute per-call timeout means the process is stalled, usually after sleep.

## Stopping

Kill the drivers, then the review processes, then any model calls whose parent is
PID 1. Check each PID before killing; other sessions run their own `codex exec` and
`claude -p` processes.

```bash
pkill -f "eval/run_known_errors.py"; pkill -f "reviscope review .*known-errors-all"; pkill -f "plain_review.py .*known-errors-all"
ps -eo pid,ppid,command | grep -E "gpt-6-luna|claude -p" | grep -v grep
```

## After the runs

1. `.venv/bin/python eval/score_known_errors.py`
2. If tools were on:
   `.venv/bin/python eval/audit_tool_use.py --planted-errors runs/known-errors-all/reviews/<label>/paper-*`.
   Report flagged runs separately or exclude them; do not pool them silently.
3. A partial review is scored with `--allow-partial` and stays labelled. The paper-2
   flag in the Luna 5.6 run is deterministic (an editorial merge to a missing target)
   and does not clear on retry. Paper 2 contains simulated placeholder data, and the
   pipeline publishes a single triage finding for it.
4. In the report, give `uncertain` counts next to `detected`, the breakdown by audit
   verdict, and the originals false-credit rate.

## Not yet committed

`eval/prepare_known_errors.py`, `eval/run_known_errors.py`, `eval/plain_review.py`,
`eval/score_known_errors.py`, the changes to `eval/adjudicate_known_errors.py`,
`eval/results/known-errors-all.json`, and the `gpt-6-luna` default changes in
`src/reviscope/cli.py`, `src/reviscope/pipeline.py`, `README.md` and
`docs/DISCOVERY_V3.md`. The working tree also holds another session's uncommitted
tools-enabled pipeline changes; commit the two sets separately.
