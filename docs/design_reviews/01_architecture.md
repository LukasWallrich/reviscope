# Fable architecture review

## Verdict

**Revise with conditions.** The core architecture is sound. Seven refinements are needed before alpha, and one bounds the scope. None require rethinking the pipeline shape.

## Alpha blockers

- **Modules as pure contracts, profiles as data.** A module is a function over (StudyMap, source spans, resolved profile config) returning candidate Findings, registered by name. Profiles are data files. Inheritance is resolved at load time into a flat effective rubric, and that flattened rubric's hash is what gets cached and logged. Method modules stay discipline-agnostic and take thresholds from the profile. Without flattening, "inherited generation and verification criteria" makes the cache key ambiguous and runs unreproducible. Enforce "no observed power, no rote alpha rules" as a module-level filter, not as prompt text.

- **Verification checks grounding, never re-asks the question.** Run deterministic quote matching first, then deterministic number presence and recomputation, then an LLM pass that sees only claim plus quote plus surrounding span, never the generating rationale. The Finding status enum must distinguish verified_deterministic, recomputed, llm_supported, and unverified. Editorial selection cannot upgrade a status. Severity is editorial and stays out of verification. Encode "agreement is not truth" in the schema by documenting llm_supported as a weak label.

- **PDF normalization layer under strict quote checks.** Raw PDF text breaks on ligatures, hyphenation, line breaks, and minus-sign variants, so strict matching will silently drop true findings. Define canonical normalization and make "strict" mean exact-after-normalization. Evidence needs char offsets into the normalized text plus page, so every check is reproducible.

- **Recomputation with rounding bounds.** Compute a p interval from the reported statistic plus or minus half its last reported digit, require df, handle inequalities and one-tailed reports, and flag only when the reported p falls outside that interval. Without this the stats module floods with false positives on day one.

- **Cache key as a chain, not a tuple.** Include the ordered source file hash set, backend and model, flattened profile hash, module and prompt template version, schema version, upstream stage output hash, and backend kind so demo outputs can never be served as real. StageRecord stores every key component so a hit is auditable. Write with temp-plus-rename. ReviewRun carries an explicit partial flag listing stages run, and no final report is emitted from a partial run.

- **Subprocess sandbox for untrusted manuscripts.** The brief understates this. Codex CLI is agentic by default, so require no-tools or read-only sandbox mode, pass manuscript text via stdin or temp file rather than argv, validate output against the schema with one repair retry, hard-kill on timeout, and ship a prompt-injection fixture as a smoke test. Untrusted manuscript plus tool-capable CLI is an arbitrary execution risk.

- **Version manifest per eval paper.** Public reviews correspond to the submitted version, and the accessible PDF is usually post-revision with the flagged problems already fixed. Require a manifest recording reviewed-version identifier and date, feed that exact version to every system including stock coarse, and exclude or separately report papers where only the revised version exists. Pin the coarse version and model. Record publication date against model cutoff and stratify. Leakage hits your system and the baselines alike, so the pairwise comparison survives it, and the claim-truth audit is the leakage-resistant leg.

## Scope and eval controls

- **Cut alpha to three or four modules, JSON and Markdown output, Codex only, one profile chain.** HTML, the Claude backend, and additional disciplines are future work.
- **Pilot pairwise on five papers before twenty.** Pairwise usefulness judges reward length, so cap finding count or judge on top-k. At least one judge family must differ from the generation backend.
- **Claim-truth audit needs a human adjudicator** except where Dawes seeded errors supply gold. Human reviews stay a comparator only on version-matched papers.
- **Cost estimate formula before any bulk run**, with per-paper token counts from the pilot.

## Future work

- Claude backend, HTML report, cross-discipline profiles beyond the skeleton.
- Fuzzy quote tolerance as a separate, lower-confidence status once exact-after-normalization is stable.
- Per-file MIT headers and a LICENSE-coarse file are routine and not a blocker, but do them in the first commit.