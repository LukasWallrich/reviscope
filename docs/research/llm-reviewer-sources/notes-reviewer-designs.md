# Designs of LLM-based scientific paper reviewers and error-checkers: survey for ReviScope

Compiled 2026-10-08. All 47 entries were checked by opening their arXiv, venue, vendor or GitHub page, and DOIs were cross-checked with Crossref where available. Numbers are as reported on those pages; [unverified] marks what I could not confirm. Several commercial tools (Refine, Reviewer3, q.e.d) publish no independent evaluation; their descriptions are vendor or press claims.

## (a) Takeaways for designing ReviScope's specialist pipeline

1. **Evidence that decomposition beats single calls exists, but it depends on how outcomes are measured.**
   - In favour:
     - AAAI-26: a five-stage specialist pipeline beat a single-prompt baseline on planted-error detection in all 5 criteria, by 0.15 to 0.32 absolute.
     - Refine benchmark: coarse scaffolding cut Refine's win margin over the same base model by roughly 3 to 25 points.
     - MARG: halved generic comments.
     - TreeReview and Gauntlet: preferred by LLM judges.
   - Against: Georgantas (2026) found a one-paragraph prompt almost matched a full pipeline on accept/reject AUROC.
   - The gains appear when the outcome is coverage or recall of specific, grounded concerns across many aspects. They shrink when the outcome is a global score. ReviScope's finding that the plain call matches or beats it on 2 papers is within noise, given how variable runs are (see point 2).

2. **Run-to-run variance is enormous, so one run per configuration cannot settle anything.**
   - SPOT: models rarely rediscovered the same real errors across 8 runs.
   - Parsa & Rezaei: independent samples covered 44.9% of historical concerns, while pooling with deduplication covered 78.7%.
   - Georgantas: within-paper score SD was 0.7 for the pipeline against 2.8 for a bare prompt.
   - Recommendation: use several seeds per configuration and per paper, and report variance. Also consider "single call × k with union" as the fair baseline for a multi-stage pipeline at equal token cost.

3. **The bottleneck is selection, not generation.**
   - With a large candidate pool, coverage approaches 80%, but selectors that see only the paper keep only 40 to 44% of the coverage an oracle selector keeps (Parsa & Rezaei).
   - AAAI-26 users complained about nitpicking, verbosity and poor prioritisation. Gauntlet lost to humans on "unstructured comprehensiveness".
   - ReviScope's specialist stage is probably adequate at generating concerns. Invest in the verifier and in editorial ranking (consequence × confidence), and evaluate those stages separately (e.g. candidate-pool recall against final-report recall).

4. **Verification and filter stages are widely used but rarely ablated on precision.**
   - Deployed systems use critics or guards: AAAI-26 (self-critique plus a separate critic LLM plus human checks of flagged reviews), the ICLR Review Feedback Agent (actor, aggregator and critic plus 4 pass/fail reliability tests with retries), SEA (a mismatch-score self-correction loop), DeepReview (a trained "reliability verification" stage), and coarse (quote verification plus an editorial filter).
   - Only the AI Scientist reports an ablation, and it covers reflection: +2% accuracy, with ensembling reducing variance but not raising accuracy.
   - Unfiltered systems produce many false positives: YesNoError had 14 of 40 flagged papers that were false positives (Nature 2025), and SPOT's best precision was 6.1%.
   - Gap: no one has ablated verifier precision against recall loss on expert-adjudicated findings. ReviScope's planned verifier calibration probe set would be novel.

5. **Narrow, targeted prompts beat "review this paper" for finding errors.**
   - Liu & Shah: error-specific prompts outperformed generic review prompts.
   - Narrow checks work: Liu & Shah reached 86.6% accuracy on checklist verification, the NeurIPS checklist assistant (Goldberg et al.) was found useful by most authors, and RegCheck works one preregistration dimension at a time.
   - Dycke & Gurevych: generic review generators were insensitive to injected logic flaws.
   - Recommendation: specialist modules should be framed as concrete hunts ("does any reported test statistic contradict its df and p?", "is the causal claim supported by the design?"), not as aspect essays.

6. **Put deterministic checkers first, and treat their findings as trusted.**
   - statcheck has 96 to 99.9% accuracy against manual coding, and its use at journals is associated with fewer inconsistencies.
   - metacheck restricts LLMs to classifying text.
   - Agents4Science's reference checker and injection scanner caught real problems cheaply.
   - Recommendation: route deterministic hits around the LLM verifier (or verify them only for consequence), and reserve LLM verification for judgement claims.

7. **Code execution and re-analysis need blinding and are still weak at finding errors.**
   - I4R: AI-led teams reproduced only 37% of results, against 94% for human-only teams, and found fewer major coding errors.
   - REPRO-Bench: the best agent reached 21.4%, about 36.7% after improvement.
   - Alizadeh et al.: giving agents the original PDF biased them towards confirmation on impossible tasks, and prompts can induce specification search.
   - Recommendation: sandboxed re-analysis should recompute from the data or the reported numbers before seeing the claimed result, and its findings should be labelled as checks rather than verdicts.

8. **Retrieval helps novelty and context but is domain-limited.**
   - Stanford Agentic Reviewer, DeepReview, ReviewRL, MAMORX and AAAI-26 all use literature retrieval for novelty.
   - The Stanford system's own docs say it is weaker outside arXiv-heavy fields, and AAAI-26 users still rated novelty and significance judgements as weak.
   - For social psychology, retrieval should target replications, meta-analyses and retractions (e.g. FLoRA, Retraction Watch through metacheck) rather than generic "related work".

9. **Expect sycophancy and inflated scores, and pick the verifier model family with care.**
   - OpenReviewer: GPT-4 and Claude-3.5 were overly positive.
   - Akella et al.: scores inflated by 3 to 5 points while self-reported confidence stayed at 8 to 9 out of 10.
   - Agents4Science: Gemini 2.5 Pro gave a mean of 4.23 against 2.30 for GPT-5, with sycophantic text.
   - Ye et al.: LLM reviews echo the authors' disclosed limitations 4.5x more than human reviews do.
   - Recommendations: do not use LLM self-confidence as a filter. Measure each family's leniency on the calibration set. Down-weight findings that merely restate the paper's limitations section.

10. **Treat the manuscript as adversarial input.**
    - Hidden prompts manipulate targeted parts of reviews (Zhu et al. 2025; Ye et al. 2024).
    - Presentation-only rewrites raised AI scores by +1.21/10, a 75.1% attack success rate (Yang et al. 2026). Zero-shot "laundering" rewrites added +0.45 (Baumann et al. 2026).
    - Recommendations: add an injection scan as Agents4Science did, keep verifier prompts separate from paper text, and avoid letting polish drive judgements of severity.

11. **Planted-error benchmarks are fragile, and ReviScope's audit result has independent support.**
    - AAAI-26: human audit found only 22 of 35 LLM-generated perturbations to be valid significant errors, with presentation and significance perturbations the weakest.
    - SPOT, built on real errata and retractions, shows far lower performance than planted benchmarks.
    - Recommendations: report recall separately for demonstrable errors and for reporting gaps. Add real-error items (errata or retracted social psychology papers, statcheck-confirmed decision errors). Consider counterfactual paired tests (Dycke & Gurevych) and localisation metrics (FLAWS top-k spans) that do not depend on an LLM matcher.

