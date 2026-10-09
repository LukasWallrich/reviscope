## Answer

I would request **major revision before using section 7 to commission the next evaluation**. The separation of validity, recovery, utility and human agreement is useful. The main problems are inaccurate attribution of project results, an unsupported diagnosis of the bottleneck, and an evaluation programme that needs tighter endpoints and staging. No files were modified.

1. **Sections 1 and 5.2: distinguish the specialist results from the holistic pilot.**  
   The opening blends specialist planted-error results with submitted-manuscript preference results that concern **holistic discovery and holistic plus audit**. It also says “judges prefer” plain, although Sol’s group-membership judgments were mixed. Readers could infer that the default specialist product has already lost these submitted-manuscript comparisons.

   **Suggested replacement:**  
   > “The older specialist pilot matched the saved plain baseline on the eight provisionally audited demonstrable targets, while recovering fewer annotations overall. The later holistic pilot matched plain on strict retrieval and recovered seven versus six demonstrable targets. On two submitted manuscripts, Opus preferred plain to both holistic variants; Sol’s judgments were mixed on one manuscript. These development results do not establish the performance of the current specialist configuration.”

   Add a small configuration/version/results table, citing [KNOWN_ERROR_RESULTS.md](/home/lukas/Documents/Coding/coarse-socpsy/docs/KNOWN_ERROR_RESULTS.md) and [PIPELINE_DEVELOPMENT_RESULTS.md](/home/lukas/Documents/Coding/coarse-socpsy/docs/PIPELINE_DEVELOPMENT_RESULTS.md:48).

2. **Section 1, conclusion 3; sections 3.3 and 8: the “selection, not generation” diagnosis contradicts the specialist trace.**  
   A reduction from 52 candidates to 18 publications does not establish loss of valuable criticism: it includes duplicates, contradicted claims and unresolved concerns. The 0.4.1 results explicitly identify discovery as the principal remaining loss: Luna’s misses were all discovery misses; Sol never raised ten targets. The later holistic comparison also documents missing conceptual/design coverage. [Project evidence](/home/lukas/Documents/Coding/coarse-socpsy/docs/KNOWN_ERROR_RESULTS.md:81).

   **Suggested replacement:**  
   > “Both discovery and finalization may limit performance. Existing specialist traces identify substantial discovery misses; publication-count reductions alone cannot distinguish useful filtering, deduplication and harmful loss. Adjudicate stage contributions before deciding where additional effort belongs.”

   Retain fixed-candidate evaluation, but remove the recommendation that discovery is probably adequate.

