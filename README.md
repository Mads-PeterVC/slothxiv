# slothxiv

A Python tool for retrieving research papers for named profiles and preserving
discovery and evaluation history in SQLite. Claude CLI can evaluate and rank
stored candidates. Digest generation is planned but not yet implemented.

## Retrieve papers

```sh
uv tool install .
slothxiv scrape --config /absolute/path/to/config.toml --profile graphs
```

Example configuration:

```toml
[profiles.graphs]
lookback_days = 2

[profiles.graphs.arxiv]
categories = ["cs.LG"]
keywords = ["graph learning"]
```

See the [retrieval guide](docs/retrieval.md) for default locations, path overrides,
query and window semantics, history, failures, and library usage.

## Rank stored papers

Install and authenticate Claude CLI, then add evaluation instructions to a profile:

```toml
[profiles.graphs.evaluation]
instructions = "Prioritize methodological contributions to graph representation learning."
model = "sonnet" # Change to "opus" or another supported model when desired.
timeout_seconds = 120
```

```sh
slothxiv rank --config /absolute/path/to/config.toml --profile graphs --limit 3
```

Results include relevance scores, justifications, and generated keywords. Successful
evaluations persist and are reused when inputs match; `--force` preserves history
while evaluating again. See the [ranking guide](docs/ranking.md) for configuration,
execution prerequisites, selection, reuse, failures, and library use.

Interactive output uses Rich for readable paper panels. Use `--format plain`,
`--format markdown`, or `--format json` for undecorated or structured output;
redirected output defaults to plain text. See [CLI output formats](docs/output.md)
for downstream usage and error handling.

Project requirements and agent instructions are in [AGENTS.md](AGENTS.md).
Development context is recorded in the [development log](docs/development-log.md).

## Tests

```sh
uv sync --group dev
uv run --group dev pytest
```

Unit tests in `tests/unit/` mirror the package layout; offline integration tests
belong in `tests/integration/`. The default suite is intended to run quickly in CI
without network services, credentials, or installed LLM agents. See `AGENTS.md`
for testing and module organization guidance.

## Documentation

The documentation site uses [Zensical](https://zensical.org/docs/).

```sh
uv sync --group docs
uv run --group docs zensical serve
```

To build the static site in `site/`:

```sh
uv run --group docs zensical build --strict
```
