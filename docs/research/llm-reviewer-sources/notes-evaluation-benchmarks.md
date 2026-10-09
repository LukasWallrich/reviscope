## Answer

This survey covers **32 verified works from 2023–2026**, searched through **8 October 2026**. I opened the linked primary records or full texts; preprints, a conference abstract, a working paper, and a benchmark repository are identified explicitly. Numerical results refer to the versions specified below.

The central finding is that **recovering known errors, agreeing with human reviewers, producing useful comments, and making scientifically correct criticisms are different outcomes**. ReviScope needs separate evaluations for each.

### A. Key takeaways for evaluating ReviScope

- **Use separate evaluations for error detection and whole-review quality.** A system can recover injected errors while producing poor reviews, or provide useful feedback without recovering the benchmark’s designated error. Measure known-error recovery, adjudicated finding validity, supported review-point utility, and overall review preference separately. [Liang et al.](https://arxiv.org/abs/2310.01783) and [FLAWS](https://arxiv.org/html/2511.21843v1) illustrate these different targets.

- **Audit the gold standard before comparing systems.** Your context already distinguishes demonstrable errors, reporting gaps, issues requiring external verification, and weak or invalid targets. Preserve those distinctions in denominators and report category-specific performance. Injection does not establish scientific importance: in the AAAI SPECS audit, only **22/35 sampled perturbations** were jointly judged significant scientific errors; nine were minor and four disputed. [AAAI-26 pilot](https://arxiv.org/html/2604.13940v1)

- **Call closed-gold scores “finding overlap,” not factual precision.** An unmatched criticism may be correct and absent from the reference set. PaperAudit explicitly acknowledges this, whereas SPOT scores unmatched findings as false positives under an exhaustive-gold assumption. Report both recovery of known targets and independently adjudicated validity of generated findings. [PaperAudit-Bench](https://arxiv.org/html/2601.19916v1), [SPOT](https://arxiv.org/pdf/2505.11855)

- **Pool criticism clusters across humans and systems, then adjudicate them blind to origin.** Include unmatched findings rather than judging only reference matches. Have at least two suitably qualified reviewers independently inspect the manuscript, supporting evidence, and relevant external material; preserve their initial labels before consensus. SciCoQA provides a particularly useful precedent, although systems contributing findings to the pool can gain an evaluation advantage. [SciCoQA](https://aclanthology.org/2026.acl-long.1795.pdf)

- **Judge the criticism’s argument, not just its location.** Separately assess whether the observation is supported, the methodological inference follows, the claimed consequence is justified, and the remedy is appropriate. A correct quotation can accompany an incorrect criticism. CRED’s deterministic scoring deliberately ignores the rationale, while STRICTA models structured assessment reasoning; these measure different capabilities. [CRED working paper](https://ape.socialcatalystlab.org/cred/verifying-the-verifiers.pdf), [STRICTA](https://aclanthology.org/2025.acl-long.1107/)

- **Retain an “unresolved” category and report its consequences.** Distinguish supported, contradicted, unresolved, and supported-but-out-of-scope findings. Report conservative precision with unresolved findings in the denominator, resolved-only precision, and the unresolved share. Also report contradicted findings per paper and expert verification time; open-ended review usually lacks a meaningful count of true negatives, so “false-positive rate” is often actually a false-discovery proportion.

- **Evaluate ReviScope’s verifier and synthesis stages directly.** Measure how many valid candidate findings the verifier retains, how many invalid ones it removes, and how often it alters claims incorrectly. Track whether supported important points survive deduplication and final synthesis. AAAI’s stage analysis shows that a targeted stage can detect an issue that disappears from the final review. [AAAI-26 pilot](https://arxiv.org/html/2604.13940v1)

- **Measure utility separately from correctness.** RevUtil offers useful dimensions—actionability, grounding/specificity, verifiability, and helpfulness—but its comment-only annotations do not establish manuscript-level truth. For ReviScope, score utility both across all comments and conditional on supported criticisms, so an actionable but erroneous recommendation does not receive unqualified credit. [RevUtil](https://arxiv.org/html/2509.04484v1)

- **Use paired comparisons with credible budget controls.** Compare pipelines on the same manuscript version, appendices, tools, retrieval permissions, output limits, and model snapshots. Include an equal-cost plain reviewer or repeated-call ensemble alongside the single-call baseline; otherwise extra computation can masquerade as an architectural benefit. MARG and DIAGPaper motivate specialist workflows, but their results do not establish that any specialist pipeline beats a current, equally resourced baseline. [MARG](https://arxiv.org/html/2401.04259v1), [DIAGPaper](https://arxiv.org/html/2601.07611v1)

- **Treat papers as the main independent sampling unit.** Errors, comments, judges, and repeated runs are nested within papers; multiple manuscripts may also share authors or datasets. Use paired paper-level estimates and cluster bootstrap intervals, with runs and findings retained within sampled papers. Report macro averages alongside pooled micro averages so papers generating many comments do not dominate the result.

- **Choose sample size from the desired uncertainty and paired variability.** Two development papers cannot establish comparative superiority. As a planning illustration—not a literature-derived minimum—if paired paper-level differences have standard deviation 0.20, approximately **62 independent papers** give a normal-approximation 95% interval with half-width 0.05: \(n\approx(1.96s_\Delta/h)^2\). Estimate that variability in a pilot, then allow for strata, missingness, and clustering; adding many planted errors to the same ten papers does not supply the same information as adding independent papers.

- **Repeat generation and inspect issue-level stability.** Aggregate recall can remain similar while different errors are caught on different runs. SPOT evaluates eight independent runs; CRED separately examines repeatability and interference from adding another error. For ReviScope, report between-run variance, per-issue detection frequency, and whether consequential unsupported criticisms recur. [SPOT](https://arxiv.org/pdf/2505.11855), [CRED](https://ape.socialcatalystlab.org/verify)

- **Calibrate automated judges against independent experts and control presentation effects.** Swapping pairwise order and using different judge families helps, but does not establish scientific validity. Validate point matching, factual adjudication, and preference judging separately; retain disputed cases in reliability analysis. Humans also exhibit presentation bias: experimentally lengthening reviews without adding useful content increased their perceived quality. [Goldberg et al.](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0320444)

- **Freeze provenance and distinguish usefulness from demonstrated improvement.** Record manuscript versions, mutation dates, model/harness versions, retrieval traces, and whether public reviews, errata, or answer keys were accessible. Use recent/private held-out manuscripts where possible, while recognizing that unpublished mutations do not eliminate familiarity with original papers. Author surveys and adoption are valuable secondary outcomes; stronger deployment evidence includes blinded expert validation and whether resulting revisions improve the manuscript. [Dawes benchmark](https://github.com/Dawes-Institute/ai-peer-review-benchmark/blob/main/README.md), [ICLR randomized study](https://arxiv.org/html/2504.09737v1)

### B. Annotated bibliography

#### Error detection, injected flaws, corrections, and paper–code consistency

**1. Son, Guijin, et al. (2025). “When AI Co-Scientists Fail: SPOT—a Benchmark for Automated Verification of Scientific Research.” arXiv:2505.11855.**  
[Primary record](https://arxiv.org/abs/2505.11855) · [Full paper](https://arxiv.org/pdf/2505.11855)

SPOT contains **83 papers with 91 acknowledged errors across ten fields**, drawn from errata/retractions and screened through author acknowledgment and human auditing. Evaluation combines location and semantic matching, reports precision/recall and paper-level success, and repeats inference eight times. The strongest reported model, o3, achieves **21.1% recall and 6.1% precision** on average. Crucially, unmatched findings are counted as false positives because the annotated list is treated as exhaustive; without comprehensive adjudication, this is reference-relative precision. The benchmark emphasizes errors detectable from the supplied manuscript and offers limited direct coverage of quantitative social psychology.

**2. Xi, Sarina, Vishisht Rao, Justin Payan, and Nihar B. Shah. (2025). “FLAWS: A Benchmark for Error Identification and Localization in Scientific Papers.” arXiv:2511.21843, v1.**  
[Full paper](https://arxiv.org/html/2511.21843v1)

FLAWS uses LLM-generated, filtered, claim-invalidating mutations, producing **713 paper–error pairs** from accepted ICML papers; these are not 713 independent source papers. Models rank candidate erroneous excerpts, scored through text similarity or an LLM matcher. GPT-5 recovers the target at **9.0% accuracy@1, 19.2%@3, and 39.1%@10**. A small human audit found 29/29 Gemini-generated and 28/29 GPT-generated errors valid, with identification agreement **Krippendorff’s α=0.73**. The matcher’s positive-class precision/recall, **0.91/0.98**, describe matching reliability—not the scientific precision of generated criticisms—and were estimated on human-agreed cases.

**3. Tu, Songjun, et al. (2026). “PaperAudit-Bench: Benchmarking Error Detection in Research Papers for Critical Automated Peer Review.” arXiv:2601.19916, v1.**  
[Full paper](https://arxiv.org/html/2601.19916v1)

PaperAudit constructs mutated versions of **220 source papers**, using eight generators and roughly 10–20 errors per paper across local and cross-section error types. A semantic judge computes error coverage, finding precision, and paper-level macro-F1. In the Fast setting, Gemini 2.5 Pro and GPT-5 obtain **41.4 and 40.6 macro-F1**, respectively; GPT-5’s error coverage is **51.4%**. The authors explicitly recognize that an unmatched finding may identify a genuine, non-injected issue, so their “finding precision” is not established factual precision. Its multiple-error design suits ReviScope, but generator-dependent difficulty and incomplete truth sets complicate comparisons.

**4. Selch, Lukas, et al. (2026). “PRISMM-Bench: A Benchmark of Peer-Review Grounded Multimodal Inconsistencies.” ICLR 2026; arXiv:2510.16505, v3.**  
[Primary record](https://arxiv.org/abs/2510.16505) · [Evaluated version](https://arxiv.org/html/2510.16505v3)

The verified v3 contains **384 inconsistencies from 353 papers**, grounded in reviewer-flagged problems involving text, figures, tables, and equations, followed by filtering and human verification. It evaluates identification, remediation, and matching under focused, page-level, and document-level contexts. Across 21 models, the strongest aggregate reported score is **53.9%**. Eight PhD-level participants achieved **77.5% with focused context versus 65% with whole-document context** in a small human comparison. These structured tasks isolate multimodal reasoning, but their accuracy does not establish precision for unrestricted reviews; earlier versions contain different dataset counts.

**5. Baumgärtner, Tim, and Iryna Gurevych. (2026). “SciCoQA: Quality Assurance for Scientific Paper–Code Alignment.” Proceedings of ACL 2026, pp. 38740–38770.**  
[Published record](https://aclanthology.org/2026.acl-long.1795/) · [Published paper](https://aclanthology.org/2026.acl-long.1795.pdf)

The published benchmark contains **635 discrepancies: 92 real and 543 synthetic**, evaluating 22 models against paper–code inconsistencies. The best reported recall on real discrepancies is **46.7%**. Particularly relevant is a separate 20-paper analysis pooling existing annotations with expert-verified unmatched system findings, yielding **129 distinct verified discrepancies**. In that manually evaluated pooled analysis, GPT-5 achieves **88.0% precision and 51.2% recall**, while Gemini achieves **94.6% precision and 41.1% recall**. This is a strong precedent for acknowledging valid findings outside the original gold set, although pooled-ground-truth contributors receive a potential advantage and preprint/published numbers differ.

**6. Barkallah, Slim, Luke Bailey, Kaiyue Wen, Mohammed Abouzaid, and Tengyu Ma. (2026). “Pseudo-Formalization for Automatic Proof Verification.” arXiv:2605.20531, v1.**  
[Full paper](https://arxiv.org/html/2605.20531v1)

The authors introduce **ArxivMathGradingBench**, comprising **35 research papers** with author-disclosed corrected error locations, and compare direct verification with modular pseudo-formalization and block verification. Research-paper scoring matches predicted locations to disclosed locations and reports precision/recall, explicitly recognizing incomplete annotations. Even with eight rollouts, both approaches leave approximately **half the annotated errors undetected**. The headline **40% reduction in falsely flagged steps** concerns the separate Hard2Verify benchmark, not the research-paper dataset. For ReviScope, the work illustrates both the benefit of structured verification and the limitation of evaluating localization without fully validating the accompanying argument.

**7. Jiang, Fengqing, Yichen Feng, Yuetai Li, Luyao Niu, Basel Alomair, and Radha Poovendran. (2025). “BadScientist: Can a Research Agent Write Convincing but Unsound Papers that Fool LLM Reviewers?” arXiv:2510.18003.**  
[Primary record](https://arxiv.org/abs/2510.18003) · [Version underlying these results](https://arxiv.org/html/2510.18003v1)

BadScientist generates convincing but deliberately unsound papers, including fabricated experiments, and evaluates whether automated reviewers raise integrity concerns or recommend acceptance. In v1, an ensemble of o3, o4-mini, and GPT-4.1 accepts **52%** under a conference-rate-calibrated threshold, or **69%** under an alternative threshold. The ensemble nevertheless raises integrity concerns for **51.7%**, showing that concern detection and acceptance can coexist. These are adversarial acceptance outcomes, not error-level recall or precision. The task exposes susceptibility to scientific-looking fabrication, but should not be equated with ordinary manuscript auditing; the latest record includes a later revision.

**8. Dycke, Nils, and Iryna Gurevych. (2025). “Automatic Reviewers Fail to Detect Faulty Reasoning in Research Papers: A New Counterfactual Evaluation Framework.” arXiv:2508.21422, v1.**  
[Full paper](https://arxiv.org/html/2508.21422v1)

The framework creates **931 counterfactuals from 133 papers**, comprising 391 soundness-critical and 540 soundness-neutral modifications. It examines changes in review focus, scores, and assertion alignment rather than only asking whether a designated passage was located. Automated reviewers show little meaningful sensitivity to the critical alterations. Humans judged **90.2%** of sampled critical counterfactuals soundness-compromising, but agreement on edit correctness was weak, with **Goldstein’s S=0.20**. The paired neutral controls are valuable for ReviScope; mutation validity, omitted appendices, and review-level sensitivity measures limit interpretation as comprehensive flaw-detection accuracy.

**9. Xu, Zhijian, Yilun Zhao, Manasi Patwardhan, Lovekesh Vig, and Arman Cohan. (2025). “Can LLMs Identify Critical Limitations within Scientific Research? A Systematic Evaluation on AI Research Papers.” Proceedings of ACL 2025.**  
[Published record](https://aclanthology.org/2025.acl-long.1009/) · [Full preprint](https://arxiv.org/html/2507.02694v1)

LimitGen combines synthetic perturbations and limitations extracted from human reviews: **1,000 synthetic examples based on 500 papers and 1,000 human-reference examples**. Automatic evaluation uses subtype recovery or review-point precision/recall/Jaccard, followed by reference-relatedness and specificity scoring; unmatched limitations receive zero. Human evaluators initially judge without references, then may revise after seeing them, helping recognize valid alternatives. On fixed annotation samples, Cohen’s κ is **0.833** for synthetic identification and **0.772/0.735/0.717** for importance/faithfulness/soundness on human examples. This offers a useful annotation protocol, but research limitations are broader than demonstrable errors and automatic reference scoring remains incomplete.

**10. Rao, Delip, Jonathan Young, Thomas Dietterich, and Chris Callison-Burch. (2024). “WithdrarXiv: A Large-Scale Dataset for Retraction Study.” arXiv:2412.03775.**  
[Primary record](https://arxiv.org/abs/2412.03775)

WithdrarXiv collects **more than 14,000 withdrawn arXiv papers** and their author-provided withdrawal comments through September 2024. It categorizes withdrawal reasons and reports approximately **0.96 weighted F1** for reason classification. That score measures classification of withdrawal notes, not discovery of manuscript errors. Withdrawal can reflect reasons other than scientific invalidity, and short author notes often fail to specify the actual flaw. The dataset is useful for constructing real-error evaluations after substantial filtering, but cannot be used directly as an exhaustive paper-level truth set.

**11. Zhang, Tianmai M., and Neil F. Abernethy. (2025). “Reviewing Scientific Papers for Critical Problems With Reasoning LLMs: Baseline Approaches and Automatic Evaluation.” arXiv:2505.23824, v1.**  
[Full paper](https://arxiv.org/html/2505.23824v1)

WithdrarXiv-Check filters withdrawal cases for clearly stated, manuscript-detectable critical problems, yielding **1,225 cases**, with **245 held out for testing**. Models may report up to five concerns; a hit requires agreement from both o3 and Gemini judges that a generated concern matches the author’s error description. o3 obtains **64.9% hit rate@5 using PDFs and 71.0% under the LaTeX-input approach**, which falls back to PDF when source is unavailable. This is recovery of an acknowledged withdrawal reason, without adjudication of every unmatched finding. Public historical papers and withdrawal comments create contamination concerns, while model-specific document ingestion materially affects results.

**12. Liu, Ryan, and Nihar B. Shah. (2023). “ReviewerGPT? An Exploratory Study on Using Large Language Models for Paper Reviewing.” arXiv:2306.00622.**  
[Primary record](https://arxiv.org/abs/2306.00622)

This early study evaluates deliberately flawed short papers, targeted review questions, and paper comparisons. GPT-4 detects errors in **7 of 13** constructed papers, with targeted error-detection instructions performing better than generic reviewing instructions. On **119 paper–question pairs** involving 15 NeurIPS papers, reported accuracy is **86.6%**. The results demonstrate that factual checking, error discovery, and comparative reviewing differ substantially in difficulty. The sample is exploratory and too small or specialized to establish deployment-level precision or general performance in social science.

**13. Bianchi, Federico, Yongchan Kwon, Zachary Izzo, Linjun Zhang, and James Zou. (2025). “To Err Is Human: Systematic Quantification of Errors in Published AI Papers via LLM Analysis.” arXiv:2512.05925, v1.**  
[Full paper](https://arxiv.org/html/2512.05925v1)

This study targets relatively objective mistakes in formulas, calculations, figures, and tables rather than broad novelty judgments. Experts inspected **316 candidate mistakes from 60 papers**, confirming **263, or 83.2%**, including 86 substantive mistakes. The paper also reports **75.8% correctness for proposed fixes**. These validations are much closer to finding-level scientific precision than similarity to existing human reviews. However, confirming generated findings does not establish recall, and estimated error counts across the larger corpus should not be treated as if every finding received expert confirmation.

**14. Willner, Olaf, and David Yanagizawa-Drott. (2026). “Verifying the Verifiers: Towards Autonomous Policy Evaluation.” University of Zurich working paper, 25 September; CRED v0.92.**  
[Working paper](https://ape.socialcatalystlab.org/cred/verifying-the-verifiers.pdf) · [Benchmark report](https://ape.socialcatalystlab.org/verify)

CRED uses **100 AI-generated economics host papers**, two single-error arms totaling 200 instances, and a paired two-error arm; detectors receive manuscript/code plus a precomputed reproduction record. Deterministic quote matching measures localization and ignores the rationale, with best single-error recall reported as **99% for Codex 5.6 Sol high**. A separate precision exercise uses **Codex 5.5 high** on 100 unmutated papers: two reviewers adjudicate 461 findings, confirming **449, or 97.4%**, with **91.3% pre-consensus agreement**. These recall and precision figures concern different configurations and samples. This is unusually relevant empirical-social-science evidence, but selected AI-generated hosts, supplied execution diagnostics, withheld answer keys, and finding-level precision intervals limit transferability.

**15. Dawes Institute. (2026). “AI Peer Review Benchmark.” Public benchmark repository, released August.**  
[Primary repository and methodology](https://github.com/Dawes-Institute/ai-peer-review-benchmark/blob/main/README.md)

This psychology-specific benchmark inserts **100 methodological/statistical targets into ten open-access papers**, covering 50 subcategories of a 62-subcategory taxonomy. Fuzzy matching plus an LLM judge measures target recovery; the current README reports **71/100 for GPT-5.5 high**, and **93/100 for the union of 14 configurations**. All seven universally missed targets are omissions, highlighting the difficulty of noticing absent information. These scores do not establish finding precision, and the pooled union uses substantially more total resources than an individual configuration. For ReviScope, the project context’s independent target-validity audit is essential; the repository itself warns that its public answer key compromises future leaderboard use.

#### Whole-review quality, point matching, utility, and structured assessment

**16. Liang, Weixin, et al. (2024). “Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis.” NEJM AI, 1(8), AIoa2400196. DOI: 10.1056/AIoa2400196.**  
[Verified author preprint](https://arxiv.org/abs/2310.01783)

The study compares GPT-4 feedback with human review points for **3,096 Nature-family papers and 1,709 ICLR papers**. LLM–human overlap is **30.85% and 39.23%**, compared with human–human overlap of **28.58% and 35.25%**. In a prospective study involving 308 researchers, **57.4%** considered the feedback helpful/very helpful, and **82.4%** considered it better than at least some human-review feedback. Point overlap and author-perceived usefulness support complementary feedback, but do not demonstrate that every unmatched point is correct. Human references are incomplete, and author ratings introduce selection and preference effects.

**17. Du, Jiangshu, et al. (2024). “LLMs Assist NLP Researchers: Critique Paper (Meta-)Reviewing.” Proceedings of EMNLP 2024, pp. 5081–5099. DOI: 10.18653/v1/2024.emnlp-main.292.**  
[Published record and paper](https://aclanthology.org/2024.emnlp-main.292/)

ReviewCritique contains submitted manuscripts, human and LLM reviews, and expert sentence-level deficiency labels with explanations. Its construction involves **40 expert annotators, 100 submissions, and 380 human reviews**, with LLM comparisons on a 20-paper subset. **6.27% of human review segments versus 13.97% of LLM segments** are labeled deficient; every evaluated LLM review contains at least one deficiency. The best reported automated deficiency-detection F1 is only **21.99**, demonstrating that reviewing reviews is itself difficult. “Meta-reviewing” here means detecting deficient review segments, rather than synthesizing an area-chair decision; a numerical human inter-annotator coefficient was **[unverified]** in the material inspected.

**18. Sadallah, Abdelrahman, Tim Baumgärtner, Iryna Gurevych, and Ted Briscoe. (2025). “The Good, the Bad and the Constructive: Automatically Measuring Peer Review’s Utility for Authors.” Proceedings of EMNLP 2025.**  
[Published record](https://aclanthology.org/2025.emnlp-main.1476/) · [Full paper](https://arxiv.org/html/2509.04484v1)

RevUtil provides **1,430 human-annotated comments and 10,000 synthetic annotations per aspect**, covering actionability, grounding/specificity, verifiability, and helpfulness. Three annotators assess comments, with quadratic-weighted κ of **0.614/0.435/0.495/0.511** and α of **0.561/0.391/0.458/0.469**, respectively, on the full dataset. Agreement rises when low-agreement cases are excluded, which should not be confused with full-sample reliability. In a 20-paper comparison, human ratings favor human comments on all four dimensions, but those human-rated differences are not statistically significant. Because annotations primarily consider comments in isolation, the instrument measures communicated utility rather than verified manuscript-level correctness.

**19. Garg, Madhav Krishan, Tejash Prasad, Tanmay Singhal, Chhavi Kirtani, Murari Mandal, and Dhruv Kumar. (2025). “ReviewEval: An Evaluation Framework for AI-Generated Reviews.” Findings of EMNLP 2025, pp. 20542–20564.**  
[Published record and paper](https://aclanthology.org/2025.findings-emnlp.1120/)

The published framework evaluates **120 papers**, using topic coverage, factual correctness, constructiveness, depth, and guideline alignment; earlier preprints used a much smaller dataset. Factual evaluation decomposes comments into questions and applies retrieval/judging, while constructiveness checks specificity, feasibility, and implementation detail. The associated ReviewAgent reports actionability improvements of **6.78% over AI baselines and 47.62% over human reviews** under these metrics. These reported improvements are metric results, not independent evidence of superior scientific review. Optimizing and evaluating with related LLM-derived criteria raises circularity and Goodhart concerns, particularly without comprehensive expert adjudication.

**20. Shin, Hyungyu, et al. (2025). “Automatically Evaluating the Paper Reviewing Capability of Large Language Models.” arXiv:2502.17086, v1.**  
[Evaluated version](https://arxiv.org/html/2502.17086v1)

This framework evaluates **676 OpenReview papers** through labels describing the target of a comment—such as method or experiment—and its assessment aspect, such as validity or novelty. The best overall target–aspect agreement F1 is approximately **0.37**. LLMs generate more review points on average than humans and concentrate disproportionately on technical validity while overlooking other dimensions. Because agreement concerns category labels rather than the detailed criticism, even matching labels need not indicate matching arguments or correct criticism. This is useful for evaluating ReviScope’s breadth, but should supplement claim-level validation rather than replace it.

**21. Zhou, Ruiyang, Lu Chen, and Kai Yu. (2024). “Is LLM a Reliable Reviewer? A Comprehensive Evaluation of LLM on Automatic Paper Reviewing Tasks.” Proceedings of LREC-COLING 2024, pp. 9340–9351.**  
[Published record and paper](https://aclanthology.org/2024.lrec-main.816/)

The study evaluates score prediction, review generation, aspect coverage, and multiple-choice review questions informed by reviews, rebuttals, and revisions. Its question benchmark contains **197 questions** from ICLR 2023 papers. Models exceed **60% accuracy on individual-option judgments**, but achieve only approximately **20%** when required to get all options for a question correct. Text-generation metrics and aspect coverage assess resemblance and breadth, while these questions test recognition of selected reviewing judgments. Neither supplies open-ended criticism precision, and reference-derived questions inherit the judgments and limitations of the underlying review process.

**22. D’Arcy, Mike, Tom Hope, Larry Birnbaum, and Doug Downey. (2024). “MARG: Multi-Agent Review Generation for Scientific Papers.” arXiv:2401.04259, v1.**  
[Full paper](https://arxiv.org/html/2401.04259v1)

MARG organizes specialist agents around review dimensions and uses discussion and refinement to generate feedback. Evaluation combines human-reference point matching with a user study assessing feedback quality. Reported generic comments decrease from **60% to 29%**, while good comments increase from **1.7 to 3.7 per paper**. Reference precision/recall/Jaccard quantify agreement with existing reviews, while the user study can recognize useful comments beyond those references. The work supports evaluating paper-specific feedback, but older model/context limitations and resource differences restrict direct conclusions about current specialist-versus-plain pipelines.

**23. Zou, Zhuoyang, Abolfazl Ansari, Delvin Ce Zhang, Dongwon Lee, and Wenpeng Yin. (2026). “DIAGPaper: Diagnosing Valid and Specific Weaknesses in Scientific Papers via Multi-Agent Reasoning.” arXiv:2601.07611, v1.**  
[Full paper](https://arxiv.org/html/2601.07611v1)

DIAGPaper combines customized specialists, a rebuttal stage, and prioritization, evaluating semantic overlap with human weaknesses and validity-oriented review benchmarks. It reports **51.89 F1 versus 47.43 for GPT-4o** on its AAAR comparison. Importantly, three senior PhD students also assess **50 low-reference-precision weakness instances**, using majority votes on validity and realism. That targeted audit acknowledges that unmatched criticisms may be valid, while distinguishing factual plausibility from feasible, in-scope demands. The selected sample does not estimate precision across all emitted findings, and normalized invalid-overlap metrics should not be interpreted as conventional false-positive rates.

**24. Dycke, Nils, Matej Zečević, Ilia Kuznetsov, Beatrix Suess, Kristian Kersting, and Iryna Gurevych. (2025). “STRICTA: Structured Reasoning in Critical Text Assessment for Peer Review and Beyond.” Proceedings of ACL 2025.**  
[Published record and paper](https://aclanthology.org/2025.acl-long.1107/)

STRICTA represents critical assessment as structured reasoning rather than a single overall rating. Its human data involve approximately **40 biomedical experts, more than 20 papers, and over 4,000 reasoning steps**, organized around a detailed assessment workflow. Evaluation examines whether models reproduce reasoning steps and how those steps support assessment outcomes. Models can imitate parts of the workflow while assigning different importance to observations. For ReviScope, this motivates evaluating the chain from evidence to consequence and recommendation, although matching expert reasoning does not independently establish that every expert premise is correct.

**25. Xu, Shengwei, Yuxuan Lu, Grant Schoenebeck, and Yuqing Kong. (2025). “Benchmarking LLMs’ Judgments with No Gold Standard.” ICLR 2025; arXiv:2411.07127, v2.**  
[Full paper](https://arxiv.org/html/2411.07127v2)

The paper introduces generative mutual-information metrics, GEM/GEM-S, and GRE-bench to evaluate judgments through information shared with other judgments rather than an assumed perfect reference. It examines robustness to stylistic changes and validates against an educational peer-review setting with **30 proposals and roughly 180 reviews**. Correlations with instructor ratings are **0.431 for GEM and 0.479 for GEM-S**, compared with **0.537 for a GPT-4 examiner**. This addresses imperfect-reference problems more thoughtfully than literal overlap alone. However, shared information can include shared mistakes, so the metric cannot replace independent scientific adjudication.

#### Author/editor evaluations and field deployments

**26. Thakkar, Nitya, et al. (2025). “Can LLM Feedback Enhance Review Quality? A Randomized Study of 20K Reviews at ICLR 2025.” arXiv:2504.09737, v1.**  
[Evaluated preprint](https://arxiv.org/html/2504.09737v1)

The Review Feedback Agent comments on existing human reviews, with **22,467 reviews assigned to feedback and 22,364 to control**; 18,946 actually receive feedback. Of recipients, **26.6% update their reviews**, and the study estimates incorporation of 12,222 suggestions. In a selected sample of 100 updated reviews with substantial incorporation, blinded human judges prefer the revision **89% of the time**. That preference result is conditional on uptake, rather than an intention-to-treat estimate across all assigned reviews. The study is strong evidence for review-writing assistance, but does not test replacing human paper assessment with an autonomous reviewer.

**27. Biswas, Joydeep, et al. (2026). “AI-Assisted Peer Review at Scale: The AAAI-26 AI Review Pilot.” arXiv:2604.13940, v1.**  
[Full paper](https://arxiv.org/html/2604.13940v1)

AAAI deploys one labeled AI review for each of **22,977 submissions** and collects **5,834 voluntary survey responses**, with AI reviews rated higher on six of nine dimensions but also criticized for minor-issue emphasis and their own technical errors. Its SPECS benchmark creates **783 perturbations from 120 papers**, scoring designated-error recovery in full reviews. Final-system recovery is **63.86% versus 42.91% for a single-prompt baseline**, without comprehensive unmatched-finding adjudication. Human audit establishes that only **22/35 sampled perturbations** are jointly considered significant scientific errors; nine are minor and four disputed. The deployment supports operational feasibility and perceived usefulness, while survey selection, unequal budgets, clustered mutations, and benchmark validity constrain effectiveness claims.

**28. Chen, Shiping, Shu Zhong, Duncan P. Brumby, and Anna L. Cox. (2026). “What Happens When Reviewers Receive AI Feedback in Their Reviews?” CHI 2026. DOI: 10.1145/3772318.3791431.**  
[Author preprint](https://arxiv.org/html/2602.13817v1)

This study examines reviewers’ experiences of receiving AI feedback through **51 survey responses and nine interviews**. Seven-point ratings cover usefulness, actionability, constructiveness, ownership, and responsibility, alongside qualitative accounts of actual revisions. Mean constructiveness and actionability ratings are **3.88 and 4.22**, illustrating mixed rather than uniformly enthusiastic responses. Interviews show that adoption and perceived utility can diverge, with some suggestions prompting revisions despite reservations. This is valuable human–AI interaction evidence, but self-selection, small samples, and subjective outcomes prevent conclusions about scientific error-detection accuracy.

**29. Alahdab, Fares, Juan Franco, Helen Macdonald, and Sara Schroter. (2025). “Quality and Comprehensiveness of Peer Reviews of Journal Submissions Produced by Large Language Models vs Humans.” Tenth International Congress on Peer Review and Scientific Publication, conference abstract.**  
[Primary conference abstract](https://peerreviewcongress.org/abstract/quality-and-comprehensiveness-of-peer-reviews-of-journal-submissions-produced-by-large-language-models-vs-humans)

This BMJ study compares five models with two human reviews per manuscript using an experienced editor’s Review Quality Instrument ratings. Verified preliminary results comprise **35 reviews of five submissions**, with mean strengths/weaknesses ratings of **4.12 for LLMs versus 2.70 for humans**, and constructiveness **4.00 versus 3.00**. The abstract states that 200 submissions across four BMJ journals, author surveys, and a second editor’s ratings are planned. Those planned data and interrater agreement are not reported results in the opened abstract. This is directly relevant journal-editor evaluation, but the tiny paper sample and multiple correlated reviews require considerable caution.

**30. Goldberg, Alexander, Ivan Stelmakh, Kyunghyun Cho, Alice Oh, Alekh Agarwal, Danielle Belgrave, and Nihar B. Shah. (2025). “Peer Reviews of Peer Reviews: A Randomized Controlled Trial and Other Experiments.” PLOS ONE, 20(4), e0320444. DOI: 10.1371/journal.pone.0320444.**  
[Journal article](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0320444)

The study investigates how authors, reviewers, and area chairs judge review quality, including a randomized manipulation of review length. In the length experiment, **458 participants** assess reviews from ten papers, with an intervention increasing average length from **268 to 755 words** without adding useful content. Mean perceived quality rises from **3.73 to 4.29** on a seven-point scale. Other analyses reveal disagreement and outcome-related biases in review assessments. Consequently, human preference panels are valuable but imperfect, and ReviScope should control verbosity and distinguish satisfaction from validated scientific contribution.

**Journal-pilot verification gap.** Manrai, Arjun K., David Ouyang, Joseph W. Hogan, and Isaac S. Kohane’s *“Accelerating Science with Human+AI Review”* is bibliographically identifiable as **NEJM AI 2(12), 2025, DOI 10.1056/AIe2501175**, but the [publisher full text](https://ai.nejm.org/doi/full/10.1056/AIe2501175) returned an access error. Its detailed pilot methods and comparative outcomes therefore remain **[unverified]** here and are excluded from the 32 verified entries. Secondary descriptions should not be used to claim that this was a randomized evaluation of the review process.

#### Diversity, gaming, and contamination of review benchmarks

**31. Baumann, Joachim, Jiaxin Pei, Sanmi Koyejo, and Dirk Hovy. (2026). “Stop Automating Peer Review Without Rigorous Evaluation.” arXiv:2605.03202, v2; ICML 2026 position paper.**  
[Evaluated version](https://arxiv.org/html/2605.03202v2)

This work evaluates reviewer diversity and susceptibility to manuscript rewriting using **75,800 ICLR 2026 reviews** and controlled experiments on **60 papers**. Automated reviews show greater within-paper and cross-paper embedding similarity, while automated rewriting increases review scores. Across 24 rewriting/reviewing conditions, the reported mean paired score increase is **0.45**. The observational comparison relies on AI-generation classifications, and embedding similarity captures linguistic regularity as well as substantive convergence. For ReviScope, the useful lesson is to test distinct supported-issue coverage and invariance to superficial rewriting, rather than equating reviewer agreement with reliability.

**32. Ho, Sy-Tuyen, Minghui Liu, and Furong Huang. (2026). “When AI Reviews Train AI Reviewers: Scientific-Judgment Collapse and Mitigation.” arXiv:2609.20942, v1.**  
[Full paper](https://arxiv.org/html/2609.20942v1)

The authors fine-tune a reviewer on official ICLR reviews and train successors on different mixtures of official and generated reviews. Introducing synthetic supervision compresses ratings and reduces semantic diversity, with approximately **11% lower same-paper diversity and 5% lower corpus-level diversity** between zero and fully synthetic exposure. The study examines **one recursive training step**, rather than demonstrating inevitable collapse across many generations. Its mitigation system is evaluated through recommendation alignment and diversity, neither of which establishes criticism correctness. This September 2026 preprint highlights that public “human review” corpora can become increasingly unsuitable as uncontaminated reference standards.

### C. Open methodological debates

- **How complete must a gold set be?** Author corrections establish some real errors, not their absence elsewhere. Pooled annotation improves coverage but advantages contributing systems; independently collected findings and leave-one-system-out sensitivity analyses could help quantify that bias.

- **What counts as an error rather than a limitation or unreasonable demand?** Reporting omissions, weak identification, questionable interpretation, missing robustness checks, and speculative alternatives require different evidential standards. Expert disagreement may reflect legitimate scope judgments rather than annotation failure.

- **What is the proper target: correct criticism, useful revision, or editorial judgment?** A factually correct minor comment may add little value; a consequential criticism may require substantial verification. No single overlap, preference, or utility score captures these trade-offs.

- **Can scalable LLM judging be scientifically independent?** Good matching agreement does not establish factual-adjudication ability. Shared model assumptions, selection of only human-agreed validation cases, and optimizing against the judge can make impressive metric gains misleading.

- **How should results transfer across prevalence and domains?** Precision on flawed or AI-generated papers may differ sharply from precision on mostly sound manuscripts. CS-heavy benchmarks also provide limited evidence about causal identification, construct validity, measurement, and interpretive disputes in social psychology.

- **How should secrecy and reproducibility be balanced?** Public errors, reviews, and answer keys facilitate auditing but contaminate future evaluations; private benchmarks preserve novelty but impede scrutiny. Versioned public methods combined with rotating independently adjudicated holdouts are a promising compromise.

- **What establishes the value of a complex pipeline?** Improvements must survive equal-budget baselines, repeated runs, paper-level uncertainty, and direct audits of verifier/synthesis losses. More agents, longer reviews, or higher human-reference agreement do not alone demonstrate better scientific assessment.