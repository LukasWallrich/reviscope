import importlib.util
import json
import sys
from pathlib import Path

import pytest

from reviscope.backend import Backend
from reviscope.ingest import ingest
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import Finding, MetacheckRecord, ReviewRun, RunMetadata, StageRecord, StudyMap


SCRIPT = Path(__file__).parents[1] / "eval" / "experiment_discovery.py"
QUOTE = "24 of 60 people withdrew."


@pytest.fixture
def experiment():
    spec = importlib.util.spec_from_file_location("experiment_discovery", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def issue(**updates):
    return {"description": "Report the attrition denominator to assess the result.",
            "quote": QUOTE, "location": "Results", "severity": "moderate", **updates}


@pytest.mark.parametrize("necessity", ["essential", "strengthening", "extending", "invalid", None])
def test_import_plain_preserves_general_remedy_and_valid_necessity(experiment, necessity):
    row = issue(remedy="Report the denominator.", remedy_necessity=necessity)
    finding, = experiment.import_plain({"issues": [row]}, "source")
    assert finding.claim == finding.rationale == row["description"]
    assert finding.remedy == row["remedy"]
    assert finding.remedy_necessity == (None if necessity == "invalid" else necessity)
    assert finding.severity == "minor"
    assert finding.evidence[0].source_id == "source"


def test_import_plain_preserves_older_dawes_behavior(experiment):
    rows = [issue(category="statistical_errors", subcategory="attrition"),
            issue(severity="major", remedy_necessity="essential")]
    findings = experiment.import_plain({"issues": rows}, "source")
    assert [f.id for f in findings] == ["plain:01", "plain:02"]
    assert [f.severity for f in findings] == ["minor", "major"]
    assert all(f.remedy == "" and f.remedy_necessity is None for f in findings)
    with pytest.raises(ValueError, match="partial"):
        experiment.import_plain({"issues": rows, "partial": True}, "source")


class ReplayBackend(Backend):
    version = "stub-cli"

    def __init__(self, name, model, timeout, effort):
        self.name, self.model, self.timeout, self.effort = name, model, timeout, effort
        self.calls = []

    def generate(self, instruction, evidence, response_model):
        kind = response_model.__name__
        self.calls.append((kind, instruction, evidence))
        if kind == "StudyMap":
            return StudyMap(studies=[], research_question="question", design_summary="Descriptive seed.",
                            contribution_summary="Contribution.", strengths=[])
        if kind == "VerificationResponse":
            rows = json.loads(instruction.split("CANDIDATES\n")[1].split("\nDISCIPLINE RULES")[0])
            return response_model.model_validate({"decisions": [
                {"finding_id": row["finding_id"], "status": "supported", "rationale": "Checked.",
                 "evidence": row["quoted_evidence"], "remedy_status": "supported",
                 "remedy_rationale": "Proportionate."} for row in rows]})
        if kind == "EditorialResponse":
            rows = json.loads(instruction.split("\nFINDINGS\n")[1])
            return response_model.model_validate({"decisions": [
                {"finding_id": row["id"], "disposition": "keep", "reason": "Distinct.", "severity": row["severity"]} for row in rows],
                "reconciled_overview": {"design_summary": "Descriptive seed.",
                                        "contribution_summary": "Contribution.", "strengths": []}})
        raise AssertionError(f"Unexpected model stage: {kind}")


@pytest.fixture
def backends(experiment, monkeypatch):
    created = []

    def factory(name):
        def build(model, timeout, effort):
            backend = ReplayBackend(name, model, timeout, effort)
            created.append(backend)
            return backend
        return build

    monkeypatch.setattr(experiment, "CodexBackend", factory("codex"))
    monkeypatch.setattr(experiment, "ClaudeBackend", factory("claude"))
    return created


@pytest.fixture
def documents(tmp_path):
    manuscript = tmp_path / "paper.txt"
    manuscript.write_text(QUOTE + " Manuscript context." * 100)
    supplement = tmp_path / "supplement.txt"
    supplement.write_text("Supplement: the analysis used complete cases.")
    return manuscript, supplement


def write_plain(tmp_path, sources):
    plain = tmp_path / "plain.json"
    plain.write_text(json.dumps({"sources": [{"kind": s.kind, "sha256": s.sha256} for s in sources],
                                 "stages": [{"name": "review-plain", "status": "completed"}],
                                 "generator_version": "plain-cli",
                                 "issues": [issue(remedy="Report the denominator.", remedy_necessity="essential")]}))
    return plain


def write_seed(tmp_path, sources):
    seed = ReviewRun(metadata=RunMetadata(run_id="seed", backend="codex", model="gpt-6.1-sol", effort="high",
                                         profile="social_psychology", profile_hash="old", input_hash="seed-input",
                                         output_dir=str(tmp_path), verifier_backend="codex",
                                         verifier_model="gpt-6.1-sol", verifier_effort="high"),
                     sources=sources,
                     study_map=StudyMap(studies=[], research_question="question", design_summary="Editorial summary.",
                                        contribution_summary="Contribution.", strengths=[]),
                     preliminary_study_map=StudyMap(studies=[], research_question="question",
                                                    design_summary="Descriptive seed.",
                                                    contribution_summary="Contribution.", strengths=[]),
                     candidates=[Finding(id="excluded", module="specialist", claim="Seed candidate.",
                                         rationale="Seed rationale.", remedy="Seed remedy.")],
                     metacheck=MetacheckRecord(status="completed"),
                     stages=[StageRecord(name="study_map", status="completed"),
                             StageRecord(name="metacheck", status="completed")])
    path = tmp_path / "seed.json"
    path.write_text(seed.model_dump_json())
    return path


def run_replay(experiment, monkeypatch, tmp_path, plain, arguments):
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--mode", "replay", "--plain-review", str(plain),
                                     "--out", str(out), *map(str, arguments)])
    assert experiment.main() == 0
    return ReviewRun.model_validate_json((out / "review.json").read_bytes()), json.loads((out / "experiment.json").read_text())


