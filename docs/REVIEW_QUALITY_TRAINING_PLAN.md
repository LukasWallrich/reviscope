# Broad training-set review-quality assessment

The owner's 5 October 2026 instruction designates all six curated Meta-Psychology
submissions and all other existing Meta-Psychology entries as training/development data
and authorizes subscription-backed CLI calls. Corpus entries outside the curated six
also carry explicit training roles, so they cannot later be mistaken for independent
validation data.
No API-key billing, public uploads, recruitment or pushes are authorized. An independent
validation set will be selected later. Training here means iterative pipeline/prompt
development, not fitting model weights. This assessment diagnoses quality and repairs
failures; it cannot establish generalization or independent scientific validity.

## Suggestions carried forward from the latest benchmark work

The latest benchmark handoff and pilot diagnosis are recorded in
[KNOWN_ERROR_EVAL_HANDOFF.md](KNOWN_ERROR_EVAL_HANDOFF.md) and
[KNOWN_ERROR_PILOT_ANALYSIS.md](KNOWN_ERROR_PILOT_ANALYSIS.md). The subsequent
development thread is summarized in
[PIPELINE_DEVELOPMENT_RESULTS.md](PIPELINE_DEVELOPMENT_RESULTS.md), with the underlying
Opus feedback retained under `runs/pipeline-redesign-20261003/feedback/`.

1. Read broadly, then scrutinize sources and calculations. Keep the independent audit
   optional until it earns its marginal cost, including comparison with another broad
   read of comparable compute. Specialist fan-out and additional findings alone are not
   evidence of value.
2. Check complete criticisms, including their rationales; assess remedies separately.
   Distinguish reporting gaps and specification conflicts from alleged implementation
   errors. Preserve publication/source rules and immutability of editorial text/severity.
3. Track where useful criticism is lost: not discovered, contradicted, inaccessible
   external evidence, source-task failure, severity hold or editorial disposition.
   Source follow-up and structured operation records are already implemented. Match
   execution records without treating a recorded calculation as an independent proof.
4. Compare fresh baselines at fixed model, effort, extraction and tool access. Freeze
   code and retain every condition before making a repair. Keep partial or contaminated
   outputs separate. Saved pilot conditions remain historical evidence.
5. Assess correct, material, non-redundant criticism, missed conceptual advice,
   unsupported claims/rationales, false absence claims, remedy burden, genre fit and
   author usefulness. Atomic criticism correctness complements whole-report preference;
   verifier support rates and annotation recall are not precision.
6. Blind model/stage provenance, swap order, allow ties and use two judge families.
   Human reports are comparators rather than correctness labels. Source-dependent and
   image-dependent assertions require evidence; judges without it must abstain.
7. Have qualified assessors adjudicate disagreement, high-impact problems and unique
   added-stage contributions. Separate deliberately targeted and reproducibly sampled
   strata. Select an independent validation corpus after development, rather than calling
   unused Meta-Psychology cases validation.

Severity rewriting, a new publication route for executed calculations and an always-on
additional discovery stage remain separate changes; the present implementation retains
those contracts. Some original feedback predates fixes: recommendations already covered
must not be reintroduced as bugs without checking the current code.

## Diagnostic conditions

Use all six submitted versions and their pinned extracted text: Bonetto and Ziano
(experiments), Sætrevik (experiments), Heyman (education tutorial), Mackinnon (statistical
tutorial) and Niemeyer (meta-research). Use each case's curated profile. Review generation
receives manuscript material and metacheck leads only; no human reports, revisions,
editor letters, correctness labels or judge feedback enter the frozen initial generation.

Run one fresh replicate per case for the existing plain review without its category
checklist and the current broad-first pipeline, then extend the shared broad run with
the optional evidence audit. The nested arm retains the broad and verification artifacts
and archives its first editorial report before extension. One replicate is sufficient
for this diagnostic pass, not for estimating sampling variance or an advancement claim.
Default discovery strategy remains specialist; the shared reasoning and verification
guidance applies to both strategies.

Review generation uses Sol/high and verification Opus/high, matching the development
configuration. Judge calls use subscription-backed CLI tools with tools disabled.
Record code/source hashes, CLI versions, commands, stage time, fresh/reused calls,
source-task completion, remedies and editorial losses. Source-audit every output before
including it in primary comparisons. Findings unique to the audit require substantive
assessment, not a count of extra ledger rows.

Primary paired comparisons use published criticisms from complete, clean runs with
metadata removed. Keep unresolved author-visible concerns and supported severity-held
claims separate. Both presentation orders and both judge families assess AI contrasts.
Use selected first-round expert reports as additional comparators, preserving reports
separately. Whole-report preference is supplemented by criticism-level scrutiny of
unique contributions, disputed claims, all suspected high-impact false criticism and a
reproducible sample of the remainder. Numerical assertions are checked offline when
possible; required literature or visual evidence unavailable to the assessor yields
uncertainty, not a correctness badge.

When a problem is discovered, retain the frozen result, diagnose the stage and scope,
add a meaningful regression check, and repair the smallest appropriate behavior. Run
new diagnostic conditions only for affected cases; document tuning and keep those
results separate. Independent validation and expert correctness assessment remain needed.


The education profile is alpha and explicitly unvalidated for production claims; Heyman
is included to diagnose genre fit and restraint, not to validate that profile. The runner
requires an explicit case profile and preserves frozen-code/input provenance on resume.
Comparison gates independently check the curated profile, submitted-text identity and
current complete clean audit. Primary comparisons reject unknown paper identity and
stale audit rules. The audit now recognizes OSF short/download/storage aliases and both
Linnaeus journal hosts; listed search results remain warnings rather than flags.
