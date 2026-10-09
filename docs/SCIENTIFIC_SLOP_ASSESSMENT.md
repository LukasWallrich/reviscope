# ScientificSlop: additions for reasoning assessment

ReviScope would benefit most from an explicit record connecting consequential claims to their premises and evidence, and from more structured assessment of literature-based contribution claims. ScientificSlop provides useful prompts for these tasks, but its released scores measure structural proxies and discrimination between generated and human papers. Neither establishes whether an inference is justified. Adapt selected ideas within the existing review and verification stages; evaluate their added value before adding another default stage.

## Recommended additions

| Priority | Addition | Existing coverage | Added value |
| --- | --- | --- | --- |
| First | Record claim → premises/evidence → inferential step → qualification or defeating context | Broad discovery reads the paper as an argument; contribution and interpretation assess theory; the evidence audit reconstructs inferential targets | Makes the particular missing or invalid connection inspectable, including successful and unresolved checks |
| First | Structure consequential relations to prior work | Contribution checks novelty and missing literature; tool-enabled stages open sources whose use carries an inference | Identifies the cited target, comparison criterion, asserted relation, and source evidence before assessing the contribution |
| Selective | Check whether an example is necessary to assess a specific claim | Measurement checks operationalisation; consistency checks reproducibility; interpretation checks claim/evidence agreement | Exposes case-level or coding claims that aggregate results cannot establish, without demanding examples from every quantitative paper |
| Later | Assess whether figures and tables support the argument attributed to them | Consistency and statistics compare extractable text and values | Extends assessment to visual evidence once ingestion supplies readable page images and figure provenance |

### 1. Trace the substantive argument

Borrow ScientificSlop's idea of recording a claim and its context, while assessing the actual inferential relationship. For each consequential claim inspected, record its location, supporting passages, necessary assumptions, inferential step, and strongest defeating context. Distinguish a missing premise, a false premise, circular support, and evidence compatible with several explanations. Support can occur anywhere in the supplied manuscript or supplements, before or after the claim.

For example, a manipulation may change both perceived group membership and perceived norm violation. A result compatible with both explanations does not identify group membership as the mechanism unless the design or other evidence distinguishes them. The useful finding identifies that ambiguity and the affected conclusion; it does not criticise the order of the introduction.

Implement this first as a small extension of `EVIDENCE_AUDIT`'s `inferential_targets` operations, with corresponding contribution/interpretation guidance. `AuditOperation` already records a question, evidence, reported inputs, assumptions, method, result, and unresolved status. Use that contract for a pilot before introducing graph schemas or a separate model call. The broad review should retain its open reading of the paper rather than acquire a quota of claims or graph nodes.

ScientificSlop's [argument-graph implementation](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislop/Argument/Argument_Graph/code/measure.py) selects a sentence's strongest PMI predictor and calls a key claim argued when that predictor occurs earlier. Its [labelling prompt](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislop/Argument/Argument_Graph/code/PROMPT_label.txt) covers superiority, prior limitations, and design choices in introductions. Linguistic predictability and sentence order do not establish logical support. A well-supported claim followed by its explanation can fail this rule; an unsupported claim following related prose can pass. Social-science assessment must also cover theoretical predictions, construct interpretations, causal claims, and generalisation throughout the paper.

### 2. Check what contribution claims say about prior work

The useful component is the [optional relation-extraction prompt](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislop/Argument/citation/code/PROMPT_relation.txt). It distinguishes limitation, comparison, use, and extension, and records the target work, criterion, and content of the relation. Adapt these fields for claims that materially support the research question or contribution. Add social-science relations such as conflicting predictions and theoretical synthesis where needed.

For “prior studies cannot distinguish X from Y”, establish which studies are meant, what would distinguish the explanations, and whether their designs actually lack that capability. Search or open the cited sources and retain evidence under ReviScope's existing external-source rules. Check the surrounding argument rather than one sentence in isolation.

The [released citation score](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislop/Argument/citation/code/measure.py) instead counts isolated citing sentences using deterministic tags. Requiring two citations in one sentence would penalise accurate, readable summaries and reward citation bundles that contain no useful synthesis. Do not adopt that rule.

### 3. Make missing examples consequential

