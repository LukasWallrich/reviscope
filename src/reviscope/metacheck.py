"""Deterministic metacheck screening stage.

Runs the metacheck R package through the vendored skill scripts (`vendor/metacheck`) on the
manuscript, records per-module status and traffic lights, and turns module tables into
compact, unverified leads for the review modules. A module that did not complete is passed
on as "could not check", never as clean.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .schemas import MetacheckModule, MetacheckRecord

VENDOR = Path(__file__).parent / "vendor" / "metacheck"
R_TIMEOUT = 1800
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".xml", ".json"}
# SKILL.md step 2: the package's default report set plus the modules the rubrics also use.
EXTRA_MODULES = "all_p_values,all_urls,open_practices,causal_claims,ref_consistency,ref_miscitation,coi_check_oi,funding_check_oi"

STATISTICS = ("stat_check", "stat_p_exact", "stat_p_nonsig", "marginal", "stat_effect_size", "power", "all_p_values")
REFERENCES = ("ref_accuracy", "ref_consistency", "ref_miscitation", "ref_pubpeer", "ref_replication", "ref_retraction", "ref_summary")
TRANSPARENCY = ("open_practices", "prereg_check", "repo_check", "code_check", "coi_check", "coi_check_oi",
                "funding_check", "funding_check_oi", "all_urls")
RUBRICS = {
    "marginal": "marginal.md", "stat_p_nonsig": "nonsig_claims.md", "stat_check": "stat_check_triage.md",
    "stat_p_exact": "stat_p_exact.md", "stat_effect_size": "effect_size.md", "power": "power.md",
    "causal_claims": "causal_claims.md", "all_p_values": "urls_pvalues.md", "all_urls": "urls_pvalues.md",
    "ref_retraction": "citation_context.md", "ref_replication": "citation_context.md",
    "ref_miscitation": "citation_context.md", "ref_pubpeer": "citation_context.md",
    "ref_accuracy": "ref_triage.md", "ref_consistency": "ref_triage.md", "ref_summary": "ref_triage.md",
    "open_practices": "open_practices.md", "repo_check": "repo_code.md", "code_check": "repo_code.md",
    "prereg_check": "prereg_compare.md", "coi_check": "coi_funding.md", "coi_check_oi": "coi_funding.md",
    "funding_check": "coi_funding.md", "funding_check_oi": "coi_funding.md",
}
DROP_COLUMNS = {"paper_id", "candidate_id", "formatted", "paragraph_id", "section_id", "page_number", "div", "p", "s"}
MAX_ROWS, MAX_CELL = 30, 400
LEADS_HEADER = """METACHECK SCREENING LEADS (UNVERIFIED)
Automated candidates from the metacheck R package for your module. They are leads, not evidence:
check each one against the manuscript (and with your tools) before raising it, and cite the
manuscript, not the lead. A module marked "could not check" was not checked; do not treat it as
clean. The rubrics were written for an agent with metacheck helper scripts (mc_context.R,
mc_compute.R); use the supplied manuscript text and your own shell instead."""


class MetacheckError(RuntimeError):
    pass


def run_r(script: str, args: list[str]) -> tuple[dict[str, Any], str]:
    """Run one vendored mc_*.R script; return its JSON result and stderr log."""
    result = subprocess.run(["Rscript", str(VENDOR / "scripts" / script), *args],
                            capture_output=True, text=True, timeout=R_TIMEOUT)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"status": "error", "message": result.stderr[-1000:].strip() or f"no JSON output (exit {result.returncode})"}
    if result.returncode or payload.get("status") != "ok":
        raise MetacheckError(f"{script}: {payload.get('message', 'failed')}")
    return payload, result.stderr


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _converter(suffix: str, log: str) -> str:
    if suffix in {".xml", ".json"}:
        return "none (structured input read offline)"
    if "Using local grobid" in log:
        return "local GROBID (localhost:8070)"
    if "Using local bibr" in log:
        return "local bibr (localhost:8000)"
    checked = re.findall(r"Checking (\S+)", log)
    return f"online server {checked[-1] if checked else '(unknown)'} (manuscript uploaded)"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _own_doi(value: str | None) -> str | None:
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _rows(mc_dir: Path, module: str, own_doi: str | None) -> tuple[list[dict[str, Any]], int]:
    """Module table rows, minus any row about the manuscript's own DOI (count returned)."""
    path = mc_dir / "modules" / f"{module}.json"
    rows = _read(path).get("table") or [] if path.is_file() else []
    kept = [row for row in rows if not (own_doi and _own_doi(row.get("doi")) == own_doi)]
    return kept, len(rows) - len(kept)


