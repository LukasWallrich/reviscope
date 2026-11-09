"""Final reader pass: a separate call reads the assembled review as its recipients will and revises
the wording of each item for clarity, specificity and proportion without changing what was established.

The revision is presentation only. The verified claim, rationale and remedy stay on the finding and in
the audit record; the report shows the reader's wording where it passes a deterministic number check."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field

from .schemas import Finding, ReaderEdit, SourceDocument, StudyMap

READER_PROMPT = """You are the final reader of a peer review before it goes to the authors and the editor.
Read the review as they will, alongside the manuscript. Make each item clear, specific and proportionate
without changing what has been established. You revise wording; you do not review the paper again.

For every item under ITEMS, return a revision with its id:
- claim: one sentence naming the specific problem, understandable without the rest of the review.
- rationale: what the manuscript says or does, why that is a problem, and what it means for the paper's
  conclusions. Lead with the concrete discrepancy, not a general principle. Explain a technical term the
  first time if a reader in the paper's field might not know it. Keep it as short as the argument allows.
- remedy: what the authors should do, concretely. Return an empty string when remedy_shown is false.
- changes: one sentence saying what you changed and why, or "none".
- doubt: if reading the manuscript leaves you doubting that the item is correct, not merely unclear, say
  why; otherwise an empty string. Do not rewrite the item to resolve a doubt.
- wording and wording_location: only when wording_allowed is true (a request to report something more
  clearly). Draft the sentence or short passage the authors could add or substitute, and say where it goes
  (section, page, and the passage it replaces or follows). Put any detail the manuscript does not give in
  square brackets, for example [number of participants excluded]. Leave both empty when a drafted passage
  would not help or wording_allowed is false.

Rules:
- Keep the substance. Every factual statement must already be in the item's own text, its verification
  notes or its quotations. Do not add facts, numbers, citations or new criticisms. A number that does not
  appear in that material is rejected automatically and the original text is shown instead.
- You may narrow a statement that the verification notes do not fully support, or drop a sentence that
  overreaches. Never strengthen a claim or raise its stakes.
- Check whether the manuscript already acknowledges the issue. If it does, aim the item at what is still
  missing or contradictory, and say so in changes.
- Remove pipeline vocabulary (module names, "candidate", "verifier", identifiers) and hedges that add nothing.
- Write plain text: no Markdown links, headings or lists. Name a cited source in words; its link stays in the
  item's evidence.
- If an item is already clear, return its text unchanged with changes "none".

Also return overview: design_summary, contribution_summary and strengths revised for clarity under the same
rules (a number must already appear in the current overview), and report_notes: problems that span items,
such as two items that contradict or repeat each other, or a severity that does not match the explanation.
Report notes are recorded for audit and do not change the review."""


class ReaderRevision(BaseModel):
    id: str
    claim: str
    rationale: str
    remedy: str = ""
    changes: str = ""
    doubt: str = ""
    wording: str = ""
    wording_location: str = ""


class ReaderOverview(BaseModel):
    design_summary: str | None
    contribution_summary: str | None
    strengths: list[str]


class ReaderResponse(BaseModel):
    revisions: list[ReaderRevision] = Field(default_factory=list)
    overview: ReaderOverview | None = None
    report_notes: list[str] = Field(default_factory=list)


_NUMBER = re.compile(r"(?<!\w)[-−]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")


def numbers(text: str) -> set[str]:
    """Numeric tokens in a canonical form, so 0.05 and .05, or 1,200 and 1200, compare equal."""
    found: set[str] = set()
    for token in _NUMBER.findall(text):
        sign = "-" if token[0] in "-−" else ""
        token = token.lstrip("-−").rstrip(",")
        parts = [token.replace(",", "")] if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token) else token.split(",")
        for part in filter(None, parts):
            try:
                value = Decimal(part).normalize()
            except InvalidOperation:
                continue
            found.add(sign + format(value, "f"))
    return found


def _placeholders_removed(text: str) -> str:
    return re.sub(r"\[[^\]]*\]", " ", text)


def wording_allowed(finding: Finding, remedy_shown: bool) -> bool:
    return remedy_shown and finding.kind == "clarification_request"


def item_material(finding: Finding) -> str:
    """Everything an item's revised wording may draw numbers from."""
    parts = [finding.claim, finding.rationale, finding.remedy, finding.verification or "", finding.verifier_rationale or "",
             finding.remedy_verification or ""]
    parts += [f"{e.quote} {e.location or ''} {e.page or ''}" for e in finding.evidence]
    parts += [f"{p.claim} " + " ".join(e.quote for e in p.evidence) for p in finding.merged_points]
    parts += [f"{e.quote} {e.shows} {e.locator}" for e in finding.external_evidence]
    for check in finding.table_checks:
        r = check.reading
        parts.append(f"{r.table} {' '.join(r.row)} {' '.join(r.column)} {r.value} {r.marks} {r.page} {check.reason}")
    parts += [f"{r.table} {' '.join(r.row)} {' '.join(r.column)} {r.value} {r.page}" for r in finding.table_readings]
    return "\n".join(parts)


