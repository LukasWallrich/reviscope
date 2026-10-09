"""Criticism-level judging of review outputs: a development instrument, not validation.

Three stages per paper. Extraction turns each arm's author-visible output into criticism
variants with opaque ids; origin (arm, run, module, status, severity) is kept apart and never
enters a model prompt. A tool-free call clusters the pooled variants into underlying issues.
Tool-enabled judges from one or more model families then check every variant against the full
manuscript. Metrics are computed per judge family and for a conservative combination.

Every model stage is cached on its complete prompt, schema and backend identity. Judgments are
also indexed per variant, so adding a run judges only its new variants. A failed stage is
recorded and makes the result partial; nothing is dropped silently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence, TypeVar

from pydantic import BaseModel, Field

from .backend import Backend, ClaudeBackend, CodexBackend
from .ingest import ingest
from .schemas import ReviewRun, SourceDocument, StageProvenance, StageRecord
from .verification import verify_quote

PROTOCOL = "criticism-judge-v1"
CLUSTER_PROTOCOL = "criticism-cluster-v3"
NORMALIZE_STAGE = "normalize-human-review-v1"
DEFAULT_JUDGES = ("codex:gpt-6.1-sol:high", "claude:claude-opus-5-5:high")
DEFAULT_CLUSTERER = "codex:gpt-6.1-sol:high"
DEFAULT_NORMALIZER = "claude:claude-opus-5-5:high"
DEFAULT_SEED = 20261009
CORRECTNESS = ("supported", "contradicted", "unresolved", "not_assessable")
NON_CRITICISM_TYPES = ("strength", "praise", "endorse", "positive", "summary", "overall")

M = TypeVar("M", bound=BaseModel)
Verdict = Literal["supported", "contradicted", "unresolved", "not_assessable"]
Part = Literal["supported", "contradicted", "unresolved", "not_assessable", "not_stated"]
Tri = Literal["yes", "no", "unclear", "not_applicable"]


# ---------------------------------------------------------------- extraction

class Variant(BaseModel):
    """Content shown to clustering and judging prompts. Nothing here identifies the arm."""
    id: str
    claim: str
    rationale: str = ""
    remedy: str | None = None
    quotes: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


class Origin(BaseModel):
    """Where a variant came from; kept out of every prompt."""
    variant_id: str
    arm: str
    run: str
    path: str
    format: Literal["pipeline", "plain", "human", "probe"]
    display: Literal["published", "unresolved"] = "published"
    module: str | None = None
    status: str | None = None
    severity: str | None = None
    kind: str | None = None
    source_item: str | None = None
    remedy_withheld: bool = False
    quote_anchoring: list[bool] = Field(default_factory=list)


class RunOutput(BaseModel):
    arm: str
    run: str
    path: str
    format: Literal["pipeline", "plain", "human"]
    sha256: str
    output_words: int
    variant_ids: list[str]
    partial_source: bool = False
    notes: list[str] = Field(default_factory=list)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def _words(*texts: str | None) -> int:
    return sum(len((text or "").split()) for text in texts)


def _variant_id(file_sha: str, item: str, content: Mapping[str, Any]) -> str:
    return "V" + _hash([file_sha, item, content])[:10]


def _make(file_sha: str, item: str, origin: dict[str, Any], sources: Sequence[SourceDocument], **content: Any) -> tuple[Variant, Origin]:
    content = {"claim": content["claim"].strip(), "rationale": (content.get("rationale") or "").strip(),
               "remedy": (content.get("remedy") or "").strip() or None,
               "quotes": [q for q in content.get("quotes", []) if q and q.strip()], "external": content.get("external", [])}
    variant = Variant(id=_variant_id(file_sha, item, content), **content)
    maps = [{"source_id": s.id, "text": s.text} for s in sources]
    anchoring = [verify_quote(q, maps).status == "supported" for q in variant.quotes]
    return variant, Origin(variant_id=variant.id, source_item=item, quote_anchoring=anchoring, **origin)


def _pipeline_variants(run: ReviewRun, base: dict[str, Any], file_sha: str, sources: Sequence[SourceDocument]) -> list[tuple[Variant, Origin]]:
    """Published findings and author-visible unresolved concerns, as rendered in review.md."""
    from .render import published_findings, unconfirmed_concerns

    rows = []
    shown = [(f, "published") for f in published_findings(run)] + [(f, "unresolved") for f in unconfirmed_concerns(run)]
    for finding, display in shown:
        # The report withholds overreaching or unresolved remedies and shows no remedy for unresolved concerns.
        withheld = display == "unresolved" or finding.remedy_status in {"overreaching", "unresolved"}
        external = [f"{e.quote} ({e.locator}); offered to show: {e.shows}" for e in finding.external_evidence]
        rows.append(_make(file_sha, finding.id, {**base, "display": display, "module": finding.module, "status": finding.status,
                                                 "severity": finding.severity.value, "kind": finding.kind, "remedy_withheld": withheld},
                          sources, claim=finding.claim, rationale=finding.rationale, remedy=None if withheld else finding.remedy,
                          quotes=[e.quote for e in finding.evidence], external=external))
    return rows


def _shown_words(variants: Iterable[Variant]) -> int:
    return sum(_words(v.claim, v.rationale, v.remedy, *v.quotes, *v.external) for v in variants)


def _human_issues(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if data.get("audit_schema_version") == 1:
        data = data["normalization"]
    return [row for row in data["inventory"]["issues"]
            if not any(term in str(row.get("assessment_type", "")).casefold() for term in NON_CRITICISM_TYPES)]


def extract_arm(arm: str, run_label: str, path: Path, sources: Sequence[SourceDocument],
                normalize: Callable[[str], Mapping[str, Any]] | None = None) -> tuple[RunOutput, list[Variant], list[Origin]]:
    """Variants for one run of one arm. Structured inputs are read deterministically; a free-text
    human report is normalized into atomic issues by `normalize` (strengths are excluded)."""
    raw = path.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    base = {"arm": arm, "run": run_label, "path": str(path)}
    notes: list[str] = []
    partial = False
    manuscript_sha = {s.sha256 for s in sources if s.kind == "manuscript"}
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
        if isinstance(data, Mapping) and "findings" in data and "metadata" in data:
            run = ReviewRun.model_validate(data)
            if not any(s.sha256 in manuscript_sha for s in run.sources if s.kind == "manuscript"):
                raise ValueError(f"{path}: the run's manuscript does not match --manuscript (sha256)")
            pairs = _pipeline_variants(run, {**base, "format": "pipeline"}, file_sha, sources)
            partial = run.partial
            fmt, words = "pipeline", _shown_words(v for v, _ in pairs)
        elif isinstance(data, Mapping) and isinstance(data.get("issues"), list):
            declared = [s.get("sha256") for s in data.get("sources", []) if isinstance(s, Mapping) and s.get("kind") == "manuscript"]
            if declared and not set(declared) & manuscript_sha:
                raise ValueError(f"{path}: the plain review's manuscript does not match --manuscript (sha256)")
            if not declared:
                notes.append("plain review records no manuscript hash; source match not checked")
            pairs = []
            for index, issue in enumerate(data["issues"]):
                # Dawes format (no remedy) or the general prompt's format (remedy, remedy_necessity).
                pairs.append(_make(file_sha, f"issue-{index}", {**base, "format": "plain", "module": issue.get("category"),
                                                                "severity": issue.get("severity"), "status": "plain",
                                                                "kind": issue.get("remedy_necessity")},
                                   sources, claim=str(issue.get("description", "")), remedy=str(issue.get("remedy") or ""),
                                   quotes=[str(issue.get("quote", ""))]))
            partial = bool(data.get("partial"))
            fmt, words = "plain", sum(_words(*(str(i.get(k) or "") for k in ("subcategory", "description", "remedy", "quote")))
                                      for i in data["issues"])
        elif isinstance(data, Mapping) and (data.get("normalization_schema_version") == 1 or data.get("audit_schema_version") == 1):
            if data.get("audit_schema_version") == 1 and not data.get("comparison_eligible"):
                notes.append("normalized inventory did not pass its audit")
            pairs = _human_from_inventory(_human_issues(data), base, file_sha, sources)
            fmt, words = "human", _shown_words(v for v, _ in pairs)
            notes.append("pre-normalized inventory: output_words counts inventory text, not the original report")
        else:
            raise ValueError(f"{path}: not a pipeline review.json, plain review JSON or normalized review inventory")
    elif path.suffix.lower() in {".md", ".txt"}:
        text = raw.decode("utf-8")
        if re.match(r"^# (Peer review \(|DEMONSTRATION)", text):
            raise ValueError(f"{path}: pass the pipeline's review.json, not its rendered report")
        if normalize is None:
            raise ValueError(f"{path}: free-text reports need a normalizer")
        normalized = normalize(text)
        checks = normalized.get("deterministic_checks", {})
        if not checks.get("all_source_spans_matched", True):
            notes.append(f"normalization: {len(checks.get('unmatched_spans', []))} span(s) not found in the report")
        pairs = _human_from_inventory(_human_issues(normalized), base, file_sha, sources)
        fmt, words = "human", _words(text)
    else:
        raise ValueError(f"{path}: unsupported review format")
    variants, origins = [v for v, _ in pairs], [o for _, o in pairs]
    if len({v.id for v in variants}) != len(variants):
        raise ValueError(f"{path}: duplicate variant content")
    return (RunOutput(arm=arm, run=run_label, path=str(path), format=fmt, sha256=file_sha, output_words=words,
                      variant_ids=[v.id for v in variants], partial_source=partial, notes=notes), variants, origins)


def _human_from_inventory(issues: list[Mapping[str, Any]], base: dict[str, Any], file_sha: str,
                          sources: Sequence[SourceDocument]) -> list[tuple[Variant, Origin]]:
    return [_make(file_sha, str(row.get("issue_id", i)), {**base, "format": "human", "status": "human",
                                                           "kind": str(row.get("assessment_type") or "") or None},
                  sources, claim=str(row.get("evaluation", "")), rationale=str(row.get("rationale", "")),
                  remedy=str(row.get("remedy", "")), quotes=[str(q) for q in row.get("evidence", [])])
            for i, row in enumerate(issues) if str(row.get("evaluation", "")).strip()]


# ---------------------------------------------------------------- caching

def _write_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _take_calls(backend: Any) -> list[Any]:
    take = getattr(backend, "take_tool_calls", None)
    return take() if callable(take) else []


def cached_stage(cache: Path, name: str, components: Mapping[str, Any], model_type: type[M],
                 fn: Callable[[], M], backend: Any) -> tuple[M, StageRecord]:
    """Run or reuse one model stage. `components` must contain the complete prompt (or its hash)
    and the inputs; the response schema and backend identity are added here. Tool calls are kept
    in a sidecar. Exceptions propagate with the tool calls recorded so far attached."""
    components = {"stage": name, **components, "schema_hash": _hash(model_type.model_json_schema()), "backend": backend.identity}
    key = _hash(components)
    artifact = cache / "stages" / f"{name}-{key[:24]}.json"
    tools = artifact.with_suffix(".tools.json")
    if artifact.is_file() and tools.is_file():
        recorded = StageProvenance.model_validate_json(tools.read_bytes())
        return model_type.model_validate_json(artifact.read_text(encoding="utf-8")), StageRecord(
            name=name, status="cached", cache_key=key, artifact=str(artifact), duration_seconds=0,
            backend_version=recorded.backend_version, tool_calls=recorded.tool_calls)
    started = time.monotonic()
    _take_calls(backend)
    try:
        value = fn()
    except Exception as exc:
        exc.tool_calls = [c.model_copy(update={"stage": name}) for c in _take_calls(backend)]  # type: ignore[attr-defined]
        raise
    calls = [c.model_copy(update={"stage": name}) for c in _take_calls(backend)]
    version = getattr(backend, "version", None)
    _write_atomic(tools, StageProvenance(backend_version=version, tool_calls=calls).model_dump_json(indent=2))
    _write_atomic(artifact, value.model_dump_json(indent=2))
    return value, StageRecord(name=name, status="completed", cache_key=key, artifact=str(artifact),
                              duration_seconds=time.monotonic() - started, backend_version=version, tool_calls=calls)


def _failed(name: str, exc: Exception, backend: Any) -> StageRecord:
    return StageRecord(name=name, status="failed", error=f"{type(exc).__name__}: {exc}",
                       tool_calls=getattr(exc, "tool_calls", []), backend_version=getattr(backend, "version", None))


# ---------------------------------------------------------------- clustering

class Cluster(BaseModel):
    cluster_id: str
    label: str
    variant_ids: list[str]


class ClusterResponse(BaseModel):
    clusters: list[Cluster]


class Partition(BaseModel):
    """Validated clustering result; violations and repairs stay on record."""
    clusters: list[Cluster]
    attempts: int
    violations: list[str] = Field(default_factory=list)
    repairs: list[str] = Field(default_factory=list)


CLUSTER_INSTRUCTION = """Group review criticisms that raise the same underlying problem in the manuscript. The criticisms
come from several anonymous reviews of one manuscript; their order is random and carries no information.
Put criticisms in one cluster when they point to the same problem in the manuscript: the same reported quantity,
passage, construct, design decision, analysis or claim, found wanting in the same respect. They belong together
even when they describe its consequence differently, propose different remedies, or one is broader or more severe
than another (for example, one says a test statistic is inconsistent with the reported means and another that the
nonsignificant result drawn from it is wrong). Keep criticisms apart when they allege different problems, even about
the same passage or study (for example, one doubts a measure's validity and another its scoring). Problems with
different reported quantities or different measures are different problems, even in the same table or study; do not
form a cluster for a category such as "statistical inconsistencies in Study 1". Consequences and
remedies are assessed separately for each criticism, so do not split a cluster because of them.
Do not judge whether a criticism is correct, important or well argued, and ignore length, tone and confidence.
Assign every criticism id to exactly one cluster; a criticism with no counterpart forms its own cluster. Give
each cluster a short neutral label describing the problem. Use cluster_id values c1, c2, ... in any order."""

MERGE_INSTRUCTION = """The clusters below were formed separately in batches from one pooled set of review criticisms
of one manuscript. Merge clusters from different batches that raise the same underlying problem in the manuscript
(the same quantity, passage, construct, design decision, analysis or claim found wanting in the same respect),
even when their stated consequences or remedies differ; keep clusters about different problems separate. Do not
judge correctness or importance. Return clusters whose variant_ids list the input cluster ids (k1, k2, ...); every
input cluster id must appear exactly once."""


def _partition_errors(response: ClusterResponse, ids: Sequence[str]) -> list[str]:
    wanted, seen, errors = set(ids), {}, []
    for cluster in response.clusters:
        if not cluster.variant_ids:
            errors.append(f"cluster {cluster.cluster_id} is empty")
        for vid in cluster.variant_ids:
            if vid not in wanted:
                errors.append(f"unknown id {vid} in cluster {cluster.cluster_id}")
            elif vid in seen:
                errors.append(f"id {vid} assigned to both {seen[vid]} and {cluster.cluster_id}")
            else:
                seen[vid] = cluster.cluster_id
    errors += [f"id {vid} not assigned" for vid in ids if vid not in seen]
    return errors


def _repair(response: ClusterResponse, ids: Sequence[str]) -> tuple[list[Cluster], list[str]]:
    """Deterministic fallback: drop unknown ids, keep a repeated id in its first cluster, add singletons."""
    wanted, seen, clusters, repairs = set(ids), set(), [], []
    for cluster in response.clusters:
        kept = [v for v in cluster.variant_ids if v in wanted and v not in seen]
        repairs += [f"removed {v} from {cluster.cluster_id}" for v in cluster.variant_ids if v not in kept]
        seen.update(kept)
        if kept:
            clusters.append(cluster.model_copy(update={"variant_ids": kept}))
    for vid in ids:
        if vid not in seen:
            clusters.append(Cluster(cluster_id=f"singleton-{vid}", label="(unassigned by clustering model)", variant_ids=[vid]))
            repairs.append(f"added singleton for {vid}")
    return clusters, repairs


def _partition(backend: Any, instruction: str, evidence: str, ids: Sequence[str]) -> Partition:
    """One clustering call, one repair retry naming every violation, then deterministic repair."""
    response = backend.generate(instruction, evidence, ClusterResponse)
    errors = _partition_errors(response, ids)
    violations = list(errors)
    attempts = 1
    if errors:
        attempts = 2
        retry = (instruction + "\n\nYOUR PREVIOUS ANSWER VIOLATED THE ASSIGNMENT RULES:\n- " + "\n- ".join(errors[:50])
                 + "\nPREVIOUS ANSWER\n" + response.model_dump_json() + "\nReturn a complete corrected partition.")
        response = backend.generate(retry, evidence, ClusterResponse)
        errors = _partition_errors(response, ids)
        violations += [f"retry: {e}" for e in errors]
    if errors:
        clusters, repairs = _repair(response, ids)
        return Partition(clusters=clusters, attempts=attempts, violations=violations, repairs=repairs)
    return Partition(clusters=response.clusters, attempts=attempts, violations=violations)


def _cluster_view(variant: Variant) -> dict[str, Any]:
    return {"id": variant.id, "claim": variant.claim, "rationale": variant.rationale, "quoted_passages": variant.quotes}


def cluster_variants(variants: Sequence[Variant], backend: Any, cache: Path, *, seed: int = DEFAULT_SEED,
                     batch_size: int = 120) -> tuple[list[dict[str, Any]], list[StageRecord], dict[str, Any]]:
    """Origin-blind clustering. Large pools are clustered in batches and then merged in one call."""
    order = sorted(variants, key=lambda v: v.id)
    random.Random(seed).shuffle(order)
    stages: list[StageRecord] = []
    record: dict[str, Any] = {"seed": seed, "batches": [], "merge": None}
    if not order:
        return [], stages, record
    chunks = math.ceil(len(order) / batch_size)
    parts = [order[i::chunks] for i in range(chunks)]
    first_level: list[Cluster] = []
    for index, part in enumerate(parts):
        evidence = "CRITICISMS\n" + json.dumps([_cluster_view(v) for v in part], ensure_ascii=False, indent=1)
        ids = [v.id for v in part]
        result, stage = cached_stage(cache, "cluster", {"protocol": CLUSTER_PROTOCOL, "instruction": CLUSTER_INSTRUCTION,
                                                         "evidence_sha": _hash(evidence)}, Partition,
                                     lambda: _partition(backend, CLUSTER_INSTRUCTION, evidence, ids), backend)
        stages.append(stage)
        record["batches"].append({"variants": len(part), **result.model_dump(exclude={"clusters"})})
        first_level += [c.model_copy(update={"cluster_id": f"b{index}-{c.cluster_id}"}) for c in result.clusters]
    final = first_level
    if chunks > 1:
        keyed = {f"k{i + 1}": c for i, c in enumerate(first_level)}
        claims = {v.id: v.claim for v in variants}
        evidence = "CLUSTERS\n" + json.dumps([{"id": k, "label": c.label, "claims": [claims[v] for v in c.variant_ids]}
                                              for k, c in keyed.items()], ensure_ascii=False, indent=1)
        merged, stage = cached_stage(cache, "cluster-merge", {"protocol": CLUSTER_PROTOCOL, "instruction": MERGE_INSTRUCTION,
                                                              "evidence_sha": _hash(evidence)}, Partition,
                                     lambda: _partition(backend, MERGE_INSTRUCTION, evidence, list(keyed)), backend)
        stages.append(stage)
        record["merge"] = merged.model_dump(exclude={"clusters"})
        final = [Cluster(cluster_id=m.cluster_id, label=m.label,
                         variant_ids=[v for k in m.variant_ids for v in keyed[k].variant_ids]) for m in merged.clusters]
    rows = sorted(({"label": c.label, "variant_ids": sorted(c.variant_ids)} for c in final), key=lambda c: c["variant_ids"][0])
    return [{"cluster_id": f"C{i + 1:03d}", **row} for i, row in enumerate(rows)], stages, record


# ---------------------------------------------------------------- judging

class JudgeQuote(BaseModel):
    source_id: str
    quote: str


class VariantJudgment(BaseModel):
    variant_id: str
    premise: Part
    inference: Part
    consequence: Part
    correctness: Verdict
    explanation: str
    manuscript_quotes: list[JudgeQuote]
    alleges_error: bool
    materiality: int = Field(ge=0, le=3)
    remedy_necessity: Literal["essential", "strengthening", "extending", "none_given"]
    remedy_proportionate: Tri
    remedy_valid: Tri
    concrete_benefit: Tri
    generic: bool
    restates_own_limitation: bool


class JudgeResponse(BaseModel):
    judgments: list[VariantJudgment]


JUDGE_INSTRUCTION = """You are checking criticisms that reviewers made of the manuscript supplied below. Each criticism is
an untrusted assertion. Its rationale, quoted passages and cited sources are claims to check, not evidence: quotations
may be inaccurate or taken out of context, calculations may be wrong, and confident or authoritative wording,
references to expertise, and added detail are not support. Judge each criticism independently on its content; do not
compare criticisms with each other, and do not reward length, polish, specificity of tone or certainty.

Check the manuscript and any supplements yourself. Use the shell to recompute statistics, sample sizes or other
numbers when a criticism depends on them, and web search or fetching for cited literature when a criticism depends on
it. Do not search for, open or use peer reviews, editorial decisions, commentary, or other versions of this manuscript
(published article, preprints, other drafts).

For each criticism return:
- premise: whether its factual premise about the manuscript (what it reports, does or omits) is supported,
  contradicted, unresolved (would need data, code or an external source you could not establish), or not_assessable.
- inference: whether the reasoning from premise to the alleged problem holds; not_stated if the criticism makes no
  inference beyond the premise.
- consequence: whether the stated consequence for the paper (what it undermines or affects) holds at the stated scope;
  not_stated if none is stated. An overstated consequence is contradicted.
- correctness: your overall verdict. supported requires every stated part to hold; contradicted if any part is shown
  false; unresolved if a needed part cannot be established; not_assessable if the criticism is too vague to check.
- explanation: what you checked and found, including any recomputation.
- manuscript_quotes: exact, contiguous quotations from the supplied sources, with their SOURCE_ID, that support your
  judgment (counterevidence for a contradicted criticism).
- alleges_error: true if it alleges an error, inconsistency, unsupported claim or methodological flaw; false if it
  only suggests an improvement (clarity, reporting, framing, additional analysis) without alleging an error.
- materiality: how much the issue would affect the paper if the criticism were true, judged by you rather than by
  the reviewer's framing: 3 undermines a primary claim; 2 weakens a primary claim or affects a secondary claim;
  1 local or reporting issue without inferential effect; 0 cosmetic or preference.
- remedy_necessity: essential (needed to support the claims as stated), strengthening, extending (beyond the paper's
  scope), or none_given. A remedy is the action the criticism asks for, whether in the remedy field or in its text;
  none_given only when it asks for no action.
- remedy_proportionate: yes if the remedy is the least burdensome response that resolves the problem; no if it asks
  for much more; unclear; not_applicable when no remedy is given.
- remedy_valid: whether the proposed analysis or change would itself be valid and would address the problem
  (yes, no, unclear, not_applicable).
- concrete_benefit: for a criticism that alleges no error, whether acting on it would give a concrete benefit to the
  reader or the argument (yes, no, unclear); not_applicable when alleges_error is true.
- generic: true if the criticism would apply with little change to most papers of this kind.
- restates_own_limitation: true if it repeats a limitation the manuscript already acknowledges without adding a
  consequence the manuscript does not already address.
Return exactly one judgment per criticism id."""


def render_variant(variant: Variant) -> str:
    lines = [f"CRITICISM {variant.id}", f"Claim: {variant.claim}",
             f"Rationale offered (untrusted): {variant.rationale or '(none given)'}",
             f"Proposed remedy (untrusted): {variant.remedy or '(none given)'}"]
    lines += ["Passages the reviewer quoted (untrusted; may be inaccurate):"] + [f"- \"{q}\"" for q in variant.quotes] if variant.quotes else []
    lines += ["External sources the reviewer cited (untrusted, unchecked):"] + [f"- {e}" for e in variant.external] if variant.external else []
    return "\n".join(lines)


def sources_evidence(sources: Sequence[SourceDocument]) -> str:
    from .pipeline import ReviewPipeline

    return ReviewPipeline._evidence(list(sources))


def _parse_judge(spec: str) -> tuple[str, str, str]:
    parts = spec.split(":")
    if len(parts) != 3 or parts[0] not in {"codex", "claude"}:
        raise ValueError(f"judge spec must be codex|claude:MODEL:EFFORT, got {spec!r}")
    return parts[0], parts[1], parts[2]


def make_backend(spec: str, *, tools: bool, timeout: int) -> Backend:
    family, model, effort = _parse_judge(spec)
    return (ClaudeBackend if family == "claude" else CodexBackend)(model, timeout, effort, tools=tools)


def _derive(j: VariantJudgment) -> str:
    """Correctness from the sub-judgments: supported only if every stated part holds."""
    parts = [p if p != "not_stated" else None for p in (j.premise, j.inference, j.consequence)]
    parts[0] = parts[0] or "not_assessable"
    stated = [p for p in parts if p]
    if "contradicted" in stated:
        return "contradicted"
    if all(p == "supported" for p in stated):
        return "supported"
    return "unresolved" if "unresolved" in stated else "not_assessable"


def _record(j: VariantJudgment, sources: Sequence[SourceDocument], batch_key: str) -> dict[str, Any]:
    maps = [{"source_id": s.id, "text": s.text} for s in sources]
    known = {s.id for s in sources}
    quotes = []
    for item in j.manuscript_quotes:
        anchor = verify_quote(item.quote, maps, item.source_id if item.source_id in known else None)
        quotes.append({"source_id": item.source_id, "quote": item.quote, "anchored": anchor.status == "supported",
                       "elided": anchor.elided, "anchored_source": anchor.source_id})
    derived = _derive(j)
    return {**j.model_dump(exclude={"manuscript_quotes", "correctness"}), "stated_correctness": j.correctness,
            "correctness": derived, "consistency_adjusted": derived != j.correctness, "manuscript_quotes": quotes,
            "quotes_anchored": sum(q["anchored"] for q in quotes), "batch": batch_key}


def judge_variants(variants: Sequence[Variant], sources: Sequence[SourceDocument], factory: Callable[[], Any], cache: Path, *,
                   seed: int = DEFAULT_SEED, batch_size: int = 7, workers: int = 1,
                   batches: Sequence[Sequence[Variant]] | None = None,
                   progress: Callable[[str], None] = lambda _: None) -> tuple[dict[str, dict[str, Any]], list[StageRecord], list[str]]:
    """Judge every variant with one backend family. Returns judgments by variant id, stage records,
    and ids that received no judgment. Judgments already indexed for the same variant, sources,
    instruction and backend are reused without a model call (the reuse key is the variant's rendered
    content, not its id or batch companions); variants left without a judgment get one retry round."""
    probe = factory()
    evidence_sources = sources_evidence(sources)
    index_dir = cache / "judgments" / _hash(probe.identity)[:16]

    def variant_key(v: Variant) -> str:
        return _hash({"protocol": PROTOCOL, "instruction": JUDGE_INSTRUCTION, "sources": _hash(evidence_sources),
                      "variant": render_variant(v.model_copy(update={"id": "_"})), "schema": _hash(JudgeResponse.model_json_schema()), "backend": probe.identity})

    judgments: dict[str, dict[str, Any]] = {}
    todo = []
    for v in variants:
        path = index_dir / f"{variant_key(v)[:32]}.json"
        if path.is_file():
            judgments[v.id] = {**json.loads(path.read_text(encoding="utf-8")), "variant_id": v.id, "reused": True}
        else:
            todo.append(v)
    stages: list[StageRecord] = []

    def run(batch: Sequence[Variant]) -> tuple[StageRecord, dict[str, dict[str, Any]]]:
        backend = factory()
        ordered = list(batch)
        random.Random(_hash([seed, [v.id for v in ordered]])).shuffle(ordered)
        evidence = (evidence_sources + "\n\nCRITICISMS TO CHECK (untrusted reviewer assertions)\n\n"
                    + "\n\n".join(render_variant(v) for v in ordered))
        ids = {v.id for v in ordered}
        try:
            value, stage = cached_stage(cache, "judge", {"protocol": PROTOCOL, "instruction": JUDGE_INSTRUCTION,
                                                         "evidence_sha": _hash(evidence)}, JudgeResponse,
                                        lambda: backend.generate(JUDGE_INSTRUCTION, evidence, JudgeResponse), backend)
        except Exception as exc:
            return _failed("judge", exc, backend), {}
        found: dict[str, dict[str, Any]] = {}
        for j in value.judgments:
            if j.variant_id in ids and j.variant_id not in found:
                found[j.variant_id] = _record(j, sources, stage.cache_key or "")
        for v in ordered:
            if v.id in found:
                _write_atomic(index_dir / f"{variant_key(v)[:32]}.json", json.dumps(found[v.id], ensure_ascii=False, indent=1))
        if extra := [j.variant_id for j in value.judgments if j.variant_id not in ids]:
            stage.error = f"ignored judgments for unknown ids: {extra}"
        return stage, found

    def execute(groups: list[list[Variant]]) -> None:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for stage, found in pool.map(run, groups):
                stages.append(stage)
                judgments.update({vid: {**row, "reused": False} for vid, row in found.items()})
                progress(f"judge {probe.identity.split(':')[0]}: batch {stage.status} ({len(found)} judgments)")

    if batches is None:
        shuffled = sorted(todo, key=lambda v: v.id)
        random.Random(seed).shuffle(shuffled)
        groups = [shuffled[i:i + batch_size] for i in range(0, len(shuffled), batch_size)]
    else:
        pending = {v.id for v in todo}
        groups = [[v for v in batch if v.id in pending] for batch in batches]
        groups = [g for g in groups if g]
    execute(groups)
    missing = [v for v in todo if v.id not in judgments]
    if missing:
        execute([missing[i:i + batch_size] for i in range(0, len(missing), batch_size)])
    return judgments, stages, [v.id for v in variants if v.id not in judgments]


# ---------------------------------------------------------------- metrics

NECESSITY_ORDER = ("none_given", "extending", "strengthening", "essential")


def combine(rows: Sequence[Mapping[str, Any] | None]) -> dict[str, Any] | None:
    """Conservative combination across judge families. Supported only if all say supported,
    contradicted if any does. Benefit-side fields take the least favourable value; harm-side
    materiality is the largest value (harm_materiality)."""
    if not rows or any(r is None for r in rows):
        return None
    verdicts = [r["correctness"] for r in rows]  # type: ignore[index]
    correctness = ("contradicted" if "contradicted" in verdicts else "supported" if all(v == "supported" for v in verdicts)
                   else "unresolved" if "unresolved" in verdicts else "not_assessable")

    def worst(field: str) -> str:
        values = {r[field] for r in rows}  # type: ignore[index]
        return "no" if "no" in values else values.pop() if len(values) == 1 else "unclear"

    return {"correctness": correctness, "materiality": min(r["materiality"] for r in rows),  # type: ignore[index]
            "harm_materiality": max(r["materiality"] for r in rows),  # type: ignore[index]
            "alleges_error": any(r["alleges_error"] for r in rows),  # type: ignore[index]
            "remedy_necessity": min((r["remedy_necessity"] for r in rows), key=NECESSITY_ORDER.index),  # type: ignore[index]
            "remedy_proportionate": worst("remedy_proportionate"), "remedy_valid": worst("remedy_valid"),
            "concrete_benefit": worst("concrete_benefit"),
            "generic": any(r["generic"] for r in rows), "restates_own_limitation": any(r["restates_own_limitation"] for r in rows)}  # type: ignore[index]


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _supported_material(row: Mapping[str, Any] | None) -> bool:
    return bool(row) and row["correctness"] == "supported" and row["materiality"] >= 2  # type: ignore[index]


def _harm(row: Mapping[str, Any], origin: Origin) -> bool:
    bad = (row["correctness"] == "contradicted" or row["remedy_proportionate"] == "no" or row["remedy_valid"] == "no")
    serious = origin.severity in {"major", "critical"} or row.get("harm_materiality", row["materiality"]) >= 2
    return bool(bad and serious)


def run_metrics(ids: Sequence[str], view: Mapping[str, Mapping[str, Any] | None], origins: Mapping[str, Origin], words: int) -> dict[str, Any]:
    judged = [(view[i], origins[i]) for i in ids if view.get(i) is not None]
    count = lambda pred: sum(1 for row, origin in judged if pred(row, origin))  # noqa: E731
    supported = count(lambda r, o: r["correctness"] == "supported")
    contradicted = count(lambda r, o: r["correctness"] == "contradicted")
    n = len(judged)
    return {
        "variants": len(ids), "judged": n, "not_judged": len(ids) - n,
        "supported": supported, "contradicted": contradicted,
        "unresolved": count(lambda r, o: r["correctness"] == "unresolved"),
        "not_assessable": count(lambda r, o: r["correctness"] == "not_assessable"),
        "supported_rate": _ratio(supported, n), "supported_of_resolved": _ratio(supported, supported + contradicted),
        "unresolved_rate": _ratio(count(lambda r, o: r["correctness"] == "unresolved"), n),
        "supported_material": count(lambda r, o: _supported_material(r)),
        "supported_beneficial_suggestions": count(lambda r, o: r["correctness"] == "supported" and not r["alleges_error"]
                                                  and r["concrete_benefit"] == "yes"),
        "serious_harms": count(_harm),
        "generic": count(lambda r, o: r["generic"]), "restates_own_limitation": count(lambda r, o: r["restates_own_limitation"]),
        "output_words": words,
    }


def issue_metrics(clusters: Sequence[Mapping[str, Any]], view: Mapping[str, Mapping[str, Any] | None],
                  origins: Mapping[str, Origin], runs: Sequence[RunOutput]) -> dict[str, Any]:
    arms = list(dict.fromkeys(r.arm for r in runs))
    runs_by_arm = {arm: [r.run for r in runs if r.arm == arm] for arm in arms}
    per_arm = {arm: {"clusters_detected": 0, "clusters_supported": 0, "clusters_supported_material": 0,
                     "unique_supported_material": 0, "unique_supported_material_no_mention": 0, "unique_by_module": {}}
               for arm in arms}
    per_run = {r.run: {"clusters_detected": 0, "clusters_supported": 0} for r in runs}
    stability = []
    for cluster in clusters:
        members = [(origins[v], view.get(v)) for v in cluster["variant_ids"]]
        mention = {arm: any(o.arm == arm for o, _ in members) for arm in arms}
        sup = {arm: any(o.arm == arm and r and r["correctness"] == "supported" for o, r in members) for arm in arms}
        mat = {arm: any(o.arm == arm and _supported_material(r) for o, r in members) for arm in arms}
        for run in per_run:
            per_run[run]["clusters_detected"] += any(o.run == run for o, _ in members)
            per_run[run]["clusters_supported"] += any(o.run == run and r and r["correctness"] == "supported" for o, r in members)
        row = {"cluster_id": cluster["cluster_id"], "label": cluster["label"], "arms": {}}
        for arm in arms:
            stats = per_arm[arm]
            stats["clusters_detected"] += mention[arm]
            stats["clusters_supported"] += sup[arm]
            stats["clusters_supported_material"] += mat[arm]
            if mat[arm] and not any(mat[a] for a in arms if a != arm):
                stats["unique_supported_material"] += 1
                stats["unique_supported_material_no_mention"] += not any(mention[a] for a in arms if a != arm)
                for module in sorted({o.module or "(none)" for o, r in members if o.arm == arm and o.format == "pipeline" and _supported_material(r)}):
                    stats["unique_by_module"][module] = stats["unique_by_module"].get(module, 0) + 1
            n_runs = len(runs_by_arm[arm])
            detected = sum(any(o.run == run for o, _ in members) for run in runs_by_arm[arm])
            supported_runs = sum(any(o.run == run and r and r["correctness"] == "supported" for o, r in members) for run in runs_by_arm[arm])
            row["arms"][arm] = {"runs": n_runs, "detected_runs": detected, "detection_frequency": _ratio(detected, n_runs),
                                "supported_runs": supported_runs}
        stability.append(row)
    return {"per_arm": per_arm, "per_run": per_run, "stability": stability}


def _kappa(pairs: Sequence[tuple[Any, Any]], categories: Sequence[Any], weights: str | None = None) -> float | None:
    n = len(pairs)
    if not n:
        return None
    k = len(categories)
    index = {c: i for i, c in enumerate(categories)}
    observed = [[0.0] * k for _ in range(k)]
    for a, b in pairs:
        observed[index[a]][index[b]] += 1 / n
    rows = [sum(observed[i]) for i in range(k)]
    cols = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    weight = (lambda i, j: abs(i - j) / (k - 1)) if weights == "linear" else (lambda i, j: float(i != j))
    disagreement_obs = sum(weight(i, j) * observed[i][j] for i in range(k) for j in range(k))
    disagreement_exp = sum(weight(i, j) * rows[i] * cols[j] for i in range(k) for j in range(k))
    return round(1 - disagreement_obs / disagreement_exp, 4) if disagreement_exp else None


def agreement(views: Mapping[str, Mapping[str, Mapping[str, Any] | None]], variants: Mapping[str, Variant]) -> dict[str, Any]:
    families = list(views)
    out: dict[str, Any] = {}
    for i, left in enumerate(families):
        for right in families[i + 1:]:
            both = [vid for vid in variants if views[left].get(vid) and views[right].get(vid)]
            correctness = [(views[left][v]["correctness"], views[right][v]["correctness"]) for v in both]  # type: ignore[index]
            materiality = [(views[left][v]["materiality"], views[right][v]["materiality"]) for v in both]  # type: ignore[index]
            disagreements = [{"variant_id": v, "claim": variants[v].claim,
                              left: {"correctness": views[left][v]["correctness"], "materiality": views[left][v]["materiality"],  # type: ignore[index]
                                     "explanation": views[left][v]["explanation"]},  # type: ignore[index]
                              right: {"correctness": views[right][v]["correctness"], "materiality": views[right][v]["materiality"],  # type: ignore[index]
                                      "explanation": views[right][v]["explanation"]}}  # type: ignore[index]
                             for v in both if views[left][v]["correctness"] != views[right][v]["correctness"]  # type: ignore[index]
                             or abs(views[left][v]["materiality"] - views[right][v]["materiality"]) >= 2]  # type: ignore[index]
            out[f"{left}~{right}"] = {
                "n": len(both),
                "correctness_agreement": _ratio(sum(a == b for a, b in correctness), len(both)),
                "correctness_kappa": _kappa(correctness, CORRECTNESS),
                "materiality_agreement": _ratio(sum(a == b for a, b in materiality), len(both)),
                "materiality_weighted_kappa_linear": _kappa(materiality, (0, 1, 2, 3), "linear"),
                "disagreements": disagreements}
    return out


def compute_metrics(variants: Sequence[Variant], origins: Mapping[str, Origin], runs: Sequence[RunOutput],
                    clusters: Sequence[Mapping[str, Any]] | None, judgments: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    ids = [v.id for v in variants]
    views: dict[str, dict[str, Mapping[str, Any] | None]] = {family: {vid: rows.get(vid) for vid in ids} for family, rows in judgments.items()}
    if len(judgments) > 1:
        views["combined"] = {vid: combine([judgments[f].get(vid) for f in judgments]) for vid in ids}  # type: ignore[misc]
    result: dict[str, Any] = {"views": {}}
    for name, view in views.items():
        per_run = []
        for run in runs:
            published = [vid for vid in run.variant_ids if origins[vid].display == "published"]
            per_run.append({"arm": run.arm, "run": run.run, "format": run.format,
                            "author_visible": run_metrics(run.variant_ids, view, origins, run.output_words),
                            "published_only": run_metrics(published, view, origins, run.output_words)})
        entry: dict[str, Any] = {"per_run": per_run}
        if clusters is not None:
            entry["issues"] = issue_metrics(clusters, view, origins, runs)
        result["views"][name] = entry
    result["agreement"] = agreement({f: views[f] for f in judgments}, {v.id: v for v in variants}) if len(judgments) > 1 else {}
    return result


def arm_means(metrics: Mapping[str, Any], scope: str = "author_visible") -> dict[str, dict[str, dict[str, float | None]]]:
    """Per view and arm: run metrics averaged over runs (runs are repeated measures of one paper)."""
    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for view, entry in metrics["views"].items():
        by_arm: dict[str, list[Mapping[str, Any]]] = {}
        for row in entry["per_run"]:
            by_arm.setdefault(row["arm"], []).append(row[scope])
        out[view] = {}
        for arm, rows in by_arm.items():
            keys = rows[0].keys()
            out[view][arm] = {k: _mean([r[k] for r in rows]) for k in keys}
            out[view][arm]["runs"] = len(rows)
            issues = entry.get("issues", {}).get("per_arm", {}).get(arm)
            if issues:
                out[view][arm].update({k: v for k, v in issues.items() if k != "unique_by_module"})
    return out


def _mean(values: Sequence[float | int | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None


def macro_summary(results: Sequence[Mapping[str, Any]], scope: str = "author_visible") -> dict[str, Any]:
    """Paper is the unit: average each paper's arm means, with per-paper rows. No inferential tests."""
    per_paper = [{"paper_id": r["paper_id"], "partial": r["partial"], "arms": arm_means(r["metrics"], scope)} for r in results]
    macro: dict[str, dict[str, dict[str, Any]]] = {}
    for row in per_paper:
        for view, arms in row["arms"].items():
            for arm, values in arms.items():
                macro.setdefault(view, {}).setdefault(arm, {}).setdefault("_rows", []).append(values)
    for view in macro:
        for arm, holder in macro[view].items():
            rows = holder.pop("_rows")
            keys = dict.fromkeys(k for r in rows for k in r)
            macro[view][arm] = {"papers": len(rows), **{k: _mean([r.get(k) for r in rows]) for k in keys}}
    return {"scope": scope, "unit": "paper (mean over papers of the per-paper mean over runs)", "papers": len(results),
            "macro": macro, "per_paper": per_paper}


SUMMARY_FIELDS = ("variants", "supported", "supported_rate", "supported_of_resolved", "unresolved_rate", "contradicted",
                  "supported_material", "supported_beneficial_suggestions", "serious_harms", "generic",
                  "restates_own_limitation", "output_words", "clusters_supported", "unique_supported_material")


def summary_markdown(summary: Mapping[str, Any], title: str = "Criticism judge summary") -> str:
    lines = [f"# {title}", "", "Development instrument: LLM judge labels, not validated assessments. "
             f"Scope: {summary['scope']}. Unit: {summary['unit']}. No significance tests.", ""]
    for view, arms in summary["macro"].items():
        lines += [f"## {view}", "", "| arm | papers | " + " | ".join(SUMMARY_FIELDS) + " |",
                  "|---" * (len(SUMMARY_FIELDS) + 2) + "|"]
        for arm, values in arms.items():
            lines.append(f"| {arm} | {values['papers']} | " + " | ".join(_fmt(values.get(k)) for k in SUMMARY_FIELDS) + " |")
        lines.append("")
    lines += ["## Per paper", ""]
    for paper in summary["per_paper"]:
        lines.append(f"### {paper['paper_id']}{' (PARTIAL)' if paper['partial'] else ''}")
        for view, arms in paper["arms"].items():
            lines.append(f"- {view}: " + "; ".join(
                f"{arm}: supported {_fmt(v.get('supported'))}/{_fmt(v.get('variants'))}, material {_fmt(v.get('supported_material'))}, "
                f"contradicted {_fmt(v.get('contradicted'))}, harms {_fmt(v.get('serious_harms'))}" for arm, v in arms.items()))
        lines.append("")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    return "–" if value is None else f"{value:.2f}" if isinstance(value, float) and not float(value).is_integer() else str(int(value)) if isinstance(value, float) else str(value)


# ---------------------------------------------------------------- orchestration

class StageFailure(RuntimeError):
    """A model stage failed; recorded as a failure rather than treated as invalid input."""


def _normalizer(spec: str | Any, cache: Path, timeout: int, stages: list[StageRecord]) -> Callable[[str], Mapping[str, Any]]:
    """Tool-free normalization of a free-text report with normalization.py's prompt, cached here."""
    from .normalization import ReviewInventory, _assemble_inventory, _instruction

    def normalize(text: str) -> Mapping[str, Any]:
        backend = make_backend(spec, tools=False, timeout=timeout) if isinstance(spec, str) else spec
        instruction = _instruction()
        try:
            inventory, stage = cached_stage(cache, "normalize", {"protocol": NORMALIZE_STAGE, "instruction": instruction,
                                                                 "evidence_sha": _hash(text)}, ReviewInventory,
                                            lambda: backend.generate(instruction, text, ReviewInventory), backend)
        except Exception as exc:
            stages.append(_failed("normalize", exc, backend))
            raise StageFailure(f"normalization failed: {type(exc).__name__}: {exc}") from exc
        stages.append(stage)
        return _assemble_inventory(text, inventory, backend)
    return normalize


def _labels(specs: Iterable[str]) -> dict[str, str]:
    """Judge label per spec: the backend family, or the full spec when a family repeats."""
    specs = list(specs)
    families = [s.split(":", 1)[0] for s in specs]
    return {s: f if families.count(f) == 1 else s for s, f in zip(specs, families)}


def judge_paper(paper_id: str, manuscript: Path, arms: Sequence[tuple[str, Path]], out: Path, *,
                supplements: Sequence[Path] = (), judges: Sequence[str] = DEFAULT_JUDGES, clusterer: str | Any = DEFAULT_CLUSTERER,
                normalizer: str | Any = DEFAULT_NORMALIZER, judge_factories: Mapping[str, Callable[[], Any]] | None = None,
                seed: int = DEFAULT_SEED, batch_size: int = 7, cluster_batch_size: int = 120, timeout: int = 3600,
                workers: int = 2, skip_judging: bool = False, progress: Callable[[str], None] = lambda _: None) -> dict[str, Any]:
    """Extract, cluster and judge one paper's arms; write result.json and summary.md under `out`."""
    out = out.resolve()
    cache = out / "cache"
    sources = [ingest(manuscript)] + [ingest(p, "supplement") for p in supplements]
    stages: dict[str, list[StageRecord]] = {"extraction": [], "clustering": []}
    normalize = _normalizer(normalizer, cache, timeout, stages["extraction"])
    runs: list[RunOutput] = []
    variants: list[Variant] = []
    origins: dict[str, Origin] = {}
    failures: list[str] = []
    counters: dict[str, int] = {}
    for arm, path in arms:
        counters[arm] = counters.get(arm, 0) + 1
        label = f"{arm}/{counters[arm]}"
        try:
            run, found, found_origins = extract_arm(arm, label, path, sources, normalize)
        except StageFailure as exc:
            failures.append(f"extraction {label} ({path}): {exc}")
            continue
        for v in found:
            if v.id in origins:
                raise ValueError(f"{path}: variant {v.id} already extracted from {origins[v.id].path}; was a file given twice?")
        runs.append(run)
        variants += found
        origins.update({o.variant_id: o for o in found_origins})
        progress(f"extracted {len(found)} variants from {label}")
    clusters = None
    cluster_record: dict[str, Any] = {}
    try:
        backend = make_backend(clusterer, tools=False, timeout=timeout) if isinstance(clusterer, str) else clusterer
        clusters, cluster_stages, cluster_record = cluster_variants(variants, backend, cache, seed=seed, batch_size=cluster_batch_size)
        stages["clustering"] += cluster_stages
        if any(b.get("repairs") for b in cluster_record.get("batches", [])) or (cluster_record.get("merge") or {}).get("repairs"):
            failures.append("clustering needed deterministic repair after a failed retry; see clustering record")
    except Exception as exc:
        stages["clustering"].append(_failed("cluster", exc, clusterer))
        failures.append(f"clustering failed: {type(exc).__name__}: {exc}")
        clusters = None
    judgments: dict[str, dict[str, dict[str, Any]]] = {}
    factories = dict(judge_factories or {s: (lambda s=s: make_backend(s, tools=True, timeout=timeout)) for s in judges})
    labels = _labels(factories)
    identities = {labels[s]: f().identity for s, f in factories.items()}
    if not skip_judging:
        for spec, factory in factories.items():
            label = labels[spec]
            rows, judge_stages, missing = judge_variants(variants, sources, factory, cache, seed=seed, batch_size=batch_size,
                                                         workers=workers, progress=progress)
            judgments[label] = rows
            stages[f"judge:{label}"] = judge_stages
            if missing:
                failures.append(f"judge {label}: {len(missing)} variant(s) not judged")
    metrics = compute_metrics(variants, origins, runs, clusters, judgments)
    # A failed judge batch whose variants were judged on retry stays on record without making the result partial.
    partial = bool(failures)
    result = {
        "protocol": PROTOCOL, "paper_id": paper_id, "partial": partial, "failures": failures,
        "sources": [{"id": s.id, "path": s.path, "kind": s.kind, "sha256": s.sha256} for s in sources],
        "judges": identities, "clusterer": getattr(clusterer, "identity", clusterer),
        "normalizer": getattr(normalizer, "identity", normalizer),
        "seed": seed, "runs": [r.model_dump() for r in runs], "variants": [v.model_dump() for v in variants],
        "origins": {k: o.model_dump() for k, o in origins.items()}, "clusters": clusters, "clustering": cluster_record,
        "judgments": judgments, "stages": {k: [s.model_dump(mode="json") for s in v] for k, v in stages.items()},
        "metrics": metrics,
    }
    _write_atomic(out / "result.json", json.dumps(result, indent=2, ensure_ascii=False, default=str))
    summary = macro_summary([result])
    _write_atomic(out / "summary.md", summary_markdown(summary, f"Criticism judge: {paper_id}"))
    return result


# ---------------------------------------------------------------- calibration

class ProbeCriticism(BaseModel):
    claim: str
    rationale: str
    remedy: str | None = None
    quotes: list[str] = Field(default_factory=list)


class ProbeSource(BaseModel):
    path: str
    kind: Literal["manuscript", "supplement"]


class ProbeExpected(BaseModel):
    correctness: Literal["supported", "contradicted", "unresolved"]
    # Other labels a judge may legitimately reach, e.g. contradicted for a false claim that only
    # an opened external source can settle.
    also_acceptable: list[Literal["supported", "contradicted", "unresolved"]] = Field(default_factory=list)
    materiality: int | None = Field(default=None, ge=0, le=3)
    remedy_necessity: str | None = None


class Probe(BaseModel):
    id: str
    case: str
    sources: list[ProbeSource]
    criticism: ProbeCriticism
    expected: ProbeExpected
    label_basis: str
    label_source: str
    variant_of: str | None = None
    manipulation: Literal["none", "confident_rationale", "authority_appeal", "irrelevant_detail"] = "none"


class ProbeSet(BaseModel):
    version: Literal[1]
    probes: list[Probe]


def _probe_batches(probes: Sequence[tuple[Probe, Variant]], size: int) -> list[list[Variant]]:
    """Batches in which no two members of one variant family meet, so the judge cannot compare them."""
    family = {p.id: p.variant_of or p.id for p, _ in probes}
    batches: list[list[tuple[str, Variant]]] = []
    for probe, variant in sorted(probes, key=lambda pv: (family[pv[0].id], pv[0].id)):
        home = next((b for b in batches if len(b) < size and all(f != family[probe.id] for f, _ in b)), None)
        if home is None:
            batches.append(home := [])
        home.append((family[probe.id], variant))
    return [[v for _, v in b] for b in batches]


def calibrate(probe_paths: Path | Sequence[Path], out: Path, *, judges: Sequence[str] = DEFAULT_JUDGES, root: Path | None = None,
              judge_factories: Mapping[str, Callable[[], Any]] | None = None, batch_size: int = 6, timeout: int = 3600,
              workers: int = 2, seed: int = DEFAULT_SEED, progress: Callable[[str], None] = lambda _: None) -> dict[str, Any]:
    probe_paths = [probe_paths] if isinstance(probe_paths, Path) else list(probe_paths)
    sets = [ProbeSet.model_validate_json(path.read_text(encoding="utf-8")) for path in probe_paths]
    probe_set = ProbeSet(version=sets[0].version, probes=[probe for s in sets for probe in s.probes])
    probe_path = probe_paths[0]
    ids = [p.id for p in probe_set.probes]
    if len(ids) != len(set(ids)):
        raise ValueError("probe ids must be unique")
    unknown = [p.variant_of for p in probe_set.probes if p.variant_of and p.variant_of not in ids]
    if unknown:
        raise ValueError(f"variant_of refers to unknown probes: {unknown}")
    root = (root or _repo_root(probe_path)).resolve()
    out = out.resolve()
    cache = out / "cache"
    factories = dict(judge_factories or {s: (lambda s=s: make_backend(s, tools=True, timeout=timeout)) for s in judges})
    names = _labels(factories)
    by_case: dict[str, list[Probe]] = {}
    for probe in probe_set.probes:
        by_case.setdefault(probe.case, []).append(probe)
    labels: dict[str, dict[str, dict[str, Any] | None]] = {}
    stages: dict[str, list[dict[str, Any]]] = {}
    failures: list[str] = []
    for case, probes in by_case.items():
        specs = {(s.path, s.kind) for p in probes for s in p.sources}
        if len({frozenset((s.path, s.kind) for s in p.sources) for p in probes}) > 1:
            raise ValueError(f"case {case}: probes of one case must share their sources")
        ordered = sorted(specs, key=lambda s: (s[1] != "manuscript", s[0]))
        sources = [ingest(root / path, kind) for path, kind in ordered]
        pairs = []
        for probe in probes:
            c = probe.criticism
            content = {"claim": c.claim.strip(), "rationale": c.rationale.strip(), "remedy": (c.remedy or "").strip() or None,
                       "quotes": [q for q in c.quotes if q.strip()], "external": []}
            pairs.append((probe, Variant(id=_variant_id(_hash(case), probe.id, content), **content)))
        for spec, factory in factories.items():
            label = names[spec]
            rows, judge_stages, missing = judge_variants([v for _, v in pairs], sources, factory, cache, seed=seed,
                                                         batch_size=batch_size, workers=workers,
                                                         batches=_probe_batches(pairs, batch_size), progress=progress)
            stages.setdefault(label, []).extend(s.model_dump(mode="json") for s in judge_stages)
            if missing:
                failures.append(f"{label} case {case}: {len(missing)} probe(s) not judged")
            for probe, variant in pairs:
                labels.setdefault(label, {})[probe.id] = rows.get(variant.id)
    report = calibration_report(probe_set.probes, labels)
    result = {"protocol": PROTOCOL, "probes": [str(path) for path in probe_paths],
              "probe_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in probe_paths},
              "judges": {names[s]: f().identity for s, f in factories.items()},
              "partial": bool(failures), "failures": failures, "judgments": labels, "stages": stages, "report": report}
    _write_atomic(out / "calibration.json", json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return result


def _repo_root(path: Path) -> Path:
    for parent in path.resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def calibration_report(probes: Sequence[Probe], labels: Mapping[str, Mapping[str, Mapping[str, Any] | None]]) -> dict[str, Any]:
    expected_labels = ("supported", "contradicted", "unresolved")
    judged_labels = (*CORRECTNESS, "not_judged")
    report: dict[str, Any] = {}
    for family, rows in labels.items():
        matrix = {e: {j: 0 for j in judged_labels} for e in expected_labels}
        for probe in probes:
            row = rows.get(probe.id)
            matrix[probe.expected.correctness][row["correctness"] if row else "not_judged"] += 1
        judged = [(p, rows[p.id]) for p in probes if rows.get(p.id)]
        materiality = [abs(r["materiality"] - p.expected.materiality) for p, r in judged if p.expected.materiality is not None]
        necessity = [r["remedy_necessity"] == p.expected.remedy_necessity for p, r in judged if p.expected.remedy_necessity]
        # Every variant_of pair counts; manipulation "none" pairs act as neutral-rewrite controls in by_manipulation.
        pairs = [(p, rows.get(p.id), rows.get(p.variant_of)) for p in probes if p.variant_of]
        compared = [(p, a, b) for p, a, b in pairs if a and b]
        persuasion: dict[str, Any] = {"pairs": len(pairs), "compared": len(compared),
                                      "label_changed": sum(a["correctness"] != b["correctness"] for _, a, b in compared),
                                      "changed_to_supported": sum(a["correctness"] == "supported" != b["correctness"] for _, a, b in compared),
                                      "materiality_changed": sum(a["materiality"] != b["materiality"] for _, a, b in compared),
                                      "by_manipulation": {}}
        persuasion["rate"] = _ratio(persuasion["label_changed"], len(compared))
        for kind in sorted({p.manipulation for p, _, _ in compared}):
            subset = [(a, b) for p, a, b in compared if p.manipulation == kind]
            persuasion["by_manipulation"][kind] = {"compared": len(subset), "label_changed": sum(a["correctness"] != b["correctness"] for a, b in subset)}
        persuasion["changes"] = [{"probe": p.id, "base": p.variant_of, "manipulation": p.manipulation,
                                  "base_label": b["correctness"], "manipulated_label": a["correctness"]}
                                 for p, a, b in compared if a["correctness"] != b["correctness"]]
        accepted = lambda p, r: r["correctness"] == p.expected.correctness or r["correctness"] in p.expected.also_acceptable
        correct = sum(accepted(p, r) for p, r in judged)
        report[family] = {"probes": len(probes), "judged": len(judged), "accuracy": _ratio(correct, len(judged)),
                          "confusion": matrix,
                          "supported_false_claims": sum(p.expected.correctness == "contradicted" and r["correctness"] == "supported" for p, r in judged),
                          "materiality_mean_abs_error": _mean(materiality), "remedy_necessity_agreement": _ratio(sum(necessity), len(necessity)),
                          "persuasion_sensitivity": persuasion,
                          "errors": [{"probe": p.id, "expected": p.expected.correctness, "judged": r["correctness"],
                                      "label_basis": p.label_basis} for p, r in judged if not accepted(p, r)]}
    return report


def calibration_text(report: Mapping[str, Any]) -> str:
    lines = []
    for family, values in report.items():
        lines += [f"{family}: accuracy {_fmt(values['accuracy'])} on {values['judged']}/{values['probes']} judged probes; "
                  f"false claims supported {values['supported_false_claims']}"]
        header = ["expected \\ judged", *next(iter(values["confusion"].values())).keys()]
        lines.append("  " + " | ".join(f"{h:>14}" for h in header))
        for expected, row in values["confusion"].items():
            lines.append("  " + " | ".join(f"{c:>14}" for c in [expected, *map(str, row.values())]))
        p = values["persuasion_sensitivity"]
        lines.append(f"  persuasion sensitivity: {p['label_changed']}/{p['compared']} manipulated probes changed label "
                     f"({p['changed_to_supported']} to supported); materiality changed {p['materiality_changed']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def _arm(value: str) -> tuple[str, Path]:
    name, sep, path = value.partition("=")
    if not sep or not name or not path:
        raise argparse.ArgumentTypeError("--arm takes NAME=PATH")
    return name, Path(path)


def _progress(quiet: bool) -> Callable[[str], None]:
    import sys
    return (lambda _: None) if quiet else (lambda message: print(message, file=sys.stderr, flush=True))


def _judge_command(args: argparse.Namespace) -> int:
    result = judge_paper(args.paper_id or args.manuscript.stem, args.manuscript, args.arm, args.out, supplements=args.supplement,
                         judges=args.judge or DEFAULT_JUDGES, clusterer=args.clusterer, normalizer=args.normalizer,
                         seed=args.seed, batch_size=args.batch_size, cluster_batch_size=args.cluster_batch_size,
                         timeout=args.timeout, workers=args.workers, skip_judging=args.skip_judging, progress=_progress(args.quiet))
    print(f"Wrote {'partial' if result['partial'] else 'complete'} criticism judgments to {args.out / 'result.json'}")
    for failure in result["failures"]:
        print(f"  failure: {failure}")
    return 2 if result["partial"] else 0


def _summary_command(args: argparse.Namespace) -> int:
    results = [json.loads(p.read_text(encoding="utf-8")) for p in args.results]
    summary = macro_summary(results, args.scope)
    _write_atomic(args.output, json.dumps(summary, indent=2, ensure_ascii=False))
    _write_atomic(args.output.with_suffix(".md"), summary_markdown(summary))
    print(f"Wrote {args.output} and {args.output.with_suffix('.md')}")
    return 2 if any(r["partial"] for r in results) else 0


def _calibrate_command(args: argparse.Namespace) -> int:
    result = calibrate(args.probes, args.out, judges=args.judge or DEFAULT_JUDGES, root=args.root, batch_size=args.batch_size,
                       timeout=args.timeout, workers=args.workers, seed=args.seed, progress=_progress(args.quiet))
    print(calibration_text(result["report"]))
    for failure in result["failures"]:
        print(f"failure: {failure}")
    return 2 if result["partial"] else 0


def register(subparsers: Any) -> None:
    judge = subparsers.add_parser("judge-criticisms", help="cluster and judge every criticism variant of one paper's review arms")
    judge.add_argument("--manuscript", required=True, type=Path)
    judge.add_argument("--supplement", action="append", default=[], type=Path)
    judge.add_argument("--paper-id")
    judge.add_argument("--arm", action="append", required=True, type=_arm,
                       help="NAME=PATH; repeat NAME for several runs of one arm (review.json, plain JSON, or .md/.txt human report)")
    judge.add_argument("--out", required=True, type=Path)
    judge.add_argument("--clusterer", default=DEFAULT_CLUSTERER, help="tool-free clustering model, BACKEND:MODEL:EFFORT")
    judge.add_argument("--normalizer", default=DEFAULT_NORMALIZER, help="tool-free normalizer for free-text reports, BACKEND:MODEL:EFFORT")
    judge.add_argument("--batch-size", type=int, default=7, help="variants per judge call")
    judge.add_argument("--cluster-batch-size", type=int, default=120)
    judge.add_argument("--skip-judging", action="store_true", help="extract and cluster only")
    summary = subparsers.add_parser("judge-summary", help="combine criticism-judge results across papers (paper as unit)")
    summary.add_argument("results", nargs="+", type=Path)
    summary.add_argument("--output", required=True, type=Path)
    summary.add_argument("--scope", choices=["author_visible", "published_only"], default="author_visible")
    summary.set_defaults(func=_summary_command)
    calibrate_parser = subparsers.add_parser("judge-calibrate", help="score the criticism judge against labelled probes")
    calibrate_parser.add_argument("--probes", required=True, type=Path, action="append",
                                  help="probe file; repeat to combine, e.g. with a private gitignored set")
    calibrate_parser.add_argument("--out", type=Path, default=Path("runs/judge-calibration"))
    calibrate_parser.add_argument("--root", type=Path, help="directory that probe source paths are relative to (default: repository root)")
    calibrate_parser.add_argument("--batch-size", type=int, default=6)
    for command in (judge, calibrate_parser):
        command.add_argument("--judge", action="append", help=f"BACKEND:MODEL:EFFORT, repeatable (default: {' and '.join(DEFAULT_JUDGES)})")
        command.add_argument("--seed", type=int, default=DEFAULT_SEED)
        command.add_argument("--timeout", type=int, default=3600, help="per-call timeout in seconds")
        command.add_argument("--workers", type=int, default=2, help="concurrent judge calls per family")
        command.add_argument("--quiet", action="store_true")
    judge.set_defaults(func=_judge_command)
    calibrate_parser.set_defaults(func=_calibrate_command)
