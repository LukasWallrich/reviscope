from __future__ import annotations

import html
import os
import re
from pathlib import Path

from .metacheck import describe
from .schemas import SUPPORTED_STATUSES, Evidence, Finding, ReviewRun, TableReading
from .verification import held_for_tables

UNCONFIRMED_HEADING = "## Concerns the verifier could not confirm"


def unconfirmed_concerns(run: ReviewRun) -> list[Finding]:
    """Findings the verifier judged unresolved on the evidence, or supported while the table cells
    they rest on were not confirmed against the page images, with an anchored supplied-source quotation.

    Findings left unresolved by quote anchoring or external-source checks are not included."""
    source_ids = {source.id for source in run.sources}
    return [f for f in run.findings if f.status == "unresolved" and f.editorial_disposition != "merged"
            and (f.verifier_status == "unresolved" or f.verifier_status == "supported" and held_for_tables(f))
            and any(ev.source_id in source_ids and ev.location for ev in f.evidence)]


def published_findings(run: ReviewRun) -> list[Finding]:
    """Findings shown in the report's Findings section."""
    return sorted([f for f in run.findings if f.editorial_disposition == "publish" and f.status in SUPPORTED_STATUSES], key=finding_order)


def finding_order(finding: Finding) -> tuple[int, bool, int]:
    return ({"critical": 0, "major": 1, "minor": 2}[finding.severity.value],
            finding.priority is None, finding.priority or 0)


def _quotation_lines(evidence: list[Evidence]) -> list[str]:
    lines = []
    for ev in evidence:
        where = ev.location or (f"page {ev.page}" if ev.page else "location unavailable")
        lines.append(f"> “{ev.quote}” — `{ev.source_id}`, {where}")
    return lines


def _cell(reading: TableReading) -> str:
    marks = f", marks `{reading.marks}`" if reading.marks else ""
    emphasis = f", {reading.emphasis} type" if reading.emphasis not in (None, "none") else ""
    unit = f" ({reading.unit})" if reading.unit else ""
    return (f"{reading.table}, row “{' › '.join(reading.row)}”, column “{' › '.join(reading.column)}”: "
            f"**{reading.value}**{unit}{marks}{emphasis}")


def _page_link(run: ReviewRun, source_id: str, page: int) -> str:
    """Link to the whole-page image, relative to the report."""
    for rendered in run.page_images:
        for image in rendered.images:
            if rendered.source_id == source_id and image.page == page and image.view == "page":
                target = os.path.relpath(Path(rendered.directory) / image.file, run.metadata.output_dir)
                return f"[page {page} image]({Path(target).as_posix()})"
    return f"page {page} (no image)"


def _table_lines(run: ReviewRun, finding: Finding) -> list[str]:
    lines = []
    for check in finding.table_checks:
        r = check.reading
        lines.append(f"> Read from the page image, not a text quotation ({check.origin}): {_cell(r)} — `{r.source_id}`, "
                     f"{_page_link(run, r.source_id, r.page)}; separate reading: **{check.outcome.replace('_', ' ')}**. {check.reason}")
    if not finding.table_checks:
        for r in finding.table_readings:
            lines.append(f"> Claimed reading from the page image, not checked: {_cell(r)} — `{r.source_id}`, {_page_link(run, r.source_id, r.page)}")
    return lines


def _evidence_lines(finding: Finding, run: ReviewRun | None = None) -> list[str]:
    lines = _quotation_lines(finding.evidence)
    if run is not None:
        lines += _table_lines(run, finding)
    for ext in finding.external_evidence:
        lines.append(f"> External source ({ext.check}): “{ext.quote}” — {ext.locator}; shows: {ext.shows}")
    return lines


KIND_LABEL = {"defect": "Claimed defect", "specification_conflict": "Conflicting specifications",
              "clarification_request": "Reporting clarification"}
AUDIT_FILE = "audit.md"


def remedy_shown(finding: Finding, display: str = "published") -> bool:
    return display == "published" and finding.remedy_status not in {"overreaching", "unresolved"}


