**Verdict: BLOCK**, narrowly. The frame no longer freezes a pilot at all, and most prior findings are cleared. Three residual gaps still leave a path to freezing an invalid one.

**Cleared from the previous audit**

- **In-cohort exact pairs.** No pilot is frozen; sample sizes are deferred until eligible counts are enumerated. PeerJ 236 is explicitly a retrospective diagnostic outside any estimate.
- **BMJ status.** Original-submission `policy_guarantee` with evidence at policy level and "exceptions possible" is now consistent with the hedged prose and the article-level check requirement.
- **Blocked retrieval.** BMJ Open, F1000Research and eLife carry `access_blocked`, defined as retrieval failure rather than absence.
- **Mandatory/optional windows.** Dated boundaries are present for PeerJ, Nature Communications, Nature and Nature Human Behaviour. The unresolved Royal Society Open Science transition is declared rather than hidden.
- **PeerJ demotion.** Stated as non-neutral, with all Version 0.1 reports still reportable.
- **Exact versus proxy.** Labels like R0 or Version 0 no longer count as exact without a tied file. Proxies go to a sensitivity stratum only.

**Remaining release blockers**

1. **Two competing definitions of the first sample.** The admission-states section calls PeerJ mandatory plus BMJ/BMJ Open plus article-verified cases "the most defensible first conventional sample." The next paragraphs call the same venues an artifact-feasibility sample that is not the validation population. A reader can freeze either. Relabel that paragraph as the feasibility sample or delete it.
2. **Memorization probe covers only the manuscript.** Human reports have been public alongside these papers for years before the June 2026 cutoff, and the whole 2023–2025 window is pre-cutoff. Review-text memorization inflates agreement directly. The preregistered probe must target each published report as well as the paper.
3. **Eligibility screen is not required to be blind.** Topic and design screening for empirical social and personality psychology is a human read of title and abstract. On PeerJ and Nature Portfolio pages the review file sits on the same page. Require screening from a metadata export before any article page is opened. Otherwise the PeerJ 236 demotion mechanism recurs at scale.

**Note, not a blocker.** PeerJ, Nature Communications and Nature each hold mandatory and optional eras in one JSON row with policy set to mandatory. The boundary date lives only in the free-text cohort string, so the frame's separate-strata rule cannot be executed from the JSON without hand parsing. A `mandatory_from` field or split rows would close this.

**Conditional.** I reviewed only the frame and JSON as instructed. The `verified_example` labels for Nature, BMC and Meta-Psychology are taken as given, so this verdict assumes the linked research files back them.