12. **Pairwise LLM judging needs atomic decomposition to resist length bias.**
    - Refine's benchmark extracts atomic concerns, verifies their anchors, aligns shared items and judges only the residual differences, with flip-averaged and bias-filtered judges.
    - Baumann et al.: AI scores correlate 0.49 with each other but only 0.15 with humans, which points to shared stylistic preferences and self-preference.
    - Recommendations: judge at the level of individual criticisms (as ReviScope plans with clustering), and anchor judgements to the paper.

13. **Human comparison measures a different profile, not just quality.**
    - Overlap between LLM and human comments (31 to 39%) is similar to human–human overlap (Liang et al.).
    - LLM critiques have a different functional profile (more integrative and formal), and "expert" prompting amplifies this rather than making them more human-like (Yang, Thelwall & He 2026).
    - Recommendation: human reviews are a weak gold standard for recall. Use them for coverage of what experts consider important, not for precision.

14. **Field evidence on usefulness is positive but mixed, and length is the main complaint.**
    - AAAI-26: 53.9% of respondents found the AI reviews useful, and AI reviews were preferred on 6 of 9 criteria. However, 49.4% said they missed points a human would catch, and verbosity was a top complaint.
    - Users of the NeurIPS checklist assistant became less positive after use.
    - Recommendation: a short, prioritised report with labelled unresolved concerns (ReviScope's design) addresses the most common complaint. Test it with readers.

## (b) Comparison table

| System | Year | Architecture | Tools / retrieval | Verification / filtering | Evaluation | Headline result |
|---|---|---|---|---|---|---|
| ReviewerGPT (Liu & Shah) | 2023 | Single GPT-4 calls on targeted tasks | none | none | Planted errors in 13 papers; 119 checklist pairs; 10 abstract pairs | 7/13 errors found; 86.6% checklist accuracy; 6/10 comparison errors |
| Liang et al. (NEJM AI) | 2024 | Single GPT-4 structured prompt | PDF parsing | none | Comment overlap with humans (Nature, ICLR); user study | 30.85–39.23% overlap (≈ human–human); 57.4% found it helpful |
| MARG | 2024 | Multi-agent: leader, chunk workers, aspect experts | none | Inter-agent discussion | Author-rated user study | Generic comments 60% → 29%; good comments 1.7 → 3.7 per paper |
| AI Scientist reviewer | 2024 | GPT-4o, 5 self-reflection rounds, 1-shot, 5-review ensemble plus meta-review | none | Self-reflection; ensemble | 500 ICLR 2022 papers, decision prediction | Balanced accuracy 0.65 (humans 0.66); reflection +2% |
| AgentReview | 2024 | Simulated reviewer, author and AC agents | none | n/a | Simulation | 37.1% of decision variation attributed to biases |
| SEA | 2024 | Fine-tuned generator plus standardisation | none | Mismatch-score self-correction | 8 venues | Qualitative gains |
| MAMORX | 2024 | Specialist agents for novelty, figures, clarity; multimodal | Semantic Scholar | none reported | Arena human evaluation | Estimated 93% win rate vs human reviews |
| OpenReviewer | 2024/25 | Fine-tuned Llama 8B, single pass | none | none | 400 papers | Less positive and closer to human score distribution than GPT-4 or Claude-3.5 |
| CycleReviewer | 2025 | Fine-tuned open LLM (Review-5k) | none | none | Score MAE | 26.89% lower MAE than individual humans |
| DeepReview | 2025 | Fine-tuned 14B: novelty, multi-dimensional evaluation, reliability stages | Literature retrieval | Trained reliability verification | LLM-judged win rates | 88.21% vs o1; 80.20% vs DeepSeek-R1 |
| TreeReview | 2025 | Question-tree decomposition, bottom-up aggregation | none | none | LLM judge plus human win rates | Specificity +12.27%; 80% fewer tokens than MARG |
| ReviewRL | 2025 | Retrieval, SFT and RL with composite reward | ArXiv-MCP | none | ICLR 2025 | "Significantly outperforms" (no headline numbers) |
| ICLR Review Feedback Agent | 2025 | 5× Claude 3.5 Sonnet: 2 actors, aggregator, critic, formatter | none | Critic plus 4 reliability tests with retries | Randomised trial, ~20k reviews | 26.6% of reviewers updated; 89% preferred the updated reviews |
| Stanford Agentic Reviewer | 2025 | Retrieval-grounded single review; 7 sub-scores combined by regression | Tavily arXiv search, relevance filter | none disclosed | ICLR 2025 score correlation | Spearman 0.42 (human–human 0.41); AUC 0.75 |
| Agents4Science reviewers | 2025 | 3 single-call LLMs (GPT-5, Gemini, Claude) | Reference-check web search; injection scanner | Deterministic guards | 79 papers with human scores | Mean absolute difference from humans 0.91 (GPT-5), 2.73 (Gemini); sycophancy noted |
| NeurIPS checklist assistant | 2024 | LLM per checklist item | none | none | 234 papers, author surveys | >70% found it useful; complaints about inaccuracy and strictness |
| AAAI-26 pilot | 2026 | 5 specialist stages (gpt-5), synthesis, self-critique | Python interpreter, venue-restricted web search, olmOCR | Self-critique, critic LLM, human checks, citation audit | 22,977 papers; SPECS planted benchmark; 5,834 survey responses | Beat single prompt on all criteria (e.g. Story 0.67 vs 0.35); 53.9% found it useful |
| coarse | 2025/26 | Overview, completeness, parallel section agents, synthesis | Perplexity literature search | Adversarial proof check, editorial filter, fuzzy quote verification | none published | (scaffold beat single-shot in Refine's benchmark) |
| Refine | 2025/26 | Closed; deep consistency and logic critique | n/d | n/d | Vendor benchmark: 150 economics papers vs 9 systems | 90.4% win rate; 94.8% vs single-shot, 85.0% vs scaffolded |
| Gauntlet | 2026 | 5 expert personas (3 fixed, 2 dynamic) plus adversarial synthesis | none | Disagreement-preserving synthesis | 98-paper LLM-judged ablation; 20-paper human evaluation | Beat single rich-persona agent on 96% of papers |
| AIPR (Georgantas) | 2026 | Engineered 5-dimension scorer | n/d | n/d | 300 ICLR papers | AUROC 0.82; bare prompt nearly as good but SD 2.8 vs 0.7 |
| Pre-submission pool (Parsa & Rezaei) | 2026 | Sample atomic concerns, deduplicate, refill, compress | none | Selector | 3,398 ICLR 2026 papers vs historical reviews | 78.7% coverage from pool; selectors keep only 40–44% |
| Reviewer3 | 2025/26 | Specialist agents (design, statistics, code, data) | Sandbox re-runs; 5 citation databases | n/d | none published | >30k manuscripts reviewed |
| q.e.d Science | 2025 | Claim-tree decomposition, validity engine, multi-agent | Literature comparison | n/d | none published | bioRxiv integration |
| YesNoError | 2025 | High-volume LLM error scan | n/d | none evident | Independent spot check (Nature) | 14/40 flagged papers were false positives |
| Black Spatula | 2024– | Crowdsourced model and prompt trials | varies | Human expert adjudication | ~500 papers | Errors reported privately to authors |
| statcheck | 2016 | Deterministic regex plus p-value recomputation | none | n/a | Validated against manual coding | 96.2–99.9% accuracy |
| metacheck | 2024–26 | Deterministic R modules; LLM only for classification | Retraction Watch, PubPeer, FLoRA | n/a | none reported | v0.1.0 |
| RegCheck | 2026 | LLM per preregistration dimension | none | Verbatim quotes checked by a human | Validation study (numbers [unverified]) | — |
| CORE-Agent (CORE-Bench) | 2024 | Task-adapted AutoGPT | Code execution | none | 270 tasks / 90 papers | 60% easy, 21.48% hard |
| REPRO-Agent (REPRO-Bench) | 2025 | Agent assessing reproduction packages | Code execution | none | 112 social science papers | Best existing 21.4%; +71% relative |
| Claude Code / Codex (Alizadeh et al.) | 2026 | General coding agents | Code execution | none | 221 social science tasks | High reproduction rates; PDF causes confirmation bias |
| I4R AI replication games | 2025/26 | ChatGPT assisting or leading teams | Code execution | Human | RCT, 103 teams | Reproduction 94% human, 91% AI-assisted, 37% AI-led |

Error-detection benchmarks for reference (not systems):

| Benchmark | Errors | Headline result |
|---|---|---|
| SPOT | Real errors | Best recall 21.1%, precision 6.1% |
| FLAWS | LLM-inserted errors | Best 39.1% at top-10 |
| PaperAudit-Bench | Within- and cross-section errors | Detectability varies widely by model and depth |
| Dycke & Gurevych | Counterfactual logic flaws | No effect on generated reviews |
| Zhang & Abernethy | Withdrawn arXiv papers | o3 best |

## (c) Annotated bibliography (appended incrementally)

### Early systems and simulators

1. **D'Arcy, M., Hope, T., Birnbaum, L., & Downey, D. (2024). MARG: Multi-Agent Review Generation for Scientific Papers.** arXiv:2401.04259. https://arxiv.org/abs/2401.04259
   - Architecture: several GPT-4 agents that pass messages to each other. A leader agent coordinates worker agents, each of which holds one chunk of the paper, so the full text fits even with short contexts. Separate expert instantiations cover experiments, clarity and impact. Prompted, not trained.
   - Evaluation: user study in which authors rated comments on their own papers.
   - Result: compared with GPT-4 single-prompt baselines, generic comments fell from 60% to 29%, and good comments per paper rose from 1.7 to 3.7 (2.2x).
   - Relevance: this is the clearest early evidence that a specialist (aspect-specific) decomposition beats a single call. However, the outcome measured was specificity and perceived helpfulness, not error recall, and the baseline was a context-limited single call.

2. **Liu, R., & Shah, N. B. (2023). ReviewerGPT? An Exploratory Study on Using Large Language Models for Paper Reviewing.** arXiv:2306.00622. https://arxiv.org/abs/2306.00622
   - Design: GPT-4 prompted on three targeted tasks.
   - Results:
     - Error detection: it found the planted errors in 7 of 13 short CS papers.
     - Checklist verification: 86.6% accuracy across 119 checklist-question/paper pairs from NeurIPS 2022.
     - Paper comparison: it erred on 6 of 10 abstract pairs that were built so one was clearly better.
   - Takeaway: targeted prompts ("find the error") worked better than generic review requests. LLMs are useful for specific checks, not for overall judgement. This is an early argument for task-specific rather than holistic prompting.

3. **Lu, C., Lu, C., Lange, R. T., Foerster, J., Clune, J., & Ha, D. (2024). The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery.** arXiv:2408.06292. https://arxiv.org/abs/2408.06292
   - Reviewer design: GPT-4o follows the NeurIPS review form and outputs scores, strengths, weaknesses and a decision. It adds 5 rounds of self-reflection, 1-shot examples, and an ensemble of 5 reviews aggregated by an "area chair" meta-review.
   - Evaluation: 500 ICLR 2022 papers, threshold 6. The reviewer reached balanced accuracy 0.65 (humans 0.66), F1 0.57 (humans 0.49) and AUC 0.65 (humans 0.65). Its false positive rate was 0.31 against 0.17 for humans.
   - Ablations: self-reflection added about 2% accuracy and one-shot about 2%. Ensembling did not raise accuracy but reduced variance.
   - Caveat: this measures decision prediction, not the quality of individual criticisms.

4. **Jin, Y., Zhao, Q., Wang, Y., Chen, H., Zhu, K., Xiao, Y., & Wang, J. (2024). AgentReview: Exploring Peer Review Dynamics with LLM Agents.** EMNLP 2024 (oral). arXiv:2406.12708. https://arxiv.org/abs/2406.12708
   - What it is: a simulation of the review process with reviewer, author and area-chair agents. It studies process biases rather than producing usable reviews.
   - Finding: 37.1% of the variation in paper decisions was attributed to reviewer biases (social influence, altruism fatigue, authority bias).
   - Relevance: low for ReviScope's design. It shows that persona and interaction choices in multi-agent setups change outcomes substantially.

### Trained reviewers

5. **Weng, Y., Zhu, M., Bao, G., Zhang, H., Wang, J., Zhang, Y., & Yang, L. (2025). CycleResearcher: Improving Automated Research via Automated Review.** ICLR 2025. arXiv:2411.00816. https://arxiv.org/abs/2411.00816
   - Design: CycleReviewer is an open LLM fine-tuned on the Review-5k dataset. It supplies the reward for iterative preference training of a paper-writing model.
   - Result: 26.89% lower mean absolute error in score prediction than individual human reviewers.
   - Relevance: it optimises agreement with scores, not the validity of criticisms.

6. **Zhu, M., Weng, Y., Yang, L., & Zhang, Y. (2025). DeepReview: Improving LLM-based Paper Review with Human-like Deep Thinking Process.** arXiv:2503.08569 (ACL 2025 [venue unverified]). https://arxiv.org/abs/2503.08569
   - Design: a fine-tuned model (DeepReviewer-14B, trained on DeepReview-13K) runs three stages: novelty verification with literature retrieval, multi-dimensional evaluation, and reliability verification. The staged structure is learned from synthetic reasoning traces.
   - Results: it beats CycleReviewer-70B and has win rates of 88.21% against o1 and 80.20% against DeepSeek-R1 (LLM-judged).
   - Relevance: it puts a built-in "reliability verification" stage into training. Its evaluation relies on LLM judges and score prediction.

7. **Idahl, M., & Ahmadi, Z. (2025). OpenReviewer: A Specialized Large Language Model for Generating Critical Scientific Paper Reviews.** NAACL 2025 System Demonstrations. arXiv:2412.11948. https://arxiv.org/abs/2412.11948
   - Design: Llama-OpenReviewer-8B, fine-tuned on 79k expert reviews from ML/AI conferences. It takes a PDF and a review template and produces one review in a single pass.
   - Evaluation: 400 test papers. Its recommendations were more critical and closer to the human distribution than those of GPT-4 or Claude-3.5, which were "overly positive".
   - Relevance: it documents the positivity/sycophancy failure of general-purpose LLMs. Fine-tuning mainly recalibrates tone and score.

8. **Zeng, S., Tian, K., Zhang, K., Wang, Y., Gao, J., Liu, R., Yang, S., Li, J., Long, X., Ma, J., Qi, B., & Zhou, B. (2025). ReviewRL: Towards Automated Scientific Review with RL.** arXiv:2508.10308. https://arxiv.org/abs/2508.10308
   - Design: retrieval-augmented context through an ArXiv-MCP server, then SFT, then RL with a composite reward that combines review quality and rating accuracy.
   - Evaluation: ICLR 2025 papers. It "significantly outperforms" existing methods on rule-based and model-judged metrics. The abstract gives no headline numbers, so these are not stated here.

9. **Chang, Y., Li, Z., Zhang, H., Kong, Y., Wu, Y., So, H. K.-H., Guo, Z., Zhu, L., & Wong, N. (2025). TreeReview: A Dynamic Tree of Questions Framework for Deep and Efficient LLM-based Scientific Peer Review.** EMNLP 2025 (main). arXiv:2506.07642. https://arxiv.org/abs/2506.07642
   - Architecture: high-level review questions are decomposed recursively into sub-questions, with dynamic follow-up questions where needed. Leaf questions are answered against the paper, and the answers are aggregated bottom-up into the review. Prompted, single model, no inter-agent chat.
   - Baselines: direct prompting, structured template prompting, fine-tuned Reviewer2 and SEA-E, MARG.
   - Results (LLM judge): overall quality 8.18, with specificity +12.27% and comprehensiveness +11.22% over the best baseline. It used 80.2% fewer tokens than MARG (459K vs 2.3M per paper). Human win rates were 66.25 to 90.00% (kappa 0.70).
   - Takeaway: question decomposition with aggregation beat both single calls and chatty multi-agent setups at lower cost. The authors call MARG-style communication costly and "vulnerable to communication errors".

10. **Yu, J., Ding, Z., Tan, J., Luo, K., Weng, Z., Gong, C., Zeng, L., Cui, R., Han, C., Sun, Q., Wu, Z., Lan, Y., & Li, X. (2024). Automated Peer Reviewing in Paper SEA: Standardization, Evaluation, and Analysis.** Findings of EMNLP 2024. arXiv:2407.12857. https://arxiv.org/abs/2407.12857
    - Design: SEA-S uses GPT-4 distillation to merge several human reviews into one standard training target. SEA-E is a fine-tuned review generator. SEA-A computes a "mismatch score" between paper and review and drives a self-correction loop that regenerates reviews when consistency is low.
    - Relevance: a learned consistency check between paper and review, which is an early form of verification or filtering.

### Deployed systems and field evidence

11. **Biswas, J., Schoepp, S., Vasan, G., Opipari, A., Zhang, A., Hu, Z., Joseph, S., Lease, M., Li, J. J., Stone, P., Wagstaff, K. L., Taylor, M. E., & Jenkins, O. C. (2026). AI-Assisted Peer Review at Scale: The AAAI-26 AI Review Pilot.** arXiv:2604.13940. https://arxiv.org/abs/2604.13940
    - Architecture: five sequential specialist stages, each running gpt-5 with high reasoning effort:
      - Story: problem and claims.
      - Presentation.
      - Evaluations: baselines and data, with a Python interpreter.
      - Correctness: equations, algorithms, figures and tables, with a Python interpreter.
      - Significance: web search restricted to published venues.
    - These stages are followed by synthesis, self-critique and a final review. A separate critic LLM screens outputs for anonymity breaches, bias and missing sections, and humans inspect flagged reviews. Citation hallucinations were checked on 100 sampled reviews (GPTZero). PDFs are converted with olmOCR.
    - Scale: all 22,977 main-track papers in under a day.
    - SPECS benchmark: 783 LLM-generated perturbations planted in the LaTeX of 120 AAAI-25 papers, spread across the same 5 criteria. A judge counts a detection only if the review identifies the error with textual evidence.
    - Pipeline vs single-prompt baseline (detection rates):

      | Criterion | Pipeline | Single-prompt baseline |
      |---|---|---|
      | Story | 0.67 | 0.35 |
      | Presentation | 0.57 | 0.42 |
      | Evaluations | 0.75 | 0.52 |
      | Correctness | 0.76 | 0.61 |
      | Significance | 0.45 | 0.26 |

      All differences were significant at alpha = 0.01.
    - Benchmark validity: human audit found only 22 of 35 sampled perturbations to be valid significant errors. Presentation and significance perturbations were especially weak.
    - Survey: 5,834 responses. 53.9% of respondents found the AI reviews useful (20.2% did not). AI reviews were preferred on 6 of 9 criteria, including +0.67 on finding technical errors. 46.6% said the AI found concerns humans would miss, but 49.4% said it missed points a human would catch.
    - Reported failure modes: weak judgement of novelty and significance, nitpicking and over-emphasis on minor issues, excessive verbosity and cognitive overload, misreading equations and tables, poor prioritisation, and shallow domain context.
    - Relevance: this is the strongest evidence so far that a specialist staged pipeline beats a single prompt on planted-error recall. Caveats: the single prompt may have been weaker, it is ML/AI only, and the benchmark was LLM-generated with roughly 37% invalid targets. That invalid-target problem matches the one ReviScope found in its own benchmark.

12. **Parsa, P., & Rezaei, A. (2026). More Than Mimicking Reviewers: Evaluating LLMs for Pre-Submission Peer Review.** arXiv:2609.05788. https://arxiv.org/abs/2609.05788
    - Design: an author-facing system that generates a broad pool of "atomic concerns" and compresses them into a short report.
    - Evaluation: 3,398 ICLR 2026 manuscripts with pre-review versions, measured by coverage of the concerns raised in the historical reviews.
    - Results: independent sampling covered 44.9%. Deduplicating and refilling covered 78.7% strictly and 84.9% when weighted by seriousness, at 3.6x more requests and 5.2x more tokens. An oracle selector kept 79.3% from 256 candidates, but selectors that only see the paper kept 40 to 44%.
    - Takeaway: "broad coverage with a large candidate pool but compresses poorly". Generation is not the bottleneck; selection, filtering and prioritisation are. They also report sensitivity to the matcher, which is directly relevant to ReviScope's verifier and editorial stage and to its LLM-matching recall metric.

13. **Akella, A. P., Siravuri, H. V., & Rohatgi, S. (2025). Pre-review to Peer review: Pitfalls of Automating Reviews using Large Language Models.** arXiv:2512.22145. https://arxiv.org/abs/2512.22145
    - Findings for open-weight LLM reviewers: correlation with human reviewers was only about 0.15. Scores were inflated by 3 to 5 points, and stated confidence stayed uniformly high (8 to 9 out of 10) even when predictions were wrong. LLM scores correlated more with later publication metrics than with human scores.
    - Takeaway: self-reported LLM confidence is not usable for filtering and needs a separate calibration check.

14. **Jiang, Y., & Ng, A. (2025). Stanford Agentic Reviewer (paperreview.ai), technical overview.** Web tool and documentation. https://paperreview.ai/tech-overview (launch post: https://x.com/AndrewYNg/status/1993001922773893273)
    - Architecture:
      - PDF to Markdown with LandingAI Agentic Document Extraction, plus a check that the document is an academic paper.
      - Search queries generated at several levels of specificity.
      - Retrieval of arXiv papers through the Tavily API.
      - Relevance filtering on metadata, then use of the abstract or a full-PDF summary.
      - Generation of a review grounded in the summaries of related work.
    - Scoring: seven sub-scores (originality, importance of the question, claim support, experimental soundness, clarity, community value, positioning against prior work). A linear regression fitted to ICLR 2025 ratings combines them, rather than the LLM giving the overall score directly.
    - Results: Spearman correlation of 0.42 with a single human reviewer, against 0.41 between two humans. Acceptance AUC was 0.75 (humans 0.84).
    - Stated limits: errors are possible, it is weaker outside AI and arXiv-heavy fields, and it handles English only. Prompt injection is not addressed.
    - Usage claims (launch post and press, not peer reviewed): about 21.5k papers in the first week. The figures of 95% of users finding reviews useful and 91% finding them actionable are [unverified].
    - Relevance: retrieval-first grounding of novelty, with scores calibrated by regression. The evaluation is agreement with scores, not validity of criticisms.

15. **Thakkar, N., Yuksekgonul, M., Silberg, J., Garg, A., Peng, N., Sha, F., Yu, R., Vondrick, C., & Zou, J. (2025/2026). Can LLM feedback enhance review quality? A randomized study of 20K reviews at ICLR 2025.** arXiv:2504.09737; published as "A large-scale randomized study of large language model feedback in peer review", Nature Machine Intelligence (2026). https://arxiv.org/abs/2504.09737 ; https://www.nature.com/articles/s42256-026-01188-x ; code: https://github.com/zou-group/review_feedback_agent
    - Architecture: five Claude Sonnet 3.5 calls run in sequence: two parallel "actors", an aggregator, a critic that removes inaccurate or superficial items, and a formatter.
    - Guardrails: four deterministic or LLM "reliability tests" (no praise of reviewers, address only the reviewer, no restating of the review, correct format). Each item gets up to 2 retries and is dropped if it still fails.
    - Results: 26.6% of reviewers who received feedback updated their reviews. 12,222 suggestions were incorporated. Blinded humans preferred the updated reviews 89% of the time.
    - Relevance: a deployed actor, aggregator and critic design with explicit pass/fail gates. Note that the task (feedback on reviews) is narrower than reviewing a paper.

16. **Baumann, J., Pei, J., Koyejo, S., & Hovy, D. (2026). Stop Automating Peer Review Without Rigorous Evaluation.** arXiv:2605.03202. https://arxiv.org/abs/2605.03202
    - "Hivemind" finding: across 75,800 ICLR 2026 reviews, AI reviews were more similar to each other than human reviews were. Within-paper agreement rose 8.7 to 9.8%, and across-paper similarity rose 4.1 to 39.8% depending on the model.
    - "Paper laundering": zero-shot LLM rewrites raised AI review scores by +0.45 (p<0.0001) without any change in substance.
    - Correlations: AI scores correlated r=0.15 with human scores but r=0.49 with each other. Acceptance AUC was 0.710 for AI against 0.822 for humans.
    - Generic templates recurred across reviews.
    - Recommendations: adversarial robustness testing, validated false-positive rates, and user studies.
    - Relevance to ReviScope's judge evaluation: AI judges and AI reviewers share stylistic preferences, which supports worries about self-preference bias and gaming by polished prose.

17. **van Dijcke, D. coarse: free open-source AI academic paper reviewer.** GitHub repository (MIT). https://github.com/Davidvandijcke/coarse (web: coarse.ink)
    - Architecture:
      - Document conversion (Mistral OCR with optional vision QA), followed by structure analysis, math detection and domain classification.
      - Domain calibration and literature search (Perplexity), optionally with deeper research.
      - Overview agent, then a completeness agent, then section agents in parallel producing 15 to 25 detailed comments.
      - Adversarial proof verification for sections heavy in mathematics.
      - Cross-section synthesis checking that results and discussion agree.
      - Editorial filtering and deduplication.
      - Quote verification by fuzzy matching against the source text.
    - Models: any litellm model. Typical cost is under $2 per review.
    - Evaluation: the repository reports no comparative benchmark.
    - Relevance: ReviScope's direct ancestor. Its quote anchoring and editorial filter are design elements that ReviScope inherited.

18. **Golub, B., Fradkin, A., Pracher, L., & Calvó López, Y. (2026, June 16). A Structured Benchmark for AI Paper Review.** Refine.ink blog. https://www.refine.ink/blog/refine-ai-reviewer-benchmark (product: https://www.refine.ink/)
    - Refine design: commercial and closed. It returns deep critiques of logic, notation and internal consistency in under about 40 minutes. It does not verify citations or parse figures (third-party description). Internal architecture is not disclosed.
    - Benchmark set-up:
      - Data: 150 economics preprints (100 NBER working papers, 50 arXiv theory papers).
      - Competitors: Refine against 9 systems, namely 5 single-shot LLMs and 4 coarse-scaffolded versions of GPT-5.5, Claude, Gemini and DeepSeek.
      - Judging: an LLM pipeline extracts atomic concerns, classifies them, verifies their anchors against the paper, aligns shared issues, harmonises and filters them, then ranks and judges only the residual unique concerns. Judges are flip-averaged with bias filtering.
    - Results: Refine won 90.4% of 1,349 matches (95% CI 88.8 to 91.9). It won 94.8% against single-shot LLMs and 85.0% against scaffolded systems.
    - Evidence on scaffolding vs single calls: coarse scaffolding consistently reduced Refine's margin over the same base model.

      | Base model | Refine win rate vs single-shot | Refine win rate vs coarse-scaffolded |
      |---|---|---|
      | GPT-5.5 | 90.7% | 72.0% |
      | Claude | 96.7% | 80.7% |
      | Gemini | 99.3% | 91.3% |
      | DeepSeek | 98.7% | 96.0% |

      This is indirect but consistent evidence that a specialist, section-wise scaffold beats a single call on unique, grounded concerns.
    - Judge rationales: Refine's wins cited verified, grounded catches (59.9%), precision (46.9%) and false positives in the opposing review (21.4%).
    - Caveats: the benchmark was run by the vendor, the measurement is entirely LLM-based, and it covers economics only.
    - Methodological value for ReviScope: decomposing reviews into atomic concerns, verifying anchors and then judging only the residual differences directly addresses length and verbosity bias in pairwise judging.

19. **The Black Spatula Project (2024 to present).** Open-source community project. https://github.com/The-Black-Spatula-Project/black-spatula-project ; https://the-black-spatula-project.github.io/
    - Design: crowdsourced testing of models and prompts. Contributors submit a model, a prompt and a PDF through GitHub issues, and the analyses run automatically. Test material includes withdrawn or retracted papers (e.g. the WithdrarXiv dataset and Retraction Watch). Volunteer domain experts judge whether flagged errors are real and how serious they are.
    - Reported progress (Nature news, 2025): about 500 papers analysed. Errors are reported privately to authors rather than published.
    - Relevance: it frames the core questions as how many errors, how serious, and which pipeline, with an explicit concern about false positives.

20. **Gibney, E. (2025). AI tools are spotting errors in research papers: inside a growing movement.** Nature (news), March 2025. https://doi.org/10.1038/d41586-025-00648-5 (author and date confirmed via Crossref)
    - Covers the Black Spatula Project and YesNoError, which scanned more than 37,000 papers in two months and is funded by a cryptocurrency.
    - Key failure evidence: Nick Brown found 14 false positives among 40 papers that YesNoError had flagged. One example was claiming that a figure cited in the text was missing when it was present.
    - Relevance: an unfiltered, high-volume error-flagging system produced a false-positive rate of roughly a third in this check. This is a cautionary case for skipping verification.

21. **Zhu, C., Xiong, J., Ma, R., Lu, Z., Liu, Y., & Li, L. (2025). When Your Reviewer is an LLM: Biases, Divergence, and Prompt Injection Risks in Peer Review.** arXiv:2509.09912. https://arxiv.org/abs/2509.09912
    - Setting: 1,441 ICLR 2023 and NeurIPS 2022 papers reviewed by a small GPT-4-family model (the page says "GPT-4-mini").
    - Findings: ratings for weaker papers were inflated. Hidden PDF instructions targeting specific fields of the review successfully manipulated those parts, whereas broad malicious prompts caused only minor shifts.
    - Relevance: manuscripts must be treated as untrusted input. Targeted hidden instructions are the realistic threat.

### Error-detection benchmarks (evidence on what reviewers miss)

22. **Liang, W., Zhang, Y., Cao, H., Wang, B., Ding, D. Y., Yang, X., Vodrahalli, K., He, S., Smith, D. S., Yin, Y., McFarland, D. A., & Zou, J. (2024). Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis.** NEJM AI, 1(8). https://doi.org/10.1056/AIoa2400196 (metadata confirmed via Crossref)
    - Design: a single GPT-4 pipeline that parses the PDF and produces structured feedback in one prompt.
    - Results: overlap between GPT-4 and human comments was 30.85% for Nature journals and 39.23% for ICLR, similar to the overlap between two humans (28.58% and 35.25%). In a user study, 57.4% rated the feedback helpful and 82.4% found it more beneficial than at least some human reviewers.
    - Caveat: other parts of the paper [not re-opened here] report that GPT-4 is more generic and less likely to comment on novelty.
    - Relevance: the origin of the comment-overlap matching metric that ReviScope's human-review comparison resembles.

23. **Son, G., Hong, J., Fan, H., Nam, H., Ko, H., Lim, S., Song, J., Choi, J., Paulo, G., Yu, Y., & Biderman, S. (2025). When AI Co-Scientists Fail: SPOT, a Benchmark for Automated Verification of Scientific Research.** arXiv:2505.11855. https://arxiv.org/abs/2505.11855
    - Benchmark: 83 published papers containing 91 real errors serious enough to lead to errata or retraction, validated with the authors.
    - Results: the best model, o3, reached 21.1% recall and 6.1% precision, and other models were near zero. Confidence was uniformly low. Across 8 runs, models rarely rediscovered the same errors, so run-to-run variance is huge.
    - Relevance: real, consequential errors are far harder than planted ones, and precision is the binding constraint. Single runs (like ReviScope's one run per configuration) are unreliable for comparing configurations.

24. **Xi, S., Rao, V., Payan, J., & Shah, N. B. (2025). FLAWS: A Benchmark for Error Identification and Localization in Scientific Papers.** arXiv:2511.21843. https://arxiv.org/abs/2511.21843
    - Benchmark: 713 claim-invalidating errors inserted into peer-reviewed papers by LLMs. An automated metric scores localisation, i.e. whether the error text appears among the top-k candidate spans.
    - Result: GPT-5 was best, at 39.1% identification with k=10. Also tested were Claude Sonnet 4.5, DeepSeek v3.1, Gemini 2.5 Pro and Grok 4.
    - Relevance: a localisation (quote-anchor) metric is a cheap, matcher-free alternative to LLM matching of free-text criticisms.

25. **Dycke, N., & Gurevych, I. (2025/2026). Automatic Reviewers Fail to Detect Faulty Reasoning in Research Papers: A New Counterfactual Evaluation Framework.** TACL 2026. arXiv:2508.21422. https://arxiv.org/abs/2508.21422
    - Design: counterfactual pairs of papers with and without flaws in research logic.
    - Finding: across a range of automatic review generators, introducing such flaws had "no significant effect" on the reviews they produced.
    - Relevance: a paired (counterfactual) design checks sensitivity, i.e. whether the reviewer's output changes when only the flaw changes. That is cleaner than absolute recall and is feasible for small samples.

26. **Tu, S., Ma, Y., Lin, J., Zhang, Q., Lan, X., Li, J., Xu, N., Li, L., & Zhao, D. (2026). PaperAudit-Bench: Benchmarking Error Detection in Research Papers for Critical Automated Peer Review.** arXiv:2601.19916. https://arxiv.org/abs/2601.19916
    - Content: an error dataset covering both errors visible within one section and errors that need reasoning across sections, plus PaperAudit-Review, which runs structured error detection before writing an evidence-aware review.
    - Results: error detectability varies widely by model and by detection depth. The detect-then-review approach gives "stricter and more discriminative" evaluations than baseline reviewers. Small detectors trained with SFT and RL are viable.
    - Precision numbers were not available on the abstract page.

### Deterministic and semi-deterministic checkers (psychology and social science)

27. **Nuijten, M. B., Hartgerink, C. H. J., van Assen, M. A. L. M., Epskamp, S., & Wicherts, J. M. (2016). The prevalence of statistical reporting errors in psychology (1985–2013).** Behavior Research Methods, 48(4), 1205–1226. https://doi.org/10.3758/s13428-015-0664-2 ; tool: https://mbnuijten.com/statcheck/
    - Design: regex extraction of APA-formatted test statistics, recomputation of p-values, and flagging of inconsistent results and of "decision" (significance-changing) inconsistencies.
    - Results: across more than 250k p-values, about 50% of articles had at least one inconsistency and about 12.5% had a decision inconsistency. Validation against manual coding gave sensitivity of 85.3 to 100%, specificity of 96.0 to 100%, and accuracy of 96.2 to 99.9% depending on settings.
    - Follow-up: Nuijten & Wicherts (2024), Advances in Methods and Practices in Psychological Science, found that using statcheck during peer review was associated with a steep decline in inconsistencies (AMPPS 7(2), https://doi.org/10.1177/25152459241258945; confirmed via Crossref).
    - Relevance: a high-precision deterministic layer whose output can be trusted without LLM verification.

28. **DeBruine, L., Lakens, D., et al. (2024 to 2026). metacheck (formerly papercheck): Check Research Outputs for Best Practices.** R package v0.1.0 (experimental). https://www.scienceverse.org/metacheck/ ; manual: https://www.scienceverse.org/metacheck_book/ ; intro: http://daniellakens.blogspot.com/2025/06/introducing-papercheck.html
    - Design: modular, CRAN-check-style screening covering citation problems, missing DOIs, retracted or replicated references (Retraction Watch, PubPeer, FLoRA), commonly misreported items such as power analyses, and statistical inconsistencies.
    - Explicit policy: LLM use is "restricted to classification of existing text, not evaluation of the quality of practice", and is opt-in.
    - Relevance: ReviScope's first stage. Its design philosophy (deterministic checks first, LLMs only to classify text) is a principled counterpoint to LLM-only review.

29. **Cummins, J., Clarke, B., Hussey, I., & Elson, M. (2026). RegCheck: A tool for structured comparisons between study registrations and papers.** arXiv:2601.13330. https://arxiv.org/abs/2601.13330 ; https://regcheck.app/ ; validation study repository: https://github.com/beth099/RegCheck-Validation-Study
    - Design: the user chooses the dimensions to compare (sample size, hypotheses, variables, models, exclusions, missing data, and so on). The LLM judges each dimension as consistent, deviating, or insufficient information. Every judgement is backed by verbatim text segments extracted deterministically, which the human checks.
    - Validation: quantitative results were not visible on the abstract page [unverified]; a separate validation study repository exists.
    - Relevance: the tool is narrow, one dimension per call, and grounded in quotes, with the human as verifier. This is the model for a "preregistration consistency" specialist.

### Reproducibility and replication agents (social science)

30. **Brodeur, A., Valenta, D., Marcoci, A., Aparicio, J. P., Mikola, D., Barbarioli, B., Alexander, R., Deer, L., Stafford, T., Vilhuber, L., Bensch, G., Fitzgerald, J., et al. (2025). Comparing Human-Only, AI-Assisted, and AI-Led Teams on Assessing Research Reproducibility in Quantitative Social Science.** I4R Discussion Paper No. 195 / IZA DP 17645. https://ideas.repec.org/p/zbw/i4rdps/195.html ; later published as "AI-assisted teams outperform AI-led teams but not human-only teams in assessing research reproducibility in quantitative social science", PNAS 123(22) (2026), https://doi.org/10.1073/pnas.2524747123 (Crossref lists additional authors, including Motoki)
    - Design: a randomised "AI replication games" study with 288 researchers in 103 teams, assigned to human-only, AI-assisted (ChatGPT) or AI-led conditions.
    - Results:
      - Reproduction rates were 94% for human-only teams, 91% for AI-assisted teams and 37% for AI-led teams.
      - Human teams found more major coding errors: 0.7 more per team than AI-assisted teams and 1.1 more than AI-led teams.
      - Time to reproduction averaged 82, 93 and 180 minutes respectively.
      - AI-led teams were worse at proposing robustness checks.
    - Relevance: error detection was the weakest AI capability, even with humans in the loop.

31. **Hu, C., Zhang, L., Lim, Y., Wadhwani, A., Peters, A., & Kang, D. (2025). REPRO-Bench: Can Agentic AI Systems Assess the Reproducibility of Social Science Research?** Findings of ACL 2025. arXiv:2507.18901. https://arxiv.org/abs/2507.18901
    - Benchmark: 112 social science papers with published reproduction reports. The agent receives the PDF, the replication package and the list of major findings, and must score reproducibility on a 1 to 4 scale.
    - Results: the best existing agent reached 21.4% accuracy. The authors' REPRO-Agent improved this by 71% relative (about 36.7% by my arithmetic).

32. **Siegel, Z. S., Kapoor, S., Nadgir, N., Stroebl, B., & Narayanan, A. (2024). CORE-Bench: Fostering the Credibility of Published Research Through a Computational Reproducibility Agent Benchmark.** TMLR (2024, per mlanthology listing). arXiv:2409.11363. https://arxiv.org/abs/2409.11363
    - Benchmark: 270 tasks from 90 papers in computer science, social science and medicine, at three difficulty levels.
    - Results: CORE-Agent with GPT-4o solved 60.00% of easy tasks, 57.78% of medium and 21.48% of hard. Adapting a generalist agent (AutoGPT) to the task-specific CORE-Agent gave large gains.
    - Relevance: task-specific scaffolding of a generalist agent helps.

33. **Alizadeh, M., Mosleh, M., Gilardi, F., Kasirzadeh, A., & Tucker, J. (2026). AI Coding Agents Can Reproduce Social Science Findings.** arXiv:2606.11447. https://arxiv.org/abs/2606.11447
    - Benchmark: SocSci-Repro-Bench, 221 tasks across 4 disciplines, including tasks that cannot be reproduced.
    - Results: Claude Code and Codex reproduced a substantial share of findings, at rates well above earlier agent benchmarks, and Claude Code beat Codex.
    - Failure modes: supplying the original PDF helped modestly but biased the agents on impossible tasks (they "found" the published result). Prompt framing could induce confirmatory specification search.
    - Relevance: showing the paper's claims to a code-executing checker biases it towards confirmation. Run re-analysis checks blind to the reported numbers where possible.

34. **Kubota, S., Yakura, H., Coavoux, S., Yamada, S., & Nakamura, Y. (2026). LLM-Assisted Replication for Quantitative Social Science.** arXiv:2602.18453. https://arxiv.org/abs/2602.18453
    - Design: an iterative loop of interpreting the text, generating code, executing it and analysing discrepancies, demonstrated by reproducing a seminal sociology paper.
    - Proposed uses: pre-submission checks, assistance for peer review, and meta-scientific audits.
    - Evaluation: a single-case demonstration.

### Commercial tools

35. **Reviewer3 (reviewer3.com).** Described in Bradford, S. (2026). Reviewer3: An AI-Based System to Streamline Peer Review. The Scientist. https://www.the-scientist.com/reviewer3-an-ai-based-system-to-streamline-peer-review-74934 ; https://reviewer3.com/
    - Design (vendor description): multiple specialist agents covering design, statistics, analytical framework, data and code availability, and limitations. It can rerun statistics and validate code in a sandbox, cross-checks citations against 5 databases, and includes AI-text detection.
    - Scale: more than 30k manuscripts.
    - Evaluation: none published.
    - Noted failure: it recommends experiments that are scientifically invalid in context (shallow domain grounding).

36. **q.e.d Science (qedscience).** bioRxiv pilot announcement, 4 Nov 2025: https://connect.biorxiv.org/news/2025/11/04/qed_review_tool ; The Scientist feature: https://www.the-scientist.com/q-e-d-an-ai-tool-for-smarter-manuscript-review-73759
    - Design: the manuscript is decomposed into claims and their supporting evidence. A "validity engine" checks whether the evidence supports each claim, and multiple agents cover statistics, consistency across figures, alternative hypotheses, contradictions with the literature and reporting standards. Originality is reported separately from validity, and manuscripts are anonymised before scoring. A report takes about 30 minutes.
    - Integration: offered at bioRxiv submission.
    - Evaluation: none published.
    - Note: the description of the claim–evidence graph comes from third-party summaries, so treat the details as vendor claims.

### Robustness, manipulation and critique profiles

37. **Ye, R., Pang, X., Chai, J., Chen, J., Yin, Z., Xiang, Z., Dong, X., Shao, J., & Chen, S. (2024). Are We There Yet? Revealing the Risks of Utilizing Large Language Models in Scholarly Peer Review.** arXiv:2412.01708. https://arxiv.org/abs/2412.01708
    - Explicit manipulation: hidden injected content inflates ratings. In a simulation, manipulating 5% of reviews pushed about 12% of papers out of the top 30%.
    - Implicit manipulation: when authors disclose minor limitations, LLM reviews echo them, with 4.5x higher consistency with the disclosed limitations than human reviews show.
    - Inherent flaws: incomplete papers receive higher ratings than complete ones, and well-known authors are favoured under single-blind review.
    - Relevance: a reviewer that parrots the paper's own limitations section can look good on coverage without adding value. Track novelty relative to the stated limitations.

38. **Yang, X., Sha, Z., Li, J., Yu, J., Sun, Y., Zhao, M., Fang, J., Guo, X., Wu, Y., Hu, X., Luo, Y., Liu, Q., & Wang, Z. (2026). No Hidden Prompts Needed! You Can Game AI Peer Review with Presentation-Only Revisions.** arXiv:2606.13044. https://arxiv.org/abs/2606.13044
    - Finding: revising only the presentation (abstract, framing, related work, narrative), with methods and results unchanged, achieved a 75.1% attack success rate and +1.21/10 mean score gain across three mainstream AI reviewers.
    - "AI reviewers are easier to impress than to convince": they struggle to tell real fixes from apparent ones.

39. **Xin, Y., Weng, Y., Zhu, M., Ling, Y., Qin, C., Backes, M., Zhang, Y., & Yang, L. (2026). SafeReview: Defending LLM-based Review Systems Against Adversarial Hidden Prompts.** arXiv:2604.26506. https://arxiv.org/abs/2604.26506
    - Design: co-evolutionary adversarial training, in which an attack generator and a preference-trained defender reviewer improve against each other.
    - Result: improved robustness to adaptive injection that generalises across attackers. No headline number was given on the abstract page.

40. **Yang, Y., Thelwall, M., & He, G. (2026). Beyond Human-Likeness: Mapping the Scientific Critique Profiles of LLMs and Human Reviewers.** arXiv:2609.01895. https://arxiv.org/abs/2609.01895
    - Method: ICLR 2025 human reviews compared with LLM reviews written under baseline and "expert-optimised" prompts, coded with Toulmin, SOLO, Hattie and other frameworks.
    - Findings: humans prioritise scientific framing, higher-order weaknesses and improvement-oriented questions. LLMs show more explanatory and integrative argument structure. Expert prompting "mainly amplified LLM-specific tendencies" rather than making the critiques more human-like.
    - Relevance: comparing against human reviews measures a different functional profile, not just quality.

### Direct comparisons of decomposed vs single-call designs, and further deployments

41. **Aggarwal, N., Chithra, A. L., Dubal, A., Kannakarankodi, S., McDougall, I., Mittal, A., Ramadas, V., Scott, N., Selagamsetty, R., Yang, W., & Sankaralingam, K. (2026). Can LLMs Perform Technical Comprehension of Computer Architecture Papers?** arXiv:2607.11859. https://arxiv.org/abs/2607.11859
    - "Gauntlet" design: Claude Opus 4.5 runs five independent expert-persona reviewers, each reading the whole paper. Three are fixed (microarchitecture, workload evaluation, simulation fidelity), and two are chosen per paper from a library of about 90 personas. An adversarial synthesiser then keeps disagreements rather than averaging them.
    - Ablation on 98 papers, three conditions: (A) a one-sentence directive, (B) a single rich-persona agent, (C) the full pipeline. A blind Gemini 3.1 Pro judge, run 3 times with randomised order, preferred the pipeline over the same model as a single rich-persona agent on 96% of papers (p<0.001).
    - Human evaluation on 20 papers against graduate students: Gauntlet won 15, humans 4, with 1 tie. Blinding failed, so judging was open-label.
    - Where humans won: confident errors (one precise but wrong claim destroys trust), and unprioritised weakness lists ("unstructured comprehensiveness").
    - Caveats: the comparison is LLM-judged, with no control for length, and it measures comprehension and critique quality rather than verified error recall.

42. **Georgantas, C. (2026). Intelligence Is Not the Bottleneck: Validating an LLM First-Pass Manuscript Score Against Peer-Review Outcomes.** arXiv:2606.15887. https://arxiv.org/abs/2606.15887
    - Design: the AIPR system scores 5 quality dimensions.
    - Validation: 300 ICLR submissions, AUROC 0.82 (95% CI 0.78 to 0.87).
    - Key result: "a one-paragraph prompt on the same model discriminates almost as well as the full pipeline". However, the engineered pipeline was far more reliable, with scores varying 0.7 points within a paper against 2.8 for the bare prompt.
    - Relevance: a clear case where scaffolding adds reliability rather than accuracy. ReviScope's evaluation should report variance across runs, not only mean recall.

43. **Bianchi, F., Queen, O., Thakkar, N., Sun, E., & Zou, J. (2025). Exploring the use of AI authors and reviewers at Agents4Science.** arXiv:2511.15534. https://arxiv.org/abs/2511.15534
    - Design: three single-call LLM reviewers (GPT-5, Gemini 2.5 Pro, Claude Sonnet 4) on the NeurIPS 2025 rubric. Prompts were iteratively tuned to correlate with ICLR 2022 and 2025 human scores. Papers averaging 4.0 or more (79) went on to human review.
    - Results:
      - The three reviewers' scores had a mean pairwise correlation of 0.48.
      - Mean scores: GPT-5 2.30 (harshest), Claude 3.0, Gemini 4.23.
      - Mean absolute difference from human scores: GPT-5 0.91, Claude 1.09, Gemini 2.73.
      - Gemini showed clear sycophancy ("groundbreaking ... technically flawless").
    - Additional deterministic checks: a web-search reference checker found that only about 44% of submissions had no flagged hallucinated references, and a prompt-injection scanner caught 2 manipulation attempts.
    - Relevance: model family matters for leniency, which bears on the choice of verifier model. Cheap deterministic guards for references and injection worked in deployment.

44. **Goldberg, A., Ullah, I., Khuong, T. G. H., Rachmat, B. K., Xu, Z., Guyon, I., & Shah, N. B. (2024). Usefulness of LLMs as an Author Checklist Assistant for Scientific Papers: NeurIPS'24 Experiment.** arXiv:2411.03417. https://arxiv.org/abs/2411.03417
    - Design: an LLM checks paper compliance with each item of the NeurIPS checklist.
    - Results: 234 papers were submitted voluntarily. Over 70% of authors found it useful and 70% would revise. The main complaints were inaccuracy (20 of 52) and over-strictness (14 of 52). Ratings of usefulness dropped significantly from before to after use. Scores could be gamed with fabricated justifications.
    - Relevance: narrow, checklist-style specialist checks are the best-validated deployed use. Over-strictness (false positives on reporting items) is the main complaint.

45. **Zhang, T. M., & Abernethy, N. F. (2025). Reviewing Scientific Papers for Critical Problems With Reasoning LLMs: Baseline Approaches and Automatic Evaluation.** NeurIPS 2025 AI for Science Workshop. arXiv:2505.23824. https://arxiv.org/abs/2505.23824
    - Design: LLMs act as "manuscript quality checkers" that hunt for critical problems, rather than writing full reviews. Withdrawn arXiv papers serve as ground truth, and reasoning LLMs judge the outputs.
    - Result: o3 was best at identifying critical problems, at modest cost.
    - Relevance: supports narrow "find the fatal problem" prompting and real-error benchmarks.

46. **Wang, G., Taechoyotin, P., Zeng, T., Sides, B., & Acuna, D. (2024). MAMORX: Multi-agent Multi-Modal Scientific Review Generation with External Knowledge.** NeurIPS 2024 Workshop on Foundation Models for Science. https://neurips.cc/virtual/2024/105900
    - Design: specialist agents for novelty (Semantic Scholar retrieval and function calling), figure critique and clarity, with multimodal input. Large context windows reduce the number of agents needed compared with MARG.
    - Arena-style human evaluation: an estimated 93% win rate against human reviews, and it lost only 12% of matches against the next-best multi-agent baseline.

47. **Basch, S., Qu, L., & Gurevych, I. (2026). ReGround: Grounding Reviewer Comments in Multimodal Evidence.** EMNLP 2026. arXiv:2609.11460. https://arxiv.org/abs/2609.11460
    - Dataset: 10,267 reviewer comments linked to 16,274 pieces of evidence in 3,656 submissions, using author rebuttals as the annotation source.
    - Findings: retrieving evidence across the whole paper is hard, identifying the evidence type is the bottleneck, and figures and tables add complementary signal.
    - Relevance: quote anchoring for ReviScope's verifier. Text-only anchoring will miss table- or figure-based evidence.

