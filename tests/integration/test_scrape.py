from datetime import UTC, datetime
import sqlite3

import pytest

from slothxiv.application import ScrapeError, scrape
from slothxiv.config import ArxivSettings, Profile
from slothxiv.models import RetrievalWindow
from slothxiv.sources.arxiv import ArxivSource, parse_feed
from slothxiv.storage.sqlite import SQLiteStore

START = datetime(2026, 11, 16, tzinfo=UTC)


def profile():
    return Profile(lookback_days=2, arxiv=ArxivSettings(categories=("cs.LG",)))


def source(data):
    return ArxivSource(profile().arxiv, transport=lambda _: data, sleep=lambda _: None)


def test_repeat_revisions_profiles_and_reopen(tmp_path, arxiv_page):
    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        first = scrape("graphs", profile(), store, source=source(arxiv_page()), started_at=START)
        second = scrape("graphs", profile(), store, source=source(arxiv_page()), started_at=START)
        third = scrape("other", profile(), store, source=source(arxiv_page([
            ("2611.00001v2", "2026-11-15T14:00:00Z"),
        ])), started_at=START)
        assert first.status == second.status == third.status == "completed"
        assert first.run_id != second.run_id
        assert first.profile_snapshot == profile().model_dump(mode="json")
        assert first.window.start == datetime(2026, 11, 14, tzinfo=UTC)
        assert all(run.observation_count == 1 for run in store.list_runs())
    with SQLiteStore(path) as store:
        assert len(store.list_papers()) == 2
        assert {paper.revision for paper in store.list_papers("graphs")} == {"1", "2"}
        assert store.list_papers("missing") == []
        assert store.get_run(first.run_id).finished_at is not None
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM papers").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM retrieval_observations").fetchone()[0] == 3
        assert connection.execute("SELECT count(*) FROM profile_papers").fetchone()[0] == 2


def test_observations_preserve_changed_metadata(tmp_path, arxiv_page):
    with SQLiteStore(tmp_path / "history.db") as store:
        scrape("graphs", profile(), store, source=source(arxiv_page()), started_at=START)
        scrape("graphs", profile(), store, source=source(arxiv_page().replace(b"12 pages", b"13 pages")), started_at=START)
        assert store.list_papers()[0].metadata["comment"] == "12 pages"
    with sqlite3.connect(tmp_path / "history.db") as connection:
        rows = connection.execute("SELECT paper_json FROM retrieval_observations ORDER BY rowid").fetchall()
        assert "12 pages" in rows[0][0]
        assert "13 pages" in rows[1][0]


def test_failure_retains_partial_history(tmp_path, arxiv_page):
    calls = []

    def transport(_):
        calls.append(1)
        if len(calls) == 2:
            return b"malformed XML"
        return arxiv_page(total=2)

    adapter = ArxivSource(profile().arxiv, transport=transport, page_size=1, sleep=lambda _: None)
    with SQLiteStore(tmp_path / "history.db") as store:
        with pytest.raises(ScrapeError) as caught:
            scrape("graphs", profile(), store, source=adapter, started_at=START)
        run = store.get_run(caught.value.run_id)
        assert run.status == "failed"
        assert run.observation_count == 1
        assert run.error.startswith("SourceError:")
        assert run.finished_at is not None
        assert len(store.list_papers()) == 1


def test_empty_run_completes(tmp_path, arxiv_page):
    with SQLiteStore(tmp_path / "history.db") as store:
        result = scrape("graphs", profile(), store, source=source(arxiv_page([])), started_at=START)
        assert result.status == "completed"
        assert result.observation_count == 0
        assert store.list_papers() == []


def test_application_checks_window_for_other_sources(tmp_path, arxiv_page):
    papers = parse_feed(arxiv_page([
        ("2611.00001v1", "2026-11-14T00:00:00Z"),
        ("2611.00002v1", "2026-11-16T00:00:00Z"),
        ("2611.00003v1", "2026-11-13T23:59:59Z"),
    ]))[2]

    class Adapter:
        name = "arxiv"

        def fetch(self, window):
            return iter(papers)

    with SQLiteStore(tmp_path / "history.db") as store:
        result = scrape("graphs", profile(), store, source=Adapter(), started_at=START)
        assert result.observation_count == 1
        assert store.list_papers()[0].source_id == "2611.00001"


def test_interruption_and_abandoned_run_are_not_success(tmp_path):
    class Interrupted:
        name = "arxiv"

        def fetch(self, window):
            raise KeyboardInterrupt

    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        with pytest.raises(KeyboardInterrupt):
            scrape("graphs", profile(), store, source=Interrupted(), started_at=START)
        assert store.list_runs()[0].status == "failed"
        run_id = store.start_run("graphs", profile(), "arxiv", RetrievalWindow(
            start=datetime(2026, 11, 14, tzinfo=UTC), end=START,
        ))
    with SQLiteStore(path) as store:
        assert store.get_run(run_id).status == "running"
        assert store.get_run(run_id).finished_at is None
