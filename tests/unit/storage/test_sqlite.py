from datetime import UTC, datetime
import sqlite3

import pytest

from slothxiv.config import ArxivSettings, Profile
from slothxiv.models import RetrievalWindow
from slothxiv.sources.arxiv import parse_feed
from slothxiv.storage.migrations import migrate
from slothxiv.storage.sqlite import SQLiteStore


def start_run(store):
    return store.start_run("example", Profile(lookback_days=1, arxiv=ArxivSettings(keywords=("graphs",))),
                           "arxiv", RetrievalWindow(start=datetime(2026, 11, 14, tzinfo=UTC),
                                                    end=datetime(2026, 11, 16, tzinfo=UTC)))


def test_newer_schema_rejected_without_modification(tmp_path):
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")
    with pytest.raises(RuntimeError, match="newer"):
        SQLiteStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 999


def test_migration_failure_is_atomic(monkeypatch):
    import slothxiv.storage.migrations as migrations

    connection = sqlite3.connect(":memory:")
    monkeypatch.setattr(migrations, "MIGRATIONS", (("CREATE TABLE example (id INTEGER)", "INVALID SQL"),))
    with pytest.raises(sqlite3.OperationalError):
        migrate(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    connection.close()


def test_finished_run_rejects_observations_and_recompletion(tmp_path, arxiv_page):
    with SQLiteStore(tmp_path / "history.db") as store:
        run_id = start_run(store)
        store.finish_run(run_id)
        with pytest.raises(ValueError, match="running"):
            store.observe(run_id, parse_feed(arxiv_page())[2][0], datetime.now(UTC))
        assert store.list_papers() == []
        with pytest.raises(ValueError, match="finished"):
            store.finish_run(run_id)


def test_observation_failure_rolls_back_paper_and_association(tmp_path, arxiv_page):
    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        run_id = start_run(store)
        with sqlite3.connect(path) as connection:
            connection.execute('''CREATE TRIGGER fail_observation BEFORE INSERT ON retrieval_observations
                               BEGIN SELECT RAISE(ABORT, 'simulated failure'); END''')
        with pytest.raises(sqlite3.IntegrityError, match="simulated"):
            store.observe(run_id, parse_feed(arxiv_page())[2][0], datetime.now(UTC))
        assert store.list_papers() == []
        assert store.get_run(run_id).observation_count == 0


def test_naive_observation_time_rejected(tmp_path, arxiv_page):
    with SQLiteStore(tmp_path / "history.db") as store:
        run_id = start_run(store)
        with pytest.raises(ValueError, match="timezone-aware"):
            store.observe(run_id, parse_feed(arxiv_page())[2][0], datetime(2026, 11, 15))
