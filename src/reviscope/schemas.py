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


class Evidence(BaseModel):
    source_id: str
    quote: str = Field(min_length=1)
    location: str | None = None
    page: int | None = Field(default=None, ge=1)
    source_char_start: int | None = Field(default=None, ge=0)
    source_char_end: int | None = Field(default=None, ge=0)


class ExternalEvidence(BaseModel):
    """A passage from a source outside the supplied documents, found with a tool.

    `check` is set by the pipeline after verification: confirmed only when the verifier said so
    and its own recorded tool calls touched this URL or DOI."""

    url: str | None = None
    doi: str | None = None
    quote: str = Field(min_length=1)
    shows: str = Field(min_length=1)
    check: Literal["confirmed", "refuted", "unchecked"] = "unchecked"

    @model_validator(mode="after")
    def _needs_locator(self) -> "ExternalEvidence":
        if not (self.url or self.doi):
            raise ValueError("external evidence needs a url or doi")
        return self

    @property
    def locator(self) -> str:
        return (self.url or self.doi or "").strip()


class ExternalCheck(BaseModel):
    """The verifier's verdict on one cited external source, identified by its URL or DOI."""

    locator: str = Field(min_length=1)
    verdict: Literal["confirmed", "refuted", "not_found"]
    rationale: str


class ToolCall(BaseModel):
    stage: str = ""
    backend: str
    sequence: int = Field(ge=0)
    kind: Literal["search", "fetch", "exec", "other"]
    name: str
    query: str | None = None
    url: str | None = None
    command: str | None = None
    output: str = ""
    opened_urls: list[str] = Field(default_factory=list)  # pages a fetch actually opened
    result_urls: list[str] = Field(default_factory=list)  # every URL mentioned in the output, including links inside pages
    error: bool = False
    timestamp: datetime


class PageText(BaseModel):
    page: int = Field(ge=1)
    text: str


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


class Finding(BaseModel):
    id: str
    module: str
    claim: str
    rationale: str
    remedy: str
    severity: Severity = Severity.major
    evidence: list[Evidence] = Field(default_factory=list)
    external_evidence: list[ExternalEvidence] = Field(default_factory=list)
    study_id: str | None = None
    status: Literal["candidate", "verified_deterministic", "recomputed", "llm_supported", "supported", "contradicted", "unresolved", "unverified", "merged", "rejected"] = "candidate"
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification: str | None = None
    # The separate verifier's own verdict and reason, kept apart from `status`, which also
    # reflects quote anchoring and external-source checks.
    verifier_status: Literal["supported", "contradicted", "unresolved"] | None = None
    verifier_rationale: str | None = None
    remedy_status: Literal["supported", "overreaching", "unresolved"] | None = None
    remedy_verification: str | None = None
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
    engine_version: str = "0.4.0a1"


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
