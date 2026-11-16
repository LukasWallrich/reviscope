import json
import os
from pathlib import Path

import pytest

from reviscope import materials
from reviscope.backend import ClaudeBackend, CodexBackend, FixtureBackend, PolicyError, StagedImages, _stage
from reviscope.pipeline import ReviewPipeline
from reviscope.schemas import SourceDocument


def source(text: str) -> SourceDocument:
    return SourceDocument(id="manuscript", path="paper.md", kind="manuscript", sha256="0", text=text)


def test_links_to_repositories_are_found_once_and_preprints_are_kept_apart():
    text = ("Data: https://osf.io/AB12C/ and doi:10.17605/OSF.IO/ab12c; reviewers' link https://osf.io/xy34z/?view_only=" + "f" * 32 +
            "\nCode: github.com/lab/analysis.git, https://github.com/Lab/analysis/tree/main. Archive: 10.5281/zenodo.1234567;"
            " figshare: https://doi.org/10.6084/m9.figshare.7654321. Preprint: https://osf.io/preprints/psyarxiv/qq11r"
            " https://osf.io/preprints/ and https://github.com/orgs/lab. Split URL https://osf.io/mn5\nop/")
    assert materials.find_links([source(text)]) == [
        ("osf-preprint", "qq11r", "https://osf.io/preprints/qq11r"),
        ("osf", "ab12c", "https://osf.io/ab12c"),
        ("osf", "xy34z?view_only=" + "f" * 32, "https://osf.io/xy34z?view_only=" + "f" * 32),
        ("osf", "mn5op", "https://osf.io/mn5op"),
        ("zenodo", "1234567", "https://zenodo.org/records/1234567"),
        ("figshare", "7654321", "https://figshare.com/articles/7654321"),
        ("github", "lab/analysis", "https://github.com/lab/analysis"),
    ]


class FakeWeb:
    def __init__(self, responses):
        self.responses, self.requests = responses, []

    def __call__(self, url, limit):
        self.requests.append(url)
        body = self.responses[url]
        if isinstance(body, Exception):
            raise body
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        if len(data) > limit:
            raise materials.TooLarge(f"{len(data)} bytes")
        return data


def osf_file(name, url, size=None):
    return {"attributes": {"kind": "file", "name": name, "size": size}, "links": {"download": url}}


OSF = {
    "https://api.osf.io/v2/guids/ab12c/": {"data": {"type": "nodes", "id": "ab12c"}},
    "https://api.osf.io/v2/nodes/ab12c/files/osfstorage/": {"data": [
        osf_file("data.csv", "https://osf.io/download/d1/"),
        {"attributes": {"kind": "folder", "name": "code"}, "links": {},
         "relationships": {"files": {"links": {"related": {"href": "https://api.osf.io/v2/nodes/ab12c/files/osfstorage/code/"}}}}},
        osf_file("Response to reviewers.pdf", "https://osf.io/download/r1/"),
        osf_file("Manuscript_v2.docx", "https://osf.io/download/m1/"),
        osf_file("huge.sav", "https://osf.io/download/h1/", size=materials.MAX_FILE_BYTES + 1),
        osf_file("../../escape.R", "https://osf.io/download/e1/"),
    ], "links": {"next": None}},
    "https://api.osf.io/v2/nodes/ab12c/files/osfstorage/code/": {"data": [osf_file("analysis.R", "https://osf.io/download/c1/")], "links": {}},
    "https://api.osf.io/v2/nodes/ab12c/children/": {"data": [], "links": {}},
    "https://osf.io/download/d1/": b"id,score\n1,3\n",
    "https://osf.io/download/c1/": b"summary(lm(score ~ 1))\n",
    "https://osf.io/download/e1/": b"x <- 1\n",
    "https://zenodo.org/api/records/1234567": ConnectionError("offline"),
}