@pytest.mark.parametrize("plain_has_supplement", [False, True])
def test_saved_seed_matches_manuscript_kind_and_keeps_supplements(
        experiment, backends, documents, monkeypatch, tmp_path, plain_has_supplement):
    manuscript, supplement = documents
    sources = [ingest(manuscript), ingest(supplement, "supplement")]
    # General reviews can list supplements first; archived Dawes reviews have only the manuscript.
    plain = write_plain(tmp_path, list(reversed(sources)) if plain_has_supplement else sources[:1])
    seed = write_seed(tmp_path, sources)
    run, inputs = run_replay(experiment, monkeypatch, tmp_path, plain, ["--seed-review", seed])
    verifier, editorial = backends
    assert [c[0] for c in verifier.calls] == ["VerificationResponse"]
    assert [c[0] for c in editorial.calls] == ["EditorialResponse"]
    assert verifier.identity == "claude:claude-opus-5-5:high"
    assert (run.metadata.verifier_backend, run.metadata.verifier_model, run.metadata.verifier_effort) == (
        "claude", "claude-opus-5-5", "high")
    assert run.metadata.verification_relationship == "different_model_family"
    assert run.sources == sources
    assert all(sources[1].text in c[2] for b in backends for c in b.calls)
    assert [f.id for f in run.candidates] == ["plain:01"]
    assert run.findings[0].remedy == "Report the denominator."
    assert run.findings[0].remedy_necessity == "essential"
    assert run.findings[0].status == "llm_supported"
    assert run.preliminary_study_map.design_summary == "Descriptive seed."
    assert run.metacheck.status == "completed"
    assert run.stages[0].name == "study_map" and run.stages[0].status == "cached"
    assert inputs["seed_path"] == str(seed.resolve()) and inputs["seed_sha256"]
    assert inputs["verifier"] == verifier.identity and inputs["verifier_backend_version"] == "stub-cli"
    assert inputs["parallel"] == 2 and inputs["timeout"] == 3600
    assert inputs["sources"][1]["sha256"] == sources[1].sha256
    assert "general-format remedies" in inputs["adapter"]


