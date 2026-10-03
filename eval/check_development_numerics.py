"""Reproduce selected numerical criticisms without using an LLM verdict as truth.

The checks use reported summaries, not participant data. Inconsistency establishes
that the reports cannot all be correct; it does not identify the erroneous field.
These selected development checks are neither a complete error key nor a precision
estimate. Run against the frozen, prepared submitted manuscripts.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import scipy
from scipy import stats


def check(corpus):
    sources = {}
    texts = {}
    for name in ("bonetto", "ziano"):
        prepared = json.loads((corpus / name / "prepared.json").read_text())
        path = Path(prepared["manuscript_text"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != prepared["manuscript_text_sha256"]:
            raise ValueError(f"Submitted text hash mismatch for {name}")
        texts[name] = path.read_text()
        sources[name] = {"paper_id": prepared["paper_id"], "manuscript_text_sha256": digest}
    bonetto, ziano = texts["bonetto"], texts["ziano"]
    checks = []

    assert "151 | 149 | 0.05(1.01) | -0.47(1.00) | -0.81(298)" in bonetto
    n1, n2, m1, m2, s1, s2 = 151, 149, .05, -.47, 1.01, 1.00
    pooled_sd = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    checks.append({"id": "bonetto-thermometer", "case": "bonetto", "location": "Table 1, Study 1, feeling thermometer",
                   "reported": {"n": [n1, n2], "mean": [m1, m2], "sd": [s1, s2], "t": -.81, "d": .10},
                   "calculated": {"absolute_t": abs((m1 - m2) / (pooled_sd * math.sqrt(1/n1 + 1/n2))),
                                  "absolute_d": abs((m1 - m2) / pooled_sd)},
                   "conclusion": "The means, SDs and sample sizes contradict the reported absolute t and d. Group order cannot resolve the magnitude discrepancy."})
    assert "0.52(298) | .96" in bonetto
    checks.append({"id": "bonetto-blame-p", "case": "bonetto", "location": "Table 1, Study 1, blame",
                   "reported": {"t": .52, "df": 298, "p": .96},
                   "calculated": {"two_sided_p": 2 * stats.t.sf(.52, 298)},
                   "conclusion": "The reported t and p are incompatible under the specified two-sided t test."})
    demographics = re.findall(r"(?:recruited|among) (\d+).*?\(([\d.]+)% male; Mage = ([\d.]+)", bonetto)
    assert len(demographics) == 6
    ns, male, ages = zip(*[(int(n), float(p), float(a)) for n, p, a in demographics])
    checks.append({"id": "bonetto-pooled-demographics", "case": "bonetto", "location": "Six recruitment descriptions and Results, pooled sample",
                   "reported": {"n": list(ns), "male_percent": list(male), "mean_age": list(ages),
                                "pooled_n": 1132, "pooled_mean_age": 23.83, "pooled_male_percent": 27.27},
                   "calculated": {"total_n": sum(ns), "weighted_mean_age": sum(n*a for n, a in zip(ns, ages))/sum(ns),
                                  "weighted_male_percent": sum(n*p for n, p in zip(ns, male))/sum(ns),
                                  "unweighted_mean_age": sum(ages)/len(ages), "unweighted_male_percent": sum(male)/len(male)},
                   "conclusion": "The reported pooled demographics match unweighted study averages, not participant-weighted summaries. This assumes each recruitment N is the demographic denominator; missing demographic responses need clarification."})

    assert ".166***" in ziano and "*** p < .001" in ziano
    n, r = 314, .166
    # The rounded coefficient's upper endpoint and maximum N give the most
    # favourable possible significance among the specified Pearson tests.
    upper_r = r + .0005
    t_value = r * math.sqrt((n - 2)/(1-r*r))
    best_t = upper_r * math.sqrt((n-2)/(1-upper_r*upper_r))
    checks.append({"id": "ziano-correlation-stars", "case": "ziano", "location": "Table 5, MTurk organ, intent Not a Reason",
                   "reported": {"r": r, "maximum_n": n, "stars_threshold": .001},
                   "calculated": {"t": t_value, "two_sided_p": 2*stats.t.sf(t_value, n-2),
                                  "minimum_two_sided_p_with_rounding": 2*stats.t.sf(best_t, n-2),
                                  "minimum_one_sided_p_with_rounding": stats.t.sf(best_t, n-2)},
                   "conclusion": "Even the maximum N and favourable coefficient rounding do not support p < .001 under a conventional Pearson test. The subgroup N can only weaken this evidence."})
    assert "t(313) = -2.03 = .040" in ziano
    checks.append({"id": "ziano-comparison-p", "case": "ziano", "location": "Table 4, MTurk scenario comparison",
                   "reported": {"t": -2.03, "df": 313, "p": .040},
                   "calculated": {"two_sided_p": 2*stats.t.sf(2.03, 313),
                                  "rounding_p_interval": [2*stats.t.sf(2.035, 313), 2*stats.t.sf(2.025, 313)]},
                   "conclusion": "The displayed t rounding does not yield the displayed three-decimal p value; this is a small reporting discrepancy."})
    table5 = ziano.split("Probability 28.3%", 1)[1].split("Mini meta-analysis effect summary", 1)[0]
    coefficients = []
    for line in table5.splitlines():
        if "Not a Reason" in line:
            for part in line.split("Not a Reason")[1:]:
                match = re.search(r"[\d.]+%\s+[\d.]+%\s+(-?\.\d+)", part)
                assert match, line
                coefficients.append(float(match[1]))
    assert len(coefficients) == 16 and "of which half were negative" in ziano
    checks.append({"id": "ziano-negative-correlations", "case": "ziano", "location": "Reasons paragraph and Table 5, Not a Reason rows",
                   "reported": {"description": "half were negative", "coefficients": coefficients},
                   "calculated": {"negative": sum(r < 0 for r in coefficients), "total": len(coefficients)},
                   "conclusion": "Four of sixteen correlations are negative. Half applies only to the Hong Kong subset, not the complete set described."})
    assert "MTurk zoo .26 .73 t(313) = 6.31 < .001 0.36 0.24 0.47 Signal; consistent" in ziano
    checks.append({"id": "ziano-replication-label", "case": "ziano", "location": "Table 4, MTurk zoo",
                   "reported": {"original_d": .70, "replication_ci": [.24, .47], "label": "Signal; consistent"},
                   "criterion_source": "https://ppw.kuleuven.be/okp/_pdf/LeBel2019ABGTE.pdf",
                   "criterion": "Signal requires the replication CI to exclude zero; consistency requires it to include the original effect point estimate.",
                   "calculated": {"signal": not (.24 <= 0 <= .47), "consistent": .24 <= .70 <= .47},
                   "conclusion": "The reported CI implies signal with an inconsistent, smaller estimate under the manuscript's named LeBel criterion. This classification does not itself establish a failed substantive replication."})
    return {"scope": "Selected post-review development checks; conditional on reported inputs, not raw-data validation",
            "sources": sources, "scipy_version": scipy.__version__, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("eval/corpus/cache/open-review-curation-20261002"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for row in result["checks"]:
        print(row["id"], row["calculated"])


if __name__ == "__main__":
    main()
