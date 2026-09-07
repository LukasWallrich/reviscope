**SHIP**, with the amendments below. All are specification gaps rather than design faults, and none changes the sampling approach.

1. **`version_dependent_unevaluable` has no assigner or timing.** If a scorer applies it after seeing AI output, it becomes a rescue for AI misses. Assign it during the substantive audit from the proxy text alone, before any AI output exists. Flag the symmetric case too: AI points about content present only in the proxy should not be scored as unmatched or false. Add a preregistered per-paper cap on the flagged share of human points. Above the cap, the audited-proxy label is falsified and the record drops out of that tier.

2. **The audit has no pass criterion and no inconclusive outcome.** Short or positive reports cannot discriminate versions, so absence of detected mismatch currently defaults to admission. Require positive concordance on a minimum field set and add an `audit_inconclusive` result that leaves the record at `temporal_proxy_unconfirmed`.

3. **"Before any review feedback could have been incorporated" has no date source.** Make it a hard constraint: the proxy version must predate the earliest dated report or first decision in the published exchange. For transfers, use the earliest report in the whole chain, which may predate the accepting journal's received date. The ±7-day window is secondary to this constraint.

4. **Admissibility beyond 30 days is implied but undefined.** "Do not use an older close match without the substantive audit" reads as permitting audited proxies at any gap, which places them outside every sensitivity window. Set a hard maximum or exclude proxies beyond 30 days from primary estimates.

5. **Tier and contamination are confounded.** Preprints post months before publication, so audited proxies will predate model cutoffs far more often than exact files. Report memorization probes stratified by tier and state the confound. Also name the pathway where the published post-review version is in training data and lets the model anticipate reviewer-driven changes.

6. **Exclusion timing is ambiguous between scoring and generation.** Lock mismatch exclusions before the auditor sees any AI output. Generate for every frozen-included paper regardless, and retain outputs for excluded papers.

7. **"Where feasible, preregister" the 0/7/30 windows is a loophole.** At minimum, record the actual gap in days for every proxy so sensitivity is always computable. Record version-specific timestamps from the preprint server, not the landing-page date, since PsyArXiv and OSF show created and last-edited dates that differ from version dates.

8. **Matching fields omit reviewer-cited locations.** Line, page, figure and table references in reports are the cheapest strong version discriminator, and Nature Portfolio reports use them routinely. Add a three-way comparison of proxy, published version and exchange. Any proxy-to-published difference the exchange does not explain is evidence of pre-submission revision and should downgrade the record.

9. **Excluded-for-mismatch cases vanish from reporting.** The auditor decides exclusion after reading review content with only a partial rubric. Report excluded cases with their review characteristics and run a sensitivity analysis that readmits them with all disputed points flagged.

10. **`exact` via "text match" has no threshold.** Define the normalization and similarity cutoff, or near-identical files will be labelled exact.
