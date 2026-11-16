# slothxiv

slothxiv is a Python tool being designed to discover research papers, rank them
against configurable research profiles using an LLM, and produce structured
digests. The project is currently in design; the application is still a skeleton.

The initial workflow will use arXiv metadata and abstracts, headless LLM CLI
agents, and persistent retrieval and evaluation history. Paper sources and agent
implementations will sit behind separate interfaces.

## Project memory

The [development log](development-log.md) records changes, their rationale,
validation, and unresolved questions for future development sessions. Read it
alongside the repository's `AGENTS.md`, which holds the current requirements and
development instructions. Historical entries describe decisions at the time;
`AGENTS.md` describes the current agreed direction.

## Running tests

```sh
uv sync --group dev
uv run --group dev pytest
```

Unit tests mirror the package layout under `tests/unit/`. Offline integration
tests live in `tests/integration/` and are included in the default suite. Use
fixtures and fake external adapters rather than live paper sources or LLM calls.

## Working on the documentation

From the repository root, install the documentation dependencies and preview:

```sh
uv sync --group docs
uv run --group docs zensical serve
```

Build the static site:

```sh
uv run --group docs zensical build --strict
```

Source pages live in `docs/`, and navigation is configured in `zensical.toml`.
Generated output goes to `site/` and is not committed. No hosting or automatic
deployment has been configured.

See the [official Zensical documentation](https://zensical.org/docs/) for the
documentation tool's configuration and usage.