def run_metacheck(manuscript: Path, out: Path, progress: Callable[[str], None] = lambda _: None) -> MetacheckRecord:
    suffix = manuscript.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return MetacheckRecord(status="not_checked", reason=f"unsupported input type ({suffix or 'no extension'})")
    if shutil.which("Rscript") is None:
        return MetacheckRecord(status="failed", reason="Rscript not found on PATH")
    mc_dir = out / "metacheck"
    provenance = mc_dir / "reviscope.json"
    sha = _sha256(manuscript)
    try:
        if not (provenance.is_file() and _read(provenance).get("sha256") == sha and (mc_dir / "paper.rds").is_file()):
            if mc_dir.exists():
                shutil.rmtree(mc_dir)  # output of a different input; module results would not apply
            progress("metacheck: importing manuscript")
            _, log = run_r("mc_import.R", ["--file", str(manuscript), "--run-dir", str(mc_dir), "--crossref-lookup"])
            provenance.write_text(json.dumps({"sha256": sha, "converter": _converter(suffix, log)}), encoding="utf-8")
        for modules in ("default", EXTRA_MODULES):
            progress(f"metacheck: running {'default' if modules == 'default' else 'extra'} modules")
            run_r("mc_run.R", ["--run-dir", str(mc_dir), "--modules", modules])
    except (MetacheckError, subprocess.TimeoutExpired, OSError) as exc:
        return MetacheckRecord(status="failed", reason=str(exc), output_dir=str(mc_dir))
    summary = _read(mc_dir / "import_summary.json")
    own_doi = _own_doi(summary.get("doi"))
    modules, excluded = [], []
    for row in _read(mc_dir / "run_status.json")["modules"]:
        name = row["module"]
        details = _read(mc_dir / "modules" / f"{name}.json")
        rows, dropped = _rows(mc_dir, name, own_doi)
        if dropped:
            excluded.append(f"{name}: {dropped} row(s) about the manuscript's own DOI withheld from reviewers")
        modules.append(MetacheckModule(module=name, status=row["status"], traffic_light=details.get("traffic_light"),
                                       n_rows=len(rows), error=row.get("error"), summary_text=details.get("summary_text")))
    return MetacheckRecord(status="completed", output_dir=str(mc_dir), converter=_read(provenance).get("converter"),
                           paper_doi=summary.get("doi"), parse_warnings=list(summary.get("parse_warnings") or []),
                           modules=modules, excluded=excluded)


def describe(record: MetacheckRecord) -> str:
    if record.status != "completed":
        return f"metacheck: {record.reason}" if record.status == "skipped" else f"metacheck: {record.status}: {record.reason}"
    unchecked = [m.module for m in record.modules if m.status != "ok"]
    text = f"metacheck: {len(record.modules) - len(unchecked)} of {len(record.modules)} modules completed; converter: {record.converter}"
    return text + (f"; could not check: {', '.join(unchecked)}" if unchecked else "")


def route(module: str, review_modules: list[str]) -> str | None:
    """Review module that receives a metacheck module's leads."""
    def first(*names: str) -> str | None:
        return next((name for name in names if name in review_modules), None)
    transparency = next((name for name in review_modules if "transparency" in name), None)
    if module in STATISTICS:
        return first("statistical_inference")
    if module == "causal_claims":
        return first("interpretation")
    if module in REFERENCES:
        return first("contribution", "social_psychology_context", "interpretation")
    if module in TRANSPARENCY:
        return transparency or first("design", "interpretation")
    return None


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in row.items():
        if key in DROP_COLUMNS or value is None or value == "" or value == []:
            continue
        if isinstance(value, str) and len(value) > MAX_CELL:
            value = value[:MAX_CELL] + "..."
        out[key] = value
    return out


def leads(record: MetacheckRecord | None, review_modules: list[str]) -> dict[str, str]:
    """Lead text per review module. Empty when metacheck did not complete."""
    if record is None or record.status != "completed" or not record.output_dir:
        return {}
    mc_dir = Path(record.output_dir)
    own_doi = _own_doi(record.paper_doi)
    blocks: dict[str, list[str]] = {}
    rubrics: dict[str, list[str]] = {}
    for item in record.modules:
        target = route(item.module, review_modules)
        if target is None:
            continue
        light = item.traffic_light or "none"
        if item.status != "ok":
            blocks.setdefault(target, []).append(f"## {item.module}: could not check ({item.status}: {item.error or 'no reason recorded'})")
            continue
        rows, _ = _rows(mc_dir, item.module, own_doi)
        lines = [f"## {item.module}: metacheck light {light}; {len(rows)} candidate row(s)"]
        if item.summary_text:
            lines.append(item.summary_text.strip())
        if rows:
            lines.append(json.dumps([_compact(row) for row in rows[:MAX_ROWS]], ensure_ascii=False))
            if len(rows) > MAX_ROWS:
                lines.append(f"({len(rows) - MAX_ROWS} further rows not shown)")
            rubric = RUBRICS.get(item.module)
            if rubric and rubric not in rubrics.setdefault(target, []):
                rubrics[target].append(rubric)
        blocks.setdefault(target, []).append("\n".join(lines))
    result = {}
    for target, parts in blocks.items():
        texts = [f"RUBRIC {name}\n{(VENDOR / 'references' / name).read_text(encoding='utf-8')}" for name in rubrics.get(target, [])]
        result[target] = "\n\n".join([LEADS_HEADER, *parts, *texts])
    return result
