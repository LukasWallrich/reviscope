"""Recheck retained raw judge quotations offline without replacing historical judgments."""
import argparse
import hashlib
import json
from pathlib import Path

from assess_criticisms import archive, checked_labels, method_hash, require_repaired_matcher, save


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rederive(root, case, model):
    launch = json.loads((root / "launch.json").read_text())
    matcher_module = require_repaired_matcher(launch)
    entry = next(x for x in launch["inputs"] if x["case"] == case)
    manuscript = Path(entry["input"])
    if sha(manuscript) != entry["manuscript_sha256"]:
        raise ValueError("Frozen submitted text changed")
    source = root / "criticism-assessments" / model / (case + ".json")
    if not source.exists():
        return None
    data = json.loads(source.read_text())
    for arm, digest in data["source_hashes"].items():
        if sha(root / "reviews" / arm / case / "review.json") != digest:
            raise ValueError("Historical report identity changed")
    rows = []
    for row in data["assessments"]:
        checked = checked_labels(row, manuscript.read_text())
        checked["original_derived_claim_status"] = row["claim_status"]
        checked["original_limits"] = row["limits"]
        if checked["quote_check_passed"]:
            checked["limits"] = row["limits"].replace(" Deterministic check: missing relevant exact manuscript evidence.", "")
        rows.append(checked)
    result = {**data, "assessments": rows, "rederivation": {
        "original_artifact": str(source), "original_sha256": sha(source),
        "method_sha256": method_hash(), "matcher_module": matcher_module, "input_sha256": sha(manuscript),
        "changed_labels": [x["item_id"] for x in rows if x["claim_status"] != x["original_derived_claim_status"]],
        "limits": "Offline quotation bookkeeping only. No new model judgments, no correction of scientific reasoning or duplicated-item influence; frozen generation unchanged."}}
    target = root / "criticism-assessments-rederived" / model / (case + ".json")
    archive(target)
    save(target, result)
    return result["rederivation"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    launch = json.loads((args.root / "launch.json").read_text())
    results = []
    for case in [x["case"] for x in launch["inputs"]]:
        for model in ("claude-opus-5-5", "gpt-6.1-sol"):
            result = rederive(args.root, case, model)
            if result:
                results.append({"case": case, "model": model, **result})
    save(args.root / "quote-label-rederivation.json", {"results": results})
    print([(x["case"], x["model"], len(x["changed_labels"])) for x in results])