@pytest.mark.parametrize("with_supplement", [False, True])
def test_replay_builds_only_study_map_and_records_skipped_metacheck(
        experiment, backends, documents, monkeypatch, tmp_path, with_supplement):
    manuscript, supplement = documents
    sources = [ingest(manuscript)] + ([ingest(supplement, "supplement")] if with_supplement else [])
    plain = write_plain(tmp_path, list(reversed(sources)))

    def forbidden(*args, **kwargs):
        pytest.fail("Replay must not run metacheck or specialist discovery")

    monkeypatch.setattr(ReviewPipeline, "run", forbidden)
    monkeypatch.setattr(ReviewPipeline, "_metacheck", forbidden)
    pipelines = []

    def pipeline(*args, **kwargs):
        result = ReviewPipeline(*args, **kwargs)
        pipelines.append(result)
        return result

    monkeypatch.setattr(experiment, "ReviewPipeline", pipeline)
    arguments = ["--manuscript", manuscript, "--parallel", "3", "--timeout", "123",
                 "--verifier-backend", "codex", "--verifier-model", "gpt-6-luna", "--verifier-effort", "medium"]
    if with_supplement:
        arguments += ["--supplement", supplement]
    run, inputs = run_replay(experiment, monkeypatch, tmp_path, plain, arguments)
    verifier, editorial = backends
    assert [c[0] for c in verifier.calls] == ["VerificationResponse"]
    assert [c[0] for c in editorial.calls] == ["StudyMap", "EditorialResponse"]
    assert (verifier.name, verifier.model, verifier.effort, verifier.timeout) == ("codex", "gpt-6-luna", "medium", 123)
    assert run.metadata.verifier_model == "gpt-6-luna" and run.metadata.verifier_effort == "medium"
    assert run.metadata.verification_relationship == "different_model_same_family"
    assert run.sources == sources
    assert pipelines[0].parallel == 3
    assert run.metacheck.status == "skipped"
    assert next(s for s in run.stages if s.name == "metacheck").status == "skipped"
    assert any("metacheck: skipped" in c for c in run.coverage)
    assert run.preliminary_study_map.design_summary == "Descriptive seed."
    assert inputs["seed_mode"] == "study_map" and "seed_sha256" not in inputs
    assert inputs["manuscript_path"] == str(manuscript.resolve())
    assert inputs["supplement_paths"] == ([str(supplement.resolve())] if with_supplement else [])
    assert inputs["parallel"] == 3 and inputs["timeout"] == 123
    assert inputs["verifier_backend"] == "codex" and inputs["verifier_model"] == "gpt-6-luna"
    assert inputs["verifier_effort"] == "medium" and inputs["verifier"] == verifier.identity
    if with_supplement:
        assert all(sources[1].text in c[2] for b in backends for c in b.calls)


def test_replay_rejects_different_manuscript_even_with_matching_supplement(
        experiment, backends, documents, monkeypatch, tmp_path):
    manuscript, supplement = documents
    sources = [ingest(manuscript), ingest(supplement, "supplement")]
    plain = write_plain(tmp_path, list(reversed(sources)))
    data = json.loads(plain.read_text())
    data["sources"][0]["sha256"] = sources[0].sha256
    data["sources"][1]["sha256"] = "different manuscript"
    plain.write_text(json.dumps(data))
    seed = write_seed(tmp_path, sources)
    with pytest.raises(ValueError, match="manuscripts differ"):
        run_replay(experiment, monkeypatch, tmp_path, plain, ["--seed-review", seed])
    assert all(not b.calls for b in backends)


@pytest.mark.parametrize("arguments", [[], ["--manuscript", "paper.txt", "--mode", "holistic"],
                                       ["--seed-review", "seed.json", "--supplement", "supplement.txt"]])
def test_cli_rejects_missing_or_incompatible_seed_options(experiment, monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--mode", "replay", "--plain-review", "plain.json",
                                     "--out", "out", *arguments])
    with pytest.raises(SystemExit) as exc:
        experiment.main()
    assert exc.value.code == 2
