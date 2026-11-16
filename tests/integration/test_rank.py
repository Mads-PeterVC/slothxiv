from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from slothxiv.cli import main
from slothxiv.config import ArxivSettings, EvaluationSettings, Profile
from slothxiv.evaluation import AgentResponse, EvaluationResult
from slothxiv.evaluation.workflow import RankError, rank
from slothxiv.models import RetrievalWindow
from slothxiv.sources.arxiv import parse_feed
from slothxiv.storage.migrations import MIGRATIONS
from slothxiv.storage.sqlite import SQLiteStore


def profile(**changes):
    return Profile(lookback_days=2, arxiv=ArxivSettings(keywords=("graphs",)),
                   evaluation=EvaluationSettings(instructions="Graph representation learning", **changes))


def seed(store, papers, name="graphs"):
    run_id = store.start_run(name, profile(), "arxiv", RetrievalWindow(
        start=datetime(2026, 11, 1, tzinfo=UTC), end=datetime(2026, 11, 16, tzinfo=UTC)))
    for paper in papers:
        store.observe(run_id, paper, datetime.now(UTC))
    store.finish_run(run_id)


def fake_cli(tmp_path, monkeypatch, *, mode="success"):
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    executable = directory / "claude"
    # This child substitutes only the external agent; all application/storage
    # code and subprocess invocation run normally, without network or credentials.
    executable.write_text(f'''#!{sys.executable}
import json, sys
prompt = sys.stdin.read()
data = json.loads(prompt.split("# Untrusted candidate metadata (JSON)\\n\\n", 1)[1])
mode = {mode!r}
if mode == "partial" and data["source_id"].endswith("2"):
    print("authentication unavailable", file=sys.stderr)
    sys.exit(1)
result = {{"paper_id": data["paper_id"], "revision": data["revision"],
          "score": 75, "justification": "Matches graph learning criteria",
          "generated_keywords": ["graph learning"]}}
if mode == "mismatch": result["paper_id"] = "arxiv:wrong"
print(json.dumps({{"subtype":"success", "is_error":False,
                  "structured_output":result, "modelUsage":{{"claude-sonnet-fixture":{{}}}}}}))
''')
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))


def papers(arxiv_page):
    return parse_feed(arxiv_page([
        ("2611.00001v1", "2026-11-15T10:00:00Z"),
        ("2611.00001v2", "2026-11-15T12:00:00Z"),
        ("2611.00002v1", "2026-11-15T11:00:00Z"),
    ]))[2]


def test_real_subprocess_persistence_reuse_force_and_model_change(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch)
    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        seed(store, papers(arxiv_page))
        first = rank("graphs", profile(), store)
        assert first.run.status == "completed"
        assert [e.evaluation.paper.revision for e in first.entries] == ["2", "1"]
        assert all(not e.reused for e in first.entries)
    with SQLiteStore(path) as store:
        second = rank("graphs", profile(), store)
        assert all(e.reused for e in second.entries)
        assert len(store.list_evaluations()) == 2
        rank("graphs", profile(), store, force=True)
        assert len(store.list_evaluations()) == 4
        switched = rank("graphs", profile(model="opus"), store)
        assert all(not e.reused for e in switched.entries)
        assert len(store.list_evaluations("graphs")) == 6
        assert all(r.status == "completed" for r in store.list_evaluation_runs())
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM evaluation_run_entries").fetchone()[0] == 8
        assert "opus" in connection.execute(
            "SELECT agent_json FROM evaluation_runs WHERE run_id=?", (switched.run.run_id,),
        ).fetchone()[0]


def test_partial_failure_continues_and_only_failed_candidates_are_retried(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch, mode="partial")
    with SQLiteStore(tmp_path / "history.db") as store:
        seed(store, papers(arxiv_page))
        result = rank("graphs", profile(), store)
        assert result.run.status == "failed"
        assert len(result.entries) == len(result.failures) == 1
        fake_cli(tmp_path, monkeypatch)
        retried = rank("graphs", profile(), store)
        assert retried.run.status == "completed"
        assert sum(e.reused for e in retried.entries) == 1


def test_failure_of_first_candidate_does_not_stop_later_candidates(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch, mode="partial")
    rows = papers(arxiv_page)
    rows[-1] = rows[-1].model_copy(update={"updated_at": datetime(2026, 11, 15, 14, tzinfo=UTC)})
    with SQLiteStore(tmp_path / "history.db") as store:
        seed(store, rows)
        result = rank("graphs", profile(), store)
        assert len(result.entries) == len(result.failures) == 1
        assert result.entries[0].evaluation.paper.source_id == "2611.00001"


