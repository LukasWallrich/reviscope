from reviscope.ranking import CRITERIA, ListwiseJudgment, _complete_presentations, aggregate_command, rank_once, summarize_rankings


def criteria():
    return [{"criterion": criterion, "rank_groups": [["A", "B"], ["C"]], "rationale": "Compared"}
            for criterion in sorted(CRITERIA)]


class RankBackend:
    identity = "fixture:rank:test"

    def generate(self, instruction, evidence, response_model):
        assert response_model is ListwiseJudgment
        return ListwiseJudgment.model_validate({
            "overall_rank_groups": [
                {"labels": ["A", "B"], "rationale": "Comparable"},
                {"labels": ["C"], "rationale": "Less useful"},
            ],
            "confidence": .7,
            "rationale": "Two reviews tie",
            "criteria": criteria(),
        })


def test_listwise_ranking_deblinds_ties_and_summarizes_without_inflating_n():
    reviews = [{"id": value, "text": f"Review {value}"} for value in ("human", "gpt-6-luna", "gpt-6.1-sol")]
    row = rank_once("Manuscript", reviews, RankBackend(), paper_id="p", seed=3, repetition=0)
    assert sorted(row["ranks"].values()) == [1.5, 1.5, 3.0]
    summary = summarize_rankings([row], [review["id"] for review in reviews])
    assert summary["paper_count"] == 1
    assert summary["judgment_count"] == 1
    assert len(summary["implied_pairwise_counts"]) == 3


class BadRankBackend(RankBackend):
    def generate(self, instruction, evidence, response_model):
        return ListwiseJudgment.model_validate({"overall_rank_groups": [{"labels": ["A"], "rationale": "Incomplete"}],
                                                "confidence": .5, "rationale": "", "criteria": criteria()})


def test_listwise_ranking_requires_every_label_exactly_once():
    import pytest
    reviews = [{"id": value, "text": value} for value in ("one", "two")]
    with pytest.raises(ValueError, match="every blinded label"):
        rank_once("M", reviews, BadRankBackend(), paper_id="p", seed=1, repetition=0)


def ranking_payload(backend="claude:claude-opus-5-5:high", repetitions=(0, 1, 2)):
    rows = [{"repetition": i, "ranks": {"human": 1, "ai": 2}} for i in repetitions]
    return {"ranking_config": {"backend": backend, "prompt_version": "v", "seed": 1,
                                "presentations": 3, "condition": "original", "content_sha256": "x"},
            "review_kinds": {"human": "human", "ai": "ai"}, "judgments": rows,
            "invalid": [], "summary": {} if len(rows) == 3 else None}


def test_complete_presentations_rejects_duplicate_or_interrupted_rows():
    assert _complete_presentations(ranking_payload())
    assert not _complete_presentations(ranking_payload(repetitions=(0, 0, 2)))
    assert not _complete_presentations(ranking_payload(repetitions=(0, 1)))


def test_aggregate_rejects_duplicate_judge_and_partial_input(tmp_path):
    first, second, output = tmp_path / "one.json", tmp_path / "two.json", tmp_path / "out.json"
    first.write_text(__import__("json").dumps(ranking_payload()))
    second.write_text(__import__("json").dumps(ranking_payload()))
    args = type("Args", (), {"inputs": [first, second], "output": output})()
    import pytest
    with pytest.raises(ValueError, match="duplicate judge"):
        aggregate_command(args)
    second.write_text(__import__("json").dumps(ranking_payload("codex:gpt-6.1-sol:high", (0, 1))))
    with pytest.raises(ValueError, match="incomplete"):
        aggregate_command(args)


def test_ranking_resume_calls_only_missing_presentations(tmp_path, monkeypatch):
    import json
    import reviscope.ranking as module
    reviews = [{"id": f"r{i}", "kind": "human" if i < 4 else "ai",
                "generator_model": None if i < 4 else "m", "text": str(i)} for i in range(7)]
    monkeypatch.setattr(module, "_load_manifest", lambda _path: ("p", "manuscript", reviews, "original"))
    backend = type("Backend", (), {"identity": "claude:claude-opus-5-5:high", "version": None})()
    monkeypatch.setattr(module, "ClaudeBackend", lambda *args, **kwargs: backend)
    calls = []
    def fake_rank(_manuscript, rows, _backend, *, paper_id, seed, repetition):
        calls.append(repetition)
        return {"repetition": repetition, "ranks": {row["id"]: i + 1 for i, row in enumerate(rows)}}
    monkeypatch.setattr(module, "rank_once", fake_rank)
    output = tmp_path / "rank.json"
    args = type("Args", (), {"manifest": tmp_path / "manifest.json", "output": output, "backend": "claude",
                              "model": "claude-opus-5-5", "timeout": 2, "effort": "high", "seed": 1, "presentations": 3})()
    assert module.command(args) == 0 and calls == [0, 1, 2]
    payload = json.loads(output.read_text()); payload["judgments"] = payload["judgments"][:2]; payload["summary"] = None
    output.write_text(json.dumps(payload)); calls.clear()
    assert module.command(args) == 0 and calls == [2]
