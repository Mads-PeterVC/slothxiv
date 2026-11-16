"""Structured evaluation contracts, independent of agent providers."""

from typing import Annotated, Literal, Protocol

from pydantic import Field

from slothxiv.models import Model, NonEmpty, Paper, UTCDateTime


class EvaluationResult(Model):
    paper_id: NonEmpty
    revision: NonEmpty
    score: Annotated[int, Field(strict=True, ge=0, le=100)]
    justification: NonEmpty
    generated_keywords: tuple[NonEmpty, ...]


class EvaluationRequest(Model):
    paper: Paper
    system_prompt: NonEmpty
    prompt: NonEmpty
    prompt_version: NonEmpty


class AgentResponse(Model):
    result: EvaluationResult
    reported_models: tuple[NonEmpty, ...] = ()


class EvaluationAgent(Protocol):
    @property
    def identity(self) -> dict[str, str | int]: ...

    def evaluate(self, request: EvaluationRequest) -> AgentResponse: ...


class EvaluationRecord(Model):
    evaluation_id: str
    run_id: str
    paper: Paper
    response: AgentResponse
    started_at: UTCDateTime
    finished_at: UTCDateTime


class RankedEntry(Model):
    evaluation: EvaluationRecord
    reused: bool


class EvaluationRun(Model):
    run_id: str
    profile_name: str
    started_at: UTCDateTime
    finished_at: UTCDateTime | None = None
    status: Literal["running", "completed", "failed"]
    candidate_count: int
    error: str | None = None


class Ranking(Model):
    run: EvaluationRun
    entries: tuple[RankedEntry, ...]
    failures: dict[str, str]
