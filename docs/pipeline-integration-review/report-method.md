## Verdict: not ready to gate final reporting; the identity checks are mostly sound, eight concrete fixes remain

I used only Read/Glob/Grep. I made no writes, ran no commands or tests, and made no model calls. I'm not approving any outcomes that haven't been observed yet.

**What already works well:**
- **Snapshot hashes.** `provenance_audit.py` re-checks all three snapshot digests: generation f7, native judge calls `09dd60` and offline rewrap `7eaf`.
- **Native judge instruction.** It requires `09dd60` and `7eaf` to share the literal judge instruction.
- **Raw-call identity.** It rebuilds each native raw-call key from the immutable packet snapshot, the instruction, the schema, the backend identity and the protocol string. A stale or altered packet therefore can't pass, even though the `09dd60` raw files lack an explicit packet hash.
- **v4 comparisons.** It rebuilds the full whole-report inputs and checks them against `09dd60`'s own `comparison_parts`, which substitutes for the prompt metadata missing from v4.
- **Offline rewrap.** `offline_finalize.py` stops on the first failure, runs `--offline`, and confirms every raw judge file is byte-for-byte unchanged.
- **Draft interpretation.** It is generally restrained: no precision/recall, no causal stage claim, no equal-compute claim, controls described as protocol probes, and the post-hoc targeted checks labelled as such.

## Must-fix before the final reporting gate

**1. "complete_verified" doesn't require the rewrap.** The status only checks the count of 12 native rows and 48 comparisons (`provenance_audit.py:73`). It never checks `rewrapped_offline`. Rows still wrapped by `09dd60` would pass as final. Those rows lack `quote_check_passed`, still count non-shown items as legacy remedies, and have no `present_in_audit`. Require every row's matcher to sit under `7eaf`, and require the `7eaf` provenance fields.

**2. The scripts that audit and report aren't in any snapshot.** `provenance_audit.py`, `offline_finalize.py` and `summarize.py` run from `runs/` with no recorded hash. Write their SHA-256s into `offline-finalize.json`, `assessment-provenance-audit.json` and `assessment-summary.json`.

**3. The v1 rederivation isn't audited, but its counts are reported.** The methods doc reports "14 Bonetto Opus labels and one Sol label", yet nothing checks the rederived artifacts. Add checks that:
- each `original_sha256` matches the current v1 file;
- the matcher module is under `7eaf` and the method hash matches;
- raw labels and the other model fields are unchanged from v1.

Recompute the counts after v1 finishes, since the frozen runner is still adding cases.

**4. The summary drops a targeted-check artifact.** `summarize.py:138-142` globs `*check.json` and lists `review-quality-numerical-checks.json`. The actual file is `preflight/reproducible-numerical-checks.json`, which carries a `script_sha256`. It matches neither, so it never reaches the summary.

**5. The quote-boundary impact statement doesn't match its artifact, and its scope is narrower than stated.**
- `QUALITY_ASSESSMENT_METHOD_REPAIRS.md:42-44` says the only changed candidate quote was Sætrevik's "N = 781". `quote-boundary-generation-impact.json` lists 2 unique quotes. The second, "Support for less sharing in MS group (N = 781", is in `evidence_audit:8:F09`, which was merged.
- `eval/audit_quote_boundary_impact.py:28-31` scans only `candidates[].evidence`.
- It doesn't scan verifier quotes, which can carry a finding on their own (`verification.py:228-237`). Dropped verifier quotes survive only in traces, cut to 120 characters.
- It doesn't scan quotes dropped from coverage checks (`discovery.py:113`).
- Either extend the scan to the traces (flag truncated quotes as uncheckable) or limit the statement to "candidate evidence only".

**6. The draft's method text implies the quote check covers more than it does** (`REVIEW_QUALITY_TRAINING_RESULTS.md:54-59`). State that:
- the exact-quote check applies only to claim labels; rationale, remedy and consequence labels are unchecked model opinions;
- rationale and remedy labels can't be compared across arms. Plain items have no separate fields (`not_separately_supplied`), while pipeline remedies reach the judge only if the verifier marked them supported.

**7. Errors and retries are hidden for whole-report comparisons.** Neither the summary nor the audit reads `comparisons-v4/*/*/history/`, so an original invalid attempt followed by a valid retry looks like a clean single call. Report attempts per comparison: original error, then retry outcome. Native criticism `.invalid.json` files and generation attempts are already listed.

**8. The summary can show a complete-looking state from incomplete or mixed inputs.**
- The header (`summarize.py:17-18`) takes the native v2 completion file (`assessment-v2-complete.json`) alone. Gate it on `offline-finalize.json` reporting complete and on the provenance audit reporting `complete_verified`.
- `use_v2` (`:47`) switches a case to v2 if either judge has a v2 file. A missing judge is then silently skipped. A case with no v2 at all falls back to v1, so conditions get mixed across cases.
- Record a missing judge as an error, and refuse a final render unless all 12 v2 judge files are present.

## Reporting requirements for the strata you listed

- **Same ID, different presentation.** Report items shared by both nested arms, holistic-only items and audit-only items as separate strata. Report label disagreements within same-ID unmerged pairs as a within-call consistency check, not as distinct issues.
- **Excluded strata.** Beyond the counted author-visible unresolved concerns, give the count of supported-but-held or rejected findings. `finding_status_dispositions` already contains it, and the draft itself mentions "previously held" items.
- **Bundled vs atomic items.** Native item counts aren't atomic claims. Shared judgments count toward both nested arms and aren't independent.
- **Controls.**
  - The two mixed-probe failures were probe-design errors.
  - "Reject a false numerical rationale" and "abstain on the unseen figure" each rest on a single probe item per family.
  - The source-only probe was designed after seeing outputs. Its raw labels don't depend on the matcher, but record the code it actually ran with: it used the live `eval/` folder, not `09dd60`/`7eaf`.
- **Partial metacheck.** For Mackinnon and Niemeyer, say which arms received the partial screening leads, and that "no flag" there doesn't mean the check passed.
- **Original errors vs successful retries.** Sætrevik's audit is a retried sample conditional on success; show that in the case table.
- **All 18 reports.** "Passed the current recorded-source audit" means under post-generation rules, so cite the rules hash. The 48 comparisons re-run the audit gate on every AI arm, which covers all 18 reports once complete. An explicit 18-row identity table would make that visible.

## Optional implementation refinements

- In the audit, recompute the checked labels from raw output with the recorded matcher, and compare every raw field, not only `claim_status`.
- Derive the expected comparison set from `launch.json` and each case's human reviewers instead of hard-coding 48. All six cases currently have two humans, so 48 is correct today.
- Verify all snapshots with one trusted digest function rather than each snapshot's own `run_known_errors.py`.
- Bring the controls into the provenance audit as a separate stratum.
- Cite DOIs next to the third-party PDF links.

## Scientific follow-ups

Unchanged:
- expert adjudication of disputed and high-impact items, whole rationales and remedy burden;
- an atomic inventory with a reproducible sample;
- a separate assessment of the excluded unresolved and held strata;
- repeat generation;
- a compute-matched broad read;
- an independent corpus chosen after development.
