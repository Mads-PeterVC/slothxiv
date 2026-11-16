"""SQLite retrieval history; each observation is committed atomically."""

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from slothxiv.config import Profile
from slothxiv.models import Paper, RetrievalRun, RetrievalWindow
from slothxiv.storage.migrations import migrate


def timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat()


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, timeout=10)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            migrate(self._connection)
        except BaseException:
            self._connection.close()
            raise

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def start_run(self, profile_name: str, profile: Profile, source: str,
                  window: RetrievalWindow) -> str:
        run_id = str(uuid4())
        with self._connection:
            self._connection.execute(
                """INSERT INTO retrieval_runs
                (run_id, profile_name, profile_json, source, window_start,
                 window_end, started_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'running')""",
                (run_id, profile_name, profile.model_dump_json(), source,
                 timestamp(window.start), timestamp(window.end), timestamp(window.end)),
            )
        return run_id

    def observe(self, run_id: str, paper: Paper, retrieved_at: datetime) -> None:
        observed = timestamp(retrieved_at)
        payload = paper.model_dump_json()
        key = (paper.source, paper.source_id)
        with self._connection:
            # Begin before checking status, preventing finish/observe races.
            self._connection.execute("BEGIN IMMEDIATE")
            run = self._connection.execute(
                "SELECT profile_name, source, status FROM retrieval_runs WHERE run_id = ?", (run_id,),
            ).fetchone()
            if run is None or run["status"] != "running" or run["source"] != paper.source:
                raise ValueError("observation requires a running run with matching source")
            self._connection.execute("INSERT OR IGNORE INTO papers VALUES (?, ?)", key)
            self._connection.execute(
                "INSERT OR IGNORE INTO paper_revisions VALUES (?, ?, ?, ?, ?)",
                (*key, paper.revision, payload, timestamp(paper.updated_at)),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO profile_papers VALUES (?, ?, ?)", (run["profile_name"], *key),
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO retrieval_observations VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, *key, paper.revision, observed, payload),
            )

    def finish_run(self, run_id: str, *, error: str | None = None) -> None:
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE retrieval_runs SET status = ?, error = ?, finished_at = ?
                WHERE run_id = ? AND status = 'running'""",
                ("completed" if error is None else "failed", error,
                 timestamp(datetime.now(UTC)), run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("run is missing or already finished")

    def get_run(self, run_id: str) -> RetrievalRun:
        row = self._connection.execute(
            """SELECT r.*, (SELECT count(*) FROM retrieval_observations o
               WHERE o.run_id = r.run_id) AS observation_count
               FROM retrieval_runs r WHERE r.run_id = ?""", (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return RetrievalRun(
            run_id=row["run_id"], profile_name=row["profile_name"],
            profile_snapshot=json.loads(row["profile_json"]), source=row["source"],
            window=RetrievalWindow(start=row["window_start"], end=row["window_end"]),
            started_at=row["started_at"], finished_at=row["finished_at"],
            status=row["status"], error=row["error"], observation_count=row["observation_count"],
        )

    def list_runs(self) -> list[RetrievalRun]:
        rows = self._connection.execute(
            "SELECT run_id FROM retrieval_runs ORDER BY started_at, run_id",
        ).fetchall()
        return [self.get_run(row["run_id"]) for row in rows]

    def list_papers(self, profile_name: str | None = None) -> list[Paper]:
        """Return all observed revisions, optionally associated with a profile."""
        query = "SELECT r.paper_json FROM paper_revisions r"
        parameters = ()
        if profile_name is not None:
            query += """ JOIN profile_papers p USING (source, source_id)
                         WHERE p.profile_name = ?"""
            parameters = (profile_name,)
        query += " ORDER BY r.source, r.source_id, r.revision"
        return [Paper.model_validate_json(row[0]) for row in self._connection.execute(query, parameters)]
