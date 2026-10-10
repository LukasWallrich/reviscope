import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1] / "eval"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


workspace = _load("validation_workspace", EVAL / "validation_workspace.py")
owner_packet = workspace.op
packet_tests = _load("packet_tests_for_workspace", Path(__file__).resolve().parent / "test_owner_packet.py")

# A synthetic manuscript: every topic of the synthetic result is quoted except the preregistration
# and the sample, whose quotations do not occur in it.
MANUSCRIPT = """# A synthetic study of nothing in particular

We report Quoted passage about the causal claim. The design follows convention.

Our analysis shows Quoted passage about the effect size. A second sentence follows here.

Quoted passage about the power analysis. The exclusion rule text: Quoted passage about the exclusion rule.
"""
SUPPLEMENT = """Supplementary material.

Here is Quoted passage about the manipulation check. Nothing else of note appears in this file.
"""
UNFOUND = {"the sample", "the preregistration"}


@pytest.fixture
def setup(tmp_path):
    path, result, topics = packet_tests.synthetic_result(tmp_path)
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(MANUSCRIPT)
    supplement = tmp_path / "supplement.txt"
    supplement.write_text(SUPPLEMENT)
    return path, result, topics, manuscript, supplement


class Parsed(HTMLParser):
    VOID = {"meta", "input", "br", "hr", "img", "link"}

    def __init__(self):
        super().__init__()
        self.stack, self.radios, self.external, self.ids, self.scripts = [], {}, [], [], []
        self._script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in self.VOID:
            self.stack.append(tag)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "input" and attrs.get("type") == "radio":
            self.radios.setdefault(attrs["name"], []).append(attrs["value"])
        if tag == "script":
            self._script = []
        for key in ("src", "href"):
            if attrs.get(key) and not attrs[key].startswith("#"):
                self.external.append(attrs[key])

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, f"misnested </{tag}> in {self.stack}"
        self.stack.pop()
        if tag == "script":
            self.scripts.append("".join(self._script))
            self._script = None

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)


def parse(document):
    parsed = Parsed()
    parsed.feed(document)
    parsed.close()
    assert parsed.stack == [], f"unclosed {parsed.stack}"
    return parsed


def embedded(document, element_id):
    return json.loads(re.search(rf'<script type="application/json" id="{element_id}">(.*?)</script>', document, re.S).group(1))


