import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from reviscope.criticism_judge import Origin, RunOutput, Variant, VariantJudgment, compute_metrics

spec = importlib.util.spec_from_file_location("owner_packet", Path(__file__).resolve().parents[1] / "eval" / "owner_packet.py")
owner_packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner_packet)

# Distinctive origin and judge vocabulary so that any occurrence in the packet is a leak.
ARMS = {"armalpha": ("pipeline", ["armalpha/1", "armalpha/2"], "modzeta"), "armbeta": ("plain", ["armbeta/1"], "catomega")}
# (cluster, arm run, topic). Clusters c1-c2 are shared, c3-c5 armalpha only, c6-c7 armbeta only.
LAYOUT = [("c1", "armalpha/1", "the causal claim"), ("c1", "armalpha/2", "the causal claim"), ("c1", "armbeta/1", "the causal claim"),
          ("c2", "armalpha/1", "the effect size"), ("c2", "armbeta/1", "the effect size"),
          ("c3", "armalpha/1", "the power analysis"), ("c3", "armalpha/2", "the power analysis"),
          ("c4", "armalpha/2", "the exclusion rule"), ("c5", "armalpha/1", "the manipulation check"),
          ("c6", "armbeta/1", "the sample"), ("c7", "armbeta/1", "the preregistration")]
VERDICTS = {"the causal claim": ("supported", 3), "the effect size": ("contradicted", 2), "the power analysis": ("supported", 2),
            "the exclusion rule": ("unresolved", 1), "the manipulation check": ("supported", 1), "the sample": ("supported", 0),
            "the preregistration": ("not_assessable", 0)}
SEVERITIES = ("major", "critical", "minor")


def judgment(vid, topic, flip=False):
    verdict, materiality = VERDICTS[topic]
    if flip:
        verdict = "contradicted"
    row = VariantJudgment(variant_id=vid, premise="supported" if verdict == "supported" else verdict, inference="not_stated",
                          consequence="not_stated", correctness=verdict, explanation=f"JUDGEEXPLAIN {vid} {verdict}",
                          manuscript_quotes=[], alleges_error=True, materiality=materiality, remedy_necessity="essential",
                          remedy_proportionate="yes", remedy_valid="yes", concrete_benefit="not_applicable", generic=False,
                          restates_own_limitation=False)
    return {**row.model_dump(exclude={"manuscript_quotes", "correctness"}), "stated_correctness": verdict, "correctness": verdict,
            "consistency_adjusted": False, "manuscript_quotes": [], "quotes_anchored": 0, "batch": "b"}


def synthetic_result(tmp_path, layout=LAYOUT, claim_extra=""):
    variants, origins, members = [], {}, {}
    for index, (cluster, run, topic) in enumerate(layout):
        arm = run.split("/")[0]
        fmt, _, module = ARMS[arm]
        vid = "V" + hashlib.sha256(f"{run}{index}".encode()).hexdigest()[:10]
        variant = Variant(id=vid, claim=f"Criticism {index} says {topic} is flawed.{claim_extra}",
                          rationale=f"Because {topic} is reported inconsistently." if fmt == "pipeline" else "",
                          remedy=f"Revise {topic}." if index % 3 else None, quotes=[f"Quoted passage about {topic}."])
        variants.append(variant)
        origins[vid] = Origin(variant_id=vid, arm=arm, run=run, path=f"/secretpath/{run}/review.json", format=fmt,
                              module=module, status="llmstatusword" if fmt == "pipeline" else "plainstatusword",
                              severity=SEVERITIES[index % 3])
        members.setdefault(cluster, []).append(vid)
    runs = [RunOutput(arm=arm, run=run, path=f"/secretpath/{run}/review.json", format="plain" if arm == "armbeta" else "pipeline",
                      sha256="0" * 64, output_words=100, variant_ids=[v.id for v in variants if origins[v.id].run == run])
            for arm, (_, run_labels, _) in ARMS.items() for run in run_labels]
    clusters = [{"cluster_id": f"C{i + 1:03d}", "label": f"CLUSTERLABEL {name}", "variant_ids": sorted(ids)}
                for i, (name, ids) in enumerate(members.items())]
    topics = {v.id: t for v, (_, _, t) in zip(variants, layout)}
    judgments = {"famone": {v.id: judgment(v.id, topics[v.id]) for v in variants},
                 "famtwo": {v.id: judgment(v.id, topics[v.id], flip=topics[v.id] == "the power analysis") for v in variants}}
    metrics = compute_metrics(variants, origins, runs, clusters, judgments)
    result = {"protocol": "criticism-judge-v1", "paper_id": "p1", "partial": False, "failures": [],
              "judges": {"famone": "stubjudgeone:j", "famtwo": "stubjudgetwo:j"}, "seed": 1,
              "runs": [r.model_dump() for r in runs], "variants": [v.model_dump() for v in variants],
              "origins": {k: o.model_dump() for k, o in origins.items()}, "clusters": clusters, "judgments": judgments,
              "metrics": metrics}
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result, indent=2))
    return path, result, topics


