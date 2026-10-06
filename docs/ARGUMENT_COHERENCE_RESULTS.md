# Argument-coherence module: first specialist comparison

Run: `runs/argument-coherence-20261006` (training/development data; model judgments, not
expert correctness).

## Design

The default specialist strategy ran with and without the `argument_coherence` module
(commit 33df25a) against a frozen snapshot of 0263cca. Both arms keep the shared reasoning
guidance. Cases were Sætrevik, Ziano and Heyman; Bonetto was excluded because it informed the
guidance text. Each arm ran twice per case with fresh caches. Sol/high generated and
Opus/high verified. All 12 runs completed without partial output. The module added 1–8
minutes to runs of 53–146 minutes.

Points were scored by `eval/judge_points.py`. Each published finding is one point. The
earlier plain Sol review and two human reviews per paper served as references, with the human
reviews parsed into points by Opus. Opus and Sol labelled every point blind. Each disputed
point was re-judged with the other judge's anonymised labels and a classified reason.

## Results

Mean points that both judges finally rated valid and major or critical, per report:

| Case | Baseline (2 runs) | Coherence (2 runs) | Plain (1) | Human (2) |
|---|--:|--:|--:|--:|
| Sætrevik | 4.5 | 5.0 | 6 | 0 |
| Ziano | 4.5 | 5.0 | 8 | 0 |
| Heyman | 0 | 0 | 0 | 0 |

The coherence arm is 0.5 higher on two cases. This is the same size as the difference
between repeat runs, so there is no detectable effect. None of the agreed points came
from the new module itself. Of its 38 candidates, 9 were published under its own name and
17 merged into other modules' findings. On Sætrevik, 11 were held back as unresolved.

## Judge agreement

Over 425 points:

| | Initial | After seeing the other judge |
|---|--:|--:|
| Same validity verdict | 79% (κ 0.33) | 81% (κ 0.41) |
| Same material/not material verdict | 48% (κ 0.13) | 73% (κ 0.39) |

260 points were disputed. Both judges gave importance weighting as the reason about 64% of
the time and evidence standard about 30%. Misreading the manuscript accounted for 3%. Sol
changed 95 labels and Opus 48.

The importance scale is not shared between the judges. Opus rated about 10–20% of AI points
major and never used critical. Sol rated 70–98% of AI points major. Opus rated no Heyman point
major, so "both judges" yields zero there for every report. Human points were rated mostly
minor or negligible by both judges. The parsed human points carry no quoted evidence or
rationale, which may lower their perceived importance.

## Implications

- The module does not yet earn its place on this evidence. A larger effect would need more
  cases, or a scorer that can see whether merged findings were improved by the module.
- An absolute importance scale does not calibrate across judge families. Ranking points
  within a paper, or naming its top few issues, would remove each judge's own threshold.
  Validity agreement is already reasonable.
- Human-versus-AI comparisons need format matching, for example by giving human points
  located manuscript quotes, before they can be interpreted.