ScientificSlop's [evidence-gap checker](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislop/Artifacts/evidence_gap/code/measure.py) detects aggregate result tables without concrete exhibits. For ReviScope, ask whether the missing material prevents assessment of a particular claim: a coding rule without a worked application, a stimulus-dependent interpretation without inspectable stimuli, or a claimed failure pattern without supporting cases or analyses.

Many quantitative conclusions can be assessed from aggregate estimates. A displayed example can illustrate a phenomenon without validating its prevalence or mechanism. Check supplements and accessible materials, preserve privacy-based withholding, and request the smallest necessary clarification. Absence of a displayed case never establishes that the authors failed to inspect or retain cases. In particular, do not adopt the revision skill's suggestion to assert that no case was retained or inspected merely because none is available to the reviewer.

### 4. Assess visual evidence when it is available

Ask whether the text's claimed result appears in the figure, whether a diagram implies an unsupported causal connection, and whether the necessary labels and comparisons are readable. ReviScope currently extracts PDF text through `pypdf`; figure pixels are not supplied as evidence by ingestion. Record visual questions as unresolved until images can be inspected, rather than infer their contents from captions alone.

ScientificSlop's [figure checker](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislop/Artifacts/fig_exposition/code/measure.py) counts features including notation keys and enumerated stages. Those can improve understanding. Its implementation also describes excluding some features because they produce more human-paper hits or are measured asymmetrically. This makes transfer to reasoning quality particularly uncertain. Keep legends, settings, and explanatory labels when they help the reader.

## Ideas to leave out

Do not add the aggregate slop score, AI-authorship classification, PMI model dependencies, or generic requirements for more cross-references, fewer repeated sentences, multiple citations per sentence, and less text inside diagrams. Local use of a table can be sufficient, summaries legitimately repeat key claims, and a diagram legend can be necessary. Raise presentation issues only when they obscure or misrepresent a specific inference.

The revision harness's [change-by-change quality gate](https://github.com/yerimoh/ScientificSlop/blob/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d/scislopharness/harness/quality_gate.py) is relevant if ReviScope later edits manuscripts: assess every proposed change against original sources, check for invented evidence or lost qualifications, and preserve a rejected edit's record. Current verification already checks the complete criticism and its rationale, and assesses remedies separately. A manuscript-editing loop would be a separate capability.

## Validation before default adoption

Use the existing [pipeline validation plan](PIPELINE_VALIDATION_PLAN.md). Compare the frozen baseline with the same configuration plus these prompts, preserving model, extraction, tool access, and publication gates. Assess added expert-supported, non-redundant criticism, unsupported advice, remedy burden, and incremental cost by paper. Do not treat a larger ledger or higher model support rate as success.

Include expert-adjudicated probes for a valid claim whose explanation follows it, a false claim preceded by related prose, support distributed across sections, a correct singly cited summary, an inaccurate multi-citation comparison, aggregate evidence that suffices, and a missing example that prevents assessment. Include negative controls where a supplied supplement resolves the apparent gap. Keep development probes separate from held-out validation.

ScientificSlop's paired generated/human benchmark may supply exploratory examples, subject to its data licences and manuscript completeness. Authorship labels are not correctness labels. The [repository README](https://github.com/yerimoh/ScientificSlop/tree/c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d) reports that released body-only views omit appendices and change evidence-gap results; whole-document coverage must therefore be checked before interpreting an absence.

## Inspection provenance

Assessed on 5 October 2026 against ReviScope GitHub `main` at `c98e67b` and ScientificSlop at `c21ab06c5bea3e6f311f2d2e230d8cc00dc3a76d`. The local ReviScope checkout was fast-forwarded from `13b0e49`. Direct access to the OpenClaw checkout remains unverified: saved LAN and Tailscale SSH routes failed, although Tailscale ping reached the box. Unpushed commits or working-tree changes on the box could affect this comparison. No production criteria were changed and no paid model/API calls were made.

## Implementation follow-up on the OpenClaw box

The implementation was assessed against the later `known-error-benchmark` branch
at `a977767`, which already contains assessed main `c98e67b`. The compatible subset,
existing coverage, deferred work and regression/scientific-validation distinction are
recorded in [REASONING_ASSESSMENT_IMPLEMENTATION.md](REASONING_ASSESSMENT_IMPLEMENTATION.md).
The entire Meta-Psychology corpus is now designated training/development data by the
owner; an independent validation set will be selected later.
