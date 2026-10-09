I'd approve this for merge and for the Meta-Psychology development assessment; I found no remaining must-fixes. I read the updated `final.diff` and the current eval scripts and tests, and ran nothing.

**What I checked against the earlier issues:**
- **Contamination audit:**
  - Matching on OSF short links, `/download` forms, `files.osf.io` resource paths and 24-character file IDs is now limited to `osf.io` and its subdomains. The ID pattern can't pick up ordinary path words in the current manifests.
  - Look-alike hosts such as `not-osf.io` don't match.
  - Both the `open.lnu.se` and `conferences.lnu.se` view/download paths are blocked for all six cases.
  - Search listings still produce warnings only.
- **Audit rule identity:** the rule hash now covers manual overrides and `REVIEW_DOMAINS`. `checked_audit` compares against the default rules with no overrides, so an audit run with `--title`, `--block` or `--paper` is refused for primary comparisons.
- **Comparison inputs:** `prepared.json` already carries `profile` from `recommended_profile`, so the new profile check works for pipeline outputs. The plain baseline is correctly exempt.
- **Development runner:**
  - It deletes stale `review.json` and `run.log` before each arm and checks the arm and profile before archiving.
  - It refuses retained archives whose code or input hashes differ or are missing.
  - Consequence: the historical pilot root has no recorded code hash, so extending it will be refused. That's the intended behaviour; start a new root.
- **Judge identity:** it is now computed in a subprocess using the frozen snapshot, with the same environment as the adjudicator, so it can't drift from the working tree.
- **Numerical checks:** the published JSON now matches the script's conclusion.
- **Pipeline guarantees:** the source, anchoring, remedy, severity, cache and no-quota guarantees I listed last round are still intact.

**One small gap, not blocking:** a page opened through OSF's file renderer would still pass. That renderer puts the file address in the query string (for example `mfr.osf.io/render?url=https://osf.io/unjf5/...`), and only the URL path is checked. Fetching the file directly is caught. If you want to close it, also check the decoded query string for blocked IDs on OSF hosts.
