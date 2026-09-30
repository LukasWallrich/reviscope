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
METACHECK_SUFFIXES = {".pdf", ".docx", ".doc", ".xml", ".json"}
TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
# SKILL.md step 2: the package's default report set plus the modules the rubrics also use.
EXTRA_MODULES = "all_p_values,all_urls,open_practices,causal_claims,ref_consistency,ref_miscitation,coi_check_oi,funding_check_oi"
# Plain-text section names marked as headings so GROBID can assign section types.
TEXT_HEADING = re.compile(r"^(abstract|introduction|background|methods?|methodology|participants|materials|measures|procedure|"
                          r"design|results|general discussion|discussion|conclusions?|limitations|references|bibliography|"
                          r"author note|acknowledge?ments|(study|experiment) \d+[a-z]?)$", re.I)

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
# Location and bookkeeping columns; the candidate_id already identifies the row.
DROP_COLUMNS = {"item_id", "paper_id", "text_id", "paragraph_id", "section_id", "page_number", "formatted",
                "header", "section_type", "bib_id", "expanded", "contents"}
LIGHT_ORDER = {"red": 0, "yellow": 1, None: 2, "info": 3, "green": 4, "na": 5}
LEADS_LIMIT, MAX_CELL, RUBRIC_FALLBACK = 15_000, 300, 1_500
LEADS_HEADER = """METACHECK SCREENING LEADS (UNVERIFIED)
Automated candidates from the metacheck R package for your module. They are leads, not evidence:
check each one against the manuscript (and with your tools) before raising it, and cite the
manuscript, not the lead. A module marked "could not check" was not checked; do not treat it as
clean. Rows are JSON; fields that are false or empty are omitted."""


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


def text_to_pdf(manuscript: Path, directory: Path) -> tuple[Path, str]:
    """Typeset a text or Markdown manuscript as PDF for GROBID.

    metacheck 0.1.0 routes DOCX through a bibr call that fails, so text goes to PDF. Plain-text
    lines that name a standard section become Markdown headings."""
    for tool in ("pandoc", "tectonic"):
        if shutil.which(tool) is None:
            raise MetacheckError(f"{tool} not found on PATH; needed to convert {manuscript.suffix} input")
    text = manuscript.read_text(encoding="utf-8")
    marked = 0
    if manuscript.suffix.lower() == ".txt":
        lines = []
        for line in text.splitlines():
            if TEXT_HEADING.match(line.strip()):
                lines.append(f"\n# {line.strip()}\n")
                marked += 1
            else:
                lines.append(line)
        text = "\n".join(lines)
    source, pdf = directory / "manuscript.md", directory / "manuscript.pdf"
    source.write_text(text, encoding="utf-8")
    result = subprocess.run(["pandoc", "-f", "markdown", "-t", "pdf", "--pdf-engine=tectonic",
                             "-V", "mainfont=STIX Two Text", "-V", "geometry:margin=2.5cm", str(source), "-o", str(pdf)],
                            capture_output=True, text=True, timeout=R_TIMEOUT)
    if result.returncode or not pdf.is_file():
        raise MetacheckError(f"pandoc could not typeset {manuscript.name}: {result.stderr[-500:].strip()}")
    return pdf, f"pandoc Markdown to PDF (tectonic){f', {marked} section headings marked' if marked else ''}"


def _converter(suffix: str, log: str) -> str:
    if suffix in {".xml", ".json"}:
        return "none (structured input read offline)"
    if "Using local grobid" in log:
        return "local GROBID (localhost:8070)"
    if "Using local bibr" in log:
        return "local bibr (localhost:8000)"
    checked = re.findall(r"Checking (.+)", log)
    return f"online server {checked[-1].strip() if checked else '(unknown)'} (manuscript uploaded)"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(mc_dir: Path, module: str) -> list[dict[str, Any]]:
    path = mc_dir / "modules" / f"{module}.json"
    return (_read(path).get("table") or []) if path.is_file() else []


def run_metacheck(manuscript: Path, out: Path, progress: Callable[[str], None] = lambda _: None) -> MetacheckRecord:
    suffix = manuscript.suffix.lower()
    if suffix not in METACHECK_SUFFIXES | TEXT_SUFFIXES:
        return MetacheckRecord(status="not_checked", reason=f"unsupported input type ({suffix or 'no extension'})")
    if shutil.which("Rscript") is None:
        return MetacheckRecord(status="failed", reason="Rscript not found on PATH")
    mc_dir = out / "metacheck"
    provenance = mc_dir / "reviscope.json"
    sha = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    try:
        if not (provenance.is_file() and _read(provenance).get("sha256") == sha and (mc_dir / "paper.rds").is_file()):
            if mc_dir.exists():
                shutil.rmtree(mc_dir)  # output of a different input; module results would not apply
            (mc_dir / "input").mkdir(parents=True)
            source, text_conversion = manuscript, None
            if suffix in TEXT_SUFFIXES:
                progress("metacheck: typesetting text manuscript as PDF")
                source, text_conversion = text_to_pdf(manuscript, mc_dir / "input")
            progress("metacheck: importing manuscript")
            _, log = run_r("mc_import.R", ["--file", str(source), "--run-dir", str(mc_dir), "--crossref-lookup"])
            provenance.write_text(json.dumps({"sha256": sha, "text_conversion": text_conversion,
                                              "converter": _converter(source.suffix.lower(), log)}), encoding="utf-8")
        for modules in ("default", EXTRA_MODULES):
            progress(f"metacheck: running {'default' if modules == 'default' else 'extra'} modules")
            run_r("mc_run.R", ["--run-dir", str(mc_dir), "--modules", modules])
    except (MetacheckError, subprocess.TimeoutExpired, OSError) as exc:
        return MetacheckRecord(status="failed", reason=str(exc), output_dir=str(mc_dir))
    summary, conversion = _read(mc_dir / "import_summary.json"), _read(provenance)
    counts = summary.get("counts") or {}
    modules = []
    for row in _read(mc_dir / "run_status.json")["modules"]:
        details = _read(mc_dir / "modules" / f"{row['module']}.json")
        modules.append(MetacheckModule(module=row["module"], status=row["status"], traffic_light=details.get("traffic_light"),
                                       n_rows=len(details.get("table") or []), error=row.get("error"),
                                       summary_text=details.get("summary_text")))
    return MetacheckRecord(status="completed", output_dir=str(mc_dir), text_conversion=conversion.get("text_conversion"),
                           converter=conversion.get("converter"), parse_warnings=list(summary.get("parse_warnings") or []),
                           counts={key: counts[key] for key in ("sections", "sentences", "refs", "xrefs_bibr") if key in counts},
                           modules=modules)


