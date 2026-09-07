**Verdict:** the pasted code meets the fairness criteria except for one gap in the pair check. One further point cannot be verified from the supplied code.

**Blocker.** The pair check in `validate_normalized_pair` only enforces that each side's audit used a different model family from its normalization. It never checks that candidate and reference share the same normalization backend, prompt version, and issue cap. Two inventories produced by different normalizers pass as "symmetric". Add three equality checks on the two normalization records: backend, prompt version, and max issues.

**Unverified.** Span exactness rests on the tolerance of the quote verifier, whose code was not supplied. On the direct-match path the function keeps the model's span as written. Only the dehyphenation path stores the actual review slice. If the verifier normalizes whitespace, case, or quote marks, persisted spans are not exact raw text. Returning the review slice on both paths closes this regardless.

**Criteria that pass:**
- Coverage: the normalization prompt and the audit prompt both name criticisms, strengths, endorsements, and overall evaluations.
- Empty omitted fields: evaluation, rationale, and remedy are plain strings, lists default to empty, and the prompt forbids repair.
- No manuscript: only the review text enters either prompt.
- Different-family audit: enforced at pair validation by comparing the family prefix of the backend identity.
- Deterministic gates: unmatched spans, duplicate IDs, duplicate content, and the cap are computed at normalization, recomputed in the audit from the hash-bound review, and enforced in both the eligibility flag and the renderer. Reaching the cap fails closed rather than truncating.

**Non-blocking notes:**
- The eligibility flag can be true on a same-family audit. The pair check catches it, but the flag misleads if read alone.
- At normalization, the duplicate-content key is built before spans are dehyphenated, so a hyphenated and dehyphenated pair escapes that check. The audit recomputes from corrected spans, so the gate still holds.