def test_application_controls_score_order_and_ties(tmp_path, arxiv_page):
    class Scored:
        identity = {"adapter": "scored"}

        def evaluate(self, request):
            return AgentResponse(result=EvaluationResult(
                paper_id=request.paper.paper_id, revision=request.paper.revision,
                score=90 if request.paper.source_id.endswith("2") else 50,
                justification="Matches criteria", generated_keywords=(),
            ))

    with SQLiteStore(tmp_path / "history.db") as store:
        seed(store, papers(arxiv_page))
        result = rank("graphs", profile(), store, agent=Scored())
        assert [e.evaluation.response.result.score for e in result.entries] == [90, 50]
        assert result.entries[0].evaluation.paper.source_id == "2611.00002"


def test_changed_criteria_re_evaluates_and_preserves_history(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch)
    with SQLiteStore(tmp_path / "history.db") as store:
        seed(store, papers(arxiv_page))
        rank("graphs", profile(), store)
        modified = profile().model_copy(update={
            "evaluation": EvaluationSettings(instructions="Statistical graph theory"),
        })
        result = rank("graphs", modified, store)
        assert all(not e.reused for e in result.entries)
        assert len(store.list_evaluations()) == 4


def test_mismatched_response_is_failed_not_stored_as_success(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch, mode="mismatch")
    with SQLiteStore(tmp_path / "history.db") as store:
        seed(store, papers(arxiv_page))
        result = rank("graphs", profile(), store, limit=1)
        assert result.run.status == "failed"
        assert "mismatched" in next(iter(result.failures.values()))
        assert store.list_evaluations() == []


def test_empty_run_never_calls_agent(tmp_path):
    class Never:
        identity = {"adapter": "never"}

        def evaluate(self, request):
            pytest.fail("empty run must not invoke agent")

    with SQLiteStore(tmp_path / "history.db") as store:
        result = rank("graphs", profile(), store, agent=Never())
        assert result.run.status == "completed"
        assert result.entries == ()


def test_interruption_marks_attempt_and_run_failed(tmp_path, arxiv_page):
    class Interrupted:
        identity = {"adapter": "interrupted"}

        def evaluate(self, request):
            raise KeyboardInterrupt

    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        seed(store, papers(arxiv_page))
        with pytest.raises(KeyboardInterrupt):
            rank("graphs", profile(), store, agent=Interrupted())
        assert store.list_evaluation_runs()[0].status == "failed"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT status FROM evaluations").fetchall() == [("failed",)]


def test_storage_failure_stops_run_and_preserves_diagnostic(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch)
    with SQLiteStore(tmp_path / "history.db") as store:
        seed(store, papers(arxiv_page))

        def broken(*args):
            raise sqlite3.OperationalError("simulated storage failure")

        monkeypatch.setattr(store, "complete_evaluation", broken)
        with pytest.raises(RankError) as caught:
            rank("graphs", profile(), store)
        failed = store.get_evaluation_run(caught.value.run_id)
        assert failed.status == "failed"
        assert "simulated storage failure" in failed.error
        assert store.list_evaluations() == []


def test_abandoned_evaluation_run_remains_running(tmp_path):
    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        run_id = store.start_evaluation_run("graphs", profile(), {"adapter": "test"}, "v1", 0, {})
    with SQLiteStore(path) as store:
        assert store.get_evaluation_run(run_id).status == "running"
        assert store.get_evaluation_run(run_id).finished_at is None


def test_run_provenance_and_request_are_inspectable(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch)
    path = tmp_path / "history.db"
    with SQLiteStore(path) as store:
        seed(store, papers(arxiv_page))
        ranked = rank("graphs", profile(), store, limit=1)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM evaluation_runs WHERE run_id=?", (ranked.run.run_id,)).fetchone()
        assert json.loads(row["profile_json"])["evaluation"]["instructions"] == profile().evaluation.instructions
        assert json.loads(row["agent_json"])["model"] == "sonnet"
        assert json.loads(row["options_json"])["limit"] == 1
        attempt = connection.execute("SELECT * FROM evaluations").fetchone()
        assert json.loads(attempt["request_json"])["paper"]["revision"] == "2"
        assert attempt["finished_at"] >= attempt["started_at"]
        assert json.loads(attempt["record_json"])["response"]["reported_models"] == ["claude-sonnet-fixture"]


