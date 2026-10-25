from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    minor = "minor"
    major = "major"
    critical = "critical"


SUPPORTED_STATUSES = frozenset({"llm_supported", "supported", "recomputed", "verified_deterministic"})


class Evidence(BaseModel):
    source_id: str
    quote: str = Field(min_length=1)
    location: str | None = None
    page: int | None = Field(default=None, ge=1)
    source_char_start: int | None = Field(default=None, ge=0)
    source_char_end: int | None = Field(default=None, ge=0)


class ExternalCitation(BaseModel):
    """An external passage and the inference it is offered to support."""
    url: str | None = None
    doi: str | None = None
    quote: str = Field(min_length=1)
    shows: str = Field(min_length=1)

    @model_validator(mode="after")
    def _needs_locator(self) -> "ExternalCitation":
        if not (self.url or self.doi):
            raise ValueError("external evidence needs a url or doi")
        return self

    @property
    def locator(self) -> str:
        return (self.url or self.doi or "").strip()


class ExternalEvidence(ExternalCitation):
    """Confirmation belongs to verification and requires its own recorded lookup."""

    check: Literal["confirmed", "refuted", "unchecked"] = "unchecked"


class ExternalCheck(BaseModel):
    """The verifier's verdict on one cited external source, identified by its URL or DOI."""

    locator: str = Field(min_length=1)
    verdict: Literal["confirmed", "refuted", "not_found"]
    rationale: str


class ToolCall(BaseModel):
    stage: str = ""
    backend: str
    sequence: int = Field(ge=0)
    kind: Literal["search", "fetch", "exec", "view", "other"]
    name: str
    query: str | None = None
    url: str | None = None
    command: str | None = None
    path: str | None = None  # file a view opened, relative to the call's working directory
    output: str = ""
    opened_urls: list[str] = Field(default_factory=list)  # pages a fetch actually opened
    result_urls: list[str] = Field(default_factory=list)  # every URL mentioned in the output, including links inside pages
    error: bool = False
    timestamp: datetime


class PageText(BaseModel):
    page: int = Field(ge=1)
    text: str


class PageImage(BaseModel):
    page: int = Field(ge=1)
    view: str  # page, upper-left, upper-right, lower-left, lower-right; turned... for upright copies
    file: str  # relative to the rendering directory and to the staged page-images directory
    rotation: int = 0  # clockwise degrees applied to set sideways text upright
    sha256: str
    width: int
    height: int


class PageImageSet(BaseModel):
    """Rendered images of every page of one PDF source, with the configuration that produced them."""
    source_id: str
    source_sha256: str
    pages: int
    config: dict[str, Any]
    config_hash: str
    directory: str
    images: list[PageImage] = Field(default_factory=list)
    error: str | None = None


Emphasis = Literal["none", "bold", "italic", "other"]

TABLE_UNIT_DEFINITION = (
    "a unit symbol or abbreviation printed in the cell, its row or column header, or an applicable table note, "
    "such as %, ms or kg, exactly as printed; not a scale range or score description; empty when none"
)


class TableReading(BaseModel):
    """One table cell as printed on a rendered page image. It is not a text quotation and has no
    character offsets; extracted text of the same cell can differ."""
    source_id: str
    page: int = Field(ge=1)
    table: str = Field(min_length=1)  # label as printed, for example "Table 2"
    row: list[str] = Field(min_length=1)  # row labels, outermost group first
    column: list[str] = Field(min_length=1)  # column headers, outermost spanning header first
    value: str = Field(min_length=1)  # exactly as printed, sign and decimal point included, without marks
    marks: str = ""  # significance stars, footnote letters or symbols printed with the value
    emphasis: Emphasis | None = None  # typeface of the value; None when the claim does not rely on it
    unit: str = Field(default="", description=TABLE_UNIT_DEFINITION)


class CellReading(BaseModel):
    """A separate reader's reading of a cell located by table, row and column, without the claimed value."""
    request_id: str
    located: bool  # exactly one cell sits at this row and column of this table
    legible: bool
    value: str
    marks: str
    emphasis: Emphasis
    unit: str = Field(description=TABLE_UNIT_DEFINITION)
    note: str


class TableCheck(BaseModel):
    reading: TableReading
    origin: Literal["discovery", "verifier"]
    outcome: Literal["matched", "mismatched", "not_located", "illegible", "image_unavailable", "not_read"]
    reason: str
    blind: CellReading | None = None
    images: list[str] = Field(default_factory=list)  # "file sha256" of the images attached for the reading


class SourceDocument(BaseModel):
    id: str
    path: str
    kind: Literal["manuscript", "supplement", "preregistration"]
    sha256: str
    text: str
    pages: list[PageText] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)


class Study(BaseModel):
    id: str
    title: str
    description: str = ""
    source_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class StudyMap(BaseModel):
    studies: list[Study]
    research_question: str | None
    design_summary: str | None
    contribution_summary: str | None
    strengths: list[str]


