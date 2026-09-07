# Fable reconciliation and numeric-anchoring review

Model: `claude -p --model fable --effort high`, tools disabled, strict MCP configuration, safe mode, no session persistence.

## Verdict: BLOCK

Two defect classes violate the requested contracts.

## Numeric dehyphenation and anchoring

1. The line-end dehyphenation guard accepts digit neighbors. A source containing `2-\n3` normalizes to `23`, so a fabricated quote containing `23` can anchor. Restrict discretionary dehyphenation to alphabetic neighbors. A mixed compound such as `COVID-\n19` may remain a safe false negative rather than being corrupted.

2. The post-match `_numbers` comparison is tautological because the selected source slice already equals the needle. Plain substring matching permits truncated numeric prefixes: `estimate was -0.2` can match the beginning of `estimate was -0.25`; a quote beginning `0.25` can also omit a preceding sign. Add numeric boundaries around the escaped quote match, then remove the ineffective self-comparison.

3. Unicode NFKC folds some superscript numbers into ASCII, so source `10³` may anchor quote `103`. Preserve Unicode number characters in category `No` rather than compatibility-folding them.

Original-source offsets for successful matches are correct. The source-span regression over `multi-\nlevel estimate was −0.25` is consistent with the implementation. A genuine hyphenated word split across lines may fail to match a quote retaining its hyphen; this is a safe false negative.

Required regressions:

- Source `2-\n3` cannot anchor quote `23`.
- Source `-0.25` cannot anchor truncated quote `-0.2` or a sign-omitting numeric quote.
- Source `10³` cannot anchor quote `103`.

## Editorial reconciliation

1. Required reconciliation uses an allowlist for backend names `codex` and `claude`. Any other non-fixture backend can return null reconciliation, record the editorial stage completed, and cause the renderer to label untouched preliminary text as the final Study overview. Require reconciliation for every backend except the explicit deterministic fixture.

2. `ReconciledOverview` permits null summaries. A model can return null intending “unchanged,” wiping a valid preliminary summary. If a preliminary design or contribution summary is non-null, reject a null replacement and fail closed. Do not silently fall back to the preliminary field because it may contain the contradiction reconciliation was meant to remove. An empty strengths list remains valid.

The typed response cannot mutate findings. Successful reconciliation changes only summaries and strengths while retaining studies and research question. Exceptions occur before applying reconciliation, cached editorial artifacts are removed, findings are quarantined, and the renderer labels failed/skipped editorial output as preliminary and unreconciled. Cache identity includes the study map and findings.

Required regressions:

- A non-fixture backend omitting reconciliation yields a partial run, failed editorial stage, unreconciled renderer label, and unchanged preliminary study map.
- A null reconciled summary cannot erase a non-null preliminary summary.
- The editorial exception path retains the preliminary map and renders it as unreconciled.
