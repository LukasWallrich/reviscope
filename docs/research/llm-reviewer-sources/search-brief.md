# Project context (ReviScope)

ReviScope is an experimental LLM manuscript-review pipeline for quantitative social psychology
(inspired by "coarse" by David Van Dijcke). Default "specialist" strategy: deterministic metacheck
screening (statcheck-like R modules) -> descriptive study map -> coverage-first specialist modules
(contribution, design, measurement, statistical inference, interpretation, argument coherence,
consistency) with web search/fetch and a sandboxed shell -> blind-spot pass -> quote anchoring ->
separate verifier call (can be a different model family) that checks the full claim + rationale +
remedy -> editorial dedup/disposition -> report with supported findings and labelled unresolved
concerns. An experimental "holistic" strategy uses one broad review call (+ optional independent
evidence audit). The owner considers specialist modules the point of the product.

Evaluation so far and current struggles:
- Planted-error benchmark (10 papers x 10 planted errors, external benchmark). Our own audit found
  the annotation key heterogeneous: ~42 demonstrable errors, ~24 reporting gaps, ~9 need external
  verification, ~25 weak/invalid targets. Strict recall via LLM matching. A plain one-call review
  with the same model often matches or beats the multi-stage pipeline on recall (e.g. 12/20 vs 7/20
  in one version; 12/20 vs 12/20 later). n is tiny (2 dev papers), one run per config.
- Comparison with real first-round human reviews (open-review journals, submitted versions) using
  LLM-as-judge pairwise preference (both orders, two judge families), rating correctness, importance,
  specificity, grounding, actionability. Plain review is often preferred.
- Planned: criticism-level clustering across systems and humans, expert adjudication of clusters
  (supported/contradicted/unresolved, consequence, necessity of remedy), verifier calibration probe
  set, small crowd exercise for actionability.
- Open questions: how to measure precision (unmatched findings may be valid), how to value
  non-error contributions (interpretation, theory, presentation), how to avoid length/verbosity and
  self-preference bias in judges, how to decide whether added stages earn their cost, what unit of
  analysis and sample sizes are needed, whether multi-agent/specialist designs beat single calls.
