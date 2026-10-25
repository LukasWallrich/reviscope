"""Write, per development paper, a review.json view in which every iter3 discovery candidate is
shown, so the criticism judge can cluster plain issues against the full candidate pool (trace).
"""
import json, pathlib
R = pathlib.Path(__file__).resolve().parents[1] / "runs"
for case in ["bonetto", "ziano", "satrevik", "brohmer", "peerj-16147"]:
    run = json.loads((R / "dev-iter3/specialist" / case / "run-1/review.json").read_text())
    by_id = {f["id"]: f for f in run["findings"]}
    shown = []
    for c in run["candidates"]:
        f = dict(by_id.get(c["id"], c))
        f.update(status="llm_supported", editorial_disposition="publish", remedy_status="supported")
        shown.append(f)
    run["findings"] = shown
    out = R / "dev-trace" / case
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates-review.json").write_text(json.dumps(run))
    print(case, len(shown), "candidates")