def describe(record: MetacheckRecord) -> str:
    if record.status == "skipped":
        return f"metacheck: {record.reason}"
    if record.status != "completed":
        return f"metacheck: {record.status}: {record.reason}"
    unchecked = [m.module for m in record.modules if m.status != "ok"]
    text = f"metacheck: {len(record.modules) - len(unchecked)} of {len(record.modules)} modules completed; converter: {record.converter}"
    return text + (f"; could not check: {', '.join(unchecked)}" if unchecked else "")


def route(module: str, review_modules: list[str]) -> str | None:
    """Review module that receives a metacheck module's leads."""
    def first(*names: str) -> str | None:
        return next((name for name in names if name in review_modules), None)
    if module in STATISTICS:
        return first("statistical_inference")
    if module == "causal_claims":
        return first("interpretation")
    if module in REFERENCES:
        return first("contribution", "social_psychology_context", "interpretation")
    if module in TRANSPARENCY:
        return next((name for name in review_modules if "transparency" in name), None) or first("design", "interpretation")
    return None


def _compact(module: str, row: dict[str, Any]) -> str:
    out: dict[str, Any] = {"candidate_id": row.get("candidate_id"), "module": module}
    for key, value in row.items():
        if key in DROP_COLUMNS or key in out or value in (None, "", [], {}, False):
            continue
        out[key] = value[:MAX_CELL] + "..." if isinstance(value, str) and len(value) > MAX_CELL else value
    return json.dumps(out, ensure_ascii=False)


def _rubric_excerpt(name: str) -> str:
    """Purpose and known failure modes of a rubric; its procedure assumes the skill's helper scripts."""
    text = (VENDOR / "references" / name).read_text(encoding="utf-8")
    parts = [part for part in re.split(r"(?m)^(?=## )", text) if part.startswith(("## Purpose", "## Known failure modes"))]
    excerpt = "".join(parts) if parts else text[:RUBRIC_FALLBACK]
    return f"RUBRIC {name} (excerpt)\n{excerpt.strip()}"


def leads(record: MetacheckRecord | None, review_modules: list[str]) -> tuple[dict[str, str], dict[str, int]]:
    """Lead text per review module and the number of rows each lost to LEADS_LIMIT.

    Modules are taken red first, then yellow, failed, info, green; each adds its header, the
    rubric excerpt if it has candidates or failed, then rows while the budget allows."""
    if record is None or record.status != "completed" or not record.output_dir:
        return {}, {}
    mc_dir = Path(record.output_dir)
    texts: dict[str, list[str]] = {}
    dropped: dict[str, int] = {}
    ordered = sorted(record.modules, key=lambda m: LIGHT_ORDER.get(m.traffic_light if m.status == "ok" else None, 2))
    for item in ordered:
        target = route(item.module, review_modules)
        if target is None:
            continue
        parts = texts.setdefault(target, [LEADS_HEADER])
        used = sum(len(part) + 2 for part in parts)
        rows = _rows(mc_dir, item.module) if item.status == "ok" else []
        if item.status == "ok":
            block = [f"## {item.module}: metacheck light {item.traffic_light or 'none'}; {len(rows)} candidate row(s)"]
            if item.summary_text:
                block.append(item.summary_text.strip()[:MAX_CELL])
        else:
            block = [f"## {item.module}: could not check ({item.status}: {item.error or 'no reason recorded'})"]
        rubric = RUBRICS.get(item.module)
        if rubric and (rows or item.status != "ok") and not any(part.startswith(f"RUBRIC {rubric}") for part in parts):
            block.append(_rubric_excerpt(rubric))
        text = "\n".join(block)
        if used + len(text) > LEADS_LIMIT:
            parts.append(block[0] + f" (details and rows not shown: leads are capped at {LEADS_LIMIT:,} characters)")
            dropped[target] = dropped.get(target, 0) + len(rows)
            continue
        shown = 0
        for row in rows:
            line = _compact(item.module, row)
            if used + len(text) + len(line) + 1 > LEADS_LIMIT - 200:  # room for the cap note
                break
            text += "\n" + line
            shown += 1
        if shown < len(rows):
            text += f"\n({len(rows) - shown} further {item.module} row(s) not shown: leads are capped at {LEADS_LIMIT:,} characters)"
            dropped[target] = dropped.get(target, 0) + len(rows) - shown
        parts.append(text)
    return {target: "\n\n".join(parts) for target, parts in texts.items()}, dropped
