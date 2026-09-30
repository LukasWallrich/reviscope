"""Deterministic metacheck screening stage.

Runs the metacheck R package through the vendored skill scripts (`vendor/metacheck`) on the
manuscript, records per-module status and traffic lights, and turns module tables into
unverified leads for the review modules. Rows a module itself marks as fine, and rows that
repeat another module's output, are filtered out and counted; every other row is passed on
whole. A module that did not complete is passed on as "could not check", never as clean.
"""
from __future__ import annotations

import functools
import hashlib
import inspect
import json
import re
import shutil
import subprocess
from datetime import date
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
                "header", "section_type", "bib_id"}
# Warnings that mean a module's online lookups partly failed (see mc_run.R FETCH_FAIL and soft_warnings).
LOOKUP_FAILURE = re.compile(r"could not connect|could not resolve|download failed|cannot open URL|status was|timed? ?out|"
                            r"HTTP [45][0-9]{2}|failed to perform|could not be checked|No reference could be matched|"
                            r"No internet connection|Ran without failed upstream", re.I)
PANDOC_READER = "markdown-raw_tex-raw_attribute-raw_html-tex_math_dollars-tex_math_single_backslash-latex_macros"
LIGHT_ORDER = {"red": 0, "yellow": 1, None: 2, "info": 3, "green": 4, "na": 5}
LEADS_HEADER = """METACHECK SCREENING LEADS (UNVERIFIED)
Automated candidates from the metacheck R package for your module. They are leads, not evidence:
check each one against the manuscript (and with your tools) before raising it, and cite the
manuscript, not the lead. A module marked "could not check" was not checked; do not treat it as
clean. Rows are JSON; empty fields are omitted. A row with repo_error could not be checked.
Rows the module itself marks as fine, and rows repeated under another module, are not listed;
each module heading gives their number and the rule that removed them."""
ACCURACY_FLAGS = ("doi_mismatch", "year_mismatch", "title_mismatch", "author_mismatch")
CODE_ISSUE_KEYS = ("checked", "parse_error", "code_abs_path", "loaded_files_missing", "percentage_comment", "library_max_between")


def _effect_size_coherent(row: dict[str, Any]) -> bool:
    column = {"t-test": "d_coherence", "F-test": "eta_coherence"}.get(row.get("test"))
    values = row.get(column) if column else None
    return (bool(row.get("es")) and isinstance(values, str)
            and all(value.strip() == "match_under_assumptions" for value in values.split(";")))


def _code_file_clean(row: dict[str, Any]) -> bool:
    if not all(key in row for key in CODE_ISSUE_KEYS) or row.get("error"):
        return False
    between = row["library_max_between"]
    return (row["checked"] is True and row["parse_error"] is not True and row["code_abs_path"] == 0
            and row["loaded_files_missing"] == 0 and isinstance(row["percentage_comment"], (int, float))
            and row["percentage_comment"] > 0 and (between is None or between <= 3))


# Rows that are not candidates, by metacheck's own flags (module source, metacheck 0.1.0). A rule
# drops a row only when its flags positively say "fine"; a missing or unexpected value keeps it.
NOT_CANDIDATE: dict[str, tuple[str, Callable[[dict[str, Any]], bool]]] = {
    "stat_check": ("recomputed p-value consistent with the reported test (error = false)",
                   lambda row: row.get("error") is False),
    "stat_p_exact": ("p-value reported exactly and not as zero (imprecise = false, zero = false)",
                     lambda row: row.get("imprecise") is False and row.get("zero") is False),
    "stat_effect_size": ("reported effect size matches the test statistic (coherence match_under_assumptions)",
                         _effect_size_coherent),
    "ref_accuracy": ("CrossRef match found with no mismatch flag set",
                     lambda row: row.get("no_match") is False and not any(row.get(flag) is True for flag in ACCURACY_FLAGS)),
    "ref_summary": ("merges the ref_accuracy, ref_pubpeer, ref_replication and ref_retraction rows, which are listed under those modules",
                    lambda row: True),
    "code_check": ("code file checked with no issue flag (parse error, absolute path, missing file, no comments, scattered imports)",
                   _code_file_clean),
}
# all_p_values flags nothing (rubric urls_pvalues.md); stat_p_exact holds the same extracted p-values with
# their sentence and precision flags, and stat_p_nonsig lists the non-significant ones.
P_VALUE_DUPLICATE = "p-value extraction inventory; the same p-values are listed with flags under stat_p_exact and stat_p_nonsig"


class MetacheckError(RuntimeError):
    pass


