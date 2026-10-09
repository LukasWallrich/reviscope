## Answer

Most substantive concerns are addressed. The remaining work is chiefly qualification of results, sampling instructions and source-version provenance. No files were modified. Locations below refer to the revised [source body](/home/lukas/Documents/Coding/coarse-socpsy/docs/research/llm-reviewer-sources/body.html).

**Disposition of the original 22 findings**

| # | Status | What remains |
|---|---|---|
| 1 | **Partly resolved** | Configuration attribution is corrected; section 2 still overstates two interpretations, detailed below. |
| 2 | Resolved | Discovery and finalization are now distinguished. |
| 3 | Resolved | Parsa–Rezaei coverage, experimental size and expenditure are corrected. |
| 4 | **Partly resolved** | Beneficial suggestions receive credit, but optional recommendations now receive blanket immunity from harm assessment. |
| 5 | Resolved | Issues and materially distinct variants are explicitly separated. |
| 6 | **Partly resolved** | Comparators and common finalization are fixed. Define what “budget-matched” means: expenditure, tokens or latency, with actual consumption reported. |
| 7 | Resolved | Expansion is staged behind adjudication and a small practical comparison. |
| 8 | **Partly resolved** | Audit qualifications are restored. Explicitly freeze expert-approved target interpretations and acceptable narrower criticisms before scoring new outputs. |
| 9 | Resolved | Deterministic outputs are treated as leads requiring contextual checking. |
| 10 | Resolved | Case types, exposure history and target population are distinguished. |
| 11 | Resolved | Stage diagnostics now include gates, holds, consolidation and current-contract replay. |
| 12 | Resolved | Validity, material yield and unresolvedness are separated. |
| 13 | Resolved | Advancement criteria now include harm, usability, uncertainty and cost. |
| 14 | Resolved | Counterfactual validity, repaired controls and final-output testing are included. |
| 15 | **Partly resolved** | Task distinctions are improved. Narrow “No review-specific comparison controls compute” to the studies surveyed; “Gains shrink when the outcome is a global score” remains an unsupported generalisation from heterogeneous studies. |
| 16 | Resolved | SPOT’s reference-relative precision is correctly described. |
| 17 | Resolved | Atomic contribution and delivered-report assessment remain separate. |
| 18 | Resolved | Actual-endpoint simulation, dependence and expert reading time are acknowledged. |
| 19 | Resolved | Reader benefit and remedy assessment are added. |
| 20 | Resolved | Recomputation, limitations, conceptual synthesis, injection and retrieval are addressed. |
| 21 | Resolved | Human/judge results and model-family leniency are appropriately qualified. |
| 22 | **Partly resolved** | Structure is improved; references still link to unversioned arXiv records despite “at the versions linked.” Pin evaluated versions. |

**Section 2: row-by-row verification**

Checked against [KNOWN_ERROR_RESULTS.md](/home/lukas/Documents/Coding/coarse-socpsy/docs/KNOWN_ERROR_RESULTS.md:33) and [PIPELINE_DEVELOPMENT_RESULTS.md](/home/lukas/Documents/Coding/coarse-socpsy/docs/PIPELINE_DEVELOPMENT_RESULTS.md:48). **All reported score counts match.**

| Row | Assessment and required correction |
|---|---|
| **0.4.1 specialist — line 54** | Configuration, 7/20 versus 12/20, and the same six demonstrable targets are correct. Replace “raised no candidate for ten targets” with **“had no candidate match for ten targets.”** Luna’s discovery statement is correct, but identify it as a separate diagnostic and note that Luna paper 5 was contamination-flagged. |
| **0.4.3 holistic — line 55** | Configuration and both score pairs are correct. **“Holistic is not worse” implies established non-inferiority.** Replace with: “Observed strict recovery matched the saved baseline; demonstrable-target recovery was one higher. Two development papers with saved controls do not establish non-inferiority.” |
| **Submitted manuscripts — line 56** | Opus preferences and both judges’ audit-over-holistic preference are correct. Replace “Sol mostly agreed” with the exact result: **“Sol preferred plain on indirect harm; on group membership, holistic versus plain was order-discordant, and audit versus plain produced tie/audit judgments.”** |
| **Seven numerical checks — line 57** | Coverage counts are correct: broad-first missed the negative-correlation count. Replace “Existence of specific verifiable errors” with **“Specific reporting mismatches, conditional on the checked inputs and assumptions; not an estimate of overall precision or coverage.”** The demographic checks depend on assumed denominators. |

Add a short table note: papers 5 and 9 are development cases; controls were saved rather than concurrent; screening was partial; the demonstrable subset remains provisionally audited.

**Five primary-source numerical checks**

| Claim | Result |
|---|---|
| **3.73 → 4.29**, review-length experiment, line 38 | **Matches.** These are mean perceived-quality scores. [Goldberg et al.](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0320444) |
| **23 of 29 metrics shifted**, line 38 | **Matches** the primary analysis. [Amirshahi et al.](https://arxiv.org/pdf/2609.23264v1) |
| **SD 0.7 versus 2.8**, line 116 | Numbers match, but specify **median within-paper SD across ten papers, calculated from two consistent-configuration reruns per paper**. “Four times more stable” is too imprecise. [Georgantas, appendix G/J](https://arxiv.org/html/2606.15887v1) |
| **37% versus 94% reproduction**, line 126 | **Denominator mismatch.** These are proportions of **teams** achieving computational reproduction—13/35 versus 31/33—not percentages of individual results reproduced. Replace “reproduced 37% of results” accordingly. [Published PNAS paper, section 2.1](https://eprints.whiterose.ac.uk/id/eprint/241548/1/brodeur-et-al-2026-ai-assisted-teams-outperform-ai-led-teams-but-not-human-only-teams-in-assessing-research-1.pdf) |
| **34% rarely/never use statistical review**, line 190 | Number matches, but qualify the population: **36 of 107 responding journals**, from 364 surveyed. Replace “34% of leading biomedical journals” with “34% of responding leading biomedical journals.” [Hardwicke and Goodman](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0239598) |

**Problems introduced by the revision**

1. **Optional advice is exempted too broadly — lines 154 and 278.** Optional recommendations can still be scientifically invalid, misleading or disproportionate. Replace both categorical exemptions with:  
   > “An extension is not harmful merely because it is optional or beyond scope; its validity, feasibility and proportionality still require assessment.”

2. **The sampling instructions were weakened — sections 6.4 and 8.5.** The revision retains inverse-probability weighting but drops the operational requirement that every relevant stratum have positive inclusion probability. “50–100 issue packets” could become a convenience sample. Restore the validation plan’s targeted strata plus reproducibly sampled remainder, recorded inclusion probabilities and weighted estimation. Keep rubric-calibration packets distinct from the sample used to estimate performance.

3. **The opening overcorrects product attribution — line 27.** “Existing evidence does not yet test the product” contradicts the specialist benchmark row immediately below. Replace with:  
   > “Existing evidence does not yet evaluate the specialist product’s criticism validity and usefulness on real submissions.”