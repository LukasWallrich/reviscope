from __future__ import annotations

import html
from pathlib import Path

from .metacheck import describe
from .schemas import Finding, ReviewRun

UNCONFIRMED_HEADING = "## Concerns the verifier could not confirm"


def unconfirmed_concerns(run: ReviewRun) -> list[Finding]:
    """Findings the verifier itself judged unresolved on the evidence, with an anchored manuscript quotation.

    Findings left unresolved by quote anchoring or external-source checks are not included."""
    manuscripts = {source.id for source in run.sources if source.kind == "manuscript"}
    return [f for f in run.findings if f.status == "unresolved" and f.verifier_status == "unresolved"
            and any(ev.source_id in manuscripts and ev.location for ev in f.evidence)]


def published_findings(run: ReviewRun) -> list[Finding]:
    """Findings shown in the report's Findings section."""
    return [f for f in run.findings if f.editorial_disposition == "publish" and f.status not in {"candidate", "unverified", "unresolved", "contradicted"}]


def _evidence_lines(finding: Finding) -> list[str]:
    lines = []
    for ev in finding.evidence:
        where = ev.location or (f"page {ev.page}" if ev.page else "location unavailable")
        lines.append(f"> “{ev.quote}” — `{ev.source_id}`, {where}")
    for ext in finding.external_evidence:
        lines.append(f"> External source ({ext.check}): “{ext.quote}” — {ext.locator}; shows: {ext.shows}")
    return lines


def to_markdown(run: ReviewRun) -> str:
    state = "PARTIAL REVIEW" if run.partial else "COMPLETE REVIEW"
    title = "DEMONSTRATION — NOT AN AI REVIEW" if run.metadata.backend == "fixture" else f"Peer review ({state})"
    editorial_complete = any(stage.name == "editorial" and stage.status in {"completed", "cached"} for stage in run.stages)
    overview_label = "Study overview" if editorial_complete else "Preliminary manuscript account (not reconciled)"
    lines = [f"# {title}", "", f"Run status: **{state}**", "", f"Profile: `{run.metadata.profile}`  ", f"Backend: `{run.metadata.backend}` / `{run.metadata.model or 'default'}` / effort `{run.metadata.effort or 'default'}`  ", f"Verifier: `{run.metadata.verifier_backend}` / `{run.metadata.verifier_model or 'default'}` / effort `{run.metadata.verifier_effort or 'default'}`  ", f"Verification relationship: `{run.metadata.verification_relationship}`", "", f"## {overview_label}", "", run.study_map.design_summary or "No study overview was available.", "", "## Claimed contribution", "", run.study_map.contribution_summary or "No contribution summary was available.", "", "## Strengths", ""]
    lines.extend(f"- {strength}" for strength in run.study_map.strengths)
    if not run.study_map.strengths:
        lines.append("No specific strengths summary was available.")
    lines.extend(["", "## Findings", ""])
    kept = published_findings(run)
    if not kept:
        lines.append("No supported substantive findings were produced.")
    for finding in kept:
        kind = {"defect": "Claimed defect", "specification_conflict": "Conflicting specifications",
                "clarification_request": "Reporting clarification"}[finding.kind]
        support = "Claim and rationale supported in a separate model check against anchored manuscript evidence." if finding.status == "llm_supported" else f"Evidence status: {finding.status}."
        lines.extend([f"### {finding.severity.value.title()}: {finding.claim}", "", f"**{kind}.** {support}", "", finding.rationale, ""])
        if finding.remedy_status in {"overreaching", "unresolved"}:
            lines.extend([f"**Proposed response withheld:** `{finding.remedy_status}` — {finding.remedy_verification or 'The remedy requires reviewer judgment.'}", ""])
        else:
            lines.extend([f"**Suggested response:** {finding.remedy}", ""])
        lines.extend([*_evidence_lines(finding), ""])
    unconfirmed = unconfirmed_concerns(run)
    if unconfirmed:
        lines.extend([UNCONFIRMED_HEADING, "",
                      "The verifier could neither establish nor rule out these concerns from the supplied material. "
                      "They are not established findings. Each lists the verifier's reason.", ""])
        for finding in unconfirmed:
            lines.extend([f"### {finding.severity.value.title()}: {finding.claim}", "",
                          f"**Verifier's reason:** {finding.verifier_rationale or 'No reason recorded.'}", "",
                          finding.rationale, "", *_evidence_lines(finding), ""])
    lines.extend(["## Coverage and audit", ""])
    lines.extend(_metacheck(run))
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
    if kept:
        lines.extend(["", "### Verification details", ""])
        for finding in kept:
            lines.append(f"- `{finding.id}`: {finding.verification or 'No verification note.'}")
    set_aside = [f for f in run.findings if f not in kept and f not in unconfirmed]
    if set_aside:
        lines.extend(["", "### Set-aside findings", ""])
        for finding in set_aside:
            lines.append(f"- `{finding.id}` — epistemic `{finding.status}`, editorial `{finding.editorial_disposition}`: {finding.editorial_reason or finding.verification or 'No reason recorded.'}")
    return "\n".join(lines) + "\n"


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


def _tool_use(run: ReviewRun) -> list[str]:
    calls = [call for stage in run.stages for call in stage.tool_calls]
    counts = {kind: sum(call.kind == kind for call in calls) for kind in ("search", "fetch", "exec", "other")}
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
    return lines


def to_html(markdown: str) -> str:
    body = f"<pre style='white-space:pre-wrap'>{html.escape(markdown)}</pre>"
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Peer review</title><style>body{{max-width:850px;margin:3rem auto;padding:0 1.2rem;font:17px/1.55 system-ui;color:#202124}}blockquote{{border-left:3px solid #777;padding-left:1rem;color:#444}}code{{background:#eee;padding:.1rem .25rem}}h1,h2,h3{{line-height:1.2}}</style></head><body>{body}</body></html>"


def render_all(run: ReviewRun, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    markdown = to_markdown(run)
    (output_dir / "review.md").write_text(markdown, encoding="utf-8")
    (output_dir / "review.html").write_text(to_html(markdown), encoding="utf-8")
