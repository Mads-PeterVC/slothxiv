"""Validated, source-independent retrieval data."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl,
    JsonValue, StringConstraints, model_validator,
)

UTCDateTime = Annotated[AwareDatetime, AfterValidator(lambda value: value.astimezone(UTC))]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Paper(Model):
    source: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]*$")]
    source_id: NonEmpty
    revision: NonEmpty
    title: NonEmpty
    abstract: NonEmpty
    authors: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    published_at: UTCDateTime
    updated_at: UTCDateTime
    url: HttpUrl
    pdf_url: HttpUrl | None = None
    categories: tuple[NonEmpty, ...] = ()
    source_keywords: tuple[NonEmpty, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def paper_id(self) -> str:
        return f"{self.source}:{self.source_id}"


class RetrievalWindow(Model):
    start: UTCDateTime
    end: UTCDateTime

    @model_validator(mode="after")
    def ordered(self) -> "RetrievalWindow":
        if self.start >= self.end:
            raise ValueError("window start must precede end")
        return self

    def contains(self, value: datetime) -> bool:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return self.start <= value < self.end


class RetrievalRun(Model):
    run_id: str
    profile_name: str
    profile_snapshot: dict[str, JsonValue]
    source: str
    window: RetrievalWindow
    started_at: UTCDateTime
    finished_at: UTCDateTime | None = None
    status: Literal["running", "completed", "failed"]
    observation_count: int = 0
    error: str | None = None
