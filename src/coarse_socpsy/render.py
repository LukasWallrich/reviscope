from __future__ import annotations

import html
from pathlib import Path

from .schemas import ReviewRun


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
    kept = [f for f in run.findings if f.editorial_disposition == "publish" and f.status not in {"candidate", "unverified", "contradicted"}]
    if not kept:
        lines.append("No supported substantive findings were produced.")
    for finding in kept:
        lines.extend([f"### {finding.severity.value.title()}: {finding.claim}", "", f"**Verification:** `{finding.status}` — {finding.verification or 'No verification note.'}", "", finding.rationale, ""])
        if finding.remedy_status in {"overreaching", "unresolved"}:
            lines.extend([f"**Proposed response withheld:** `{finding.remedy_status}` — {finding.remedy_verification or 'The remedy requires reviewer judgment.'}", ""])
        else:
            lines.extend([f"**Suggested response:** {finding.remedy}", ""])
        for ev in finding.evidence:
            where = ev.location or (f"page {ev.page}" if ev.page else "location unavailable")
            lines.append(f"> “{ev.quote}” — `{ev.source_id}`, {where}")
        lines.append("")
    lines.extend(["## Coverage and audit", ""])
    lines.extend(f"- {item}" for item in run.coverage)
    lines.append("")
    for stage in run.stages:
        detail = f": {stage.error}" if stage.error else ""
        lines.append(f"- `{stage.name}` — {stage.status}{detail}")
    set_aside = [f for f in run.findings if f not in kept]
    if set_aside:
        lines.extend(["", "### Set-aside findings", ""])
        for finding in set_aside:
            lines.append(f"- `{finding.id}` — epistemic `{finding.status}`, editorial `{finding.editorial_disposition}`: {finding.editorial_reason or finding.verification or 'No reason recorded.'}")
    return "\n".join(lines) + "\n"


def to_html(markdown: str) -> str:
    body = f"<pre style='white-space:pre-wrap'>{html.escape(markdown)}</pre>"
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Peer review</title><style>body{{max-width:850px;margin:3rem auto;padding:0 1.2rem;font:17px/1.55 system-ui;color:#202124}}blockquote{{border-left:3px solid #777;padding-left:1rem;color:#444}}code{{background:#eee;padding:.1rem .25rem}}h1,h2,h3{{line-height:1.2}}</style></head><body>{body}</body></html>"


def render_all(run: ReviewRun, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    markdown = to_markdown(run)
    (output_dir / "review.md").write_text(markdown, encoding="utf-8")
    (output_dir / "review.html").write_text(to_html(markdown), encoding="utf-8")
