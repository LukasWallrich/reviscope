Reviewed only the pasted module. I could not confirm the `Backend.generate` signature, how `read_review` handles normalized JSON, or the imported helpers, so import or first-call failures there are unverified.

**Blockers**

- **Criterion-level rankings are optional, unvalidated, and stored blinded only.** The `criteria` field defaults to an empty list, so a judge can omit them without error. Their rank groups get no every-label-exactly-once check, unlike the overall ranking. They are saved under blinded labels with no deblinding. If per-criterion results appear in the report, make the field required with the six criteria enumerated, apply the same coverage check, and deblind via the stored mapping.

- **AI review provenance is not recorded at model-family level.** The output carries only the manifest's `kind`. If that is just "human" or "ai", the report cannot show whether each judge family favours reviews written by its own model. That split is the reason for using two judge families. Require the manifest to name the generating model for each AI review and surface it in the summary.

- **The 4 human plus 3 AI composition is not enforced.** The code accepts any 2 to 12 reviews and never inspects kind counts. One assertion on the kind counter closes this.

- **Both judge families see identical presentation orders.** The permutation hashes only paper, seed, and repetition. Identical stimuli are fine for a direct judge comparison. They confound cross-judge agreement with shared position bias if the intent is independent replication. State which one the protocol wants. If the latter, fold the judge identity into the hash.

**Non-blocking**

- One failed presentation nulls the summary and a rerun repeats the successful paid calls. Seeding fixes order only, so reruns produce different judgments anyway.
- Label validation is strict. A judge returning "Review A" or a lowercase letter invalidates that presentation. Normalising labels before checking would save calls.
- Manifest paths resolve against the working directory rather than the manifest location.
- No cross-judge synthesis exists. That matches "invoked separately" but must happen downstream.
- Implied pairwise counts cap at the number of presentations per judge. Recording that ceiling in the summary would stop a "3 vs 0" from reading as three papers.

Deterministic byte-seeded permutation, average-rank ties with fractional Borda, the single paper count flag, config-hash resume, and withholding review kinds from the judge all check out.
