"""Headless Claude CLI execution and provider response translation."""

import json
import subprocess
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from slothxiv.evaluation import AgentResponse, EvaluationRequest, EvaluationResult


class AgentError(RuntimeError):
    """An invocation failed or returned an invalid evaluation."""


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate response field: {key}")
        result[key] = value
    return result


def parse_response(output: str) -> AgentResponse:
    try:
        envelope = json.loads(output, object_pairs_hook=unique_object)
        if not isinstance(envelope, dict):
            raise ValueError("expected a single JSON result object")
        if envelope.get("is_error") or envelope.get("subtype") != "success":
            # Claude reports authentication errors on stdout as well as stderr.
            detail = envelope.get("result") or envelope.get("errors") or "unsuccessful result"
            raise ValueError(str(detail)[:1000])
        result = EvaluationResult.model_validate(envelope.get("structured_output"))
        usage = envelope.get("modelUsage", {})
        models = tuple(sorted(usage)) if isinstance(usage, dict) else ()
        return AgentResponse(result=result, reported_models=models)
    except (ValueError, TypeError, ValidationError) as error:
        raise AgentError(f"invalid Claude response: {error}") from error


class ClaudeCLIAgent:
    def __init__(self, model: str = "sonnet", timeout_seconds: int = 120) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def identity(self) -> dict[str, str | int]:
        return {"adapter": "claude-cli", "contract": "json-schema-v1",
                "model": self.model, "timeout_seconds": self.timeout_seconds}

    def evaluate(self, request: EvaluationRequest) -> AgentResponse:
        command = [
            "claude", "--print", "--safe-mode", "--model", self.model,
            "--output-format", "json", "--json-schema",
            json.dumps(EvaluationResult.model_json_schema()),
            "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--disable-slash-commands", "--no-session-persistence",
            "--permission-mode", "dontAsk", "--system-prompt", request.system_prompt,
        ]
        try:
            with TemporaryDirectory(prefix="slothxiv-agent-") as directory:
                completed = subprocess.run(
                    command, input=request.prompt, capture_output=True, text=True,
                    encoding="utf-8", timeout=self.timeout_seconds, cwd=directory,
                    check=False,
                )
        except FileNotFoundError as error:
            raise AgentError("Claude CLI not found; install claude and authenticate before ranking") from error
        except subprocess.TimeoutExpired as error:
            raise AgentError(f"Claude CLI timed out after {self.timeout_seconds}s") from error
        except OSError as error:
            raise AgentError(f"could not execute Claude CLI: {error}") from error
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip()[:1000]
            raise AgentError(f"Claude CLI exited {completed.returncode}: {detail}. "
                             "Check installation and authentication with claude auth status.")
        return parse_response(completed.stdout)