def shown(finding: Finding) -> tuple[str, str, str]:
    """Claim, rationale and remedy as the report shows them: the reader pass's wording where accepted."""
    edit = finding.reader
    return ((edit and edit.claim) or finding.claim, (edit and edit.rationale) or finding.rationale,
            (edit and edit.remedy) or finding.remedy)


def report_items(run: ReviewRun) -> list[tuple[str, Finding, str]]:
    """Every item a reader of the report sees, with its label and whether it is a finding or an unconfirmed concern."""
    return ([(f"finding {n}", f, "published") for n, f in enumerate(published_findings(run), 1)]
            + [(f"unconfirmed concern {n}", f, "unresolved") for n, f in enumerate(unconfirmed_concerns(run), 1)])


def _title(run: ReviewRun) -> str:
    state = "PARTIAL REVIEW" if run.partial else "COMPLETE REVIEW"
    return "DEMONSTRATION — NOT AN AI REVIEW" if run.metadata.backend == "fixture" else f"Peer review ({state})"


def _provenance(run: ReviewRun) -> str:
    m = run.metadata
    verifier = f"`{m.verifier_backend}` / `{m.verifier_model or 'default'}`" if m.verifier_backend else "not run"
    return (f"Generated by ReviScope {m.engine_version}, an experimental AI review tool that has not been validated: "
            f"reviewer `{m.backend}` / `{m.model or 'default'}`, verifier {verifier}. "
            f"How each item was checked is recorded in `{AUDIT_FILE}`.")


def _overview_label(run: ReviewRun) -> str:
    editorial_complete = any(stage.name == "editorial" and stage.status in {"completed", "cached"} for stage in run.stages)
    return "Study overview" if editorial_complete else "Preliminary manuscript account (not reconciled)"


def _wording_note(edit) -> str:
    where = (edit.wording_location or "").strip().rstrip(".")
    brackets = " Square brackets mark details for the authors to supply." if "[" in (edit.wording or "") else ""
    return f"{where}.{brackets}"


def _withheld(finding: Finding) -> str:
    return f"**Proposed response withheld:** {finding.remedy_verification or 'The remedy requires reviewer judgment.'}"


def to_markdown(run: ReviewRun) -> str:
    """The review as its recipients read it. Run details and verification records are in audit.md."""
    kept, unconfirmed = published_findings(run), unconfirmed_concerns(run)
    lines = [f"# {_title(run)}", "", _provenance(run), ""]
    if run.partial:
        lines.extend(["**Partial review.** Some stages did not complete; the audit record lists them.", ""])
    lines.extend([*_summary(kept, unconfirmed), "", f"## {_overview_label(run)}", "",
                  run.study_map.design_summary or "No study overview was available.", "", "## Claimed contribution", "",
                  run.study_map.contribution_summary or "No contribution summary was available.", "", "## Strengths", ""])
    lines.extend(f"- {strength}" for strength in run.study_map.strengths)
    if not run.study_map.strengths:
        lines.append("No specific strengths summary was available.")
    lines.extend(["", "## Findings", ""])
    if not kept:
        lines.append("No supported substantive findings were produced.")
    for number, finding in enumerate(kept, 1):
        claim, rationale, remedy = shown(finding)
        lines.extend([f"### {number}. {finding.severity.value.title()}: {claim}", "", f"**{KIND_LABEL[finding.kind]}.**", "",
                      "**In the manuscript:**", "", *_evidence_lines(finding, run), "", f"**The problem.** {rationale}", ""])
        if remedy_shown(finding):
            label = f" ({NECESSITY[finding.remedy_necessity]})" if finding.remedy_necessity else ""
            lines.extend([f"**Suggested response{label}:** {remedy}", ""])
        else:
            lines.extend([_withheld(finding), ""])
        if finding.reader and finding.reader.wording:
            lines.extend([f"**Possible wording.** {_wording_note(finding.reader)}", "",
                          *(f"    {line}" for line in finding.reader.wording.splitlines()), ""])
        if finding.merged_points:
            lines.extend(["**Also raised as:**", ""])
            for point in finding.merged_points:
                lines.extend([f"- {point.claim}", "", *_quotation_lines(point.evidence), ""])
    if unconfirmed:
        lines.extend([UNCONFIRMED_HEADING, "", UNCONFIRMED_INTRO, ""])
        for finding in unconfirmed:
            claim, rationale, _ = shown(finding)
            lines.extend([f"### {finding.severity.value.title()}: {claim}", "", _unconfirmed_reason(finding), "",
                          "**In the manuscript:**", "", *_evidence_lines(finding, run), "", f"**The concern.** {rationale}", ""])
            if number := _see_also(finding, kept):
                lines.extend([f"**See also finding {number}**, which raises a related point.", ""])
            if finding.merged_points:
                lines.extend(["**Also raised as:**", ""])
                for point in finding.merged_points:
                    lines.extend([f"- {point.claim}", "", *_quotation_lines(point.evidence), ""])
    return "\n".join(lines) + "\n"