def run_r(script: str, args: list[str]) -> tuple[dict[str, Any], str]:
    """Run one vendored mc_*.R script; return its JSON result and stderr log."""
    result = subprocess.run(["Rscript", str(VENDOR / "scripts" / script), *args],
                            capture_output=True, text=True, timeout=R_TIMEOUT)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        payload = {"status": "error", "message": result.stderr[-1000:].strip() or f"no JSON object in output (exit {result.returncode})"}
    if result.returncode or payload.get("status") != "ok":
        raise MetacheckError(f"{script}: {payload.get('message', 'failed')}")
    return payload, result.stderr


@functools.cache
def package_version() -> str:
    """Installed metacheck version; part of the reuse key for earlier screening output."""
    result = subprocess.run(["Rscript", "-e", 'cat(as.character(utils::packageVersion("metacheck")))'],
                            capture_output=True, text=True, timeout=120)
    if result.returncode or not result.stdout.strip():
        raise MetacheckError(f"metacheck R package not available: {result.stderr[-300:].strip()}")
    return result.stdout.strip()


def text_to_pdf(manuscript: Path, directory: Path) -> tuple[Path, str]:
    """Typeset a text or Markdown manuscript as PDF for GROBID.

    metacheck 0.1.0 routes DOCX through a bibr call that fails, so text goes to PDF. Plain-text
    lines that name a standard section become Markdown headings. The manuscript is untrusted:
    the Markdown reader drops raw TeX, TeX math and macro definitions, a filter replaces images
    by their captions so TeX never opens a linked file, pandoc runs in its sandbox, and tectonic
    runs in untrusted mode."""
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
    source, pdf, no_images = directory / "manuscript.md", directory / "manuscript.pdf", directory / "no-images.lua"
    source.write_text(text, encoding="utf-8")
    no_images.write_text("function Image(image) return image.caption end\n", encoding="utf-8")
    result = subprocess.run(["pandoc", "--sandbox", "-f", PANDOC_READER, "--lua-filter", str(no_images), "-t", "pdf", "--pdf-engine=tectonic",
                             "--pdf-engine-opt=--untrusted", "-V", "mainfont=STIX Two Text", "-V", "geometry:margin=2.5cm",
                             str(source), "-o", str(pdf)],
                            capture_output=True, text=True, timeout=R_TIMEOUT, cwd=directory)
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
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MetacheckError(f"{path.name} does not hold a JSON object")
    return value


def _rows(mc_dir: Path, module: str) -> list[dict[str, Any]]:
    path = mc_dir / "modules" / f"{module}.json"
    table = _read(path).get("table") if path.is_file() else None
    return [row for row in table if isinstance(row, dict)] if isinstance(table, list) else []


def _counts(mc_dir: Path, module: str) -> dict[str, Any]:
    """The module's own summary_table counts and flags for the paper (e.g. references vs linked
    citations). List columns repeat row text and are left to the rows."""
    table = _read(mc_dir / "modules" / f"{module}.json").get("summary_table")
    row = table[0] if isinstance(table, list) and table and isinstance(table[0], dict) else {}
    return {key: value for key, value in row.items()
            if key != "paper_id" and isinstance(value, (int, float, bool, str)) and value != ""}


@functools.cache
def tool_version(tool: str) -> str:
    """First line of `<tool> --version`, or "unavailable"."""
    try:
        result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    return (result.stdout.strip().splitlines() or ["unavailable"])[0]


def reuse_key(manuscript: Path) -> dict[str, str]:
    """Earlier screening output is reused only when all of these match. Text input adds the
    conversion code and the pandoc and tectonic versions."""
    scripts = hashlib.sha256(b"".join(path.read_bytes() for path in sorted((VENDOR / "scripts").glob("*.R")))).hexdigest()
    key = {"sha256": hashlib.sha256(manuscript.read_bytes()).hexdigest(), "suffix": manuscript.suffix.lower(),
           "scripts": scripts, "metacheck": package_version()}
    if key["suffix"] in TEXT_SUFFIXES:
        code = inspect.getsource(text_to_pdf) + PANDOC_READER + TEXT_HEADING.pattern
        key.update(conversion=hashlib.sha256(code.encode()).hexdigest(), pandoc=tool_version("pandoc"), tectonic=tool_version("tectonic"))
    return key


