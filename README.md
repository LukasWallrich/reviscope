# ReviScope

> **EARLY WORK IN PROGRESS — NOT VALIDATED FOR REAL-WORLD USE.** ReviScope is experimental research software. Its reviews can miss serious problems, invent or misstate criticisms, and express unjustified confidence. It has not been validated as a substitute for qualified human peer review and should not be used to make editorial, funding, employment, clinical, or other consequential decisions. Do not submit confidential or unpublished manuscripts unless you have checked that your use of the selected model service is authorized and appropriate for that material. Interfaces, profiles, and results may change without notice.

**Uploads.** Unless a local GROBID server is running at `localhost:8070`, the metacheck stage uploads PDF, DOCX and converted text manuscripts to an online metacheck conversion server, and its causal-claims module sends the title and abstract to a hosted classifier. Use `--no-metacheck` for material that must not leave your machine or your chosen model service.

An independent, modular manuscript-review alpha for quantitative social science, inspired by [coarse](https://github.com/Davidvandijcke/coarse) by David Van Dijcke. Coarse's staged review, source anchoring, verification, and editorial synthesis provided the starting point. This implementation owns its pipeline and authored disciplinary criteria; it does not depend on or monkey-patch coarse. See [full credits and license provenance](THIRD_PARTY_NOTICES.md).

The default `social_psychology_v2` profile covers quantitative social psychology; the original profiles are retained for development comparisons. Reusable modules assess contribution, design, measurement, statistical inference, and interpretation. Discipline profiles control both review generation and verification. An education profile demonstrates extension; it is not a validated education reviewer.

The experimental `social_psychology_v3` profile adds coverage-first discovery,
genre-aware interpretation and one blind-spot audit.
Use `--profile social_psychology_v3` to try it; the baseline default remains v2
pending evaluation. See [the v3 contract](docs/DISCOVERY_V3.md).

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

Use `--verifier-backend claude --verifier-model claude-opus-5-5` for a different-family verification pass, or select another supported backend/model explicitly. By default, verification is a separate call to the reviewer model and is labelled `same_model_separate_call`, not independent-model evidence. Model-backed calls use your CLI authentication; bulk validation should be separately budgeted. The application passes source text to the selected model service and saves source text in local run artifacts.

Review, verification and editorial calls run with tools: web search and fetching to check cited sources, related literature and novelty claims, and a sandboxed shell to recompute statistics with code. The shell cannot read the home directory (where CLI credentials live), writes only to a temporary directory per call, and has no network access. Findings can cite external evidence (URL or DOI, quotation, and what it shows). A finding is published only with an anchored quotation from the manuscript itself; if it cites external evidence, at least one item must be confirmed by the verifier with a recorded fetch or search of that URL or DOI. Each stage records its tool calls in `review.json`; the report ends with a Tool use summary. Models are instructed not to consult reviews or commentary of the manuscript itself. Before using a run as benchmark evidence, audit it:

```bash
.venv/bin/python eval/audit_tool_use.py runs/paper
```

The audit identifies the benchmark paper by source hash, flags searches, fetches and search results that could expose its human reviews, and reports a run as incomplete when a model stage failed or lacks tool-call records. Ranking, comparison and normalization judges run without tools.

Before the review modules, a deterministic stage screens the manuscript with the [metacheck](https://github.com/scienceverse/metacheck) R package (requires `Rscript` with metacheck 0.1.0; text input also needs `pandoc` and `tectonic`). It runs the default module set plus the modules its rubrics use and writes the output to `metacheck/` in the run directory. Markdown and plain-text manuscripts are typeset as PDF with pandoc first, with standard section names in plain text marked as headings, because metacheck reads only PDF, DOCX, GROBID XML and metacheck JSON. Each review module receives the relevant module results as unverified leads: compact candidate rows plus the purpose and known failure modes of the matching rubric, capped at 15,000 characters per module. Statistics modules go to statistical inference, causal claims to interpretation, reference checks to contribution, and open-practice, preregistration, repository, conflict-of-interest and funding checks to design. A module that failed is passed on as "could not check"; rows dropped by the cap are listed in the coverage section. The report shows each module's original traffic light in a Metacheck screening section under Coverage and audit. Provenance records the text conversion, the conversion server (local GROBID at `localhost:8070` if running, otherwise the online server) and per-module status. Skip the stage with `--no-metacheck`; the report then says "metacheck: skipped by flag". The R wrapper scripts and rubrics are vendored from the metacheck agent skill in `src/reviscope/vendor/metacheck/`.

A deterministic installation demonstration needs no model or credentials:

```bash
uv run reviscope review examples/demo_manuscript.md \
  --backend fixture --out runs/offline-demo
```

Fixture output is a demonstration, not an AI review. `examples/demo_manuscript.md` is intentionally short and incomplete. The default model-backed pipeline treats it as insufficient material, emits one Minor intake notice, and skips specialist review modules; it is not evidence of review quality.

## Results and resume

Each run writes `review.json`, `review.md`, `review.html`, timestamped `run.log`, and content-keyed stage artifacts. The default per-call deadline is 3,600 seconds; a max-effort stage on a full paper can take about 20 minutes. JSON retains the sources, candidate findings, verification status, editorial disposition, and coverage history. Repeating a command reuses successful matching stages. Different sources, profiles, model settings or upstream outputs invalidate dependent work.

A quotation match establishes provenance; it does not establish the criticism's truth. `llm_supported` means the verifier judged the criticism supported. Unresolved findings remain labelled. Numerical checks are conservative leads with recorded applicability and coverage. Editorial rejection and merging do not erase the original finding or its evidential status.

Exit status is 0 for successful commands, 1 for invalid input, and 2 for a partial review or evaluation. Partial reports explicitly identify failed or unavailable stages. Empty findings do not establish that a paper is sound.

## Tailor a discipline

Copy [the external profile example](examples/education_profile) and change its `profile.json`, generation protocols, verification protocols, and editorial rules. It can inherit from a bundled profile:

```bash
uv run reviscope review paper.md \
  --profile examples/education_profile --out runs/custom-review
```

Inherit from `quantitative_social_science_v2` to reuse the revised authored methods, verification, severity, and editorial rules. These rules passed engineering and adversarial prompt review but have not established scientific validity. Profiles are ordinary local data files, not runtime monkey patches. Their effective inherited content is resolved before review and recorded in the cache identity. See [architecture](docs/ARCHITECTURE.md) and [profile resources](src/reviscope/profiles).

## Evaluate

The included [corpus manifest](eval/corpus/open_peer_review.v1.json) records two version-matched Meta-Psychology manuscript/review pairs, plus Communications Psychology leads whose original reviewed versions remain unverified. The matched papers are methods-heavy technical cases, not a representative social-psychology benchmark.

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
  --max-issues 40 --timeout 900

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
