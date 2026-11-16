"""Argument parsing and terminal presentation only."""

import argparse
from pathlib import Path
import sqlite3
import sys

from pydantic import ValidationError

from slothxiv.application import ScrapeError, scrape
from slothxiv.config import default_config_path, default_database_path, load_config
from slothxiv.storage.sqlite import SQLiteStore


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="slothxiv", description="Research paper retrieval and history")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("scrape", help="Retrieve arXiv papers for a named profile")
    command.add_argument("--profile", required=True)
    command.add_argument("--config", type=Path, help=f"TOML file (default: {default_config_path()})")
    command.add_argument("--database", type=Path, help=f"SQLite path (default: {default_database_path()})")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.profile not in config.profiles:
            raise ValueError(f"unknown profile {args.profile!r}; available: {', '.join(config.profiles)}")
        database = args.database or config.storage.database or default_database_path()
        with SQLiteStore(database) as store:
            result = scrape(args.profile, config.profiles[args.profile], store)
        print(f"Completed run {result.run_id}: {result.observation_count} paper revision(s) observed")
    except ScrapeError as error:
        print(f"slothxiv: {error}: {error.__cause__}", file=sys.stderr)
        raise SystemExit(1) from error
    except (OSError, ValueError, sqlite3.Error, RuntimeError, ValidationError) as error:
        print(f"slothxiv: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        print("slothxiv: interrupted", file=sys.stderr)
        raise SystemExit(130) from None