def item_payload(number: str, finding: Finding, display: str, remedy_shown: bool) -> dict[str, object]:
    return {"id": finding.id, "shown_as": number, "display": display, "kind": finding.kind,
            "severity": finding.severity.value, "claim": finding.claim, "rationale": finding.rationale,
            "remedy": finding.remedy if remedy_shown else "", "remedy_shown": remedy_shown,
            "wording_allowed": wording_allowed(finding, remedy_shown),
            "verification_notes": [n for n in (finding.verifier_rationale, finding.remedy_verification) if n],
            "quotations": [e.quote for e in finding.evidence]}


def apply_revision(finding: Finding, revision: ReaderRevision | None, remedy_shown: bool,
                   sources: list[SourceDocument]) -> Finding:
    """Accept each revised field whose numbers all occur in the item's material; keep the original otherwise."""
    if revision is None:
        return finding
    allowed = numbers(item_material(finding))
    rejected: list[str] = []

    def accept(field: str, text: str, pool: set[str], strip_placeholders: bool = False) -> str | None:
        text = text.strip()
        if not text:
            return None
        extra = numbers(_placeholders_removed(text) if strip_placeholders else text) - pool
        if extra:
            rejected.append(f"{field}: number(s) {', '.join(sorted(extra))} not in the item's material")
            return None
        return text

    claim = accept("claim", revision.claim, allowed)
    rationale = accept("rationale", revision.rationale, allowed)
    remedy = accept("remedy", revision.remedy, allowed) if remedy_shown else None
    wording = location = None
    if wording_allowed(finding, remedy_shown) and revision.wording.strip():
        manuscript = allowed | numbers("\n".join(s.text for s in sources))
        wording = accept("wording", revision.wording, manuscript, strip_placeholders=True)
        location = accept("wording location", revision.wording_location, manuscript) if wording else None
        if wording and not location:
            rejected.append("wording: no usable location given")
            wording = None
    edit = ReaderEdit(claim=claim, rationale=rationale, remedy=remedy, wording=wording, wording_location=location,
                      changes=revision.changes.strip(), doubt=revision.doubt.strip(), rejected=rejected)
    return finding.model_copy(update={"reader": edit})


def apply_overview(study_map: StudyMap, overview: ReaderOverview | None) -> tuple[StudyMap, list[str]]:
    """Accept the revised overview only if it adds no number and keeps every section that had content."""
    if overview is None:
        return study_map, []
    original = " ".join([study_map.design_summary or "", study_map.contribution_summary or "", *study_map.strengths])
    revised = " ".join([overview.design_summary or "", overview.contribution_summary or "", *overview.strengths])
    extra = numbers(revised) - numbers(original)
    if extra:
        return study_map, [f"overview: number(s) {', '.join(sorted(extra))} not in the current overview; kept unchanged"]
    if (study_map.design_summary and not overview.design_summary) or (study_map.contribution_summary and not overview.contribution_summary) \
            or (study_map.strengths and not overview.strengths):
        return study_map, ["overview: revision dropped a section; kept unchanged"]
    return study_map.model_copy(update={"design_summary": overview.design_summary, "contribution_summary": overview.contribution_summary,
                                        "strengths": overview.strengths}), []
