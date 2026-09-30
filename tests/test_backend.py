import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import BaseModel

from reviscope.backend import (REVIEW_DOMAINS, ClaudeBackend, CodexBackend, FixtureBackend, SubprocessBackend,
                               parse_claude_events, parse_codex_events)
from reviscope.pipeline import ReviewPipeline

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


def test_codex_event_stream_yields_search_exec_and_final_message():
    calls, final = parse_codex_events((FIXTURES / "codex_tool_events.jsonl").read_text(), NOW)
    assert [c.kind for c in calls] == ["search", "exec", "exec", "exec"]
    assert calls[0].query == "Cohen 1992 A power primer Psychological Bulletin DOI" and "pubmed" in calls[0].output
    assert calls[0].result_urls[0] == "https://pubmed.ncbi.nlm.nih.gov/19565683/"
    assert "scipy" in calls[1].command and calls[1].output.startswith("0.0502")
    assert json.loads(final)["doi"] == "10.1037/0033-2909.112.1.155"


def test_codex_parser_keeps_every_query_and_marks_failed_or_unfinished_calls():
    events = [
        {"type": "item.completed", "item": {"id": "1", "type": "web_search", "action": {"type": "search", "query": "effect sizes ...", "queries": ["effect sizes", "paper title reviews"]}}},
        {"type": "item.completed", "item": {"id": "2", "type": "command_execution", "command": "rm x", "status": "declined", "exit_code": None}},
        {"type": "item.completed", "item": {"id": "4", "type": "web_search", "action": {"type": "open_page"}, "results": [{"url": "https://pubmed.ncbi.nlm.nih.gov/21474762/"}]}},
        {"type": "item.started", "item": {"id": "3", "type": "command_execution", "command": "python3 slow.py"}},
    ]
    calls, _ = parse_codex_events("\n".join(json.dumps(e) for e in events), NOW)
    assert [c.query for c in calls[:2]] == ["effect sizes", "paper title reviews"]
    assert calls[2].error and calls[4].error and "incomplete" in calls[4].output
    assert calls[3].kind == "fetch" and calls[3].result_urls == ["https://pubmed.ncbi.nlm.nih.gov/21474762/"]


def test_claude_event_stream_pairs_tool_uses_with_results_and_records_refusals():
    calls, final = parse_claude_events((FIXTURES / "claude_tool_events.jsonl").read_text(), NOW)
    assert [c.kind for c in calls] == ["exec", "exec", "exec", "fetch", "fetch"]
    assert calls[0].error and "operation not permitted" in calls[0].output
    assert "sandbox_violations" in calls[2].output
    assert calls[3].url == "https://pubpeer.com/" and calls[3].error
    assert calls[4].url == "https://example.org/" and not calls[4].error
    assert '"exampleorg":true' in final


def test_review_backends_sandbox_the_shell_and_judges_have_no_tools():
    tmp = Path("/tmp/reviscope-test")
    codex = CodexBackend("gpt-6-luna", effort="low").command(tmp)
    assert 'web_search="live"' in codex and 'default_permissions="reviscope"' in codex and codex[-1] == "-"
    profile = next(part for part in codex if part.startswith("permissions.reviscope="))
    assert f'"{Path.home()}"="deny"' in profile and '":workspace_roots"={"."="write"}' in profile and "network={enabled=false}" in profile
    assert "allow_login_shell=false" in codex and "--sandbox" not in codex
    claude_backend = ClaudeBackend("claude-opus-5-5", effort="low")
    claude = claude_backend.command(tmp)
    settings = json.loads(claude[claude.index("--settings") + 1])["sandbox"]
    assert settings["failIfUnavailable"] and not settings["allowUnsandboxedCommands"]
    assert settings["filesystem"]["denyRead"] == ["~/"] and settings["network"] == {"strictAllowlist": True, "allowedDomains": []}
    assert f"WebFetch(domain:{REVIEW_DOMAINS[0]})" in json.loads(claude[claude.index("--settings") + 1])["permissions"]["deny"]
    assert claude_backend.environment(tmp)["CLAUDE_CODE_TMPDIR"] == str(tmp)
    judge = ClaudeBackend("claude-opus-5-5", effort="low", tools=False).command(tmp)
    for flag in ("--restricted", "--safe-mode", "--no-session-persistence"):
        assert flag in claude and flag in judge
    assert judge[judge.index("--tools") + 1] == ""
    assert 'web_search="disabled"' in CodexBackend("gpt-6-luna", effort="low", tools=False).command(tmp)
    assert CodexBackend("gpt-6-luna", effort="low").identity != CodexBackend("gpt-6-luna", effort="low", tools=False).identity
    assert FixtureBackend().take_tool_calls() == []
    with pytest.raises(ValueError, match="tool-enabled"):
        ReviewPipeline(CodexBackend("gpt-6-luna", tools=False))


class Answer(BaseModel):
    value: int


class ScriptBackend(SubprocessBackend):
    """Runs a shell script instead of a model CLI; stdout is parsed as a Claude event stream."""

    name, binary = "script", "sh"

    def __init__(self, script: str, timeout: int = 60):
        super().__init__("script", timeout)
        self.script = script

    def command(self, tmp):
        return ["sh", "-c", self.script]

    def _parse(self, stdout, started):
        return parse_claude_events(stdout, started)


def test_timeout_keeps_partial_tool_calls_and_kills_the_process_group(tmp_path):
    marker = tmp_path / "child-alive"
    use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "WebFetch", "input": {"url": "https://example.org/"}}]}}
    backend = ScriptBackend(f"echo '{json.dumps(use)}'; (sleep 3; touch {marker}) & sleep 30", timeout=1)
    with pytest.raises(TimeoutError):
        backend.generate("task", "evidence", Answer)
    calls = backend.take_tool_calls()
    assert calls[0].url == "https://example.org/" and calls[0].error
    time.sleep(3.5)
    assert not marker.exists()


def test_schema_repair_repeats_the_original_task_and_the_validation_error():
    prompts = []

    class Repairing(ScriptBackend):
        def _run(self, prompt, response_model):
            prompts.append(prompt)
            return '{"value": "not a number"}' if len(prompts) == 1 else '{"value": 3}'

    assert Repairing("").generate("count the studies", "MANUSCRIPT TEXT", Answer).value == 3
    assert "count the studies" in prompts[1] and "MANUSCRIPT TEXT" in prompts[1] and "valid integer" in prompts[1]