3. **Sections 1, 3.1 and 3.3: correct the Parsa–Rezaei numbers and experimental scale.**  
   The selectors achieved **40.2–44.2% absolute weighted coverage**, versus **79.3%** for the unrestricted oracle: approximately **51–56% of oracle coverage**, not 40–44%. The headline generation and compression experiments used **ten papers**; 3,398 was the available corpus. The 44.9→78.7% increase also required 3.6 times more requests and 5.2 times more tokens, rather than merely deduplicating the same samples. [Source, Tables 2–3](https://arxiv.org/html/2609.05788v1).

   **Suggested replacement:**  
   > “On ten training papers, paper-only selectors achieved 40.2–44.2% weighted historical-review coverage, compared with 79.3% for an oracle. Separately, deduplication and refill increased strict coverage from 44.9% to 78.7% with substantially greater generation expenditure.”

   Correct the table’s evaluation column accordingly.

4. **Sections 4.2 and 7.2: the primary outcome narrows the product’s purpose too much.**  
   Counting only supported criticisms with materiality ≥2 gives no primary benefit credit to useful local reporting, presentation or explanatory improvements. The existing plan explicitly values justified suggestions that improve a paper without alleging an error. Merely showing their presence in R1 does not assess that benefit. [Validation-plan scope](/home/lukas/Documents/Coding/coarse-socpsy/docs/PIPELINE_VALIDATION_PLAN.md:9).

   **Suggested fix:** Retain consequential supported issues as one endpoint, and add **supported, nonredundant suggestions with an expert-rated concrete benefit**. Report contributions by type alongside incorrect advice, disproportionate demands and author burden. Do not automatically treat cosmetic preferences or explicitly optional extensions as equivalent to harmful requests.

5. **Sections 4.1, 5.3 and 7.2: distinguish issue identity from the validity of each system’s criticism.**  
   Cluster-level adjudication can accidentally credit an incorrect criticism because another system raised a defensible version of the same issue. ReviScope’s own examples show why headline validity cannot validate a rationale, consequence or remedy.

   **Add:**  
   > “Clusters identify shared underlying issues. Preserve and adjudicate each materially distinct claim–rationale–consequence–remedy variant. A supported cluster does not confer support on every member. Count issue recovery once per report, while attributing incorrect arguments and remedies to the outputs that contain them.”

   Include deliberately mismatched variants in the clustering audit.

6. **Section 7.1: the arms neither include the promised holistic comparator nor fully isolate decomposition.**  
   Section 7 introduces plain and holistic as comparators, but holistic disappears from the table. Moreover, specialist versus pooled plain changes both discovery and finalization unless both receive the same downstream treatment.

   **Suggested fix:** Separate practical and architectural comparisons. The practical comparison should include current specialist, fresh plain, and current holistic under fixed settings. For decomposition, compare specialist discovery with budget-matched broad sampling, applying identical verification/editorial rules. Use fixed candidates to test finalization. Keep the independent audit optional until its incremental benefit is adjudicated. Adapt the existing plan while explicitly preserving specialist as the product under test.

7. **Section 7.4: the pilot is substantially larger than its wording suggests.**  
   Four mandatory arms × three runs × six to eight papers means **72–96 complete arm outputs**, before extra calls for pooled plain, verification, adjudication or optional ablations. The plan currently stages expansion behind evidence of promise. Re-judging existing pairs is a lower priority than determining whether their criticisms are valid.

   **Suggested replacement sequence:**  
   > “First adjudicate 50–100 development issue packets and audit stage transitions. Calibrate the current complete-criticism verifier. Then run a small frozen specialist–plain–holistic comparison on untouched cases. Add matched-budget discovery controls where the initial results leave an architectural question unresolved. Expand only after benefit, harmful-advice burden and cost meet prespecified advancement criteria.”

   Add budgets for model calls and expert hours.

8. **Sections 2 and 5.1: present the benchmark audit as provisional triage, not established ground truth.**  
   The 42/24/9/25 totals describe the audit’s strongest defensible readings, sometimes narrower than the annotation’s claimed defect. Its synthesis explicitly says these are not validated ground-truth totals; subsequent feedback retains disputed classifications. [Audit qualification](/home/lukas/Documents/Coding/coarse-socpsy/docs/benchmark-validity-audit/synthesis.md:18), [feedback resolution](/home/lukas/Documents/Coding/coarse-socpsy/docs/benchmark-validity-audit/feedback-resolution.md).

   **Suggested replacement:**  
   > “An AI-assisted, unblinded provisional audit assigned targets to four evidential categories. These categories guide expert checking and sensitivity analyses; they do not establish a replacement gold standard. Preserve official annotation-overlap scores and independently freeze acceptable narrower criticisms before new comparisons.”

   Also replace SPECS’s “22/35 valid” with **“22/35 jointly judged significant enough to warrant review criticism; nine judged minor and four disputed.”** [AAAI appendix A.9.4](https://arxiv.org/html/2604.13940v1).

9. **Section 8, deterministic-check bullet: retain verification of the extracted result and its applicability.**  
   “Verified for consequence rather than existence” overstates what determinism establishes. Statcheck can misclassify corrected or one-sided tests and miss formatting-dependent results. Its cited validation paper recommends checking individual flags by hand. Overall accuracy is not the precision of positive flags. [Statcheck validation](https://link.springer.com/article/10.3758/s13428-015-0664-2).

   **Suggested replacement:**  
   > “Treat deterministic outputs as reproducible leads. Confirm extraction, test identity, rounding, sidedness and applicable corrections before establishing an inconsistency; then assess its consequence. Use recomputation to reduce arithmetic uncertainty within the existing evidential gates.”

10. **Sections 7.4 and 6: specify the target population and protect genuinely unseen cases.**  
    The four reserved submissions contain one experimental replication, two tutorials and a publication-bias analysis. They are useful challenges, but their pooled variance does not automatically describe ordinary empirical social-psychology submissions. Using all four for tuning a variance pilot also changes their later holdout status.

    **Suggested fix:** Name a development set, rubric-calibration set and untouched comparison set. Record every case’s exposure history. Report tutorials, methodological analyses and empirical submissions separately. Define confirmatory sampling by field and design, following the repository’s [sampling-frame document](/home/lukas/Documents/Coding/coarse-socpsy/docs/OPEN_REVIEW_SAMPLING_FRAME.md), rather than archive availability alone.

11. **Sections 7.2 and 7.4: expand stage diagnostics beyond binary retention.**  
    “Verifier retention” and “editorial merge losses” omit source-access holds, required-source completion, severity holds, author-visible uncertainty and successful duplicate consolidation. A publication loss may be justified; an unresolved concern may still reach the author. Historical diagnostics also assess historical verifier contracts, not the current complete-rationale contract.

    **Suggested fix:** Track each issue through discovery → verifier → source gate → editorial → publication/unresolved display. Adjudicate whether each transition helped or harmed the review. Replay frozen candidates under the current verifier to test changes. Include true headlines with false rationales and failed source lookups, as already required by the [validation plan](/home/lukas/Documents/Coding/coarse-socpsy/docs/PIPELINE_VALIDATION_PLAN.md).

12. **Sections 4.2 and 7.2: separate validity precision, materiality and unresolvedness.**  
    Defining precision as “supported and at least minimally material” mixes truth with usefulness. “Unresolved both in and out of the denominator” needs explicit definitions; resolved-only precision can improve simply by deferring difficult findings.

    **Suggested replacement:**  
    > “Report supported/all, supported/(supported + contradicted), unresolved/all, supported-material/all, and contradicted criticisms per paper. State how not-assessable items and empty outputs are handled. Report validity precision separately from material yield.”

    Show paper-level macro averages, weighted estimates where sampling was used, and a separate serious-harm count.

13. **Sections 6.3 and 7.4: make the advancement rule operational.**  
    Superiority or non-inferiority on coverage plus precision does not determine whether a much more expensive specialist configuration earns its cost. “Reported together” does not specify how competing benefits and harms will guide a decision.

    **Suggested fix:** Prespecify one principal specialist–comparator contrast, a benefit endpoint, acceptable loss margins, a serious-incorrect-advice limit, usability requirements and a cost premium. Require uncertainty bounds to clear the relevant criteria. Label remaining contrasts exploratory. A preference win must not compensate for materially harmful advice; non-significance must not establish equivalence.

14. **Section 7.3: counterfactual pairs still require a defensible key.**  
    They are not “independent of answer-key validity”: the introduced flaw, its significance and acceptable response still require validation. A changed output can reflect surface sensitivity rather than successful diagnosis. The cited study itself reports weak agreement on whether edits compromised soundness. [Counterfactual validation](https://arxiv.org/html/2508.21422v1).

    **Suggested replacement:**  
    > “Expert-validate flawed, repaired and neutral versions before generation. Measure correct target-specific criticism in the flawed version, inappropriate persistence after repair, and neutral-edit sensitivity. Test both the relevant module and the final report.”

    Add original-version negative controls, which the existing validation plan already proposes.

15. **Sections 1 and 3.2: separate evidence for staged systems from evidence for specialist decomposition.**  
    AAAI reports designated-error recovery; MARG reports author-rated comments; TreeReview and Gauntlet primarily report judged quality or overlap; Refine is vendor-run. These are complementary observations, not repeated demonstrations of superior verified recall. AAAI’s stages also receive previous-stage results, unlike independent specialist readers.

    **Suggested replacement:**  
    > “Several staged reviewer systems outperform their chosen baselines on task-specific outcomes. The strongest cited recall comparison is AAAI’s unequal-budget SPECS experiment. These findings motivate testing specialist decomposition, but do not isolate its contribution to adjudicated review quality or establish transfer to social psychology.”

    Label each table result’s task, judging method, sample size and principal control limitation.

16. **Section 3.3: SPOT’s 6.1% figure cannot substantiate the claim of widespread false criticism.**  
    The paragraph presents SPOT beside independently checked false positives, although section 5.1 correctly explains its exhaustive-key assumption. SPOT counts every unmatched finding as false and does not adjudicate its scientific correctness. [SPOT scoring protocol](https://arxiv.org/pdf/2505.11855).

    **Suggested replacement:**  
    > “SPOT reports 6.1% reference-relative precision under an exhaustive-key assumption. This establishes low agreement with its annotated errors, rather than an adjudicated false-discovery proportion.”

    Likewise, describe YesNoError’s result at the flagged-paper level; do not imply a finding-level error rate.

17. **Sections 1, 5.2 and 7.2: atomic alignment does not replace whole-report usability evaluation.**  
    Removing shared points can remove meaningful differences in qualification, explanation or remedy. Filtering unsupported points before residual preference also hides the harm caused by those points. A residual comparison estimates incremental supported coverage, rather than the quality of the delivered report.

    **Suggested fix:** Use atomic assessment for validity and contribution, then retain a separate complete author-visible report assessment covering prioritisation, burden, uncertainty and useful positive feedback. Compare native and audited normalised representations; preserve substantive content. Treat residual preference as one diagnostic alongside explicit counts of discarded incorrect advice.

18. **Sections 5.4, 6.2 and 6.4: the statistical machinery needs a feasibility boundary.**  
    The 62-paper example is correctly labelled illustrative, but its SD of 0.20 is disconnected from the proposed count endpoint. PPI and doubly robust estimation do not resolve dependence among findings, runs and papers. Two experts with a third resolving disputes also require manuscript-reading time beyond packet-rating time.

    **Suggested fix:** Estimate actual endpoint distributions, annotation time and variance components in the pilot; simulate the intended design, including unequal sampling weights and missing ratings. Start with transparent weighted totals and paper-level summaries. Make PPI an optional later efficiency method, and attach uncertainty to variance-based sample-size estimates.

19. **Sections 4 and 7: add direct helpfulness and reader-task measures.**  
    The programme’s utility outcome names C3–C5a, leaving communicated helpfulness, expert remedy validity and actual reader benefit under-specified. Specific, substantiated and actionable criticism can still be unhelpful.

    **Suggested fix:** Ask authors or qualified readers which supported points they would act on, whether they understand the necessary action, and whether the report distinguishes essential work from optional improvement. Measure reading/task time and report-level prioritisation. Experts should separately rate necessity, feasibility and validity of the proposed remedy. Downstream manuscript improvement can remain a later endpoint.

20. **Sections 3.4, 3.5 and 8: qualify several recommendations and restore missing tests.**  
    Three recommendations need narrower wording:

    - **Blind recomputation:** use a separate execution context with frozen inputs and analysis specifications. Suppressing the claimed number alone does not prevent specification search or incorrect assumptions.
    - **Limitations echo:** distinguish acknowledged-and-adequately-addressed limitations from acknowledged limitations that still undermine the claim. Restatement can have editorial value.
    - **Concrete hunts:** preserve a broad synthesis opportunity and test whether checklists lose conceptual criticism. An “assessed/no issue” ledger entry does not establish successful checking.

    Add controlled manuscript prompt-injection tests and a retrieval diagnostic for preregistrations, replications, meta-analyses and cited-source access. These directly concern the specialist product’s tools and social-psychology remit.

21. **Sections 2, 4.1 and 5.2: qualify cross-task human and judge comparisons.**  
    Historical BMJ planted-error rates do not establish that exceeding human recall on ReviScope’s different manuscripts is a “low bar.” PeeriScope’s factuality correlation used title/abstract context and trained graduate-student ratings, limiting transfer to full-manuscript expert verification. [PeeriScope protocol](https://arxiv.org/html/2604.24071v1). Similarly, manuscript-score leniency in Agents4Science does not establish verifier false-acceptance rates.

    **Suggested wording:**  
    > “These studies demonstrate weaknesses of the tested instruments and settings. They motivate task-specific calibration; they do not supply expected human performance or verifier accuracy for ReviScope.”

22. **Overall structure, particularly sections 1, 7, 8 and 10: make the report’s decision logic easier to audit.**  
    The recommendations repeat across sections while the crucial bridge from current evidence to next action remains implicit. “Below the noise floor” also overstates what has been measured: tiny samples prevent reliable general rankings but can still reveal consequential failure mechanisms.

    **Suggested fix:** Put a short project-results table before the literature survey. Follow it with a decision matrix: **uncertainty → discriminating comparison → measured outcome → advancement decision**. Number the C2 scale explicitly and reconcile “materiality ≥2” with the category that includes secondary claims. Label literature findings, project observations and proposed hypotheses separately. Replace section 10’s assurance about source verification with version-specific citations and a brief record of verification limitations.