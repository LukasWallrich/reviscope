# Fable scientific-quality review

Model: `claude -p --model fable --effort high`, with tools disabled, strict MCP configuration, safe mode, and no session persistence.

## Verdict

Neither supplied run demonstrates an end-to-end scientific alpha. The 277-character demo was inflated into twelve Major findings that reduce to roughly four missing-information categories. The z-curve run did not complete statistical inference, verification, or editorial stages. It produced fifteen unverified findings that reduce to about seven issues and missed a stronger manuscript-internal prose-versus-table inconsistency.

## Ranked findings

1. **Critical — table reasoning is absent.** The review missed that Table 9 conflicts with the prose claim used to justify the ±0.02 confidence-interval correction. At `k=1000` and true power `.75`, reported z-curve means of `.785` to `.796` imply bias of 3.5–4.6 percentage points, exceeding the manuscript's claim that bias is never above two points for larger samples.
2. **Critical — the real-paper pipeline did not finish.** Statistical inference timed out after 600 seconds; interpretation, deterministic checks, verification, and editorial selection did not run.
3. **Critical — verifier independence was overstated.** The demo generator and verifier were both Codex Luna at max effort. All 23 candidates passed, while provenance said `independent_model`. A separate call to the same model is not model independence.
4. **Major — no manuscript-maturity gate.** A stub hit the 12-finding cap. A careful review would state that it is not reviewable and consolidate four missing-information categories.
5. **Major — cross-module synthesis failed.** Z-curve's selection-model/p-hacking limitation appeared three times at Major/Major/Critical; bootstrap calibration three times; input dependence three times; test-family generality twice; and the simulation generator twice.
6. **Major — acknowledged limitations became purported discoveries.** Many z-curve findings quote the authors' own Discussion caveats without showing that conclusions exceed those caveats. The defensible residue is a narrower claim-scope mismatch about recommending z-curve for published results.
7. **Major — remedies import inappropriate conventions.** Examples include retrospective preregistration, allocation concealment language for a simple lab study, measurement invariance at total N=60, and prespecified practical thresholds for a 2018 simulation paper.

## Concrete examples

The demo dependence finding concedes that no dependence is implied, then requests clustered analysis. The measurement finding requests invariance or differential-item-functioning analysis without establishing that either is useful or feasible. The design finding imports CONSORT terms. The hypothesis finding asks authors to preregister a completed study. One finding anchors itself by quoting the entire source, which provides no discriminating evidence.

The z-curve review's concerns are mostly accurate in kind but inflated. The Z>6 finding calls a numerical approximation an unvalidated exclusion without deriving a consequential bias. The full-heterogeneity finding says rankings depend on one construction, although the reported comparisons are more mixed. The request for confirmatory hypotheses and prespecified thresholds is genre-inappropriate.

Additional manuscript-internal issues missed by the review include:

- Table 15 contains coverage below 95% in three cells, while the prose calls the interval conservative under most circumstances.
- The abstract says z-curve is better when maximum-likelihood assumptions fail, whereas the full-heterogeneity comparison is seven wins to six and the Discussion says they perform about equally well.
- The method description omits mixture-component count, grid spacing, and optimizer details.
- Page 10 says chi-squared statistics in the F-test section; page 12 describes Table 9 columns as effect-size standard deviations although they are correlations.

Questions about kernel-density boundary bias, mixture fitting by absolute deviation, and the magnitude of the Z>6 approximation require code or specialist derivation and should not be asserted from manuscript prose alone.

## System defects

- Modules behave as if they must emit a finding for each rubric topic.
- Severity is calibrated independently by module; reporting omissions default to Major.
- There is no rule to recognize an author-acknowledged limitation and require a demonstrated mismatch with the conclusions before elevating it.
- The finding cap acts as a target rather than merely a ceiling.
- Remedies are not verified, even though the largest overreach occurs there.
- Exact duplicate handling does not perform semantic cross-module consolidation.
- Deterministic arithmetic checks do not address prose-versus-table consistency.
- A same-model second call is labelled as independent verification.
- Two methods-heavy papers and same-family LLM judging cannot establish social-psychology review quality. Evaluation needs per-finding precision, distinct-issue counts, false-finding negative controls, and bounded human audit.

## Minimum completion criteria

1. Complete every stage on at least one real empirical psychology manuscript at shipped settings and save the artifacts.
2. Run verification with a different model family and label provenance accurately.
3. Demonstrate verifier rejection on planted unsupported criticisms.
4. Add semantic consolidation and show that the z-curve candidates reduce to a non-redundant review.
5. Add manuscript-maturity triage so a stub receives a short insufficiency notice.
6. Demonstrate structured table extraction and prose-versus-table checking on the Table 9 case.
7. Exercise deterministic statistics on a real eligible report.
8. Execute and retain one complete human-review comparison.
9. Freeze the implementation used for reported validation runs.

Promised but not exercised in the supplied scientific runs: supplement and preregistration handling, verifier-backend swapping, and the full evaluation workflow including planted-error recall. HTML exists in other run artifacts but was not evidence of scientific quality. Code/reproduction review and OpenAlex literature checking appear in broader research notes but are outside the current README scope.
