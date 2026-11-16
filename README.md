# slothxiv

A Python tool for retrieving research papers for named profiles and preserving
discovery history in SQLite. LLM ranking and digest generation are planned but
not yet implemented.

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