UNCONFIRMED_INTRO = ("The verifier could neither establish nor rule out these concerns from the supplied material, "
                     "or the table cells they rest on were not confirmed against the page images. "
                     "They are not established findings. Each lists the reason.")


def _see_also(finding: Finding, kept: list[Finding]) -> int | None:
    """Number of the published finding an unconfirmed concern refers to, if the reader pass linked them."""
    target = finding.reader.see_also if finding.reader else None
    return next((n for n, f in enumerate(kept, 1) if f.id == target), None)


def _unconfirmed_reason(finding: Finding) -> str:
    held = held_for_tables(finding) if finding.verifier_status == "supported" else None
    return (f"**Held because:** {held} The verifier otherwise supported it." if held else
            f"**Verifier's reason:** {finding.verifier_rationale or 'No reason recorded.'}")


def audit_markdown(run: ReviewRun) -> str:
    """Run details, the reader pass, coverage, stages, tool use and set-aside findings."""
    m = run.metadata
    lines = [f"# Audit record: {_title(run)}", "", "This record accompanies `review.md`. The full machine-readable record is `review.json`.", "",
             "## Run details", "", f"Run ID: `{m.run_id}`  ", f"Created: {m.created_at:%Y-%m-%d %H:%M} UTC  ", f"Profile: `{m.profile}`  ",
             f"Backend: `{m.backend}` / `{m.model or 'default'}` / effort `{m.effort or 'default'}`  ",
             f"Verifier: `{m.verifier_backend}` / `{m.verifier_model or 'default'}` / effort `{m.verifier_effort or 'default'}`  ",
             f"Verification relationship: `{m.verification_relationship}`", ""]
    lines.extend(_reader_audit(run))
    lines.extend(["## Coverage and audit", ""])
    lines.extend(_metacheck(run))
    lines.extend(_page_images(run))
    lines.extend(f"- {item}" for item in run.coverage)
    lines.append("")
    for stage in run.stages:
        detail = f": {stage.error}" if stage.error else ""
        lines.append(f"- `{stage.name}` — {stage.status}{detail}")
    lines.extend(_tool_use(run))
    if run.source_tasks:
        lines.extend(["", "### External-source tasks", ""])
        for task in run.source_tasks:
            lookup = "recorded lookup" if task.lookup_recorded else "no recorded lookup"
            lines.append(f"- `{task.finding_id}` / `{task.stage}`: {task.locator} — {task.dependency}, {lookup}, {task.check}; claim at this attempt: {task.claim_status}")
    kept = published_findings(run)
    if kept:
        lines.extend(["", "### Verification details", ""])
        for number, finding in enumerate(kept, 1):
            support = ("Claim and rationale supported in a separate model check against anchored supplied-source evidence."
                       if finding.status == "llm_supported" else f"Evidence status: {finding.status}.")
            lines.append(f"- Finding {number}, `{finding.id}` (`{finding.module}`): {support} {finding.verification or 'No verification note.'}")
            if not remedy_shown(finding):
                lines.append(f"  Remedy status `{finding.remedy_status}`; withheld remedy: {finding.remedy}")
            if finding.editorial_reason:
                lines.append(f"  Editorial: {finding.editorial_reason}")
            for point in finding.merged_points:
                lines.append(f"  Merged from `{point.finding_id}` (`{point.module}`).")
    unconfirmed = unconfirmed_concerns(run)
    set_aside = [f for f in run.findings if f not in kept and f not in unconfirmed]
    if set_aside:
        lines.extend(["", "### Set-aside findings", ""])
        for finding in set_aside:
            lines.append(f"- `{finding.id}` — epistemic `{finding.status}`, editorial `{finding.editorial_disposition}`: {finding.editorial_reason or finding.verification or 'No reason recorded.'}")
    return "\n".join(lines) + "\n"


