"""Argument parsing and terminal presentation only."""

import argparse
from pathlib import Path
import sqlite3
import sys

from pydantic import ValidationError

from slothxiv.application import ScrapeError, scrape
from slothxiv.config import default_config_path, default_database_path, load_config
from slothxiv.storage.sqlite import SQLiteStore
from slothxiv.evaluation.workflow import RankError, rank


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="slothxiv", description="Research paper retrieval and ranking")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("scrape", help="Retrieve arXiv papers for a named profile")
    ranking = commands.add_parser("rank", help="Evaluate and rank stored profile papers with Claude CLI")
    ranking.add_argument("--limit", type=int, help="Evaluate at most this many newest candidates")
    ranking.add_argument("--force", action="store_true", help="Evaluate again, preserving earlier results")
    for subcommand in (command, ranking):
        subcommand.add_argument("--profile", required=True)
        subcommand.add_argument("--config", type=Path, help=f"TOML file (default: {default_config_path()})")
        subcommand.add_argument("--database", type=Path, help=f"SQLite path (default: {default_database_path()})")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.profile not in config.profiles:
            raise ValueError(f"unknown profile {args.profile!r}; available: {', '.join(config.profiles)}")
        database = args.database or config.storage.database or default_database_path()
        profile = config.profiles[args.profile]
        if args.command == "rank":
            if profile.evaluation is None:
                raise ValueError("profile requires [profiles.<name>.evaluation] instructions for ranking")
            if args.limit is not None and args.limit < 1:
                raise ValueError("--limit must be a positive integer")
        with SQLiteStore(database) as store:
            database_path = store.path
            if args.command == "scrape":
                result = scrape(args.profile, profile, store)
            else:
                ranked = rank(args.profile, profile, store, limit=args.limit, force=args.force)
        print(f"Database: {database_path}")
        if args.command == "scrape":
            print(f"Completed run {result.run_id}: {result.observation_count} paper revision(s) observed")
        else:
            print(f"Run {ranked.run.run_id}: {ranked.run.status}; "
                  f"{len(ranked.entries)} ranked, {len(ranked.failures)} failed")
            for position, entry in enumerate(ranked.entries, 1):
                paper = entry.evaluation.paper
                evaluation = entry.evaluation.response.result
                reused = " (reused)" if entry.reused else ""
                print(f"{position}. {evaluation.score}/100 {paper.title}{reused}")
                print(f"   {paper.paper_id} revision {paper.revision} — {paper.url}")
                print(f"   {evaluation.justification}")
                print(f"   Generated keywords: {', '.join(evaluation.generated_keywords)}")
            for paper_id, error in ranked.failures.items():
                print(f"slothxiv: {paper_id}: {error}", file=sys.stderr)
            if ranked.failures:
                raise SystemExit(1)
    except (ScrapeError, RankError) as error:
        print(f"slothxiv: {error}: {error.__cause__}", file=sys.stderr)
        raise SystemExit(1) from error
    except (OSError, ValueError, sqlite3.Error, RuntimeError, ValidationError) as error:
        print(f"slothxiv: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        print("slothxiv: interrupted", file=sys.stderr)
        raise SystemExit(130) from None