def test_upgrade_from_milestone_one_preserves_data(tmp_path, arxiv_page):
    path = tmp_path / "history.db"
    paper = papers(arxiv_page)[0]
    with sqlite3.connect(path) as connection:
        for statement in MIGRATIONS[0]:
            connection.execute(statement)
        connection.execute("PRAGMA user_version=1")
        connection.execute("INSERT INTO papers VALUES (?,?)", (paper.source, paper.source_id))
        connection.execute("INSERT INTO paper_revisions VALUES (?,?,?,?,?)", (
            paper.source, paper.source_id, paper.revision, paper.model_dump_json(), paper.updated_at.isoformat()))
    with SQLiteStore(path) as store:
        assert store.list_papers() == [paper]
        assert store.list_evaluation_runs() == []
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2



def write_config(path, database):
    path.write_text(f'''[storage]
database = {json.dumps(str(database))}
[profiles.graphs]
lookback_days = 2
[profiles.graphs.arxiv]
keywords = ["graphs"]
[profiles.graphs.evaluation]
instructions = "Graph representation learning"
model = "sonnet"
timeout_seconds = 30
''')


def test_rank_cli_installed_outside_checkout(tmp_path, monkeypatch, arxiv_page):
    fake_cli(tmp_path, monkeypatch)
    database = tmp_path / "history.db"
    config = tmp_path / "config.toml"
    write_config(config, database)
    with SQLiteStore(database) as store:
        seed(store, papers(arxiv_page))
    executable = Path(sys.executable).parent / "slothxiv"
    completed = subprocess.run([str(executable), "rank", "--config", str(config),
                                "--profile", "graphs", "--limit", "1"], cwd=tmp_path,
                               capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert str(database) in completed.stdout
    assert "75/100" in completed.stdout
    assert "Generated keywords: graph learning" in completed.stdout


def test_rank_cli_partial_failure_exit(tmp_path, monkeypatch, arxiv_page, capsys):
    fake_cli(tmp_path, monkeypatch, mode="partial")
    database = tmp_path / "history.db"
    config = tmp_path / "config.toml"
    write_config(config, database)
    with SQLiteStore(database) as store:
        seed(store, papers(arxiv_page))
    with pytest.raises(SystemExit) as caught:
        main(["rank", "--config", str(config), "--profile", "graphs"])
    assert caught.value.code == 1
    output = capsys.readouterr()
    assert "1 ranked, 1 failed" in output.out
    assert "authentication" in output.err


@pytest.mark.parametrize("format", ["json", "markdown", "plain", "rich"])
def test_cli_output_formats(tmp_path, monkeypatch, arxiv_page, capsys, format):
    fake_cli(tmp_path, monkeypatch)
    database = tmp_path / "history.db"
    config = tmp_path / "config.toml"
    write_config(config, database)
    with SQLiteStore(database) as store:
        seed(store, papers(arxiv_page))
    main(["rank", "--config", str(config), "--profile", "graphs", "--limit", "1", "--format", format])
    output = capsys.readouterr()
    assert output.err == ""
    if format == "json":
        value = json.loads(output.out)
        assert value["ranking"]["run"]["status"] == "completed"
        assert value["ranking"]["entries"][0]["evaluation"]["response"]["result"]["score"] == 75
    elif format == "markdown":
        assert "# Paper ranking: graphs" in output.out and "**Score:** 75/100" in output.out
    else:
        assert "75/100" in output.out


def test_cli_failed_ranking_still_emits_valid_json(tmp_path, monkeypatch, arxiv_page, capsys):
    fake_cli(tmp_path, monkeypatch, mode="partial")
    database = tmp_path / "history.db"
    config = tmp_path / "config.toml"
    write_config(config, database)
    with SQLiteStore(database) as store:
        seed(store, papers(arxiv_page))
    with pytest.raises(SystemExit) as caught:
        main(["rank", "--config", str(config), "--profile", "graphs", "--format", "json"])
    assert caught.value.code == 1
    output = capsys.readouterr()
    value = json.loads(output.out)
    assert value["ranking"]["run"]["status"] == "failed"
    assert len(value["ranking"]["failures"]) == len(value["ranking"]["entries"]) == 1
    assert "authentication" in output.err


def test_rank_cli_missing_instructions_does_not_create_database(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[profiles.graphs]\nlookback_days=1\n[profiles.graphs.arxiv]\nkeywords=["graphs"]')
    database = tmp_path / "history.db"
    with pytest.raises(SystemExit) as caught:
        main(["rank", "--config", str(config), "--profile", "graphs", "--database", str(database)])
    assert caught.value.code == 1
    assert not database.exists()