def run_metacheck(manuscript: Path, out: Path, progress: Callable[[str], None] = lambda _: None) -> MetacheckRecord:
    """Screen the manuscript. Every error becomes a failed or partial record; it never raises."""
    suffix = manuscript.suffix.lower()
    if suffix not in METACHECK_SUFFIXES | TEXT_SUFFIXES:
        return MetacheckRecord(status="not_checked", reason=f"unsupported input type ({suffix or 'no extension'})")
    if shutil.which("Rscript") is None:
        return MetacheckRecord(status="failed", reason="Rscript not found on PATH")
    mc_dir = out / "metacheck"
    provenance = mc_dir / "reviscope.json"
    errors: list[str] = []
    try:
        key = reuse_key(manuscript)
        previous = _read(provenance) if provenance.is_file() else {}
        if previous.get("key") != key or not (mc_dir / "paper.rds").is_file():
            if mc_dir.exists():
                shutil.rmtree(mc_dir)  # output for other input or another metacheck version; none of it applies
            (mc_dir / "input").mkdir(parents=True)
            source, text_conversion = manuscript, None
            if suffix in TEXT_SUFFIXES:
                progress("metacheck: typesetting text manuscript as PDF")
                source, text_conversion = text_to_pdf(manuscript, mc_dir / "input")
            progress("metacheck: importing manuscript")
            _, log = run_r("mc_import.R", ["--file", str(source), "--run-dir", str(mc_dir), "--crossref-lookup"])
            provenance.write_text(json.dumps({"key": key, "text_conversion": text_conversion, "lookup_date": date.today().isoformat(),
                                              "converter": _converter(source.suffix.lower(), log)}), encoding="utf-8")
        for modules in ("default", EXTRA_MODULES):
            progress(f"metacheck: running {'default' if modules == 'default' else 'extra'} modules")
            try:
                run_r("mc_run.R", ["--run-dir", str(mc_dir), "--modules", modules])
            except (MetacheckError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{'default' if modules == 'default' else 'extra'} modules: {exc}")
        conversion, summary = _read(provenance), _read(mc_dir / "import_summary.json")
        status_rows = _read(mc_dir / "run_status.json").get("modules")
        if not isinstance(status_rows, list):
            raise MetacheckError("run_status.json has no module list")
        modules = _count_filtered(mc_dir, [_module(mc_dir, row) for row in status_rows
                                           if isinstance(row, dict) and isinstance(row.get("module"), str)])
    except (MetacheckError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return MetacheckRecord(status="failed", reason="; ".join([*errors, str(exc)]), output_dir=str(mc_dir))
    counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
    return MetacheckRecord(status="partial" if errors or any(m.status != "ok" for m in modules) else "completed", reason="; ".join(errors) or None, output_dir=str(mc_dir),
                           text_conversion=conversion.get("text_conversion"), converter=conversion.get("converter"),
                           lookup_date=conversion.get("lookup_date"),
                           parse_warnings=[str(w) for w in summary.get("parse_warnings") or []],
                           counts={key: counts[key] for key in ("sections", "sentences", "refs", "xrefs_bibr") if isinstance(counts.get(key), int)},
                           modules=modules)


def _module(mc_dir: Path, row: dict[str, Any]) -> MetacheckModule:
    """Module status from run_status.json and its output file. Swallowed lookup failures make an
    `ok` module `partial`: its table exists but some rows could not be checked."""
    name = row["module"]
    path = mc_dir / "modules" / f"{name}.json"
    if not path.is_file():
        return MetacheckModule(module=name, status="failed", error="module output file missing")
    try:
        details = _read(path)
        rows = _rows(mc_dir, name)
    except (OSError, ValueError) as exc:
        return MetacheckModule(module=name, status="failed", error=f"module output unreadable: {type(exc).__name__}: {exc}")
    warnings = [str(w) for w in details.get("warnings") or []]
    status = str(row.get("status", "failed"))
    if status == "ok" and (any(LOOKUP_FAILURE.search(w) for w in warnings) or any(r.get("repo_error") for r in rows)):
        status = "partial"
    return MetacheckModule(module=name, status=status, traffic_light=details.get("traffic_light"), n_rows=len(rows),
                           run_at=str(details["run_at"]) if details.get("run_at") else None,
                           error=row.get("error"), summary_text=details.get("summary_text"), warnings=warnings)


def candidate_rows(mc_dir: Path, modules: list[MetacheckModule]) -> dict[str, tuple[list[dict[str, Any]], int, str | None]]:
    """Per checked module: rows passed on as leads, number filtered out, and the rule that filtered them."""
    checked = {m.module for m in modules if m.status in {"ok", "partial"}}
    out: dict[str, tuple[list[dict[str, Any]], int, str | None]] = {}
    for item in modules:
        if item.module not in checked:
            continue
        rows = _rows(mc_dir, item.module)
        if item.module == "all_p_values" and {"stat_p_exact", "stat_p_nonsig"} <= checked:
            listed = {(row.get("item_id"), row.get("text")) for row in _rows(mc_dir, "stat_p_exact")}
            rule, drop = P_VALUE_DUPLICATE, lambda row: (row.get("item_id"), row.get("text")) in listed
        elif item.module in NOT_CANDIDATE:
            rule, drop = NOT_CANDIDATE[item.module]
        else:
            out[item.module] = (rows, 0, None)
            continue
        kept = [row for row in rows if not drop(row)]
        out[item.module] = (kept, len(rows) - len(kept), rule if len(kept) < len(rows) else None)
    return out


def _count_filtered(mc_dir: Path, modules: list[MetacheckModule]) -> list[MetacheckModule]:
    rows = candidate_rows(mc_dir, modules)
    return [m.model_copy(update={"n_filtered": rows[m.module][1], "filter_rule": rows[m.module][2]}) if m.module in rows else m
            for m in modules]


def fingerprint(record: MetacheckRecord) -> str:
    """Hash of the screening record and every module output; part of each review stage's cache key.
    An unreadable output contributes its name and error instead of its content."""
    digest = hashlib.sha256(record.model_dump_json(exclude={"output_dir"}).encode())
    if record.output_dir:
        for path in sorted(Path(record.output_dir).glob("modules/*.json")):
            try:
                digest.update(path.read_bytes())
            except OSError as exc:
                digest.update(f"unreadable {path.name}: {type(exc).__name__}".encode())
    return digest.hexdigest()


def describe(record: MetacheckRecord) -> str:
    if record.status == "skipped":
        return f"metacheck: {record.reason}"
    if record.status in {"failed", "not_checked"}:
        return f"metacheck: {record.status}: {record.reason}"
    done = [m for m in record.modules if m.status == "ok"]
    partial = [m.module for m in record.modules if m.status == "partial"]
    unchecked = [m.module for m in record.modules if m.status not in {"ok", "partial"}]
    text = f"metacheck: {len(done)} of {len(record.modules)} modules completed; converter: {record.converter}"
    text += f"; partly checked: {', '.join(partial)}" if partial else ""
    text += f"; could not check: {', '.join(unchecked)}" if unchecked else ""
    return text + (f"; run errors: {record.reason}" if record.reason else "")


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
        if key in DROP_COLUMNS or key in out or value is None or (isinstance(value, (str, list, dict)) and not value):
            continue
        out[key] = value
    return json.dumps(out, ensure_ascii=False)


def _rubric_excerpt(name: str) -> str:
    """Purpose and known failure modes of a rubric, or its introduction if it has neither section;
    its procedure assumes the skill's helper scripts."""
    text = (VENDOR / "references" / name).read_text(encoding="utf-8")
    sections = re.split(r"(?m)^(?=## )", text)
    parts = [part for part in sections if part.startswith(("## Purpose", "## Known failure modes"))]
    excerpt = "".join(parts) if parts else sections[0]
    return f"RUBRIC {name} (excerpt)\n{excerpt.strip()}"


def leads(record: MetacheckRecord | None, review_modules: list[str]) -> dict[str, str]:
    """Lead text per review module.

    Modules are taken red first, then yellow, failed, info, green; each adds its header, the
    rubric excerpt if it has candidates or failed, then every candidate row."""
    if record is None or record.status not in {"completed", "partial"} or not record.output_dir:
        return {}
    mc_dir = Path(record.output_dir)
    candidates = candidate_rows(mc_dir, record.modules)
    texts: dict[str, list[str]] = {}
    ordered = sorted(record.modules, key=lambda m: LIGHT_ORDER.get(m.traffic_light if m.status in {"ok", "partial"} else None, 2))
    for item in ordered:
        target = route(item.module, review_modules)
        if target is None:
            continue
        parts = texts.setdefault(target, [LEADS_HEADER])
        checked = item.module in candidates
        rows, filtered, rule = candidates.get(item.module, ([], 0, None))
        if checked:
            block = [f"## {item.module}: metacheck light {item.traffic_light or 'none'}; {len(rows)} candidate row(s)"]
            if filtered:
                block[0] += f"; {filtered} further row(s) not listed: {rule}"
            if item.status == "partial":
                block[0] += "; partly could not check: " + "; ".join(item.warnings)
            if item.summary_text:
                block.append(item.summary_text.strip())
            if counts := _counts(mc_dir, item.module):
                block.append("Module counts: " + json.dumps(counts, ensure_ascii=False))
        else:
            block = [f"## {item.module}: could not check ({item.status}: {item.error or 'no reason recorded'})"]
        rubric = RUBRICS.get(item.module)
        if rubric and (rows or not checked) and not any(f"RUBRIC {rubric} (excerpt)" in part for part in parts):
            block.append(_rubric_excerpt(rubric))
        block.extend(_compact(item.module, row) for row in rows)
        parts.append("\n".join(block))
    return {target: "\n\n".join(parts) for target, parts in texts.items()}
