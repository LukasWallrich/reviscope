# coarse-socpsy

An independent, modular manuscript-review alpha, inspired by [coarse](https://github.com/Davidvandijcke/coarse) by David Van Dijcke. Coarse's staged review, source anchoring, verification, and editorial synthesis provided the starting point. This implementation owns its pipeline and authored disciplinary criteria; it does not depend on or monkey-patch coarse. See [full credits and license provenance](THIRD_PARTY_NOTICES.md).

The default `social_psychology_v2` profile covers quantitative social psychology; the original profiles are retained for development comparisons. Reusable modules assess contribution, design, measurement, statistical inference, and interpretation. Discipline profiles control both review generation and verification. An education profile demonstrates extension; it is not a validated education reviewer.

## Install and run

Requires Python 3.11+, and an authenticated Codex CLI or Claude CLI for model-backed runs. Current Codex CLI flags are checked by live smoke tests; older CLIs may need updating.

```bash
uv sync --extra dev
uv run coarse-socpsy profiles
uv run coarse-socpsy review paper.pdf \
  --backend codex --model gpt-5.6-luna --effort max \
  --supplement appendix.pdf --preregistration registration.md \
  --timeout 1800 --out runs/paper
```

Luna at max reasoning effort is the default for inexpensive initial testing. This is a testing configuration, not a quality recommendation. `--timeout` is per model call; long papers and max reasoning can take several minutes per stage. Omit supplement/preregistration options when unavailable. PDF, DOCX, Markdown and plain text are supported. Scanned PDFs require prior OCR; the alpha does not silently call a paid OCR service.

Use `--verifier-backend claude --verifier-model fable` for a different-family verification pass, or select another supported backend/model explicitly. By default, verification is a separate call to the reviewer model and is labelled `same_model_separate_call`, not independent-model evidence. Model-backed calls use your CLI authentication; bulk validation should be separately budgeted. The application passes source text to the selected model service and saves source text in local run artifacts.

A deterministic installation demonstration needs no model or credentials:

```bash
uv run coarse-socpsy review examples/demo_manuscript.md \
  --backend fixture --out runs/offline-demo
```

Fixture output is a demonstration, not an AI review. `examples/demo_manuscript.md` is intentionally short and incomplete. The default model-backed pipeline treats it as insufficient material, emits one Minor intake notice, and skips specialist review modules; it is not evidence of review quality.

## Results and resume

Each run writes `review.json`, `review.md`, `review.html`, timestamped `run.log`, and content-keyed stage artifacts. The default per-call deadline is 1,800 seconds; long max-effort stages can require substantially more than ten minutes. JSON retains the sources, candidate findings, verification status, editorial disposition, and coverage history. Repeating a command reuses successful matching stages. Different sources, profiles, model settings or upstream outputs invalidate dependent work.

A quotation match establishes provenance; it does not establish the criticism's truth. `llm_supported` means the verifier judged the criticism supported. Unresolved findings remain labelled. Numerical checks are conservative leads with recorded applicability and coverage. Editorial rejection and merging do not erase the original finding or its evidential status.

Exit status is 0 for successful commands, 1 for invalid input, and 2 for a partial review or evaluation. Partial reports explicitly identify failed or unavailable stages. Empty findings do not establish that a paper is sound.

## Tailor a discipline

Copy [the external profile example](examples/education_profile) and change its `profile.json`, generation protocols, verification protocols, and editorial rules. It can inherit from a bundled profile:

```bash
uv run coarse-socpsy review paper.md \
  --profile examples/education_profile --out runs/custom-review
```

Inherit from `quantitative_social_science_v2` to reuse the revised authored methods, verification, severity, and editorial rules. These rules passed engineering and adversarial prompt review but have not established scientific validity. Profiles are ordinary local data files, not runtime monkey patches. Their effective inherited content is resolved before review and recorded in the cache identity. See [architecture](docs/ARCHITECTURE.md) and [profile resources](src/coarse_socpsy/profiles).

## Evaluate

The included [corpus manifest](eval/corpus/open_peer_review.v1.json) records two version-matched Meta-Psychology manuscript/review pairs, plus Communications Psychology leads whose original reviewed versions remain unverified. The matched papers are methods-heavy technical cases, not a representative social-psychology benchmark.

```bash
uv run coarse-socpsy evaluate check eval/corpus/open_peer_review.v1.json
uv run coarse-socpsy evaluate fetch-corpus \
  eval/corpus/open_peer_review.v1.json eval/corpus/cache \
  --output runs/eval/corpus-fetch.json
uv run coarse-socpsy evaluate compare --paper-id PAPER_ID \
  --manuscript manuscript.txt --candidate runs/paper/review.json \
  --reference human-review.txt --reference-kind human_review \
  --backend claude --model fable \
  --effort high --timeout 1800 --output runs/eval/comparison.json
```

Declare comparator provenance with `--reference-kind`. Partial candidates are refused unless `--allow-partial` is supplied for a diagnostic run; these runs are labelled ineligible for scientific validation. Comparisons strip application metadata, swap presentation order, permit ties, and aggregate by paper. `evaluate verify` independently checks criticisms; `audit-sample` and `audit-summary` support separate random and targeted human audits. `planted-recall` imports the Dawes psychology benchmark's error CSV and scores explicitly adjudicated error matches. Run `uv run coarse-socpsy evaluate --help` for commands and [VALIDATION.md](docs/VALIDATION.md) for interpretation and corpus limitations.

The [small pilot evaluation](docs/PILOT_EVALUATION.md) records observed real-paper results and limitations. It does not establish general human-equivalent performance or a low false-claim rate. LLM judging, known-error detection, and sampled human auditing answer different questions.

## Development and checks

```bash
uv run pytest -q
uv build
```

Implementation was delegated to GPT-5.6 Sol agents. Key decisions and integration code were independently reviewed using authenticated `claude -p --model fable` requests. [Review prompts, responses and dispositions](docs/design_reviews) are retained. See [acceptance criteria](docs/ACCEPTANCE.md) and [observed test results](docs/TEST_RESULTS.md).

MIT licensed. Scientific inputs retain their own licenses; downloaded corpus files are excluded from version control.
