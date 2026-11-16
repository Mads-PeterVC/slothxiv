"""Persistence interface used by application workflows."""

from datetime import datetime
from typing import Protocol

from slothxiv.config import Profile
from slothxiv.models import Paper, RetrievalRun, RetrievalWindow


class RetrievalStore(Protocol):
    def start_run(self, profile_name: str, profile: Profile, source: str,
                  window: RetrievalWindow) -> str: ...

    def observe(self, run_id: str, paper: Paper, retrieved_at: datetime) -> None: ...

    def finish_run(self, run_id: str, *, error: str | None = None) -> None: ...

    def get_run(self, run_id: str) -> RetrievalRun: ...