def test_linked_materials_are_downloaded_with_limits_skips_and_reuse(tmp_path):
    web = FakeWeb(OSF)
    text = "Materials at https://osf.io/ab12c and 10.5281/zenodo.1234567"
    record = materials.fetch_materials([source(text)], tmp_path, fetch=web)
    osf, zenodo = record.sources
    assert sorted(f.path for f in osf.files) == ["osf-ab12c/code/analysis.R", "osf-ab12c/data.csv", "osf-ab12c/escape.R"]
    assert (tmp_path / "materials/osf-ab12c/data.csv").read_bytes() == b"id,score\n1,3\n"
    reasons = {skip.name: skip.reason for skip in osf.skipped}
    assert "peer-review" in reasons["Response to reviewers.pdf"] and "version of the manuscript" in reasons["Manuscript_v2.docx"]
    assert "file limit" in reasons["huge.sav"] and "https://osf.io/download/r1/" not in web.requests
    assert osf.status == "partial" and zenodo.status == "failed" and "offline" in zenodo.error
    index = materials.index_text(record)
    assert "materials/osf-ab12c/data.csv" in index and "not downloaded: huge.sav" in index
    requests = len(web.requests)
    again = materials.fetch_materials([source(text)], tmp_path, fetch=web)
    assert len(web.requests) == requests and again.sources == record.sources  # reused, nothing downloaded
    assert materials.fetch_materials([source("no links here")], tmp_path, fetch=web).status == "none_linked"


def test_materials_are_staged_read_only_with_an_index(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("a\n1\n")
    call = tmp_path / "call"
    call.mkdir()
    _stage(call, StagedImages(files={}, materials={"osf-ab12c/data.csv": data}, materials_index="MATERIALS INDEX"))
    staged = call / "materials/osf-ab12c/data.csv"
    assert staged.read_text() == "a\n1\n" and not os.access(staged, os.W_OK)
    assert (call / "materials/INDEX.md").read_text().startswith("MATERIALS INDEX")
    with pytest.raises(ValueError, match="leaves its directory"):
        _stage(call, StagedImages(files={}, materials={"../x.csv": data}))


def test_review_and_verification_calls_receive_materials_and_cache_on_them(tmp_path, monkeypatch):
    class Recording(FixtureBackend):
        name = "recording"
        calls = []

        def generate(self, instruction, evidence, response_model, images=None):
            Recording.calls.append((response_model.__name__, images))
            return super().generate(instruction, evidence, response_model, images)

    paper = tmp_path / "paper.md"
    paper.write_text("# Study\n\nParticipants were recruited from the university pool. Data: https://osf.io/ab12c\n" + "Context. " * 200)
    monkeypatch.setattr(materials, "http_get", FakeWeb(OSF))
    run = ReviewPipeline(Recording(), run_metacheck=False).run(paper, output_dir=tmp_path / "run")
    assert run.materials.status == "fetched" and any("materials:" in item for item in run.coverage)
    staged = [images for model, images in Recording.calls if model in {"DiscoveryResponse", "VerificationResponse"}]
    assert staged and all(images and "osf-ab12c/data.csv" in images.materials for images in staged)
    assert "MATERIALS LINKED FROM THE MANUSCRIPT" in staged[0].materials_index
    review = next(s for s in run.stages if s.name.startswith("review-"))
    assert "materials" in review.key_components["inputs"]
    assert "Linked materials" in (tmp_path / "run/audit.md").read_text()
    skipped = ReviewPipeline(Recording(), run_metacheck=False, fetch_materials=False).run(paper, output_dir=tmp_path / "off")
    assert skipped.materials.status == "skipped"


def test_shell_network_is_a_claude_allowlist_and_refused_for_codex(tmp_path):
    claude = ClaudeBackend(shell_network=True).command(tmp_path)
    network = json.loads(claude[claude.index("--settings") + 1])["sandbox"]["network"]
    assert network["strictAllowlist"] and "api.crossref.org" in network["allowedDomains"] and "*.osf.io" in network["allowedDomains"]
    assert ClaudeBackend(shell_network=True).identity != ClaudeBackend().identity
    with pytest.raises(PolicyError, match="not available for Codex"):
        CodexBackend("gpt-6-luna", shell_network=True).check_policy()
    with pytest.raises(ValueError):
        ClaudeBackend(tools=False, shell_network=True)
