# Alpha implementation decisions

User-authorized implementation, 2026-09-07.

Build an independent, coarse-inspired manuscript review pipeline with prominent provenance credit, reusable methodological modules, and authored discipline profiles controlling both generation and verification. Initial discipline: quantitative social psychology. A small education profile demonstrates extension only.

Core sources: the research_coarse_psych_fork.md, research_coarse_fork.md, and research_error_detection_precision.md notes in ../reproduction_pipeline/research. These are scoping notes, not validated empirical evidence.

## Work allocation

Implementation is delegated to GPT-5.6 Sol agents: core pipeline/CLI/backends; rubrics/checks/verification; evaluation/journal corpus. The coordinating agent integrates and tests. Key design choices and the completed implementation receive independent `claude -p --model fable` checks, with prompts and responses retained in design_reviews/.

## Product boundaries

Input: manuscript PDF/DOCX/Markdown, optional supplements and preregistration. Output: evidence-anchored review, full finding disposition history, JSON/Markdown/HTML, coverage and explicit partial failures. No claim of computational reproduction or established human-level review performance. No journal verdict. Local CLI first; no deployment or publishing.

## Verification and evaluation

Separate usefulness from factual support. Match human review reports to the exact manuscript version they reviewed. Prioritize journal open reviews (Meta-Psychology and verified prominent journal examples); PCI is supplemental. Human reviews are comparators, not exhaustive truth labels. LLM judges are blinded and order-swapped; audit random output findings separately from targeted severe/disputed findings. Existing planted-error cases provide a regression check on useful detection surviving verification. No bulk paid evaluation without a cost estimate and explicit approval.

## Engineering acceptance

Installable package and working commands; actual model-backed end-to-end smoke in addition to clearly labeled offline fixtures; source/provenance validation; cross-study separation; numeric checks with applicability/coverage; cache invalidation and partial-run tests; all renderers escape untrusted content; evaluation fixtures with known results; documented remaining corpus/version limitations.
