I'd approve the merge. Before any Meta-Psychology bulk run, one URL-matching gap needs closing (1 below). The other residuals are small.

I read `final.diff`, the current eval scripts and tests, and the archived pilot traces in `coarse-socpsy/runs/pipeline-redesign-20261003`. I ran nothing.

## Must fix before the Meta-Psychology bulk runs

**1. Reviewer and published-version pages can still be opened without a flag** (`eval/audit_tool_use.py:117-126` and the curated manifest)

The audit only treats a URL as the paper's own if it starts with an exact block string. Three ways around that remain:

- **OSF short links:** human reports and editorial archives are blocked only in the forms the manifest lists. The same file at `https://osf.io/unjf5/` is not caught, because the block is `osf.io/download/unjf5`. Neither is `osf.io/unjf5/download`, or `files.osf.io/v1/resources/vxqj5/providers/osfstorage/<file id>`. None of these hits `REVIEW_PATHS` either. So a fetched expert report in these forms would audit as `clean`.
- **Journal mirror:** the published, revised article is also served from `conferences.lnu.se/index.php/metapsychology/article/view/<id>`. That isn't blocked. The pilot traces already list it for both bonetto and ziano.
- **Minimal fix:**
  - For OSF hosts (`osf.io` and its subdomains), flag any URL whose path contains a blocked OSF GUID: archive, review and manuscript GUIDs, plus each review's `osf_file_id`.
  - Add the `conferences.lnu.se` view/download prefixes to `other_version_urls`.
  - Add tests for the short-link, `/download` and `files.osf.io` forms.

This doesn't change any historical verdict. Searching the six pilot traces for these GUIDs, the file IDs and `conferences.lnu.se` finds them only as unopened search-result listings, never as fetched pages. Once the mirror is blocked, a re-audit would add warnings, not flags.

## Minor residuals

**2. Manual overrides aren't part of the rule identity** (`audit_tool_use.py:156-159, 170-173`)
- `--title` replaces the manifest titles, and `--block`/`--planted-errors` change the checks. But `audit_rules_sha256` is computed from the unmodified `papers`.
- So an audit run with a weaker `--title` still passes `checked_audit`.
- **Fix:** include the overrides in the hash, or have `checked_audit` reject rows that used them.

**3. The rule hash leaves out the review-site list**
- `audit_rules_hash` covers `audit_tool_use.py` and the manifests, but not `reviscope.backend.REVIEW_DOMAINS`, which the audit imports.
- **Fix:** add `sorted(REVIEW_DOMAINS)` to the hashed payload.

**4. The published numerical-checks file still has the old wording**
- `docs/pipeline-development-analysis/numerical-checks.json:161` still says "Half applies only to the Hong Kong subset". The script no longer emits or computes that.
- **Fix:** regenerate the file in your separate system-Python numerical run. The new test checks only the `calculated` values, so it won't catch this.

**5. Judge identity is built from the wrong code copy** (`run_known_errors.py:183-191`)
- `adjudication_matches` builds the judge's identity from the `reviscope` installed in the driver's environment (the working tree), not the frozen snapshot that ran the judge.
- If `backend.py` differs between them, every paper is re-judged. That wastes subscription calls but doesn't corrupt scores.
- **Fix:** compute the identity with `args.code/src` on the path, or compare against the stored identity plus the snapshot digest.

**6. The audit arm's archived log includes the holistic arm's lines** (`run_development_review.py`)
- `run.log` is appended to, not replaced, so the archived audit-arm log also contains the holistic run's progress lines. Results aren't affected.
- **Fix:** truncate the log before each arm along with `review.json`, or label the log as cumulative.

## Repairs I checked and found sound

- **Identification:** the curated manifest loads first, and the pinned text hashes identify the pilot inputs (`bf652e…` for bonetto). Every human-review URL, editorial archive and `open.lnu.se` version prefix is blocked. Listings produce warnings only.
- **Comparison checks:** `checked_audit` requires the paper ID, the manuscript-text hash, the review hash, the resolved path, the rule hash and a `clean` verdict. If the manifests or audit script change, it refuses until the review is re-audited, which is the safe direction.
- **Runner:**
  - It deletes `review.json` before each arm, so a usage error can no longer archive the previous arm's report.
  - It checks the arm and profile before archiving, and checks them again for retained archives.
  - It records the code digest and fails if no output was written.
- **Judging and scoring:**
  - Adjudication reuse is keyed on the review, annotations, adjudicator script, judge identity and tools.
  - Scoring refuses mixed judging conditions, including within the headline comparison set. `--paper` is now required.
  - The trace no longer credits a published candidate the judge didn't match.
- **Numerical checks:** each stated conclusion is now checked against its computed values, with tolerances that are correct for the reported precision.
- **Reasoning change:** operation results are now labelled `unverified audit record`, and nothing else parsed the old label. The verifier now gets an explicit "criteria, not output fields" preface.
- **No regressions:** the new `support` and `unspecified` relation labels and the material guidance for the context modules don't touch the publication, source, remedy, severity or quota contracts. Schema and prompt changes invalidate the right caches.
