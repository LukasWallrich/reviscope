"""Tabulate stored benchmark matches on the frozen audit's demonstrable-error subset."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
audit_path = HERE / "audit-100.json"
audit = json.loads(audit_path.read_text())
selected = {row["id"] for row in audit["rows"]
            if row["verdict"] == "valid_demonstrable_error"}
manifest = json.loads((HERE / "original-union-reproduction.json").read_text())
providers = {}
for item in manifest["match_files"]:
    path = ROOT / item["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    matches = json.loads(path.read_text())
    caught = {f'{item["paper"]:02d}-{index + 1:02d}'
              for index, match in enumerate(matches) if match["matched"]}
    assert caught == set(item["detected_ids"])
    providers.setdefault(item["provider"], set()).update(caught)
assert len(selected) == 42 and len(providers) == 14
rows = [{"configuration": name, "matched": len(ids & selected),
         "denominator": len(selected), "matched_ids": sorted(ids & selected)}
        for name, ids in providers.items()]
rows.sort(key=lambda row: (-row["matched"], row["configuration"]))
union = set().union(*providers.values()) & selected
result = {
    "method": "Post-hoc subset sensitivity analysis; frozen pre-feedback audit classifications and unchanged original judge matches. Includes reporting contradictions, not just errors established to invalidate results. Not independently adjudicated recall.",
    "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
    "selected_ids": sorted(selected), "configurations": rows,
    "pooled_matched": len(union), "denominator": len(selected),
    "pooled_missing_ids": sorted(selected - union),
}
(HERE / "subset-sensitivity.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"best": rows[0]["configuration"], "matched": rows[0]["matched"],
                  "denominator": len(selected), "pooled": len(union)}, indent=2))