def _reader_audit(run: ReviewRun) -> list[str]:
    stage = next((s for s in run.stages if s.name == "reader"), None)
    if stage is None:
        return []
    lines = ["## Reader pass", "", f"Status: {stage.status}{f' ({stage.error})' if stage.error else ''}. A separate call read the assembled "
             "review with the manuscript and revised each item's wording. Revised text is shown only where every number "
             "in it occurs in the item's own text, verification notes or quotations; otherwise the original is shown. "
             "Original wording is listed here wherever it changed.", ""]
    for label, finding, _ in report_items(run):
        edit = finding.reader
        if edit is None:
            lines.append(f"- {label.capitalize()} (`{finding.id}`): no revision returned.")
            continue
        lines.append(f"- {label.capitalize()} (`{finding.id}`): {edit.changes or 'no change described'}")
        for field in ("claim", "rationale", "remedy"):
            if getattr(edit, field) and getattr(edit, field) != getattr(finding, field):
                lines.append(f"  Original {field}: {getattr(finding, field)}")
        if edit.doubt:
            lines.append(f"  **Reader's doubt (not acted on):** {edit.doubt}")
        lines.extend(f"  Revision not used: {reason}" for reason in edit.rejected)
    if run.pre_reader_study_map is not None and run.pre_reader_study_map != run.study_map:
        before = run.pre_reader_study_map
        lines.extend(["", f"Original overview: {before.design_summary}", "", f"Original contribution: {before.contribution_summary}", ""])
        lines.extend(f"- Original strength: {item}" for item in before.strengths)
    if run.reader_merges:
        claims = {f.id: f.claim for f in run.findings}
        labels = {f.id: label for label, f, _ in report_items(run)}
        lines.extend(["", "Merges proposed by the reader:", ""])
        for m in run.reader_merges:
            name = lambda i: f"{labels[i]} (`{i}`)" if i in labels else f"`{i}`" + (f" (“{claims[i]}”)" if i in claims else "")
            detail = "; ".join(x for x in (m.note,) if x)
            lines.append(f"- {name(m.source)} into {name(m.target)} — {m.outcome}{f' ({detail})' if detail else ''}. Reason: {m.reason or 'none given'}")
    if run.reader_notes:
        lines.extend(["", "Reader's notes on the review as a whole:", ""])
        lines.extend(f"- {note}" for note in run.reader_notes)
    return lines + [""]


NECESSITY = {"essential": "essential to support the claims", "strengthening": "would strengthen the paper",
             "extending": "optional extension beyond the current scope"}


def _summary(kept: list[Finding], unconfirmed: list[Finding]) -> list[str]:
    """Main concerns first, so a reader sees what matters before the full list."""
    counts = ", ".join(f"{n} {level}" for level in ("critical", "major", "minor")
                       if (n := sum(f.severity.value == level for f in kept)))
    lines = ["## Summary of main concerns", "",
             f"{len(kept)} supported finding(s){f' ({counts})' if counts else ''}; "
             f"{len(unconfirmed)} concern(s) the verifier could not confirm, listed separately.", ""]
    main = [(n, f) for n, f in enumerate(kept, 1) if f.severity.value in {"critical", "major"}]
    if not main:
        lines.append("No supported finding is rated major or critical.")
    for number, finding in main:
        essential = " Remedy essential to support the claims." if finding.remedy_necessity == "essential" else ""
        lines.append(f"- **{number}. {finding.severity.value.title()}:** {shown(finding)[0]}{essential}")
    return lines


