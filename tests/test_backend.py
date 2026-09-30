import json
from datetime import datetime, timezone
from pathlib import Path

from reviscope.backend import REVIEW_DOMAINS, ClaudeBackend, CodexBackend, FixtureBackend, parse_claude_events, parse_codex_events

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 29, tzinfo=timezone.utc)


def test_codex_event_stream_yields_search_exec_and_final_message():
    calls, final = parse_codex_events((FIXTURES / "codex_tool_events.jsonl").read_text(), NOW)
    assert [c.kind for c in calls] == ["search", "exec", "exec", "exec"]
    assert calls[0].query == "Cohen 1992 A power primer Psychological Bulletin DOI" and "pubmed" in calls[0].output
    assert "scipy" in calls[1].command and calls[1].output.startswith("0.0502")
    assert json.loads(final)["doi"] == "10.1037/0033-2909.112.1.155"


def test_claude_event_stream_pairs_tool_uses_with_results_and_records_refusals():
    calls, final = parse_claude_events((FIXTURES / "claude_tool_events.jsonl").read_text(), NOW)
    assert [c.kind for c in calls] == ["exec", "exec", "exec", "fetch", "fetch"]
    assert calls[0].error and "operation not permitted" in calls[0].output
    assert "sandbox_violations" in calls[2].output
    assert calls[3].url == "https://pubpeer.com/" and calls[3].error
    assert calls[4].url == "https://example.org/" and not calls[4].error
    assert '"exampleorg":true' in final


def test_review_backends_enable_sandboxed_tools_and_judges_do_not():
    codex, claude = CodexBackend("m", effort="low"), ClaudeBackend("m", effort="low")
    assert 'web_search="live"' in codex.command and "workspace-write" in codex.command and "--json" in codex.command
    assert codex.command[-1] == "-" and "shell_tool" not in codex.command
    settings = json.loads(claude.command[claude.command.index("--settings") + 1])
    assert settings["sandbox"] == {"enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False}
    assert f"WebFetch(domain:{REVIEW_DOMAINS[0]})" in settings["permissions"]["deny"]
    assert "--restricted" in claude.command and "Bash,WebSearch,WebFetch" in claude.command
    judge = CodexBackend("m", effort="low", tools=False)
    assert 'web_search="disabled"' in judge.command and judge.identity == "codex:m:low"
    assert codex.identity.startswith("codex:m:low:tools-")
    assert FixtureBackend().take_tool_calls() == []
