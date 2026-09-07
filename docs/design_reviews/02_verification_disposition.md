# Response to Fable checker and verification review

All eight findings were accepted and addressed. Statistical checks now use rounding intervals, explicit relation parsing, line-break-aware bounded matching, matching coverage heads, and conservative handling of adjusted/corrected and one-tailed reports. A failed anchor now leaves a claim unresolved instead of calling it contradicted. Quote normalisation preserves original offsets and handles line-end dehyphenation, ligatures, Unicode compatibility forms, minus signs, and quotation marks while refusing changed numeric tokens.

Model-supported findings now require both candidate evidence and independently supplied verifier evidence to anchor. The verifier prompt omits the generator rationale and confidence. Profiles apply terminology in prompts, allow inherited editorial additions, state child precedence, distinguish unsupported from contradicted claims, and scope exact-number requirements to manuscript-attributed values.

One recommendation was interpreted conservatively: adjusted or corrected tests are marked `not_checked`, rather than attempting to reproduce adjustments whose inferential family or correction inputs are unavailable. Welch tests are checked from their reported statistic and degrees of freedom.
