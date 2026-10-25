"""Smoke-test the separate table-cell reader on planted readings with a real backend.

Each case names a PDF and planted table readings with the outcome a careful reader should
reach: `matched` for a reading checked by hand against the printed page, anything else for a
planted error (wrong value, sign, marks, typeface, row or column). The run reports every
outcome and counts planted errors that were confirmed ("accepted"), which must be zero.

    uv run python eval/smoke_table_images.py CASES.json --backend claude --out runs/table-image-smoke/claude

CASES.json: [{"pdf": "...", "readings": [{"expect": "matched", "table": "Table 2", "page": 5,
              "row": [...], "column": [...], "value": "2", "marks": "", "emphasis": null}]}]

--no-images is the negative control: the reader is called with no page images staged or
attached, so no reading may match. Cases with private manuscripts stay outside the repository.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reviscope.backend import ClaudeBackend, CodexBackend
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Finding, Profile, ReviewRun, RunMetadata, TableReading


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("cases", type=Path)
    parser.add_argument("--backend", choices=["claude", "codex"], required=True)
    parser.add_argument("--model")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-images", action="store_true", help="negative control: stage and attach no page images")
    args = parser.parse_args()
    backend = (ClaudeBackend if args.backend == "claude" else CodexBackend)(model=args.model, effort=args.effort)
    pipeline = ReviewPipeline(backend, Profile(id="smoke", title="Smoke", modules=[]), run_metacheck=False, progress=print)
    if args.no_images:
        pipeline._images = lambda run, attach=None: None  # type: ignore[method-assign]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows, accepted = [], 0
    for number, case in enumerate(json.loads(args.cases.read_text(encoding="utf-8")), 1):
        source = ingest(case["pdf"])
        run = ReviewRun(metadata=RunMetadata(run_id="smoke", backend=backend.name, model=backend.model, profile="smoke",
                                             profile_hash="smoke", input_hash="smoke", output_dir=str(out)), sources=[source])
        pipeline._render_pages(run, out)
        findings, expected = [], {}
        for index, item in enumerate(case["readings"]):
            reading = TableReading(source_id=source.id, **{k: v for k, v in item.items() if k != "expect"})
            finding_id = f"case{number}-{index}"
            expected[finding_id] = item["expect"]
            findings.append(Finding(id=finding_id, module="smoke", claim="Planted reading", rationale="Smoke test",
                                    remedy="None", status="llm_supported", table_readings=[reading]))
        checked = pipeline._check_tables(run, out, f"verification-smoke-{number}", {}, findings)
        for finding in checked:
            check = finding.table_checks[0]
            wrong_accepted = expected[finding.id] != "matched" and check.outcome == "matched"
            accepted += wrong_accepted
            rows.append({"id": finding.id, "pdf": Path(case["pdf"]).name[:40], "expect": expected[finding.id],
                         "outcome": check.outcome, "status": finding.status, "reading": check.reading.model_dump(),
                         "blind": check.blind.model_dump() if check.blind else None, "reason": check.reason,
                         "wrong_accepted": wrong_accepted})
        run.stages and print(*(f"{s.name}: {s.status} {s.error or ''}" for s in run.stages), sep="\n")
    (out / f"results-{args.backend}-{backend.model}{'-no-images' if args.no_images else ''}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    for row in rows:
        blind = row["blind"] or {}
        print(f"{row['id']:<10} expect {row['expect']:<11} got {row['outcome']:<17} read {blind.get('value')!r} {blind.get('marks')!r} "
              f"{blind.get('emphasis')!r}  {row['reading']['table']} | {' > '.join(row['reading']['row'])} | {' > '.join(row['reading']['column'])}")
    agree = sum((r["expect"] == "matched") == (r["outcome"] == "matched") for r in rows)
    print(f"{len(rows)} readings; {agree} agree with the expected match/non-match; planted errors accepted: {accepted}")
    return 1 if accepted else 0


if __name__ == "__main__":
    raise SystemExit(main())
