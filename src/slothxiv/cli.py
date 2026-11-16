"""Argument parsing and terminal presentation only."""

import argparse
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from slothxiv.application import ScrapeError, scrape
from slothxiv.config import default_config_path, default_database_path, load_config
from slothxiv.storage.sqlite import SQLiteStore
from slothxiv.evaluation.workflow import RankError, rank
from slothxiv.output import TerminalOutput


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
        subcommand.add_argument("--format", choices=("auto", "rich", "plain", "markdown", "json"),
                                default="auto", help="Output format (default: rich in a terminal, plain when piped)")
    args = parser.parse_args(argv)
    output = TerminalOutput(args.format)
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
        if args.command == "scrape":
            output.scrape(result, database_path)
        else:
            output.ranking(ranked, database_path)
            for paper_id, error in ranked.failures.items():
                output.error(f"{paper_id}: {error}")
            if ranked.failures:
                raise SystemExit(1)
    except (ScrapeError, RankError) as error:
        output.error(f"{error}: {error.__cause__}")
        raise SystemExit(1) from error
    except (OSError, ValueError, sqlite3.Error, RuntimeError, ValidationError) as error:
        output.error(str(error))
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        output.error("interrupted")
        raise SystemExit(130) from None
