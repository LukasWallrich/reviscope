## Verdict: not approved yet

I read all the requested files and the frozen evaluation and verification code, and checked the retained artifacts. I didn't run any models or tests or change any files. The framing is mostly careful: it's labelled as training data, it avoids pooling, judges aren't treated as truth and human reviews are comparators. But one harness bug distorts the criticism labels you already have, and several summary and harness gaps need fixing before the tables are completed.

## Must-fix

**1. The quote matcher rejects exact quotes that end in a number followed by a period or comma.**
- **Cause:** `_numeric_boundaries_ok` (`src/reviscope/verification.py:61-75`, same code in the frozen tree) counts `.` and `,` as part of a number. So `p = .88` in "…p = .88. Effect…" counts as cutting through a number.
- **Evidence:** all 14 downgrades in Opus's Bonetto assessment involve unmatched quotes ending in a digit. I confirmed three are verbatim in the manuscript and followed by a period: "…Z = -0.15, p = .88", "…Studies 2 and 3", "…$0 and $1000". That is 14 of 73 Bonetto items. Statistical criticisms are hit hardest, which skews comparisons between arms and inflates Opus–Sol "disagreements".
- **Wider impact:** the same function anchors evidence in the frozen pipeline (`discovery.py:113`, `verification.py:234`, `pipeline.py:335`). Generation may have lost or downgraded candidates for the same reason.
- **Fix:** treat `.`/`,` as part of a number only when a digit follows. Add regression tests both ways ("p = .88." should match; ".8" inside ".88" should not).
- **Re-derive offline:** raw quotes and labels are retained, so labels can be recomputed without model calls. Also count, from the frozen traces, evidence that failed only at a boundary. Keep the frozen outputs as they are and report this as a post-freeze repair.

**2. The nested arms put duplicate items in front of the judge.** Broad-read findings appear under both the holistic and audit arms in one packet (e.g. `broad:2:F03` is item-013 and item-039). Opus noticed: item-039's reasoning is just "This duplicates item-013 … verified there." The two copies then got different final labels only because of bug 1. As a result, per-arm counts double-count shared items, and the audit's own contribution is never isolated.
- Assess shared text once and attribute it to both arms.
- Report audit items as inherited (`broad:`) vs new (`evidence_audit:`).
- List holistic findings the audit's editorial pass dropped (e.g. `broad:6:F07`, `17:F18`, `18:F19` appear only under holistic). The audit-vs-holistic preference otherwise mixes added findings with editorial removals.

**3. The summary asserts results instead of deriving them.**
- `summarize.py:81` prints "Both families correctly handled the five … controls" whenever the results file exists. Lines 87–88 hard-code conclusions from the targeted checks and the engineering work.
- `assess_campaign.py:53` writes `assessment-complete.json` regardless of non-zero return codes or unavailable cases, and `summarize.py:15` then reports "Completed diagnostic pass".
- Nothing surfaces excluded arms, `.invalid.json` files or status-file errors.
- Disagreements (`summarize.py:55`) and label counts use labels after the quote check. Show raw and quote-checked labels side by side, and flag disagreements caused only by the quote check.

**4. Unresolved concerns that authors do see are never assessed.** The report shows a "Concerns the verifier could not confirm" section (`render.py:54-62`). Both assessments drop these items (`criticism_audit.py:127`, `compare_development_reviews.py:48`), although the plan (lines 77–78) says to keep them as a separate stratum. Either assess them separately or count them and state the exclusion. As written, "every native published criticism" (results doc, line 40) overstates the coverage.

## Method caveats to state explicitly

**5. The arms are filtered differently.**
- Pipeline items reach the judges only after the Opus verifier marked them supported; plain items are unfiltered. Per-arm support proportions are therefore not comparable, not merely "not precision".
- The bias has a direction. Opus verified, and possibly reconciled, the pipeline text, so Opus's self-preference favours the pipeline arms. Sol generated both arms, so its bias is closer to symmetric. Report results per judge family with that asymmetry stated.

**6. Blinding hides labels, not identity.**
- Formats reveal the arm: plain has severity/subcategory/location; the pipeline has claim/rationale/"Suggested response"/"External evidence".
- Human reports are full prose, while AI text is stripped to criticisms with no overview or strengths. Only Opus judges the human comparisons.

**7. The whole-report judge prompt (`evaluation.py:191-199`) lacks two rules the criticism judge has.** It says nothing about not inferring figure contents and nothing about genre (tutorial or proposal). It only covers source-dependent assertions, so your requirement that image assertions stay unresolved isn't enforced there.

**8. Items aren't judged independently.** All arms share one call, and the judge cross-references items despite the "independently" instruction. Document this.

**9. The controls are easier than stated.**
- Item-004's rationale says "No actual figure pixels are available" (`judge_controls.py:15`). Opus: "The rationale itself concedes this."
- Items 001 and 003 supply the defeating quote as the critic's own evidence.
- Item-005 scores only the remedy; Sol's claim label there was downgraded by the quote check.
- Rephrase "passed all five" as "passed the five scored fields" and harden item-004.

## Evidence and reporting gaps

10. **Targeted checks:**
    - The Ziano equivalence check (`preflight/ziano-equivalence-summary-check.json`) isn't in the doc or in `summarize.py:82`.
    - The Sætrevik and Bonetto artifacts have no `selection` field.
    - The Bonetto simulation and pooled-effect reconstruction have no retained code or output.
    - The Button PDF isn't hashed, unlike Rosenblatt's.
    - The arithmetic scripts aren't retained.
    - "Independent arithmetic" should read "post-hoc arithmetic by the assessing agent".
    - Cite DOIs rather than the unofficial PDF hosts.
11. **R repair:**
    - The full suite (205) ran before the final handler; only focused tests were rerun afterwards. Rerun the full suite or say so plainly.
    - "Local main includes the repair at `df6812f`": that is HEAD of `reasoning-assessment`. I couldn't confirm it's on main; check with `git branch --contains df6812f`.
    - "Opus approved" is a model review, not a human one.
12. **History is overwritten.** Outputs are replaced when the cache key changes or an invalid run is retried (`criticism_audit.py:152-157`, `compare_development_reviews.py:71-85`). That contradicts `summarize.py:46`'s "preserve historical outputs". Version the outputs by key.
13. **Dashboard inconsistencies:**
    - Pipeline "issued" counts include candidates (`preview_server.py:42`), unlike `summarize.py:25`.
    - "Local main: f7aab38" is actually the frozen commit.
    - "200 tests pass" is stale (the doc says 205).
14. **One-paper intervals:** raw comparison files carry a Wilson 95% interval for a single paper (`evaluation.py:332`). The summary ignores it; don't cite it anywhere.
15. **Remedy filters don't match (not triggered yet).** The comparison shows remedies when `remedy_status` is `None`; the criticism audit shows them only when it is `supported`. So far `None` appears only on candidates, but align the two or assert.

## Usefulness

Once bug 1 is fixed and labels are re-derived, the design is a reasonable diagnostic:
- separate claim, rationale and remedy labels
- raw labels retained
- no-tools judges
- both presentation orders, no pooling
- frozen inputs checked against their hashes
- clean-audit gates, with exact manuscript and profile matching

The Heyman disagreement record is a good model: whether a criticism is a useful clarification and whether its error allegation is valid are separate questions.

## Scientific follow-up still needed

- Qualified assessors to adjudicate high-impact and disputed items, items the quote check downgraded, and the audit's new contributions.
- An expert-checked atomic inventory, plus a reproducible sample.
- Repeated generation to estimate variance.
- A compute-matched broad-read comparator for the audit.
- An independent corpus chosen after development.