def _metacheck(run: ReviewRun) -> list[str]:
    record = run.metacheck
    if record is None:
        return []
    lines = ["### Metacheck screening", "",
             "Automated screening output from the metacheck R package, passed to the review modules as unverified leads. These lights are metacheck's own and are not verified findings.", ""]
    if record.status not in {"completed", "partial"}:
        return lines + [describe(record), ""]
    if record.reason:
        lines.append(f"Run errors: {record.reason}")
    if record.text_conversion:
        lines.append(f"Text conversion: {record.text_conversion}")
    lines.append(f"Conversion: {record.converter}")
    if record.lookup_date:
        lines.append(f"CrossRef lookup: {record.lookup_date}; each module's online lookups date from its run time in the provenance")
    if record.counts:
        lines.append("Imported: " + ", ".join(f"{value} {key}" for key, value in record.counts.items()))
    lines.extend(f"Parse warning: {warning}" for warning in record.parse_warnings)
    lines.append("")
    for item in record.modules:
        filtered = f" ({item.n_filtered} filtered as not a candidate: {item.filter_rule})" if item.n_filtered else ""
        state = (f"light {item.traffic_light or 'none'}, {item.n_rows} row(s){filtered}" if item.status == "ok" else
                 f"light {item.traffic_light or 'none'}, {item.n_rows} row(s){filtered}, partly could not check" if item.status == "partial" else
                 f"could not check ({item.status}: {item.error or 'no reason recorded'})")
        lines.append(f"- `{item.module}` — {state}")
    return lines + [""]


def _page_images(run: ReviewRun) -> list[str]:
    if not run.page_images:
        return []
    lines = ["### Page images", "",
             "Every page of each PDF source was rendered locally and made available to the specialist modules, the "
             "verifier and the separate cell reader. Availability does not show that a model inspected a page; table "
             "cells count as checked only where a separate reading is recorded with a finding.", ""]
    for rendered in run.page_images:
        if rendered.error:
            lines.append(f"- `{rendered.source_id}`: no page images ({rendered.error})")
            continue
        manifest = Path(os.path.relpath(Path(rendered.directory) / rendered.source_id / "manifest.json", run.metadata.output_dir)).as_posix()
        lines.append(f"- `{rendered.source_id}`: {rendered.pages} page(s), {len(rendered.images)} image(s); "
                     f"{rendered.config.get('renderer')} {rendered.config.get('pypdfium2')}, PDFium {rendered.config.get('pdfium')}; "
                     f"configuration `{rendered.config_hash}`; {_page_link(run, rendered.source_id, 1)}; "
                     f"[manifest with image hashes]({manifest})")
    return lines + [""]


def _tool_use(run: ReviewRun) -> list[str]:
    calls = [call for stage in run.stages for call in stage.tool_calls]
    counts = {kind: sum(call.kind == kind for call in calls) for kind in ("search", "fetch", "exec", "view", "other")}
    lines = ["", "### Tool use", "", f"{len(calls)} tool calls: " + ", ".join(f"{n} {kind}" for kind, n in counts.items()) + ". "
             "Every query, command and output is recorded in review.json.", ""]
    for stage in run.stages:
        if stage.tool_calls:
            stage_counts = ", ".join(f"{n} {kind}" for kind in counts if (n := sum(c.kind == kind for c in stage.tool_calls)))
            lines.append(f"- `{stage.name}`: {stage_counts}")
    opened = [(url, call.error) for call in calls if call.kind == "fetch" for url in ([call.url] if call.url else call.result_urls)]
    if opened:
        lines.extend(["", "Pages opened:", ""])
        lines.extend(f"- {url}{' (refused or failed)' if error else ''}" for url, error in dict.fromkeys(opened))
    viewed = [(call.path, call.error) for call in calls if call.kind == "view" and call.path]
    if viewed:
        lines.extend(["", "Files opened by a file or image tool (Codex image views are not recorded):", ""])
        lines.extend(f"- `{path}`{' (refused or failed)' if error else ''}" for path, error in dict.fromkeys(viewed))
    return lines


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1).replace("*", "&#42;") + "</code>", text)
    # Links to page images and manifests in the run directory; other link targets stay text.
    text = re.sub(r"\[([^\]]+)\]\(((?:\.\./)*page-images/[\w./-]+)\)", r"<a href='\2'>\1</a>", text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
           "%3Ctext y='.9em' font-size='90'%3E%F0%9F%94%8E%3C/text%3E%3C/svg%3E")

