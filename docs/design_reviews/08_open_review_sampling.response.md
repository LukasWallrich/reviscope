**Verdict: BLOCK.** The documents are carefully hedged and internally consistent on the exact-versus-proxy definition and the accepted-only caveat, but the proposed pilot rests on strata with no verified in-cohort exact pair, and several evidence labels do not match the text. All findings are fixable.

**Audit limits.** I had no file or web access in this session, so this is a document-internal consistency check. Load-bearing dates were not independently verified: the Nature Communications mandate from 1 November 2022 and the 70% figure, PeerJ from 13 February 2023, PLOS from 22 May 2019, BMC from 30 March 2015, Nature from 16 June 2025, and the PsychOpen 2027 wind-down. Treat each as "cited, not re-checked."

**Must fix before the pilot design is frozen**

1. **No pilot stratum has a verified in-cohort exact pair.** The BMJ has no admitted article and only policy text. BMJ Open returned HTTP 403 and is coded as indexed only. PeerJ's one verified exact pair is article 236, a 2014 opt-in-era paper whose manuscript came from an archived capture, not a 2023+ mandatory-cohort paper with a direct publisher download. Require one verified pair per stratum before committing to 30.

2. **BMJ Open exact-versus-proxy status is undetermined.** The draft-revisions bundle may be a tracked-change revision rather than the round-zero manuscript. Until downloaded and checked, the JSON's policy-guarantee value for original submission cannot support a pilot input. The same check applies to The BMJ's "previous manuscript versions."

3. **Nature evidence level is mislabeled.** The Nature and Royal Society document defines "Observed" as a downloaded file inspected. The Lee and Sabatini entry only says the page links a file and the package "is described as" reports and responses. The table says "inspected example" and the JSON says verified example. Downgrade to indexed only, or inspect the file.

4. **The access-blocked level is defined but never applied.** BMJ Open, eLife version one and F1000Research version one all report blocked retrieval yet are coded indexed only. The frame's own definition says retrieval failure must be recorded distinctly from absence.

5. **Mandatory and optional strata do not match the 2023 to 2025 window.** The JSON codes Nature and Nature Communications as mandatory, but nearly all Nature papers published in that window are opt-in, and 2023 Nature Communications papers submitted before November 2022 are opt-in. The BMJ and BMJ Open are not labelled in the mandatory or optional vocabulary at all, so the frame's rule that these be separate strata cannot be executed.

6. **Leakage safeguards cover context only, not pretraining or tool access.** Papers published 2023 to 2025 with public reviews are exactly what sits in model training data. Add a rule to record the model knowledge cutoff per run, prefer papers published after it or run a memorization probe, and confirm the backend has web and tool access disabled during generation.

7. **PeerJ 236 demotion conflicts with the no-post-hoc-exclusion rule.** The broad-and-health document says it became a workflow diagnostic after inspection of its weak comparator set. The frame forbids excluding a report after observing agreement with AI output. State whether the demotion preceded AI scoring and whether 236 is inside or outside the pilot estimate. Also reconcile the untracked filename referring to a seven-review pool against the document's "four Version 0.1 reports."

**Should fix, since the pilot is not executable as written**

8. **Disciplinary framing drifts.** The pilot targets "empirical social/behavioural" papers, yet 20 of 30 come from The BMJ and BMJ Open, whose own table rows say their scope differs from general social science. No operational inclusion criterion is given. The shortfall rule handles counts, not domain drift.

9. **Enumeration is unspecified.** There is no PeerJ API or subject filter, no BMJ search route, no random seed, no text-match threshold defining "exact," and no procedure or owner for fixing the challenge panel.

10. **Some policy claims rest on secondary sources.** PeerJ policy is cited from a per-article review page, and Collabra's 2020 start comes from a SAGE Open article rather than Collabra's own policy page. Keep them as leads but label them secondary.

11. **The companion CSV** for the Nature and Royal Society audit is referenced but was not in the reviewed set. Confirm it exists and matches the table.

**What holds up.** The exact-versus-proxy definition is stated identically across all five documents. Accepted-only and opt-in selection caveats are consistent. Science Advances, Frontiers in Education, Research and Politics and Sociological Science are correctly kept out of the paired corpus with evidence-bounded language. The manuscript-only derivation and contamination check for combined history PDFs is a sound safeguard.
