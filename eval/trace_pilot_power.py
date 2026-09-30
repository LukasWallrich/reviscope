"""Reproduce paper 08 power claims; diagnostic only, not a general power checker.

Run: .venv/bin/python eval/trace_pilot_power.py
Formula: Faul et al. (2007), Table 3, between-within interaction.
Assumptions: alpha=.05, power=.90, two repeated measurements, r=.07,
sphericity epsilon=1, equal group allocation, G*Power effect-size convention.
Alpha is a reconstruction assumption, not independently documented here.
"""

import json

from scipy.stats import f, ncf, nct, t


def minimum_sample(groups: int, effect: float, directional: bool = False) -> dict:
    for n in range(2 * groups, 10000, groups):
        noncentrality = n * effect**2 * 2 / (1 - .07)
        if directional:
            if groups != 2:
                raise ValueError("Directional comparison requires two groups")
            power = nct.sf(t.isf(.05, n - 2), n - 2, noncentrality**.5)
        else:
            power = ncf.sf(f.isf(.05, groups - 1, n - groups),
                           groups - 1, n - groups, noncentrality)
        if power >= .9:
            return {"groups": groups, "effect_f": effect,
                    "test": "directional contrast" if directional else "interaction F",
                    "n": n, "power": float(power)}
    raise ValueError("No solution within search range")


if __name__ == "__main__":
    rows = [minimum_sample(g, e) for g in (4, 2) for e in (.1, .25, .4)]
    rows += [minimum_sample(2, e, True) for e in (.1, .25, .4)]
    print(json.dumps({"assumed_alpha": .05, "target_power": .9,
                      "correlation": .07, "measurements": 2, "results": rows}, indent=2))