VOID = {"meta", "input", "br", "hr", "img", "link"}


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles, self.issues, self.scripts, self.text, self.stack, self.external = [], [], [], [], [], []
        self.radios = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if tag == "article":
            self.articles.append(attrs["data-variant"])
        if tag == "section" and "data-cluster" in attrs:
            self.issues.append(attrs["data-cluster"])
        if tag == "input" and attrs.get("type") == "radio":
            self.radios.setdefault(attrs["name"], []).append(attrs["value"])
        for key in ("src", "href"):
            if attrs.get(key):
                self.external.append(attrs[key])

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1] == tag, f"misnested </{tag}> in {self.stack}"
        self.stack.pop()

    def handle_data(self, data):
        (self.scripts if self.stack and self.stack[-1] == "script" else self.text).append(data)


def parse(document):
    collector = Collector()
    collector.feed(document)
    collector.close()
    assert collector.stack == [], f"unclosed {collector.stack}"
    return collector


GENERIC_LEAK_WORDS = ("major", "minor", "critical", "moderate", "severity", "supported", "contradicted", "unresolved",
                      "not_assessable", "published", "specialist", "plain", "pipeline", "baseline", "verified", "verifier",
                      "arm", "module", "judge", "codex", "claude", "opus", "sol")


def test_template_contains_no_origin_or_verdict_vocabulary():
    # Visible text and attributes; the stylesheet's "align-items:baseline" is not shown to the reader.
    fixed = re.sub(r"<style>.*?</style>", "", owner_packet.template_text(), flags=re.S).casefold()
    assert [w for w in GENERIC_LEAK_WORDS if re.search(rf"(?<!\w){w}(?!\w)", fixed)] == []


