"""Validate the eval-only criticism calibration probes (eval/probes/criticism_probes.v1.json)."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from reviscope.ingest import ingest
from reviscope.verification import verify_quote

REPO = Path(__file__).parents[1]
PROBES = REPO / "eval" / "probes" / "criticism_probes.v1.json"
SOURCES = REPO / "eval" / "probes" / "sources"

PROBE_KEYS = {"id", "case", "sources", "criticism", "expected", "label_basis", "label_source", "variant_of", "manipulation"}
CRITICISM_KEYS = {"claim", "rationale", "remedy", "quotes"}
EXPECTED_KEYS = {"correctness", "materiality", "remedy_necessity"}
CORRECTNESS = {"supported", "contradicted", "unresolved"}
NECESSITY = {"essential", "strengthening", "extending", None}
MANIPULATIONS = {"none", "confident_rationale", "authority_appeal", "irrelevant_detail"}
KINDS = {"manuscript", "supplement"}


def _load():
    return json.loads(PROBES.read_text())


PRIVATE = Path(__file__).parents[1] / "eval" / "probes" / "private" / "criticism_probes.owner.v1.json"


def _probes():
    """Public probes plus the gitignored owner probes when present on this machine."""
    private = json.loads(PRIVATE.read_text(encoding="utf-8"))["probes"] if PRIVATE.is_file() else []
    return _load()["probes"] + private


def test_schema():
    data = _load()
    assert set(data) == {"version", "probes"} and data["version"] == 1
    for probe in data["probes"]:
        assert set(probe) == PROBE_KEYS, probe.get("id")
        assert isinstance(probe["id"], str) and probe["id"]
        assert isinstance(probe["case"], str) and probe["case"]
        assert probe["sources"], probe["id"]
        for source in probe["sources"]:
            assert set(source) == {"path", "kind"} and source["kind"] in KINDS
            path = Path(source["path"])
            assert not path.is_absolute() and ".." not in path.parts
            assert source["path"].startswith("eval/probes/sources/"), "sources must be materialized copies"
        criticism, expected = probe["criticism"], probe["expected"]
        assert set(criticism) == CRITICISM_KEYS and EXPECTED_KEYS <= set(expected) <= EXPECTED_KEYS | {"also_acceptable"}
        assert set(expected.get("also_acceptable", [])) <= CORRECTNESS - {expected["correctness"]}
        assert criticism["claim"].strip() and criticism["rationale"].strip()
        assert criticism["remedy"] is None or criticism["remedy"].strip()
        assert criticism["quotes"] and all(isinstance(q, str) and q.strip() for q in criticism["quotes"])
        assert expected["correctness"] in CORRECTNESS
        assert expected["materiality"] in {0, 1, 2, 3, None}
        assert expected["remedy_necessity"] in NECESSITY
        assert probe["label_basis"].strip() and probe["label_source"].strip()
        assert probe["manipulation"] in MANIPULATIONS


def test_materiality_and_remedy_labelled_only_for_supported_criticisms():
    for probe in _probes():
        if probe["expected"]["correctness"] != "supported":
            assert probe["expected"]["materiality"] is None, probe["id"]
            assert probe["expected"]["remedy_necessity"] is None, probe["id"]


def test_ids_unique():
    ids = [probe["id"] for probe in _probes()]
    assert len(ids) == len(set(ids))


def test_variants_hold_substance_constant():
    by_id = {probe["id"]: probe for probe in _probes()}
    variants = [probe for probe in by_id.values() if probe["variant_of"] is not None]
    assert len(variants) >= 6
    for probe in by_id.values():
        assert (probe["variant_of"] is None) == (probe["manipulation"] == "none"), probe["id"]
    for variant in variants:
        base = by_id.get(variant["variant_of"])
        assert base is not None, f"{variant['id']} references a missing base"
        assert base["variant_of"] is None, "variants must reference a base probe"
        assert variant["expected"] == base["expected"]
        assert variant["case"] == base["case"] and variant["sources"] == base["sources"]
        for key in ("claim", "remedy", "quotes"):
            assert variant["criticism"][key] == base["criticism"][key], (variant["id"], key)
        assert variant["criticism"]["rationale"] != base["criticism"]["rationale"]
    assert {v["expected"]["correctness"] for v in variants} == CORRECTNESS, "variants should mix labels"


def test_label_and_size_counts():
    probes = _probes()
    counts = Counter(probe["expected"]["correctness"] for probe in probes)
    assert 30 <= len(probes) <= 48
    assert counts["contradicted"] >= 13 and counts["supported"] >= 14 and counts["unresolved"] >= 5
    supported = [p for p in probes if p["expected"]["correctness"] == "supported"]
    assert any(p["expected"]["materiality"] in {0, 1} for p in supported), "needs correct-but-immaterial probes"
    assert any(p["expected"]["remedy_necessity"] == "extending" for p in supported), "needs disproportionate remedies"


def test_owner_probes_never_enter_the_public_file():
    assert not any(p["case"] == "owner-negativity" for p in _load()["probes"])


def test_owner_case_is_separable():
    owner = [p for p in _probes() if p["case"] == "owner-negativity"]
    if not PRIVATE.is_file():
        pytest.skip("private owner probes not present")
    assert owner and all(all("owner-negativity/" in s["path"] for s in p["sources"]) for p in owner)
    assert all(all("owner-negativity/" not in s["path"] for s in p["sources"]) for p in _probes() if p["case"] != "owner-negativity")


def _materialized():
    manifest = SOURCES / "manifest.json"
    return json.loads(manifest.read_text()) if manifest.is_file() else None


def test_materialized_sources_match_recorded_hashes():
    manifest = _materialized()
    if manifest is None:
        pytest.skip("probe sources not materialized; run eval/probes/materialize_sources.py")
    for target, record in manifest.items():
        assert hashlib.sha256((SOURCES / target).read_bytes()).hexdigest() == record["sha256"], target


def test_quotes_anchor_in_materialized_sources():
    if _materialized() is None:
        pytest.skip("probe sources not materialized; run eval/probes/materialize_sources.py")
    texts: dict[str, str] = {}
    unanchored = []
    for probe in _probes():
        sources = []
        for source in probe["sources"]:
            path = source["path"]
            if path not in texts:
                texts[path] = ingest(REPO / path, kind=source["kind"]).text
            sources.append({"source_id": path, "text": texts[path]})
        unanchored += [(probe["id"], quote) for quote in probe["criticism"]["quotes"]
                       if verify_quote(quote, sources).status != "supported"]
    assert not unanchored