class CandidateConcern(BaseModel):
    """A provisional objection for independent assessment, without a support verdict."""
    id: str
    module: str
    claim: str
    rationale: str
    counterargument: str = Field(default="", description="Strongest defeating context or alternative explanation, and why the concern may remain despite it.")
    remedy: str
    # COPE: say whether a request is essential to support the claims or would strengthen or extend the work.
    remedy_necessity: Literal["essential", "strengthening", "extending"] | None = None
    severity: Severity = Severity.major
    kind: Literal["defect", "specification_conflict", "clarification_request"] = "defect"
    evidence: list[Evidence] = Field(default_factory=list)
    external_evidence: list[ExternalCitation] = Field(default_factory=list)
    table_readings: list[TableReading] = Field(default_factory=list)
    study_id: str | None = None


class MergedPoint(BaseModel):
    finding_id: str
    module: str
    claim: str
    evidence: list[Evidence] = Field(default_factory=list)


class Finding(CandidateConcern):
    discovery_severity: Severity | None = None
    priority: int | None = Field(default=None, ge=1)
    merged_points: list[MergedPoint] = Field(default_factory=list)
    external_evidence: list[ExternalEvidence] = Field(default_factory=list)
    status: Literal["candidate", "verified_deterministic", "recomputed", "llm_supported", "supported", "contradicted", "unresolved", "unverified", "merged", "rejected"] = "candidate"
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification: str | None = None
    # The separate verifier's own verdict and reason, kept apart from `status`, which also
    # reflects quote anchoring and external-source checks.
    verifier_status: Literal["supported", "contradicted", "unresolved"] | None = None
    verifier_rationale: str | None = None
    external_dependency: Literal["required", "optional"] | None = None
    external_dependency_rationale: str | None = None
    remedy_status: Literal["supported", "overreaching", "unresolved"] | None = None
    remedy_verification: str | None = None
    # Whether the verifier found that the claim rests on what a PDF table prints, and the separate
    # reading of each relied-on cell from the page images.
    table_dependence: bool | None = None
    table_checks: list[TableCheck] = Field(default_factory=list)
    editorial_disposition: Literal["publish", "merged", "rejected", "needs_review"] = "publish"
    editorial_reason: str | None = None
    merged_into: str | None = None


class StageRecord(BaseModel):
    name: str
    status: Literal["completed", "cached", "failed", "skipped"]
    cache_key: str | None = None
    artifact: str | None = None
    error: str | None = None
    key_components: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float | None = Field(default=None, ge=0)
    # Version of the CLI that produced the stage output, which is not part of the cache key.
    backend_version: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class StageProvenance(BaseModel):
    """Sidecar stored next to a cached stage artifact."""
    backend_version: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class MetacheckModule(BaseModel):
    module: str
    status: str
    traffic_light: str | None = None
    n_rows: int = 0
    run_at: str | None = None  # when the module ran; reused output keeps its original time and online lookups
    n_filtered: int = 0  # rows not passed on as leads; filter_rule says why
    filter_rule: str | None = None
    error: str | None = None
    summary_text: str | None = None
    warnings: list[str] = Field(default_factory=list)


class MetacheckRecord(BaseModel):
    """Provenance of the metacheck screening stage. Module lights are metacheck's own output."""

    status: Literal["completed", "partial", "skipped", "not_checked", "failed"]
    reason: str | None = None
    output_dir: str | None = None
    text_conversion: str | None = None
    converter: str | None = None
    lookup_date: str | None = None  # import date, when CrossRef matches were looked up; reused output keeps it
    counts: dict[str, int] = Field(default_factory=dict)
    parse_warnings: list[str] = Field(default_factory=list)
    modules: list[MetacheckModule] = Field(default_factory=list)


class RunMetadata(BaseModel):
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    backend: str
    model: str | None = None
    effort: str | None = None
    verifier_backend: str | None = None
    verifier_model: str | None = None
    verifier_effort: str | None = None
    verification_relationship: Literal["same_model_separate_call", "different_model_same_family", "different_model_family", "deterministic_fixture", "not_run"] = "not_run"
    profile: str
    profile_hash: str
    input_hash: str
    output_dir: str
    engine_version: str = "0.5.0a1"
    # "holistic" and evidence_audit=True occur only in runs archived before 0.5.0 (tag pre-specialist-only-0.4.3).
    discovery_strategy: Literal["specialist", "holistic"] = "specialist"
    evidence_audit: bool = False


class ExternalSourceTask(BaseModel):
    finding_id: str
    locator: str
    stage: str
    dependency: Literal["required", "optional"]
    lookup_recorded: bool
    check: Literal["confirmed", "refuted", "unchecked"]
    claim_status: str


class ReviewRun(BaseModel):
    metadata: RunMetadata
    sources: list[SourceDocument]
    study_map: StudyMap = Field(default_factory=lambda: StudyMap(studies=[], research_question=None, design_summary=None, contribution_summary=None, strengths=[]))
    preliminary_study_map: StudyMap | None = None
    candidates: list[Finding] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    stages: list[StageRecord] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    metacheck: MetacheckRecord | None = None
    page_images: list[PageImageSet] = Field(default_factory=list)
    source_tasks: list[ExternalSourceTask] = Field(default_factory=list)
    partial: bool = False


class Profile(BaseModel):
    id: str
    title: str
    modules: list[str]
    module_prompts: dict[str, str] = Field(default_factory=dict)
    verification_prompt: str = ""
    editorial_prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path) -> "Profile":
        import yaml

        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
