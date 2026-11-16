from datetime import UTC, datetime
from io import StringIO
import json
from pathlib import Path

import pytest
from rich.console import Console

from slothxiv.evaluation import (
    AgentResponse, EvaluationRecord, EvaluationResult, EvaluationRun, RankedEntry, Ranking,
)
from slothxiv.output.terminal import TerminalOutput
from slothxiv.sources.arxiv import parse_feed


@pytest.fixture
def ranking(arxiv_page):
    time = datetime(2026, 11, 16, tzinfo=UTC)
    paper = parse_feed(arxiv_page())[2][0].model_copy(update={
        "title": "Graph [red]learning[/red] with *sparse* structures <script>",
    })
    record = EvaluationRecord(
        evaluation_id="evaluation-1", run_id="run-1", paper=paper,
        response=AgentResponse(result=EvaluationResult(
            paper_id=paper.paper_id, revision=paper.revision, score=83,
            justification="Relevant [bold]method[/bold].\n# Not a heading",
            generated_keywords=("graph learning", "sparse structures"),
        )), started_at=time, finished_at=time,
    )
    return Ranking(run=EvaluationRun(
        run_id="run-1", profile_name="graphs", started_at=time,
        finished_at=time, status="completed", candidate_count=1,
    ), entries=(RankedEntry(evaluation=record, reused=True),), failures={})


def test_json_is_complete_undecorated_structured_data(ranking, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    stream = StringIO()
    output = TerminalOutput("json", stdout=stream)
    output.ranking(ranking, Path("/tmp/papers.db"))
    result = json.loads(stream.getvalue())
    assert result["database"] == "/tmp/papers.db"
    assert result["ranking"] == ranking.model_dump(mode="json")
    assert "\x1b" not in stream.getvalue()
    assert result["ranking"]["entries"][0]["reused"] is True


def test_markdown_is_source_and_escapes_external_markup(ranking):
    stream = StringIO()
    TerminalOutput("markdown", stdout=stream).ranking(ranking, Path("/tmp/papers.db"))
    text = stream.getvalue()
    assert "# Paper ranking: graphs" in text
    assert "**Score:** 83/100" in text
    assert r"\[red\]learning\[/red\]" in text
    assert "&lt;script&gt;" in text
    assert r"\# Not a heading" in text
    assert "\x1b" not in text


@pytest.mark.parametrize("width", [40, 80, 120])
def test_rich_wraps_without_interpreting_metadata_markup(ranking, width):
    stream = StringIO()
    output = TerminalOutput("rich", stdout=stream)
    output.console = Console(file=stream, width=width, color_system=None)
    output.ranking(ranking, Path("/tmp/papers.db"))
    text = stream.getvalue()
    assert "83/100" in text
    assert "[red]learning[/red]" in text
    assert "reused" in text
    assert "Not a heading" in text
    assert all(len(line) <= width for line in text.splitlines())


def test_plain_does_not_add_wrapping_or_ansi(ranking):
    stream = StringIO()
    TerminalOutput("plain", stdout=stream).ranking(ranking, Path("/tmp/papers.db"))
    text = stream.getvalue()
    assert ranking.entries[0].evaluation.paper.title in text
    assert "83/100" in text and "(reused)" in text
    assert "\x1b" not in text


def test_auto_chooses_rich_for_tty_and_plain_for_pipe():
    class Terminal(StringIO):
        def isatty(self):
            return True

    assert TerminalOutput(stdout=Terminal()).format == "rich"
    assert TerminalOutput(stdout=StringIO()).format == "plain"


@pytest.mark.parametrize("format", ["rich", "plain", "markdown", "json"])
def test_empty_results_and_failures_remain_visible(ranking, format):
    stream = StringIO()
    failed = ranking.model_copy(update={
        "run": ranking.run.model_copy(update={"status": "failed"}),
        "entries": (), "failures": {"arxiv:missing": "Timed out"},
    })
    output = TerminalOutput(format, stdout=stream)
    output.ranking(failed, Path("/tmp/papers.db"))
    text = stream.getvalue()
    if format == "json":
        assert json.loads(text)["ranking"]["failures"] == failed.failures
    else:
        assert "No papers were ranked." in text
        assert "1 failed" in text
    if format == "markdown":
        assert "## Failures" in text and "Timed out" in text


def test_errors_do_not_contaminate_json_stdout(ranking):
    stream, errors = StringIO(), StringIO()
    output = TerminalOutput("json", stdout=stream, stderr=errors)
    output.ranking(ranking, Path("/tmp/papers.db"))
    output.error("arxiv:missing: Timed out")
    assert json.loads(stream.getvalue())["ranking"]["run"]["status"] == "completed"
    assert "Timed out" in errors.getvalue()
