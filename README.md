# slothxiv

A Python tool being designed to find research papers, rank them against research
profiles using an LLM, and generate digests. The application is currently a skeleton.

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
