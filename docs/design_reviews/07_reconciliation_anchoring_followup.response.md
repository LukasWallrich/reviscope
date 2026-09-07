# Fable follow-up response

**VERDICT: BLOCK**

## Fix check

1. Fixed. Dehyphenation requires an alphabetic predecessor and letter lookahead, so `2-\n3` is preserved while `multi-\nlevel` can anchor with original-source offsets.
2. Fixed. A quoted `-0.2` cannot end inside source value `-0.25`, and omitted or changed signs do not anchor.
3. Fixed. NFKC is skipped for Unicode category `No`, so `10³` is not transformed to `103`.
4. Fixed. Every non-fixture backend must return a reconciled overview; omission fails the editorial stage, makes the run partial, and leaves findings unpublished as `needs_review`.
5. Fixed. Null reconciled design or contribution fields cannot erase corresponding non-null preliminary fields, and the preliminary study map is retained.

## Material regression found

Fable identified a false-negative prose case in `_numeric_boundaries_ok`: the numeric-boundary character set included `e`, `E`, punctuation, and signs without requiring a digit at the boundary. A quote ending in `positive` followed by a period could therefore be rejected because `e.` was treated as a numeric continuation. Fable recommended requiring at least one adjacent character to be a digit before classifying the boundary as a cut through a number, while retaining the exponent, grouping, sign, superscript, and decimal protections.

## Rationale

Fable found all five original blockers repaired and considered the reconciliation instruction suitable for evidence-sensitive qualification while preserving accurate statements and forbidding invented facts. It blocked only on the newly identified prose-boundary false negative. It also noted, without blocking, repeated fixture-name comparisons and terminology differences between the prompt's “supported” and stored `llm_supported` status.

