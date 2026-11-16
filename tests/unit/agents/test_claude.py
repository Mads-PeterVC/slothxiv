import json
import subprocess

import pytest

from slothxiv.agents.claude import AgentError, ClaudeCLIAgent, parse_response
from slothxiv.evaluation.prompts import build_request
from slothxiv.sources.arxiv import parse_feed


def envelope(**changes):
    result = dict(paper_id="arxiv:2611.00001", revision="1", score=75,
                  justification="Direct graph relevance", generated_keywords=["graphs"])
    result.update(changes)
    return dict(subtype="success", is_error=False, structured_output=result,
                modelUsage={"claude-sonnet-test": {"inputTokens": 100}})


@pytest.mark.parametrize("changes", [
    {"score": -1}, {"score": 101}, {"score": 1.5}, {"score": True}, {"score": "75"},
    {"justification": " "}, {"generated_keywords": [""]}, {"unexpected": "field"},
])
def test_rejects_invalid_structured_result(changes):
    with pytest.raises(AgentError):
        parse_response(json.dumps(envelope(**changes)))


@pytest.mark.parametrize("output", [
    "not json", "[]", '[{"subtype":"success"}]',
    '{"subtype":"success"}', '{"subtype":"error_during_execution","result":"Please login"}',
    '{"subtype":"success","is_error":true}',
    '{"subtype":"error","subtype":"success"}',
])
def test_rejects_missing_failed_or_multiple_results(output):
    with pytest.raises(AgentError):
        parse_response(output)


def test_translates_model_identity():
    response = parse_response(json.dumps(envelope()))
    assert response.reported_models == ("claude-sonnet-test",)
    assert response.result.score == 75


def test_subprocess_contract_uses_stdin_and_isolated_directory(monkeypatch, arxiv_page):
    import slothxiv.agents.claude as claude
    request = build_request(parse_feed(arxiv_page())[2][0], "Find graph learning")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["cwd"] != "."
        return subprocess.CompletedProcess(command, 0, json.dumps(envelope()), "")

    monkeypatch.setattr(claude.subprocess, "run", run)
    response = ClaudeCLIAgent("opus", 42).evaluate(request)
    command, kwargs = calls[0]
    assert kwargs["input"] == request.prompt
    assert kwargs["timeout"] == 42
    assert request.prompt not in command
    assert command[command.index("--model") + 1] == "opus"
    assert command[command.index("--tools") + 1] == ""
    assert "--safe-mode" in command and "--strict-mcp-config" in command
    assert "--no-session-persistence" in command
    assert response.result.paper_id == request.paper.paper_id


@pytest.mark.parametrize("failure,match", [
    (FileNotFoundError(), "not found"),
    (subprocess.TimeoutExpired("claude", 1), "timed out"),
    (PermissionError("denied"), "could not execute"),
])
def test_subprocess_failures(monkeypatch, arxiv_page, failure, match):
    import slothxiv.agents.claude as claude

    def run(*args, **kwargs):
        raise failure

    monkeypatch.setattr(claude.subprocess, "run", run)
    with pytest.raises(AgentError, match=match):
        ClaudeCLIAgent().evaluate(build_request(parse_feed(arxiv_page())[2][0], "graphs"))


def test_nonzero_exit_reports_stdout_auth_error(monkeypatch, arxiv_page):
    import slothxiv.agents.claude as claude
    monkeypatch.setattr(claude.subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess(a, 1, "Please login", ""))
    with pytest.raises(AgentError, match="Please login"):
        ClaudeCLIAgent().evaluate(build_request(parse_feed(arxiv_page())[2][0], "graphs"))