STYLE = """
:root{--paper:#f6f4ef;--card:#fffdf8;--ink:#22201c;--soft:#5d5850;--rule:#d9d3c7;--accent:#6b2737;
--quote-bg:#efe8d8;--quote-rule:#b08a3e;--wording-rule:#6b2737;--critical:#8e1f2f;--major:#a3590b;--minor:#55606e;--code:#ebe5d9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#171513;--card:#1f1c19;--ink:#ece7de;--soft:#aaa298;
--rule:#3a352f;--accent:#e08a9a;--quote-bg:#2a251d;--quote-rule:#c9a35a;--wording-rule:#e08a9a;--critical:#f08c98;--major:#e9a85c;--minor:#9fb0c2;--code:#2c2823}}
:root[data-theme="dark"]{--paper:#171513;--card:#1f1c19;--ink:#ece7de;--soft:#aaa298;--rule:#3a352f;--accent:#e08a9a;
--quote-bg:#2a251d;--quote-rule:#c9a35a;--wording-rule:#e08a9a;--critical:#f08c98;--major:#e9a85c;--minor:#9fb0c2;--code:#2c2823}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16.5px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;overflow-wrap:anywhere}
main{max-width:50rem;margin:0 auto;padding:2.5rem 16px 4rem}
h1,h2,h3{font-family:Charter,"Bitstream Charter","Iowan Old Style",Georgia,serif;line-height:1.25;font-weight:700}
h1{font-size:2rem;margin:0 0 .6rem;color:var(--accent)}
h2{font-size:1.35rem;margin:2.8rem 0 .8rem;padding-bottom:.3rem;border-bottom:2px solid var(--accent)}
h3{font-size:1.12rem;margin:0 0 .5rem}
a{color:var(--accent)}
code{background:var(--code);padding:.05rem .3rem;border-radius:3px;font-size:.86em}
.provenance{color:var(--soft);font-size:.9rem;margin:0 0 1rem}
.partial{border:1px solid var(--critical);color:var(--critical);padding:.5rem .8rem;border-radius:6px;font-weight:600}
.summary ol{list-style:none;padding:0;margin:.6rem 0}
.summary li{display:flex;gap:.6rem;align-items:baseline;padding:.45rem 0;border-bottom:1px dotted var(--rule)}
.summary li a{color:inherit;text-decoration:none}.summary li a:hover{text-decoration:underline}
.chip{display:inline-block;flex:none;font:600 .72rem/1.5 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;
border-radius:999px;padding:.05rem .6rem;color:var(--card);background:var(--minor)}
.chip.critical{background:var(--critical)}.chip.major{background:var(--major)}
.kind{font-size:.8rem;color:var(--soft);letter-spacing:.04em;text-transform:uppercase;margin-left:.4rem}
.essential{font-size:.85rem;color:var(--soft)}
article{position:relative;background:var(--card);border:1px solid var(--rule);border-left:5px solid var(--minor);
border-radius:6px;padding:1.2rem 1.3rem 1rem 3.6rem;margin:1.4rem 0}
article.critical{border-left-color:var(--critical)}article.major{border-left-color:var(--major)}
article.unconfirmed{border-style:dashed;border-left-style:solid;padding-left:1.3rem}
.num{position:absolute;left:1rem;top:1.05rem;font:700 1.5rem/1 Charter,Georgia,serif;color:var(--soft)}
.label{font:600 .74rem/1.4 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--soft);margin:1rem 0 .35rem}
.evidence{background:var(--quote-bg);border-left:3px solid var(--quote-rule);border-radius:0 4px 4px 0;padding:.5rem .9rem;
font-family:Charter,Georgia,serif;font-size:.95rem}
.evidence p{margin:.3rem 0}.evidence .where{font:.78rem system-ui,sans-serif;color:var(--soft)}.evidence .where code{background:none;padding:0}
.response{border-top:1px solid var(--rule);padding-top:.2rem}
.wording{border:1.5px dashed var(--wording-rule);border-radius:6px;padding:.6rem .9rem;font-family:Charter,Georgia,serif}
.wording p{margin:.2rem 0}
.wording .where{font:.85rem system-ui,sans-serif;color:var(--soft)}
.related{font-size:.92rem}
.see-also{font-size:.92rem;color:var(--soft)}
details{margin-top:.6rem;color:var(--soft);font-size:.92rem}
ul.strengths li{margin:.25rem 0}
@media (max-width:560px){article{padding:1rem 1rem .8rem 1rem}.num{position:static;display:block;margin-bottom:.3rem}}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<link rel='icon' href=\"{FAVICON}\"><title>{html.escape(title)}</title><style>{STYLE}</style></head>"
            f"<body><main>{body}</main></body></html>")


def _paragraphs(text: str) -> str:
    return "".join(f"<p>{_inline(part.strip())}</p>" for part in re.split(r"\n\s*\n", text) if part.strip())


def _evidence_html(lines: list[str]) -> str:
    """Quotation panel; the source locator after the last dash is set smaller."""
    def line_html(line: str) -> str:
        text, sep, where = line[2:].rpartition(" — `")
        return f"<p>{_inline(text)} <span class='where'>— {_inline('`' + where)}</span></p>" if sep else f"<p>{_inline(line[2:])}</p>"
    return "<div class='evidence'>" + "".join(line_html(line) for line in lines) + "</div>"


def report_html(run: ReviewRun) -> str:
    """The review page, built from the same parts as review.md."""
    kept, unconfirmed = published_findings(run), unconfirmed_concerns(run)
    out = [f"<h1>{_inline(_title(run))}</h1>",
           f"<p class='provenance'>{_inline(_provenance(run))} <a href='audit.html'>Open the audit record</a>.</p>"]
    if run.partial:
        out.append("<p class='partial'>Partial review. Some stages did not complete; the audit record lists them.</p>")
    summary = _summary(kept, unconfirmed)
    out.append(f"<section class='summary'><h2 id='summary'>Summary of main concerns</h2><p>{_inline(summary[2])}</p>")
    main = [(n, f) for n, f in enumerate(kept, 1) if f.severity.value in {"critical", "major"}]
    if main:
        out.append("<ol>" + "".join(
            f"<li><span class='chip {f.severity.value}'>{f.severity.value}</span><div><a href='#finding-{n}'>{n}. {_inline(shown(f)[0])}</a>"
            + ("<div class='essential'>Remedy essential to support the claims.</div>" if f.remedy_necessity == "essential" else "")
            + "</div></li>" for n, f in main) + "</ol>")
    else:
        out.append("<p>No supported finding is rated major or critical.</p>")
    out.append("</section>")
    out.append(f"<h2 id='overview'>{_overview_label(run)}</h2>{_paragraphs(run.study_map.design_summary or 'No study overview was available.')}")
    out.append(f"<h2 id='contribution'>Claimed contribution</h2>{_paragraphs(run.study_map.contribution_summary or 'No contribution summary was available.')}")
    out.append("<h2 id='strengths'>Strengths</h2>")
    out.append("<ul class='strengths'>" + "".join(f"<li>{_inline(s)}</li>" for s in run.study_map.strengths) + "</ul>"
               if run.study_map.strengths else "<p>No specific strengths summary was available.</p>")
    out.append("<h2 id='findings'>Findings</h2>")
    if not kept:
        out.append("<p>No supported substantive findings were produced.</p>")
    for number, finding in enumerate(kept, 1):
        claim, rationale, remedy = shown(finding)
        severity = finding.severity.value
        parts = [f"<article class='{severity}' id='finding-{number}'><span class='num'>{number}</span>",
                 f"<p><span class='chip {severity}'>{severity}</span><span class='kind'>{KIND_LABEL[finding.kind]}</span></p>",
                 f"<h3>{_inline(claim)}</h3>", "<div class='label'>In the manuscript</div>", _evidence_html(_evidence_lines(finding, run)),
                 "<div class='label'>The problem</div>", _paragraphs(rationale)]
        if remedy_shown(finding):
            label = f" ({NECESSITY[finding.remedy_necessity]})" if finding.remedy_necessity else ""
            parts.append(f"<div class='response'><div class='label'>Suggested response{label}</div>{_paragraphs(remedy)}</div>")
        else:
            parts.append(f"<div class='response'><p>{_inline(_withheld(finding))}</p></div>")
        if finding.reader and finding.reader.wording:
            parts.append("<div class='label'>Possible wording</div><div class='wording'>"
                         f"<p class='where'>{_inline(_wording_note(finding.reader))}</p>"
                         f"{_paragraphs(finding.reader.wording)}</div>")
        if finding.merged_points:
            parts.append("<details class='related'><summary>Also raised as</summary>")
            for point in finding.merged_points:
                parts.append(f"<p>{_inline(point.claim)}</p>{_evidence_html(_quotation_lines(point.evidence))}")
            parts.append("</details>")
        out.append("".join(parts) + "</article>")
    if unconfirmed:
        out.append(f"<h2 id='unconfirmed'>{UNCONFIRMED_HEADING[3:]}</h2><p>{_inline(UNCONFIRMED_INTRO)}</p>")
        for finding in unconfirmed:
            claim, rationale, _ = shown(finding)
            severity = finding.severity.value
            out.append(f"<article class='{severity} unconfirmed'><p><span class='chip {severity}'>{severity}</span>"
                       f"<span class='kind'>Unconfirmed</span></p><h3>{_inline(claim)}</h3><p>{_inline(_unconfirmed_reason(finding))}</p>"
                       f"<div class='label'>In the manuscript</div>{_evidence_html(_evidence_lines(finding, run))}"
                       f"<div class='label'>The concern</div>{_paragraphs(rationale)}"
                       + (f"<p class='see-also'>See also <a href='#finding-{number}'>finding {number}</a>, which raises a related point.</p>"
                          if (number := _see_also(finding, kept)) else "")
                       + ("<details class='related'><summary>Also raised as</summary>"
                          + "".join(f"<p>{_inline(p.claim)}</p>{_evidence_html(_quotation_lines(p.evidence))}" for p in finding.merged_points)
                          + "</details>" if finding.merged_points else "")
                       + "</article>")
    return _page(_title(run), "".join(out))


def to_html(markdown: str, title: str = "Peer review") -> str:
    """HTML for the subset of Markdown that audit_markdown writes: headings, paragraphs, lists,
    quotations, bold and code."""
    out: list[str] = []
    paragraph: list[str] = []
    block: str | None = None

    def flush() -> None:
        nonlocal block
        if paragraph:
            out.append(f"<p>{' '.join(paragraph)}</p>")
            paragraph.clear()
        if block:
            out.append(f"</{block}>")
            block = None

    def open_block(tag: str) -> None:
        nonlocal block
        if block != tag:
            flush()
            out.append(f"<{tag}>" if tag != "blockquote" else "<blockquote class='evidence'>")
            block = tag

    for line in markdown.splitlines():
        heading = re.match(r"(#{1,3}) (.*)", line)
        if heading:
            flush()
            level, text = len(heading.group(1)), heading.group(2)
            out.append(f"<h{level} id='{_slug(text)}'>{_inline(text)}</h{level}>")
        elif line.startswith("- "):
            open_block("ul")
            out.append(f"<li>{_inline(line[2:])}</li>")
        elif line.startswith("  ") and block == "ul" and out[-1].endswith("</li>"):
            out[-1] = out[-1][:-5] + f"<br>{_inline(line.strip())}</li>"
        elif line.startswith("> "):
            open_block("blockquote")
            out.append(f"<p>{_inline(line[2:])}</p>")
        elif not line.strip():
            flush()
        else:
            if block:
                flush()
            paragraph.append(_inline(line.rstrip()) + ("<br>" if line.endswith("  ") else ""))
    flush()
    return _page(title, "".join(out))


def render_all(run: ReviewRun, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    (output_dir / "review.md").write_text(to_markdown(run), encoding="utf-8")
    (output_dir / "review.html").write_text(report_html(run), encoding="utf-8")
    (output_dir / AUDIT_FILE).write_text(audit_markdown(run), encoding="utf-8")
    (output_dir / "audit.html").write_text(to_html(audit_markdown(run), "Audit record"), encoding="utf-8")
