"""Ordered transactional schema migrations. Never edit an applied migration."""

import sqlite3

MIGRATIONS: tuple[tuple[str, ...], ...] = ((
    """CREATE TABLE papers (
        source TEXT NOT NULL, source_id TEXT NOT NULL,
        PRIMARY KEY (source, source_id))""",
    """CREATE TABLE paper_revisions (
        source TEXT NOT NULL, source_id TEXT NOT NULL, revision TEXT NOT NULL,
        paper_json TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (source, source_id, revision),
        FOREIGN KEY (source, source_id) REFERENCES papers(source, source_id))""",
    """CREATE TABLE retrieval_runs (
        run_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL,
        profile_json TEXT NOT NULL, source TEXT NOT NULL,
        window_start TEXT NOT NULL, window_end TEXT NOT NULL,
        started_at TEXT NOT NULL, finished_at TEXT,
        status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
        error TEXT)""",
    """CREATE TABLE profile_papers (
        profile_name TEXT NOT NULL, source TEXT NOT NULL, source_id TEXT NOT NULL,
        PRIMARY KEY (profile_name, source, source_id),
        FOREIGN KEY (source, source_id) REFERENCES papers(source, source_id))""",
    """CREATE TABLE retrieval_observations (
        run_id TEXT NOT NULL, source TEXT NOT NULL, source_id TEXT NOT NULL,
        revision TEXT NOT NULL, retrieved_at TEXT NOT NULL, paper_json TEXT NOT NULL,
        PRIMARY KEY (run_id, source, source_id, revision),
        FOREIGN KEY (run_id) REFERENCES retrieval_runs(run_id),
        FOREIGN KEY (source, source_id, revision)
            REFERENCES paper_revisions(source, source_id, revision))""",
    "CREATE INDEX revision_updates ON paper_revisions(updated_at)",
), (
    """CREATE TABLE evaluation_runs (
        run_id TEXT PRIMARY KEY, profile_name TEXT NOT NULL,
        profile_json TEXT NOT NULL, agent_json TEXT NOT NULL,
        prompt_version TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
        candidate_count INTEGER NOT NULL, options_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('running','completed','failed')), error TEXT)""",
    """CREATE TABLE evaluations (
        evaluation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
        reuse_key TEXT NOT NULL, request_json TEXT NOT NULL,
        started_at TEXT NOT NULL, finished_at TEXT,
        status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
        record_json TEXT, error TEXT,
        FOREIGN KEY(run_id) REFERENCES evaluation_runs(run_id))""",
    "CREATE INDEX evaluation_reuse ON evaluations(reuse_key, status)",
    """CREATE TABLE evaluation_run_entries (
        run_id TEXT NOT NULL, paper_id TEXT NOT NULL, evaluation_id TEXT NOT NULL,
        reused INTEGER NOT NULL CHECK(reused IN (0,1)),
        PRIMARY KEY(run_id, paper_id),
        FOREIGN KEY(run_id) REFERENCES evaluation_runs(run_id),
        FOREIGN KEY(evaluation_id) REFERENCES evaluations(evaluation_id))""",
))


def migrate(connection: sqlite3.Connection) -> None:
    # Serialize startup across processes, including the version check itself.
    connection.execute("BEGIN IMMEDIATE")
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise RuntimeError("database schema is newer than this slothxiv installation")
        for index in range(version, len(MIGRATIONS)):
            for statement in MIGRATIONS[index]:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {index + 1}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
