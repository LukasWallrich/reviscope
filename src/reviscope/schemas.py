from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    study_id: str | None = None
    status: Literal["candidate", "verified_deterministic", "recomputed", "llm_supported", "supported", "contradicted", "unresolved", "unverified", "merged", "rejected"] = "candidate"
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification: str | None = None
    remedy_status: Literal["supported", "overreaching", "unresolved"] | None = None
    remedy_verification: str | None = None
    editorial_disposition: Literal["publish", "merged", "rejected", "needs_review", "cap"] = "publish"
    editorial_reason: str | None = None
    merged_into: str | None = None


class DeferredToolCheck(BaseModel):
    question: str = Field(min_length=1)
    capability: Literal["calculation", "data_analysis", "document_retrieval", "reference_lookup", "figure_inspection", "other"]
    proposed_action: str = Field(min_length=1)
    required_inputs: list[str] = Field(min_length=1)
    expected_review_impact: str = Field(min_length=1)
    stopping_rule: str = Field(min_length=1)
    priority: Literal["high", "medium", "low"]
    evidence: list[Evidence] = Field(min_length=1)
    module: str = ""
    anchor_status: Literal["unchecked", "anchored", "unanchored"] = "unchecked"


class StageRecord(BaseModel):
    name: str
    status: Literal["completed", "cached", "failed", "skipped"]
    cache_key: str | None = None
    artifact: str | None = None
    error: str | None = None
    key_components: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float | None = Field(default=None, ge=0)


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
    engine_version: str = "0.2.0a1"


class ReviewRun(BaseModel):
    metadata: RunMetadata
    sources: list[SourceDocument]
    study_map: StudyMap = Field(default_factory=lambda: StudyMap(studies=[], research_question=None, design_summary=None, contribution_summary=None, strengths=[]))
    preliminary_study_map: StudyMap | None = None
    candidates: list[Finding] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    stages: list[StageRecord] = Field(default_factory=list)
    coverage: list[str] = Field(default_factory=list)
    deferred_tool_checks: list[DeferredToolCheck] = Field(default_factory=list)
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
