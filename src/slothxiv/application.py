"""Library entry points shared by CLI and future UI."""

from datetime import UTC, datetime, timedelta

from slothxiv.config import Profile
from slothxiv.models import RetrievalRun, RetrievalWindow
from slothxiv.sources import PaperSource
from slothxiv.sources.arxiv import ArxivSource
from slothxiv.storage import RetrievalStore


class ScrapeError(RuntimeError):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"retrieval failed (run {run_id}); partial observations are preserved")


def scrape(
    profile_name: str, profile: Profile, store: RetrievalStore, *,
    source: PaperSource | None = None, started_at: datetime | None = None,
) -> RetrievalRun:
    """Retrieve into storage; failures preserve history and raise ScrapeError.

    Interruptions mark the run failed when possible and propagate. Abrupt process
    termination may leave a run 'running', never falsely 'completed'.
    """
    end = started_at if started_at is not None else datetime.now(UTC)
    window = RetrievalWindow(start=end - timedelta(days=profile.lookback_days), end=end)
    adapter = source if source is not None else ArxivSource(profile.arxiv)
    run_id = store.start_run(profile_name, profile, adapter.name, window)
    try:
        for paper in adapter.fetch(window):
            # Enforce the application window even when using a different adapter.
            if window.contains(paper.updated_at):
                store.observe(run_id, paper, datetime.now(UTC))
        store.finish_run(run_id)
    except BaseException as error:
        try:
            store.finish_run(run_id, error=f"{type(error).__name__}: {error}")
        except Exception as recording_error:
            error.add_note(f"Could not record run failure: {recording_error}")
        if not isinstance(error, Exception):
            raise
        raise ScrapeError(run_id) from error
    return store.get_run(run_id)
