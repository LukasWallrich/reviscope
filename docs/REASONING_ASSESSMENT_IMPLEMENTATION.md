# Reasoning assessment implementation

Implemented against `known-error-benchmark` at `a977767` on 5 October 2026 in
`/home/lukas/Documents/Coding/reviscope-reasoning-assessment`, branch
`reasoning-assessment`. A repository fetch confirmed that upstream main remained
`c98e67b`, already an ancestor of this branch. The shared checkout's untracked report
and `work/` directory were preserved. No upstream integration was necessary for the
implementation. The owner's later instruction requests Opus reviews and local-main
integration of all pipeline improvements; review and integration outcomes will be
recorded separately.

## Useful subset

Shared guidance in `src/reviscope/reasoning.py` connects consequential claims to
premises, inferential steps, assumptions, qualifications and defeating context. It
distinguishes missing premises, false premises, circular support and underdetermined
mechanisms. Support is sought throughout supplied sources, regardless of sentence
order. Broad review and the optional audit receive all guidance through their existing
review rules. Specialist discovery receives argument guidance, contribution receives
literature guidance, and measurement, interpretation, consistency and blind spots
and the social-psychology/education context modules receive selective material guidance. Bundled contribution, interpretation and
measurement protocols add quantitative-social-science examples and verification
criteria, inherited by social psychology and education. Verification and required-source
follow-up both receive the shared guidance through the existing claim-scope contract.

`AuditOperation` has two optional records, without another call or stage:

* `reasoning_trace`: located manuscript claim, quoted premises, inferential step and
  quoted defeating context. Existing `reported_inputs` names missing required premises;
  `assumptions` records necessary assumptions; `result` records qualifications and the
  outcome; `status` retains checked/unresolved/not-applicable semantics. A checked
  operation may support or defeat the manuscript inference and need not yield a finding.
* `literature_relation`: located manuscript claim, target prior works, asserted relation,
  comparison criterion and fetched source passages using the existing `ExternalCitation`
  contract. Relations include limitation, comparison, use, extension, conflicting
  predictions, theoretical synthesis, support and unspecified relations. Unidentified targets/criteria remain explicit,
  rather than invented. Empty source evidence cannot establish an inaccessible work's
  contents.

The full records remain inspectable in content-keyed `review-evidence_audit-*.json`
stage artifacts referenced by `review.json`. Coverage counts quotation anchors across
ordinary operation evidence and the structured claim, premise and defeating-context
passages, deduplicated by source and quote. This is anchor bookkeeping, not independent
verification of an operation's method or scientific conclusion. Raw records with
unanchored passages remain available; the coverage summary exposes the mismatch.

Any resulting finding must carry its own manuscript evidence and required external
items into ordinary verification. Operation source records have no confirmation field
and cannot establish publication eligibility. The independent audit still receives no
broad findings or overview. Its successful checks do not become criticisms. Existing
calculation code/output matching, evidence/source follow-up, remedy, severity,
contamination and publication contracts remain in place. Prompt hashes, schema hashes,
profile hashes and upstream hashes invalidate affected caches; no global cache flush
or stage-version bump is needed. Historical artifacts remain readable because the
new operation fields default to null.

Material checks name the particular blocked inference, inspect supplied supplements
and accessible materials, distinguish reviewer access from author behaviour, and
preserve privacy constraints. Aggregate estimates can be sufficient. An illustrative
case cannot establish prevalence or mechanism. Extracted table values can support
numerical checks; captions cannot support claims about figure pixels or arrows.

## Covered, deferred and excluded recommendations

Whole-manuscript defeating-context search, theory/design/estimand alignment,
external-source provenance, novelty searches, full claim-and-rationale verification,
separate remedy checks, bounded reporting requests and an independent optional audit
already existed. This change makes reasoning connections and contribution relations
more explicit within those contracts rather than replacing them.

Visual reasoning beyond extracted text is deferred: ingestion supplies PDF text, not
readable page-image evidence. Questions requiring images remain unresolved. A graph
engine or new mandatory audit is deferred pending marginal-quality and cost evidence.
A manuscript revision quality gate is deferred because manuscript editing is not a
pipeline capability. AI-authorship classification, aggregate slop scores, PMI/sentence
ordering, citation-count thresholds and generic cross-reference/diagram requirements
are excluded because they do not establish the validity of a particular inference.

The pinned ScientificSlop relation prompt, argument labelling prompt and evidence-gap
implementation linked in [the source assessment](SCIENTIFIC_SLOP_ASSESSMENT.md) were
read directly. The relation prompt supplies useful target/criterion/relation concepts;
its introduction-local extraction scope is not retained. The example checker records
exhibit presence, so absence alone is not adopted as a reasoning defect. The new
instructions and schemas are adaptations for quantitative social science, rather than
copied prompts or code.

## Verification and scientific limits

`tests/test_reasoning.py` and its handcrafted development packets exercise successful
and unsuccessful argument checks, relations, distributed/supplementary support,
selective material checks, missing/false premises, circular support, competing mechanisms,
privacy constraints and unavailable figure pixels. The backend's judgments are scripted:
these tests establish record preservation, anchor accounting, guidance routing,
unchanged source/publication gates and cache behavior, not scientific review accuracy.
Existing evidence-audit, discovery, profile and verification tests also pass. The final
suite results and Opus feedback are recorded in [the integration review](PIPELINE_INTEGRATION_REVIEW.md).

The [validation plan](PIPELINE_VALIDATION_PLAN.md) now designates all Meta-Psychology
cases as training/development data, following the owner's instruction. It calls for
expert-adjudicated probes and matched baseline comparisons measuring correct material
criticism, unsupported advice, remedy burden and marginal cost by paper. An independent
validation set is still to be selected. Larger ledgers and model support rates do not
establish improved scientific review quality. No bulk generation is authorized by
this implementation record.


The initial mechanism example was informed by the supplied assessment and mirrors the
Bonetto development case; no human reports were read or supplied during implementation.
Production guidance now uses a generic two-mediator example. The concrete scenario remains
in the assessment and offline probes, which never enter review-generation inputs. Results
on this training case are development-informed and cannot establish independent validity.
The existing engine version is retained: stage instruction, schema and profile hashes,
plus the assessment's frozen code/source identity, distinguish the new condition.
