"""Paper source boundary; adapters own query and pagination details."""

from collections.abc import Iterable
from typing import Protocol

from slothxiv.models import Paper, RetrievalWindow


class SourceError(RuntimeError):
    """A source could not provide a complete valid retrieval."""


class PaperSource(Protocol):
    name: str

    def fetch(self, window: RetrievalWindow) -> Iterable[Paper]: ...