def test_packet_is_self_contained_parses_and_leaks_nothing(tmp_path):
    path, result, _ = synthetic_result(tmp_path)
    out = tmp_path / "packet.html"
    meta = owner_packet.build(path, out, seed=7)
    document = out.read_text()
    parsed = parse(document)
    assert sorted(parsed.articles) == sorted(v["id"] for v in result["variants"]) == meta["variant_ids"]
    assert sorted(parsed.issues) == sorted(c["cluster_id"] for c in result["clusters"])
    assert parsed.external == [] and not re.search(r"https?://|@import|url\(", document)
    # Every variant has four scales; only multi-variant clusters get the grouping question.
    assert sum(name.endswith("-correctness") for name in parsed.radios) == len(result["variants"])
    assert sorted(n for n in parsed.radios if n.endswith("-same_issue")) == sorted(
        f"c-{c['cluster_id']}-same_issue" for c in result["clusters"] if len(c["variant_ids"]) > 1)
    assert set(parsed.radios[f"v-{meta['variant_ids'][0]}-materiality"]) == {"0", "1", "2", "3"}
    # No origin values, severity words, judge outputs or cluster labels anywhere in the file.
    lowered = document.casefold()
    for term in ["armalpha", "armbeta", "modzeta", "catomega", "llmstatusword", "plainstatusword", "secretpath", "famone",
                 "famtwo", "stubjudge", "judgeexplain", "clusterlabel", *SEVERITIES, "supported", "contradicted"]:
        assert term not in lowered, term
    assert owner_packet.leaks(document, result) == []
    embedded = json.loads(re.search(r'<script type="application/json" id="packet-meta">(.*?)</script>', document, re.S).group(1))
    assert embedded["result_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert embedded["variant_ids"] == sorted(v["id"] for v in result["variants"])
    assert not {"origins", "judgments", "runs", "clusters", "metrics"} & set(embedded)
    assert all(p == 1.0 for p in embedded["sampling"]["inclusion_probability"].values())
    assert "Issue 1, criticism A" in document


def test_leak_check_allows_words_from_the_criticism_text_and_catches_others(tmp_path):
    path, result, _ = synthetic_result(tmp_path, claim_extra=" This is a major problem for the armalpha design.")
    owner_packet.build(path, tmp_path / "packet.html", seed=7)  # occurrences inside criticism text are allowed
    document = (tmp_path / "packet.html").read_text()
    assert "major problem" in document
    assert owner_packet.leaks(document + "<p>modzeta</p>", result) == ["modzeta"]
    assert owner_packet.leaks(document + "<p>JUDGEEXPLAIN</p>", result) == []  # a fragment, not a full explanation
    first = next(iter(result["judgments"]["famone"].values()))["explanation"]
    assert owner_packet.leaks(document + f"<p>{first}</p>", result) == [first]


def test_order_is_seeded_random_and_not_grouped_by_origin(tmp_path):
    path, result, _ = synthetic_result(tmp_path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    order = lambda seed: [(i["cluster_id"], [v["id"] for v in i["variants"]]) for i in owner_packet.packet_content(result, sha, seed, None)["issues"]]  # noqa: E731
    assert order(3) == order(3)
    assert len({json.dumps(order(seed)) for seed in range(8)}) > 1
    assert order(3) != sorted(order(3))


def test_max_variants_samples_whole_clusters_from_every_stratum(tmp_path):
    layout = list(LAYOUT)
    for k in range(20):  # many single-arm clusters so that sampling is needed
        layout.append((f"a{k}", "armalpha/1", f"the alpha topic {k}"))
        layout.append((f"b{k}", "armbeta/1", f"the beta topic {k}"))
    verdicts = {f"the {side} topic {k}": ("supported", 2) for side in ("alpha", "beta") for k in range(20)}
    VERDICTS.update(verdicts)
    try:
        path, result, _ = synthetic_result(tmp_path, layout)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        content = owner_packet.packet_content(result, sha, 11, 20)
    finally:
        for key in verdicts:
            VERDICTS.pop(key)
    meta = content["meta"]
    clusters = {c["cluster_id"]: c["variant_ids"] for c in result["clusters"]}
    shown = [v["id"] for i in content["issues"] for v in i["variants"]]
    assert sorted(shown) == meta["variant_ids"]
    assert all(set(clusters[i["cluster_id"]]) == {v["id"] for v in i["variants"]} for i in content["issues"])  # whole clusters
    arms_of = lambda cid: tuple(sorted({result["origins"][v]["arm"] for v in clusters[cid]}))  # noqa: E731
    strata = {arms_of(c) for c in clusters}
    assert {arms_of(c) for c in meta["cluster_ids"]} == strata == {("armalpha",), ("armbeta",), ("armalpha", "armbeta")}
    for stratum in strata:
        members = [c for c in clusters if arms_of(c) == stratum]
        sampled = [c for c in meta["cluster_ids"] if arms_of(c) == stratum]
        assert {meta["sampling"]["inclusion_probability"][c] for c in sampled} == {round(len(sampled) / len(members), 6)}
    assert len(shown) < len(result["variants"]) and meta["sampling"]["pool_variants"] == len(result["variants"])
    assert owner_packet.packet_content(result, sha, 11, 20)["meta"]["cluster_ids"] == meta["cluster_ids"]
    assert "armalpha" not in json.dumps(meta)


def labels_for(meta, rows, clusters, **extra):
    return {"format": owner_packet.LABELS_FORMAT, "packet_id": meta["packet_id"], "paper_id": meta["paper_id"],
            "result_sha256": meta["result_sha256"], "seed": meta["seed"], "max_variants": meta["max_variants"],
            "started_at": "2026-10-09T10:00:00Z", "updated_at": "2026-10-09T11:00:00Z", "exported_at": "2026-10-09T11:00:01Z",
            "sampling": meta["sampling"], "variant_ids": meta["variant_ids"], "cluster_ids": meta["cluster_ids"],
            "labels": {"variants": rows, "clusters": clusters}, **extra}


OWNER = {  # owner's correctness, materiality, remedy, act per topic
    "the causal claim": ("correct", 3, "essential", "yes"),
    "the effect size": ("incorrect", 2, "wrong_or_harmful", "no"),
    "the power analysis": ("partly_correct", 2, "strengthen", "yes"),
    "the exclusion rule": ("cannot_tell", 1, "strengthen", "no"),
    "the manipulation check": ("correct", 0, "none_given", "already_addressed"),
    "the sample": ("correct", 2, "extension", "no"),
    "the preregistration": ("incorrect", 0, "none_given", "no"),
}


def test_score_maps_owner_labels_and_reports_agreement_arms_and_boundaries(tmp_path):
    path, result, topics = synthetic_result(tmp_path)
    meta = owner_packet.build(path, tmp_path / "packet.html", seed=5)
    rows = {vid: dict(zip(("correctness", "materiality", "remedy", "act"), OWNER[topics[vid]]), updated_at="t") for vid in topics}
    rows[next(iter(topics))]["note"] = "My note"
    split_cluster = next(c["cluster_id"] for c in result["clusters"] if c["label"].endswith("c1"))
    keep_cluster = next(c["cluster_id"] for c in result["clusters"] if c["label"].endswith("c2"))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(labels_for(meta, rows, {split_cluster: {"same_issue": "split", "note": "two issues"},
                                                         keep_cluster: {"same_issue": "yes"}})))
    report = owner_packet.score(path, labels)
    assert report["coverage"] == {"variants_in_packet": 11, "fully_labelled": 11, "partly_labelled": 0}

    one = report["agreement"]["famone"]
    # Judge famone vs owner strict: causal 3 agree, effect 2 agree, power 2 disagree (judge supported, owner partly ->
    # contradicted), exclusion agree (unresolved), manipulation agree, sample agree, prereg disagree (not_assessable).
    assert one["n"] == 11 and one["strict"]["agreement"] == round(8 / 11, 4)
    assert one["strict"]["confusion_judge_by_owner"]["supported"]["contradicted"] == 2
    assert one["strict"]["confusion_judge_by_owner"]["not_assessable"]["contradicted"] == 1
    assert one["lenient"]["agreement"] == round(10 / 11, 4)
    # Materiality: only the manipulation check (judge 1, owner 0) and the sample (judge 0, owner 2) differ.
    assert one["materiality"]["agreement"] == round(9 / 11, 4) and one["materiality"]["judge_higher"] == 1
    assert {d["claim"].split(" says ")[1] for d in one["disagreements"]} == {
        "the power analysis is flawed.", "the preregistration is flawed.", "the sample is flawed."}
    two = report["agreement"]["famtwo"]
    assert two["strict"]["agreement"] == round(10 / 11, 4)  # famtwo contradicts the power analysis, like the strict owner
    combined = report["agreement"]["combined"]
    assert combined["strict"]["confusion_judge_by_owner"]["contradicted"]["contradicted"] == 4
    assert one["strict"]["kappa"] is not None and -1 <= one["materiality"]["weighted_kappa_linear"] <= 1

    alpha = report["per_arm"]["armalpha"]
    assert alpha["runs"] == 2 and alpha["variants_in_packet"] == 7
    raw = alpha["raw"]
    # armalpha: causal x2 (correct), effect (incorrect), power x2 (partly), exclusion (cannot tell), manipulation (correct).
    assert raw["supported"] == 3 and raw["contradicted"] == 3 and raw["partly_correct"] == 2 and raw["cannot_tell"] == 1
    assert raw["supported_rate"] == round(3 / 7, 4) and raw["supported_rate_lenient"] == round(5 / 7, 4)
    assert raw["supported_material"] == 2 and raw["supported_material_lenient"] == 4
    assert raw["would_act"] == 4 and raw["remedy_harm"] == 1 and raw["already_addressed"] == 1
    assert raw["per_run_mean"]["supported"] == 1.5
    assert alpha["weighted"]["supported"] == raw["supported"]  # census: weights are 1
    beta = report["per_arm"]["armbeta"]["raw"]
    assert beta["labelled"] == 4 and beta["supported"] == 2 and beta["supported_material"] == 2 and beta["remedy_harm"] == 1
    runs = {r["run"]: r for r in report["per_run"]}
    assert runs["armalpha/2"]["raw"]["labelled"] == 3 and runs["armbeta/1"]["raw"]["labelled"] == 4

    bounds = report["cluster_boundaries"]
    assert bounds["multi_variant_clusters"] == 3 and bounds["answered"] == 2 and bounds["should_split"] == 1
    assert bounds["split_share"] == 0.5 and bounds["split_clusters"][0]["note"] == "two issues"
    markdown = owner_packet.report_markdown(report)
    assert "| famone | 11 |" in markdown and "| armalpha | 2 | 7 |" in markdown and "should be split" in markdown


def test_score_weights_by_inverse_inclusion_probability(tmp_path):
    path, result, topics = synthetic_result(tmp_path)
    meta = owner_packet.build(path, tmp_path / "packet.html", seed=5, max_variants=6)
    probability = meta["sampling"]["inclusion_probability"]
    assert any(p < 1 for p in probability.values())
    rows = {vid: {"correctness": "correct", "materiality": 2, "remedy": "essential", "act": "yes"} for vid in meta["variant_ids"]}
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(labels_for(meta, rows, {})))
    report = owner_packet.score(path, labels)
    assert report["sampled"]
    clusters = {c["cluster_id"]: c["variant_ids"] for c in result["clusters"]}
    for arm in ("armalpha", "armbeta"):
        expected = sum(1 / probability[c] for c in meta["cluster_ids"] for v in clusters[c] if result["origins"][v]["arm"] == arm)
        assert report["per_arm"][arm]["weighted"]["supported"] == pytest.approx(expected, abs=1e-3)
        assert report["per_arm"][arm]["weighted"]["supported_rate"] in (1.0, None)


