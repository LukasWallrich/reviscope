# Disposition of Fable scientific-quality review

## Accepted as release-blocking evidence gaps

- No completed real empirical social-psychology review exists.
- The only substantive real-paper artifact is partial and does not exercise verification or editorial synthesis.
- Same-model verification is not independent and must have accurate provenance.
- The current demo reveals severe verbosity, duplication, severity inflation, and remedy overreach.
- Current evidence does not demonstrate competitiveness with human reviews or a low false-claim rate.

## Accepted implementation defects for the next profile revision

- Add manuscript-maturity triage and make zero or few findings the default for insufficient material.
- Calibrate severity across modules and treat reporting absence separately from demonstrated methodological failure.
- Verify remedies as well as claims, with explicit prohibitions on retrospective preregistration and unsupported analysis requests.
- Consolidate semantic issue clusters across modules before enforcing a display cap.
- Identify author-acknowledged limitations and require a conclusion-scope mismatch before elevating them.
- Add structured table/prose consistency checks; quote anchoring over prose alone is inadequate.
- Record verifier relationship as different model family, same model separate call, or deterministic check.

These rubric changes were not applied immediately because a real Luna run was underway with the current profile. Changing the profile would invalidate its cache and make the resulting artifact scientifically incomparable.

## Interpretation constraints

The z-curve output is a development diagnostic, not a completed review. Fable's arithmetic reading of Tables 9 and 15 is a strong, source-grounded lead, but any public scientific claim should be independently checked against the rendered tables or extracted structured values. Questions about the estimator's numerical implementation require code or specialist analysis.

The short demo is intentionally incomplete, but that does not excuse the pipeline behavior: its role as an insufficiency stress test makes the failure to triage especially informative.

One Fable lead was narrowed after visual inspection of the rendered source. Table 15 contains three cells below 95%, but the manuscript says the interval is conservative **under most circumstances** and separately recommends a larger correction below 25 tests. Those cells do not by themselves contradict that qualified wording. They remain useful evidence about condition-specific coverage, not an established prose-versus-table error. The Table 9 bias inconsistency was visually confirmed and remains a valid held-out check.
