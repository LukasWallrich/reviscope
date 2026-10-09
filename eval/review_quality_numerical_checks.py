"""Post-hoc, explicitly conditional checks on the six-case training manuscripts.

Uses reported rounded summaries supplied below, not automatic extraction or raw data.
Requires SciPy; never calls models or changes generation/verification artifacts.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from scipy.stats import t


def source_hash(root, case):
    launch = json.loads((root / "launch.json").read_text())
    entry = next(x for x in launch["inputs"] if x["case"] == case)
    source = Path(entry["input"])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != entry["manuscript_sha256"]:
        raise ValueError("Submitted text differs from the frozen condition")
    return digest


def checks(root):
    satrevik_hash, ziano_hash = source_hash(root, "satrevik"), source_hash(root, "ziano")
    # 52/47 inferred allocation and sign are conditional, not actual settings.
    n1, n2, m1, m2, sd1, sd2 = 52, 47, -2.29, 11.60, 40.8, 58.5
    variance = sd1**2/n1 + sd2**2/n2
    statistic = (m1-m2)/math.sqrt(variance)
    df = variance**2/((sd1**2/n1)**2/(n1-1)+(sd2**2/n2)**2/(n2-1))
    stroop = {"reported_rounded_inputs": {"means": [m1,m2], "SDs": [sd1,sd2]},
              "allocation": [n1,n2], "allocation_status": "inferred, not established for this outcome",
              "conditional_welch_t": statistic, "df": df,
              "p_increase": float(t.sf(statistic,df)), "p_decrease": float(t.cdf(statistic,df)),
              "limit": "Conditional on MS-control and increasing social-word slowing. Ambiguous scoring/contrast and actual allocation prevent a wrong-tail implementation conclusion."}
    n1, n2, m1, m2, sd1, sd2 = 390, 391, .177, .234, .267, .234
    variance = sd1**2/n1 + sd2**2/n2
    statistic = (m1-m2)/math.sqrt(variance)
    df = variance**2/((sd1**2/n1)**2/(n1-1)+(sd2**2/n2)**2/(n2-1))
    pooled = math.sqrt(((n1-1)*sd1**2+(n2-1)*sd2**2)/(n1+n2-2))
    sharing = {"reported_rounded_inputs": {"means": [m1,m2], "SDs": [sd1,sd2]},
               "allocation": [n1,n2], "allocation_status": "illustrative, not established",
               "pooled_d": (m1-m2)/pooled,
               "d_magnitude_bounds_any_positive_weights": [abs(m1-m2)/max(sd1,sd2),abs(m1-m2)/min(sd1,sd2)],
               "illustrative_two_sided_p": float(2*t.sf(abs(statistic),df)),
               "limit": "Mismatch with reported .15 under usual pooled-SD d; does not identify actual estimator, scale, allocation or implementation."}
    ziano=[]
    for name,n,t0,reported in [("HK organ",46,3.70,-1.03),("HK zoo",46,2.80,-1.93),("MTurk organ",314,4.16,-8.19),("MTurk zoo",314,6.31,-6.05)]:
        statistic=t0-.697*math.sqrt(n)
        ziano.append({"scenario":name,"n":n,"reported_zero_null_t":t0,"reported_comparison_t":reported,
                      "fixed_bound":.697,"conditional_comparison_t":statistic,"left_tail_p":float(t.cdf(statistic,n-1))})
    return {"method":"Post-hoc arithmetic by the assessing agent; selected rounded inputs, not raw-data/implementation validation", "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_hashes":{"satrevik":satrevik_hash,"ziano":ziano_hash},"satrevik_sharing":sharing,"satrevik_stroop":stroop,
            "ziano_fixed_bound_reconstruction":ziano,
            "ziano_limit":"A valid TOST component could use the same statistic. Does not prove only one test was run; request both bounds/components and actual output."}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    args=parser.parse_args()
    result=checks(args.root)
    path=args.root/"preflight/reproducible-numerical-checks.json"
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(path)
