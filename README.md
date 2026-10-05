# ReviScope

> **EARLY WORK IN PROGRESS — NOT VALIDATED FOR REAL-WORLD USE.** ReviScope is experimental research software. Its reviews can miss serious problems, invent or misstate criticisms, and express unjustified confidence. It has not been validated as a substitute for qualified human peer review and should not be used to make editorial, funding, employment, clinical, or other consequential decisions. Do not submit confidential or unpublished manuscripts unless you have checked that your use of the selected model service is authorized and appropriate for that material. Interfaces, profiles, and results may change without notice.

**Uploads.** Unless a local GROBID server is running at `localhost:8070`, the metacheck stage uploads PDF, DOCX and converted text manuscripts to an online metacheck conversion server, and its causal-claims module sends the title and abstract to a hosted classifier. Its reference checks query CrossRef and other scholarly APIs with a contact address: set `REVISCOPE_CONTACT_EMAIL` to your own, which places the requests in CrossRef's polite pool under that address; otherwise metacheck sends its default `metacheck@scienceverse.org`. Use `--no-metacheck` for material that must not leave your machine or your chosen model service.

An independent, modular manuscript-review alpha for quantitative social science, inspired by [coarse](https://github.com/Davidvandijcke/coarse) by David Van Dijcke. Coarse's staged review, source anchoring, verification, and editorial synthesis provided the starting point. This implementation owns its pipeline and authored disciplinary criteria; it does not depend on or monkey-patch coarse. See [full credits and license provenance](THIRD_PARTY_NOTICES.md).

The default `social_psychology` profile covers quantitative social psychology. It extends `quantitative_social_science`, whose reusable modules assess contribution, design, measurement, statistical inference, interpretation, and consistency across the manuscript. Discipline profiles control both review generation and verification. An education profile demonstrates extension; it is not a validated education reviewer.

Discovery is coverage-first: each module audits its whole responsibility, records a coverage check per topic, and returns every distinct, justified issue; one blind-spot pass follows. No stage limits the number of findings. See [discovery and verification](docs/DISCOVERY.md).

The experimental `--strategy holistic` uses one broad review that also extracts the descriptive study map. `--evidence-audit` adds an independent-input read that reconstructs quantities, scoring recipes, categorical facts and inferential targets. Both retain every candidate and use the same verification and editorial requirements. The audit's additional findings and work can be compared with the broad review alone; see the [validation plan](docs/PIPELINE_VALIDATION_PLAN.md).

## Install and run

Requires Python 3.11+, and an authenticated Codex CLI or Claude CLI for model-backed runs. Current Codex CLI flags are checked by live smoke tests; older CLIs may need updating.

```bash
uv sync --extra dev
uv run reviscope profiles
uv run reviscope review paper.pdf \
  --backend codex --model gpt-6-luna --effort high \
  --supplement appendix.pdf --preregistration registration.md \
  --out runs/paper
```

`gpt-6-luna` at high reasoning effort is the default for inexpensive initial testing. This is a testing configuration, not a quality recommendation. `--effort max` is available. `--timeout` is per model call (default 3,600 seconds); long papers and high or max reasoning can take several minutes per stage. Omit supplement/preregistration options when unavailable. PDF, DOCX, Markdown and plain text are supported. Scanned PDFs require prior OCR; the alpha does not silently call a paid OCR service.

Use `--verifier-backend claude --verifier-model claude-opus-5-5` for a different-family verification pass, or select another supported backend/model explicitly. By default, verification uses separate calls to the reviewer model and is labelled `same_model_separate_call`, not independent-model evidence. Model-backed calls use your CLI authentication; bulk validation should be separately budgeted. The application passes source text to the selected model service and saves source text in local run artifacts.

An experimental broad review with a different-family verifier:

```bash
uv run reviscope review paper.pdf --strategy holistic --evidence-audit \
  --backend codex --model gpt-6.1-sol --effort high \
  --verifier-backend claude --verifier-model claude-opus-5-5 \
  --out runs/paper-holistic-audit
```

The existing review calls explicitly trace consequential claims to premises, inferential steps, assumptions and defeating context, and inspect consequential relations to prior work. The optional audit retains structured `reasoning_trace` and `literature_relation` records inside its normal operation artifacts; these are discovery records, not verified findings. Example/material checks require a specific blocked inference, and visual-content questions remain unresolved without inspectable images. See [reasoning assessment implementation](docs/REASONING_ASSESSMENT_IMPLEMENTATION.md) for contracts and validation limits.

Review, verification and editorial calls run with tools: web search and fetching to check cited sources, related literature and novelty claims, and a sandboxed shell to recompute statistics with code. The shell cannot read the home directory (where CLI credentials live), writes only to a temporary directory per call, and has no network access. It therefore sees only software installed outside the home directory: install the Python and R packages that reviewers may use system-wide (on Debian or Ubuntu, for example `python3-scipy`, `python3-statsmodels` and `r-base`). On Linux, Codex runs each shell command by re-executing its own binary inside the sandbox, so tool-enabled Codex calls use the first `codex` on `PATH` installed outside the home directory and refuse to run without one. Findings can cite external evidence (URL or DOI, quotation, and what it shows). A finding is published only with an anchored quotation from the manuscript itself; if it depends on external evidence, at least one item must be confirmed by the verifier with a recorded fetch or search of that URL or DOI. Verification checks the complete claim and explanatory rationale, including factual premises, calculations, citation use and inferential scope; the rationale is untrusted material to check, not evidence. Remedies are assessed separately for necessity and proportionality. The verifier may classify external evidence as optional only by explaining how the manuscript and established knowledge support the complete claim and rationale without it. Unchecked optional items are dropped; refuted items block support. Unusual empirical assertions and claims about a particular source require external verification. Each stage records its tool calls in `review.json`; the report ends with a Tool use summary. Models are instructed not to consult reviews or commentary of the manuscript itself, or other versions of it (published article, preprints, other drafts). If a managed Claude or Codex policy file widens the shell sandbox (excluded or unsandboxed commands, reads in the home directory, network access), tool-enabled calls stop with an error. Before using a run as benchmark evidence, audit it:

```bash
.venv/bin/python eval/audit_tool_use.py runs/paper
```

The audit identifies the benchmark paper by source hash, flags searches, fetches and search results that could expose its human reviews, and reports a run as incomplete when a model stage failed or lacks tool-call records. Ranking, comparison and normalization judges run without tools.

Before the review modules, a deterministic stage screens the manuscript with the [metacheck](https://github.com/scienceverse/metacheck) R package (requires `Rscript` from R 4.5 or later with metacheck 0.1.0, whose import calls `tools::md5sum(bytes = )`; text input also needs `pandoc` and `tectonic`). It runs the default module set plus the modules its rubrics use and writes the output to `metacheck/` in the run directory. Markdown and plain-text manuscripts are typeset as PDF with pandoc first, with standard section names in plain text marked as headings, because metacheck reads only PDF, DOCX, GROBID XML and metacheck JSON. Each review module receives the relevant module results as unverified leads: every candidate row in full, the module's own counts, and the purpose and known failure modes of the matching rubric. Rows that a module itself marks as fine (for example a statcheck result whose recomputed p-value matches, or a reference whose CrossRef record shows no mismatch) and rows that repeat another module's output (`ref_summary`, and `all_p_values` when `stat_p_exact` and `stat_p_nonsig` ran) are not passed on; a row whose flags are missing or unclear is kept. Statistics modules go to statistical inference, causal claims to interpretation, reference checks to contribution, preregistration checks to both consistency and statistical inference, and open-practice, repository, conflict-of-interest and funding checks to design. A module that failed is passed on as "could not check". Screening is partial when any module did not complete or only partly checked; coverage and provenance say so, and the review itself stays complete. A screening failure as a whole, including unreadable screening output, marks the review partial. The lead heading, the coverage section and the provenance record state per module how many rows were filtered and by which rule. The report shows each module's original traffic light in a Metacheck screening section under Coverage and audit. Provenance records the text conversion, the conversion server (local GROBID at `localhost:8070` if running, otherwise the online server), the CrossRef lookup date, and each module's status and run time. Screening output is reused while the manuscript, the vendored R scripts, the metacheck version and commit, the R version and, for text input, the conversion code and pandoc and tectonic versions are unchanged; reuse does not expire with age, so the dates show how current the online lookups are. Skip the stage with `--no-metacheck`; the report then says "metacheck: skipped by flag". The R wrapper scripts and rubrics are vendored from the metacheck agent skill in `src/reviscope/vendor/metacheck/`.

A deterministic installation demonstration needs no model or credentials:

```bash
uv run reviscope review examples/demo_manuscript.md \
  --backend fixture --out runs/offline-demo
```

Fixture output is a demonstration, not an AI review. `examples/demo_manuscript.md` is intentionally short and incomplete. The default model-backed pipeline treats it as insufficient material, emits one Minor intake notice, and skips specialist review modules; it is not evidence of review quality.

## Results and resume

Each run writes `review.json`, `review.md`, `review.html`, timestamped `run.log`, and content-keyed stage artifacts. The default per-call deadline is 3,600 seconds; a max-effort stage on a full paper can take about 20 minutes. JSON retains the sources, candidate findings, verification status, editorial disposition, and coverage history. Repeating a command reuses successful matching stages. Different sources, profiles, model settings or upstream outputs invalidate dependent work. Updating the Codex or Claude CLI does not: cached stages are reused, and each stage records the CLI version that produced it (`backend_version`).

A quotation match establishes provenance; it does not establish the criticism's truth. A quotation shortened with an ellipsis anchors when every segment of at least three words occurs in the named source, in order; the evidence location marks it as elided. Quotations that do not anchor are dropped from a finding's evidence and listed in its verification note. A finding is published, with status `llm_supported`, when the verifier supports it and at least one anchored manuscript quotation exists, from the generating model or from the verifier. Verification processes every candidate in batches of at most ten within each generating module. Each batch has its own cache, tool provenance and failure record; a failed batch does not erase successful batches. Published findings are ordered critical, major, minor, and their number is not limited. Concerns that the verifier could neither establish nor rule out appear in a separate report section, "Concerns the verifier could not confirm", with the verifier's reason; they keep status `unresolved`. Contradicted findings are set aside. Editorial rejection and merging do not erase the original finding or its evidential status.

Exit status is 0 for successful commands, 1 for invalid input, and 2 for a partial review or evaluation. Partial reports explicitly identify failed or unavailable stages. Empty findings do not establish that a paper is sound.

PDF extraction includes embedded CFF font support. Cache identity includes the extracted text as well as the source bytes, so an extraction change invalidates the descriptive study map and dependent review stages.

Candidates distinguish claimed defects, conflicting specifications and reporting clarification requests. Verification evaluates the complete claim at its stated scope. A source-task ledger identifies unfinished required-source checks; supported claims held for an unperformed lookup receive one full re-verification with its own evidence and tool record. The same publication gates apply to that attempt. Reports place machine verification traces in the audit, while keeping the criticism, proportionate remedy and quoted evidence together.

## Tailor a discipline

Copy [the external profile example](examples/education_profile) and change its `profile.json`, generation protocols, verification protocols, and editorial rules. It can inherit from a bundled profile:

```bash
uv run reviscope review paper.md \
  --profile examples/education_profile --out runs/custom-review
```

Inherit from `quantitative_social_science` to reuse the authored methods, verification, severity, and editorial rules. These rules passed engineering and adversarial prompt review but have not established scientific validity. Profiles are ordinary local data files, not runtime monkey patches. Their effective inherited content is resolved before review and recorded in the cache identity. See [architecture](docs/ARCHITECTURE.md) and [profile resources](src/reviscope/profiles).

## Evaluate

The included [corpus manifest](eval/corpus/open_peer_review.v1.json) records two version-matched Meta-Psychology manuscript/review pairs, plus Communications Psychology leads whose original reviewed versions remain unverified. The matched papers are methods-heavy technical cases, not a representative social-psychology benchmark.

The [curated comparison set](eval/corpus/open_peer_review_curated.v1.json) contains six version-matched Meta-Psychology submissions with twelve substantive first-round reports: three experimental social-psychology papers, a publication-bias analysis, and two tutorials. The [comparison guide](docs/OPEN_REVIEW_COMPARISONS.md) describes version evidence, content screening and limitations. Prepare hash-pinned manuscripts and separate, anonymized human reports with `.venv/bin/python eval/prepare_open_reviews.py`. Human reports are held-out judge inputs; generation receives only the submitted manuscript and verified supplements.

```bash
uv run reviscope evaluate check eval/corpus/open_peer_review.v1.json
uv run reviscope evaluate fetch-corpus \
  eval/corpus/open_peer_review.v1.json eval/corpus/cache \
  --output runs/eval/corpus-fetch.json
uv run reviscope evaluate compare --paper-id PAPER_ID \
  --manuscript manuscript.txt --candidate runs/paper/review.json \
  --reference human-review.txt --reference-kind human_review \
  --backend claude --model claude-opus-5-5 \
  --effort high --timeout 1800 --output runs/eval/comparison.json
```

Declare comparator provenance with `--reference-kind`. Partial candidates are refused unless `--allow-partial` is supplied for a diagnostic run; these runs are labelled ineligible for scientific validation. Comparisons strip application metadata, swap presentation order, permit ties, and aggregate by paper. `evaluate verify` independently checks criticisms; `audit-sample` and `audit-summary` support separate random and targeted human audits. `planted-recall` imports the Dawes psychology benchmark's error CSV and scores explicitly adjudicated error matches. Run `uv run reviscope evaluate --help` for commands.

### Normalize and rank review pools

`normalize-review` supports a sensitivity analysis in which every source review is converted to the same assessment schema. Create an inventory, audit it with a different model family, and optionally allow one audit-guided revision:

```bash
uv run reviscope normalize-review create \
  --review human-review.txt --output runs/eval/human.normalized.json \
  --backend codex --model gpt-6-luna --effort high \
  --timeout 900

uv run reviscope normalize-review audit \
  --review human-review.txt --inventory runs/eval/human.normalized.json \
  --output runs/eval/human.audit.json \
  --backend claude --model claude-opus-5-5 --effort high \
  --timeout 900

uv run reviscope normalize-review revise \
  --review human-review.txt --inventory runs/eval/human.normalized.json \
  --audit runs/eval/human.audit.json \
  --output runs/eval/human.normalized-revised.json \
  --backend codex --model gpt-6-luna --effort high \
  --timeout 900

uv run reviscope normalize-review audit \
  --review human-review.txt --inventory runs/eval/human.normalized-revised.json \
  --output runs/eval/human.final-audit.json \
  --backend claude --model claude-opus-5-5 --effort high \
  --timeout 900
```

Normalization, ranking and comparison calls run without tools; they read only the supplied texts. A revision must be audited again, as shown above; successful revision does not itself establish eligibility.

An audit failure returns exit status 2. A normalized comparison is eligible only when every input passes deterministic and model-audit gates; do not rank the surviving subset. Normalization tests sensitivity to representation and does not repair weak comparators or selection bias.

`rank-reviews` evaluates a bounded pool of 2–12 reviews for one manuscript in seeded, blinded orders. Its JSON manifest records `paper_id`, `manuscript`, `condition`, optional `expected_composition`, and review rows with unique `id`, `kind`, `path`, and `generator_model` for AI reviews. Run each judge family separately, then aggregate only compatible complete outputs:

```bash
uv run reviscope rank-reviews \
  --manifest eval/corpus/review-pool.json \
  --output runs/eval/ranks-opus.json \
  --backend claude --model claude-opus-5-5 --effort high \
  --presentations 3 --seed 20260907 --timeout 900

uv run reviscope rank-reviews \
  --manifest eval/corpus/review-pool.json \
  --output runs/eval/ranks-sol.json \
  --backend codex --model gpt-6.1-sol --effort high \
  --presentations 3 --seed 20260907 --timeout 900

uv run reviscope aggregate-review-ranks \
  runs/eval/ranks-opus.json runs/eval/ranks-sol.json \
  --output runs/eval/ranks-combined.json
```

Presentations and judges are repeated measurements of one paper, not additional papers. See [OPEN_REVIEW_SAMPLING_FRAME.md](docs/OPEN_REVIEW_SAMPLING_FRAME.md) for defining a discipline-led target population separately from an archive-accessibility sample.

LLM judging, known-error detection, and sampled human auditing answer different questions.

The project is named **ReviScope**: evidence-grounded manuscript review for authors and peer reviewers, across disciplines. [Naming exploration](docs/naming/SHORTLIST.md) lists the candidate names that were considered. The name records a product decision, not trademark or package-name clearance.

## Development and checks

```bash
uv run pytest -q
uv build
```

MIT licensed. Scientific inputs retain their own licenses; downloaded corpus files are excluded from version control.
