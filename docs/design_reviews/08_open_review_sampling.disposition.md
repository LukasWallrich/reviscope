# Disposition: open-review sampling audit

Fable returned **BLOCK** on the initial inventory and a narrower **BLOCK** on the first revision. No third model call was made: the remaining changes were direct, checkable corrections to labels and procedures.

## Initial findings

1. **No verified in-cohort exact pair for a proposed fixed pilot.** Resolved by removing the arbitrary fixed 30-paper design. The sampling frame now requires enumeration and article-level verification before sample sizes are frozen.
2. **BMJ/BMJ Open manuscript status overstated.** BMJ Open is now `policy_claim_unverified_at_article_level` with `access_blocked` evidence. Article-level checks are required for both titles.
3. **Nature example had not been inspected.** The official Lee and Sabatini peer-review PDF was downloaded and inspected. It contains initial-version reports and rebuttals, but no submitted manuscript; the audit now says so and links the exact file.
4. **Blocked retrieval was encoded as indexed-only.** BMJ Open, F1000Research and eLife are now `access_blocked`.
5. **Optional and mandatory cohorts were ambiguous.** `mandatory_from` and `earlier_policy` fields now encode the PeerJ, Nature Communications and Nature transitions.
6. **Pretraining contamination was omitted.** The protocol records knowledge cutoffs, probes possible memory of both manuscripts and human reports, disables retrieval/tool access, and recommends a prospective blinded cohort for stronger validity.
7. **PeerJ 236 was demoted after review-quality inspection.** It is explicitly a retrospective workflow diagnostic outside future estimates; all four human reports and AI outputs remain reportable.
8. **The proposed sample was dominated by convenient health venues.** It is now labelled an artifact-feasibility sample. The validation target is completed quantitative empirical social/personality psychology, defined before journal selection.
9. **Enumeration and blind selection were underspecified.** The frame requires a frozen metadata export and eligibility decisions before article pages or review files are opened. Counts precede quotas.
10. **Secondary-source and evidence limitations.** The source audits retain these as bounded leads rather than policy guarantees.
11. **CSV presence.** The companion CSV exists and is validated alongside the Markdown audit.

## Follow-up findings

1. **Competing definitions of the first sample.** Both references to PeerJ/BMJ/BMJ Open now call that set an artifact-feasibility sample, not the target validation population.
2. **Memorization probing covered only papers.** The rule now explicitly covers every public human report as well as the manuscript.
3. **Eligibility screening was not required to be blind.** Topic, design and article-type screening must now use a review-free metadata export, with decisions frozen before artifact retrieval.
4. **Mandatory/optional eras required hand parsing.** Structured `mandatory_from` and `earlier_policy` fields were added.

## Additional scope corrections

- `exact` requires a deposited file explicitly tied to the reviewed round or a byte/text match to a known submission. Externally matched preprints remain `high_confidence_proxy` sensitivity cases.
- Combined PDFs must be split into manuscript-only derivatives, with raw and derived hashes, page bounds, and manual plus automated leakage checks.
- The current alpha validation scope is quantitative. Qualitative archive examples demonstrate future corpus availability, not current method coverage.

## Validation

`docs/research/open-review-journals.json` parses successfully with Python's JSON parser, and `git diff --check` reports no whitespace errors.
