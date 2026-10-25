import hashlib
import json
import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
FENCE = runpy.run_path(str(ROOT / "eval/check_fence.py"))
FENCED_BYTES = b"%PDF-1.4 fenced submitted manuscript bytes"


@pytest.fixture
def splits(tmp_path):
    manifest = {
        "schema_version": 1,
        "cases": [
            {"id": "dev-case", "split": "development", "title": "A development paper about something else entirely",
             "doi": "10.1234/dev", "fence_sha256": []},
            {"id": "fenced-case", "split": "fenced_validation",
             "title": "Ordinary Replication of a Classic Judgment Effect",
             "doi": "10.15626/MP.2099.9999",
             "fence_sha256": [hashlib.sha256(FENCED_BYTES).hexdigest()],
             "fence_urls": ["https://osf.io/download/zzzzz/"]},
        ],
    }
    path = tmp_path / "splits.json"
    path.write_text(json.dumps(manifest))
    return path


def run(paths, splits):
    return FENCE["main"]([*map(str, paths), "--splits", str(splits)])


def test_fenced_manuscript_is_refused_by_hash(tmp_path, splits, capsys):
    manuscript = tmp_path / "renamed.pdf"
    manuscript.write_bytes(FENCED_BYTES)
    assert run([manuscript], splits) == 3
    assert "fenced-case" in capsys.readouterr().err


def test_run_directory_recording_fenced_hash_or_input_doi_is_refused(tmp_path, splits):
    run_dir = tmp_path / "runs" / "x"
    (run_dir / "inputs").mkdir(parents=True)
    (run_dir / "review.json").write_text(json.dumps({"manuscript_sha256": hashlib.sha256(FENCED_BYTES).hexdigest()}))
    assert run([run_dir], splits) == 3
    (run_dir / "review.json").unlink()
    (run_dir / "inputs" / "provenance.json").write_text(json.dumps({"doi": "https://doi.org/10.15626/mp.2099.9999"}))
    assert run([run_dir], splits) == 3


def test_fenced_citation_in_review_output_only_warns(tmp_path, splits, capsys):
    run_dir = tmp_path / "runs" / "x" / "reviews"
    run_dir.mkdir(parents=True)
    (run_dir / "review.json").write_text(json.dumps({"tool_calls": ["https://doi.org/10.15626/MP.2099.9999"]}))
    assert run([tmp_path / "runs"], splits) == 0
    assert "warning" in capsys.readouterr().err


def test_converted_text_with_fenced_title_is_refused(tmp_path, splits):
    text = tmp_path / "manuscript.txt"
    text.write_text("ORDINARY REPLICATION OF A CLASSIC\njudgment effect\n\nAbstract ...")
    assert run([text], splits) == 3


def test_development_inputs_pass_and_api_raises_only_for_fenced(tmp_path, splits):
    clean = tmp_path / "dev.txt"
    clean.write_text("A development paper about something else entirely; doi 10.1234/dev")
    assert run([clean], splits) == 0
    FENCE["assert_not_fenced"](clean, splits=splits)
    bad = tmp_path / "bad.txt"
    bad.write_text("see https://osf.io/download/zzzzz/")
    with pytest.raises(FENCE["FencedInputError"]):
        FENCE["assert_not_fenced"](bad, splits=splits)


def test_splits_manifest_copies_in_code_snapshots_are_ignored(tmp_path, splits):
    snapshot = tmp_path / "code" / "eval" / "corpus"
    snapshot.mkdir(parents=True)
    (snapshot / "splits.v1.json").write_text(splits.read_text())
    assert run([tmp_path / "code"], splits) == 0


def test_missing_manifest_is_a_usage_error(tmp_path):
    assert run([tmp_path], tmp_path / "absent.json") == 2


def test_repository_manifest_fences_at_least_ten_cases():
    fence = FENCE["load_fence"]()
    assert len(fence["ids"]) >= 10
    assert all(len(digest) == 64 for digest in fence["hashes"])


def test_identifier_prefixes_do_not_match_longer_identifiers(tmp_path, splits):
    run_dir = tmp_path / "run"
    other = run_dir / "inputs" / "manuscript.txt"
    other.parent.mkdir(parents=True)
    other.write_text("doi 10.15626/MP.2099.99991 and https://osf.io/download/zzzzzz/")
    assert run([run_dir], splits) == 0


def test_repository_split_assignments_follow_the_recorded_rule():
    splits = runpy.run_path(str(ROOT / "eval/corpus_splits.py"))
    manifest = json.loads((ROOT / "eval/corpus/splits.v1.json").read_text())
    assert splits["check"](manifest) == []
    fenced = [case for case in manifest["cases"] if case["split"] == "fenced_validation"]
    assert all(case["ordinary_empirical"] and not case["exposure"] for case in fenced)