def test_score_rejects_labels_for_another_result_or_packet(tmp_path):
    path, result, topics = synthetic_result(tmp_path)
    meta = owner_packet.build(path, tmp_path / "packet.html", seed=5)
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(labels_for(meta, {}, {}, result_sha256="f" * 64)))
    with pytest.raises(ValueError, match="sha256"):
        owner_packet.score(path, labels)
    labels.write_text(json.dumps(labels_for(meta, {}, {}, packet_id="0000")))
    with pytest.raises(ValueError, match="packet id"):
        owner_packet.score(path, labels)
    labels.write_text(json.dumps(labels_for(meta, {"Vnotinpacket": {"correctness": "correct"}}, {})))
    with pytest.raises(ValueError, match="outside the packet"):
        owner_packet.score(path, labels)


def test_cli_build_and_score(tmp_path, capsys):
    path, result, topics = synthetic_result(tmp_path)
    out = tmp_path / "packet.html"
    assert owner_packet.main(["build", str(path), "--out", str(out), "--seed", "9"]) == 0
    meta = json.loads(re.search(r'id="packet-meta">(.*?)</script>', out.read_text(), re.S).group(1))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(labels_for(meta, {next(iter(topics)): {"correctness": "correct", "materiality": 1,
                                                                        "remedy": "essential", "act": "yes"}}, {})))
    assert owner_packet.main(["score", str(path), str(labels), "--out", str(tmp_path / "report.json")]) == 0
    assert "# Owner validation: p1" in capsys.readouterr().out
    assert json.loads((tmp_path / "report.json").read_text())["coverage"]["fully_labelled"] == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_packet_script_is_valid_javascript(tmp_path):
    path, _, _ = synthetic_result(tmp_path)
    out = tmp_path / "packet.html"
    owner_packet.build(path, out)
    script = re.findall(r"<script>(.*?)</script>", out.read_text(), re.S)[0]
    (tmp_path / "packet.js").write_text(script)
    subprocess.run(["node", "--check", str(tmp_path / "packet.js")], check=True)
