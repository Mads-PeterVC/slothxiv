"""Rich terminal presentation and undecorated plain, Markdown, and JSON writers."""

import html
import json
from pathlib import Path
import re
import sys
from typing import Literal, TextIO

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from slothxiv.evaluation import Ranking
from slothxiv.models import RetrievalRun

OutputFormat = Literal["auto", "rich", "plain", "markdown", "json"]


def markdown_text(value: object) -> str:
    """Quote arbitrary metadata as inline text, never as Markdown instructions."""
    text = html.escape(" ".join(str(value).split()), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|\-])", r"\\\1", text)


def ranking_plain(ranking: Ranking, database: Path) -> str:
    lines = [f"Database: {database}",
             f"Run {ranking.run.run_id}: {ranking.run.status}; "
             f"{len(ranking.entries)} ranked, {len(ranking.failures)} failed"]
    for position, entry in enumerate(ranking.entries, 1):
        paper = entry.evaluation.paper
        result = entry.evaluation.response.result
        reused = " (reused)" if entry.reused else ""
        lines.extend(["", f"{position}. {result.score}/100 {paper.title}{reused}",
                      f"   {paper.paper_id} revision {paper.revision} — {paper.url}",
                      f"   {result.justification}",
                      f"   Generated keywords: {', '.join(result.generated_keywords)}"])
    if not ranking.entries:
        lines.extend(["", "No papers were ranked."])
    return "\n".join(lines)


def ranking_markdown(ranking: Ranking, database: Path) -> str:
    escape = markdown_text
    lines = [f"# Paper ranking: {escape(ranking.run.profile_name)}", "",
             f"Database: {escape(database)}", "", f"Run: {escape(ranking.run.run_id)}", "",
             f"Status: {ranking.run.status}; {len(ranking.entries)} ranked, "
             f"{len(ranking.failures)} failed."]
    for position, entry in enumerate(ranking.entries, 1):
        paper = entry.evaluation.paper
        result = entry.evaluation.response.result
        lines.extend(["", f"## {position}. {escape(paper.title)}", "",
                      f"**Score:** {result.score}/100", "",
                      f"**Paper:** {escape(paper.paper_id)}; revision {escape(paper.revision)}", "",
                      f"**URL:** {escape(paper.url)}", "",
                      f"**Evaluation:** {'Reused' if entry.reused else 'New'}", "",
                      escape(result.justification), "",
                      "**Generated keywords:** " + (", ".join(map(escape, result.generated_keywords)) or "None")])
    if not ranking.entries:
        lines.extend(["", "No papers were ranked."])
    if ranking.failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- **{escape(paper_id)}:** {escape(error)}"
                     for paper_id, error in ranking.failures.items())
    return "\n".join(lines)


class TerminalOutput:
    def __init__(self, format: OutputFormat = "auto", *, stdout: TextIO | None = None,
                 stderr: TextIO | None = None) -> None:
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stderr = stderr if stderr is not None else sys.stderr
        self.format = ("rich" if self.stdout.isatty() else "plain") if format == "auto" else format
        self.console = Console(file=self.stdout, highlight=False)
        self.error_console = Console(file=self.stderr, highlight=False)

    def _json(self, value: dict) -> None:
        # Builtin JSON output deliberately bypasses Rich, wrapping, and ANSI.
        print(json.dumps(value, ensure_ascii=True, indent=2), file=self.stdout)

    def scrape(self, run: RetrievalRun, database: Path) -> None:
        summary = f"Completed run {run.run_id}: {run.observation_count} paper revision(s) observed"
        if self.format == "json":
            self._json({"database": str(database), "retrieval": run.model_dump(mode="json")})
        elif self.format == "markdown":
            print(f"# Retrieval: {markdown_text(run.profile_name)}\n\n"
                  f"Database: {markdown_text(database)}\n\n{markdown_text(summary)}", file=self.stdout)
        elif self.format == "rich":
            self.console.print(Text("Retrieval complete", style="bold green"))
            self.console.print(Text(summary))
            self.console.print(Text(f"Database: {database}", style="dim"))
        else:
            print(f"Database: {database}\n{summary}", file=self.stdout)

    def ranking(self, ranking: Ranking, database: Path) -> None:
        if self.format == "json":
            self._json({"database": str(database), "ranking": ranking.model_dump(mode="json")})
        elif self.format == "markdown":
            print(ranking_markdown(ranking, database), file=self.stdout)
        elif self.format == "rich":
            self._rich_ranking(ranking, database)
        else:
            print(ranking_plain(ranking, database), file=self.stdout)

    def _rich_ranking(self, ranking: Ranking, database: Path) -> None:
        self.console.print(Text(f"Paper ranking · {ranking.run.profile_name}", style="bold cyan"))
        status = "green" if ranking.run.status == "completed" else "red"
        self.console.print(Text(f"{len(ranking.entries)} ranked, {len(ranking.failures)} failed "
                                f"· {ranking.run.status}", style=status))
        self.console.print(Text(f"Run: {ranking.run.run_id}\nDatabase: {database}", style="dim"))
        self.console.print()
        for position, entry in enumerate(ranking.entries, 1):
            paper = entry.evaluation.paper
            result = entry.evaluation.response.result
            color = "green" if result.score >= 75 else "yellow" if result.score >= 50 else "dim"
            heading = Text(f"{position}. {result.score}/100", style=f"bold {color}")
            heading.append(" · reused" if entry.reused else " · new", style="dim")
            body = Text()
            body.append(paper.title, style="bold")
            body.append(f"\n{paper.paper_id} · revision {paper.revision}", style="dim")
            body.append(f"\n{paper.url}", style="cyan")
            body.append(f"\n\n{result.justification}", style="default")
            body.append("\n\nGenerated keywords: ", style="dim")
            body.append(", ".join(result.generated_keywords) or "None", style="default")
            self.console.print(Panel(body, title=heading, title_align="left", border_style=color,
                                     padding=(1, 2)))
            self.console.print()
        if not ranking.entries:
            self.console.print(Text("No papers were ranked.", style="dim"))

    def error(self, message: str) -> None:
        if self.format == "rich":
            self.error_console.print(Text(f"slothxiv: {message}", style="red"))
        else:
            print(f"slothxiv: {message}", file=self.stderr)
