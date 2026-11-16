"""SQLite evaluation history, shared by the SQLite store."""

from datetime import UTC, datetime
import json
import sqlite3
from typing import Protocol
from uuid import uuid4

from slothxiv.config import Profile
from slothxiv.evaluation import (
    AgentResponse, EvaluationRecord, EvaluationRequest, EvaluationRun,
)
from slothxiv.models import Paper


class EvaluationStore(Protocol):
    def list_papers(self, profile_name: str | None = None) -> list[Paper]: ...
    def start_evaluation_run(self, profile_name: str, profile: Profile,
                             identity: dict[str, str | int], prompt_version: str,
                             count: int, options: dict[str, int | bool | None]) -> str: ...
    def find_evaluation(self, key: str) -> EvaluationRecord | None: ...
    def start_evaluation(self, run_id: str, key: str, request: EvaluationRequest) -> str: ...
    def complete_evaluation(self, evaluation_id: str, response: AgentResponse) -> EvaluationRecord: ...
    def fail_evaluation(self, evaluation_id: str, error: str) -> None: ...
    def link_evaluation(self, run_id: str, record: EvaluationRecord, reused: bool) -> None: ...
    def finish_evaluation_run(self, run_id: str, error: str | None = None) -> None: ...
    def get_evaluation_run(self, run_id: str) -> EvaluationRun: ...


def now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteEvaluations:
    _connection: sqlite3.Connection

    def start_evaluation_run(self, profile_name: str, profile: Profile,
                             identity: dict[str, str | int], prompt_version: str,
                             count: int, options: dict[str, int | bool | None]) -> str:
        run_id = str(uuid4())
        with self._connection:
            self._connection.execute(
                """INSERT INTO evaluation_runs
                (run_id, profile_name, profile_json, agent_json, prompt_version,
                 started_at, candidate_count, options_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running')""",
                (run_id, profile_name, profile.model_dump_json(), json.dumps(identity),
                 prompt_version, now(), count, json.dumps(options)),
            )
        return run_id

    def find_evaluation(self, key: str) -> EvaluationRecord | None:
        row = self._connection.execute(
            """SELECT record_json FROM evaluations WHERE reuse_key = ? AND status = 'completed'
            ORDER BY finished_at DESC, evaluation_id LIMIT 1""", (key,),
        ).fetchone()
        return EvaluationRecord.model_validate_json(row[0]) if row else None

    def start_evaluation(self, run_id: str, key: str, request: EvaluationRequest) -> str:
        evaluation_id = str(uuid4())
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            self._require_running(run_id)
            self._connection.execute(
                """INSERT INTO evaluations
                (evaluation_id, run_id, reuse_key, request_json, started_at, status)
                VALUES (?, ?, ?, ?, ?, 'running')""",
                (evaluation_id, run_id, key, request.model_dump_json(), now()),
            )
        return evaluation_id

    def complete_evaluation(self, evaluation_id: str, response: AgentResponse) -> EvaluationRecord:
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM evaluations WHERE evaluation_id = ? AND status = 'running'",
                (evaluation_id,),
            ).fetchone()
            if row is None:
                raise ValueError("evaluation missing or already finished")
            self._require_running(row["run_id"])
            request = EvaluationRequest.model_validate_json(row["request_json"])
            if (response.result.paper_id, response.result.revision) != (
                request.paper.paper_id, request.paper.revision,
            ):
                raise ValueError("evaluation paper identity/revision does not match request")
            record = EvaluationRecord(
                evaluation_id=evaluation_id, run_id=row["run_id"], paper=request.paper,
                response=response, started_at=row["started_at"], finished_at=now(),
            )
            self._connection.execute(
                "UPDATE evaluations SET status='completed', finished_at=?, record_json=? "
                "WHERE evaluation_id=?", (record.finished_at.isoformat(), record.model_dump_json(), evaluation_id),
            )
        return record

    def fail_evaluation(self, evaluation_id: str, error: str) -> None:
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE evaluations SET status='failed', finished_at=?, error=? "
                "WHERE evaluation_id=? AND status='running'", (now(), error, evaluation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("evaluation missing or already finished")

    def link_evaluation(self, run_id: str, record: EvaluationRecord, reused: bool) -> None:
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            self._require_running(run_id)
            self._connection.execute(
                "INSERT INTO evaluation_run_entries VALUES (?, ?, ?, ?)",
                (run_id, record.paper.paper_id, record.evaluation_id, int(reused)),
            )

    def _require_running(self, run_id: str) -> None:
        row = self._connection.execute(
            "SELECT status FROM evaluation_runs WHERE run_id=?", (run_id,),
        ).fetchone()
        if row is None or row[0] != "running":
            raise ValueError("evaluation run missing or already finished")

    def finish_evaluation_run(self, run_id: str, error: str | None = None) -> None:
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE evaluation_runs SET status=?, finished_at=?, error=? "
                "WHERE run_id=? AND status='running'",
                ("failed" if error else "completed", now(), error, run_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("evaluation run missing or already finished")

    def get_evaluation_run(self, run_id: str) -> EvaluationRun:
        row = self._connection.execute(
            "SELECT * FROM evaluation_runs WHERE run_id=?", (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return EvaluationRun.model_validate({key: row[key] for key in EvaluationRun.model_fields})

    def list_evaluation_runs(self) -> list[EvaluationRun]:
        return [self.get_evaluation_run(row[0]) for row in self._connection.execute(
            "SELECT run_id FROM evaluation_runs ORDER BY started_at, run_id",
        ).fetchall()]

    def list_evaluations(self, profile_name: str | None = None) -> list[EvaluationRecord]:
        return [EvaluationRecord.model_validate_json(row[0]) for row in self._connection.execute(
            """SELECT e.record_json FROM evaluations e JOIN evaluation_runs r USING(run_id)
            WHERE e.status='completed' AND (? IS NULL OR r.profile_name=?)
            ORDER BY e.started_at, e.evaluation_id""", (profile_name, profile_name),
        )]