def test_workspace_parses_anchors_quotes_and_shares_the_packet_id(setup, tmp_path):
    path, result, topics, manuscript, supplement = setup
    out = tmp_path / "workspace.html"
    meta = workspace.build(path, manuscript, out, [supplement], seed=7)
    document = out.read_text()
    parsed = parse(document)
    assert len(set(parsed.ids)) == len(parsed.ids)
    assert parsed.external == [] and not re.search(r"https?://|@import|url\(", document)
    # One label form: four scales with their keyboard shortcuts, and the grouping question.
    assert parsed.radios["f-correctness"] == ["correct", "partly_correct", "incorrect", "cannot_tell"]
    assert parsed.radios["f-materiality"] == ["0", "1", "2", "3"]
    assert len(parsed.radios["f-remedy"]) == 5 and len(parsed.radios["f-act"]) == 3
    assert parsed.radios["g-same"] == parsed.radios["c-same"] == ["yes", "split"]
    assert 'aria-keyshortcuts="q"' in document and 'aria-keyshortcuts="z"' in document

    # Same selection and packet id as the one-page packet.
    packet = owner_packet.build(path, tmp_path / "packet.html", seed=7)
    assert meta["packet_id"] == packet["packet_id"] and meta["variant_ids"] == packet["variant_ids"]
    page_meta = embedded(document, "packet-meta")
    assert page_meta["packet_id"] == packet["packet_id"] and page_meta["labels_format"] == owner_packet.LABELS_FORMAT
    assert page_meta["result_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

    data = embedded(document, "workspace-data")
    assert [s["title"] for s in data["sources"]] == ["Manuscript", "Supplement"]
    assert data["sources"][0]["text"].startswith("# A synthetic study")
    shown = [v for issue in data["issues"] for v in issue["variants"]]
    assert sorted(v["id"] for v in shown) == meta["variant_ids"]
    for variant in shown:
        topic = topics[variant["id"]]
        (quote,) = variant["quotes"]
        if topic in UNFOUND:
            assert quote["src"] is None and "s" not in quote
            continue
        source = data["sources"][quote["src"]]
        assert source["text"][quote["s"]:quote["e"]] == f"Quoted passage about {topic}."
        assert quote["src"] == (1 if topic == "the manipulation check" else 0)
        # The quote lies inside a paragraph block of its source.
        assert any(b[0] <= quote["s"] and quote["e"] <= b[1] and b[2] == "p" for b in source["blocks"])
    assert meta["quotes"] == len(shown) and meta["quotes_anchored"] == sum(topics[v["id"]] not in UNFOUND for v in shown)


def test_elided_and_unfound_quotations(tmp_path):
    sources = [{"title": "Manuscript", "file": "m.md", "text": MANUSCRIPT, "blocks": workspace._blocks(MANUSCRIPT, False, False)}]
    out = workspace.anchor_quotes(["We report Quoted passage about ... causal claim. The design follows", "Not in the paper at all.",
                                   "Our   analysis\nshows"], sources)
    assert out[0]["src"] == 0 and out[0]["el"] and MANUSCRIPT[out[0]["s"]:out[0]["e"]].startswith("We report")
    assert out[1] == {"t": "Not in the paper at all.", "src": None}
    assert MANUSCRIPT[out[2]["s"]:out[2]["e"]] == "Our analysis shows" and not out[2]["el"]


def test_pdf_text_keeps_paragraphs_pages_and_tables():
    full = "This line of running text is long enough to count as a full line of the page body ok"
    text = "\n".join(["[Page 1]", "A heading", full, full, "the end of it.", full, "a second paragraph ends.", "",
                      "[Page 2]", "Col A  1.0", "Col B  2.0", "Col C  3.0", full, "closing words."])
    blocks = workspace._blocks(text, paged=True, line_paragraphs=False)
    kinds = [(b[2], b[3], text[b[0]:b[1]].split("\n")[0][:12]) for b in blocks]
    assert kinds == [("page", 1, "[Page 1]"), ("p", 1, "A heading"), ("p", 1, full[:12]), ("p", 1, full[:12]),
                     ("page", 2, "[Page 2]"), ("lines", 2, "Col A  1.0"), ("p", 2, full[:12])]
    assert text[blocks[2][0]:blocks[2][1]].endswith("the end of it.")
    assert workspace._page_at(blocks, text.index("Col B")) == 2


def test_workspace_leaks_nothing_and_allows_manuscript_words(setup, tmp_path):
    path, result, topics, manuscript, supplement = setup
    # The manuscript may use a severity or arm word; that reveals nothing.
    manuscript.write_text(MANUSCRIPT + "\nA major limitation, discussed for the armalpha condition.\n")
    out = tmp_path / "workspace.html"
    workspace.build(path, manuscript, out, [supplement], seed=3)
    document = out.read_text()
    lowered = document.casefold()
    for term in ["modzeta", "catomega", "llmstatusword", "plainstatusword", "secretpath", "famone", "famtwo", "stubjudge",
                 "judgeexplain", "clusterlabel", "critical", "supported", "contradicted", "quote_anchoring", "severity"]:
        assert term not in lowered, term
    data = embedded(document, "workspace-data")
    assert not {"origins", "judgments", "runs", "clusters", "metrics"} & (set(data) | set(embedded(document, "packet-meta")))
    for variant in (v for issue in data["issues"] for v in issue["variants"]):
        assert set(variant) == {"id", "label", "claim", "rationale", "remedy", "external", "quotes"}
    allowed = [s["text"] for s in data["sources"]]
    assert owner_packet.leaks(document, result, fixed=workspace.template_text(), allowed=allowed) == []
    assert owner_packet.leaks(document + "<p>modzeta</p>", result, fixed=workspace.template_text(), allowed=allowed) == ["modzeta"]


def test_build_refuses_a_leaking_workspace(setup, tmp_path, monkeypatch):
    path, result, topics, manuscript, supplement = setup
    original = owner_packet.packet_content

    def leaking(*args):
        content = original(*args)
        content["meta"]["note"] = "llmstatusword"
        return content
    monkeypatch.setattr(owner_packet, "packet_content", leaking)
    with pytest.raises(RuntimeError, match="llmstatusword"):
        workspace.build(path, manuscript, tmp_path / "w.html", [supplement])
    assert not (tmp_path / "w.html").exists()


def test_template_contains_no_origin_or_verdict_vocabulary():
    fixed = re.sub(r"<style>.*?</style>", "", workspace.template_text(), flags=re.S).casefold()
    assert [w for w in packet_tests.GENERIC_LEAK_WORDS if re.search(rf"(?<!\w){w}(?!\w)", fixed)] == []


def test_labels_exported_from_the_workspace_are_scored(setup, tmp_path):
    path, result, topics, manuscript, supplement = setup
    out = tmp_path / "workspace.html"
    meta = embedded((workspace.build(path, manuscript, out, [supplement], seed=5) and out.read_text()), "packet-meta")
    rows = {vid: dict(zip(("correctness", "materiality", "remedy", "act"), packet_tests.OWNER[topics[vid]]), updated_at="t")
            for vid in topics}
    multi = meta["multi_variant_cluster_ids"][0]
    # The payload the workspace's export writes (see exportLabels in the page script).
    payload = {"format": meta["labels_format"], "packet_id": meta["packet_id"], "packet_format": meta["format"],
               "paper_id": meta["paper_id"], "result_sha256": meta["result_sha256"], "seed": meta["seed"],
               "max_variants": meta["max_variants"], "generated_at": meta["generated_at"], "started_at": "s", "updated_at": "u",
               "exported_at": "e", "sampling": meta["sampling"], "variant_ids": meta["variant_ids"], "cluster_ids": meta["cluster_ids"],
               "labels": {"variants": rows, "clusters": {multi: {"same_issue": "split", "note": "two", "updated_at": "t"}}}}
    assert meta["format"] == workspace.WORKSPACE_FORMAT
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(payload))
    report = owner_packet.score(path, labels)
    assert report["coverage"]["fully_labelled"] == len(topics) and report["packet_id"] == meta["packet_id"]
    assert report["cluster_boundaries"]["should_split"] == 1
    script = parse(out.read_text()).scripts[-1]
    for key in payload:
        assert re.search(rf"\b{key}:", script), key


def test_cli_build(setup, tmp_path, capsys):
    path, result, topics, manuscript, supplement = setup
    out = tmp_path / "w.html"
    assert workspace.main(["build", str(path), "--manuscript", str(manuscript), "--supplement", str(supplement),
                           "--out", str(out), "--seed", "9"]) == 0
    printed = capsys.readouterr().out
    assert "quotations anchored" in printed and f"packet {embedded(out.read_text(), 'packet-meta')['packet_id']}" in printed


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_workspace_script_is_valid_javascript(setup, tmp_path):
    path, result, topics, manuscript, supplement = setup
    out = tmp_path / "w.html"
    workspace.build(path, manuscript, out, [supplement])
    (tmp_path / "w.js").write_text(parse(out.read_text()).scripts[-1])
    subprocess.run(["node", "--check", str(tmp_path / "w.js")], check=True)
