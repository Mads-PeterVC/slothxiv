# Implementation milestones

## Milestone 1 — Retrieve and persist papers for a named profile

Completed on 2026-11-16. The behavior below is implemented and validated offline.
See the [retrieval guide](retrieval.md) for installation and use.

### Intended outcome

A `slothxiv scrape --profile <name>` command fetches arXiv candidates for a
configured research profile and preserves papers and retrieval history in SQLite.
The same workflow is independently callable as a library function.

### Included work

- Pydantic configuration for named profiles, separating arXiv retrieval settings
  from common profile settings.
- Shared paper models with source-qualified identity, source timestamps, and
  explicit revision information.
- An arXiv adapter behind a small source interface.
- SQLite persistence for papers, profile associations, retrieval runs, and
  observations, with a schema evolution approach.
- Application orchestration and a thin scrape command.
- User documentation, unit tests, and offline integration tests.
- Configurable configuration/data paths independent of the working directory.

### Exclusions

LLM execution, scoring, digest selection and rendering, the GUI, additional
sources, and cross-source deduplication are outside this milestone.

### Acceptance criteria

- A configured named profile can fetch and persist candidates.
- Repeated retrieval avoids duplicate paper revisions and preserves retrieval
  observations, following the revision policy agreed before implementation.
- Empty results are valid; failures and incomplete runs are distinguishable from
  successful completed runs.
- Installed usage works outside the repository directory.
- User documentation describes the implemented behavior and configuration.

### Validation

- Unit tests use fixture responses for parsing, malformed results, and date
  boundaries.
- Offline integration tests exercise retrieval and real temporary SQLite storage,
  including repeat retrieval, revisions, empty results, and failures.
- Verify installed CLI usage from another working directory using temporary
  configuration and data, without live network access.
- Run `uv run --group dev pytest` and
  `uv run --group docs zensical build --strict`.

### Agreed decisions

These choices are agreed and implemented for milestone 1.

| Decision | Agreement |
| --- | --- |
| Configuration | TOML, platform-appropriate user configuration/data locations, and explicit path overrides |
| Migrations | Schema version and ordered migrations from the first schema |
| Profile selection | Require explicit `--profile` initially |
| Retrieval window | Source update time, timezone-aware UTC boundaries, and separately recorded local retrieval time |
| Revisions | Preserve each observed source revision under a stable paper identity, with repeat observations recorded separately |
| Lookback default | Require an explicit configured window initially |
| Query semantics | Match any configured category AND any configured keyword, searching keywords in titles and abstracts; either group may be used alone |
| Window boundaries | `[run_started_at - lookback, run_started_at)` in UTC, calculated once per run; include the lookback start and exclude the run start |

Revision preservation covers revisions observed during retrieval; fetching unseen
historical revisions is outside this milestone. Exact platform paths and filenames
are documented in the retrieval guide.

### Completion evidence

- `uv run --group dev pytest`: 62 tests passed, covering parsing, window edges,
  pagination failures, repeat retrieval, revisions, partial failures, interruptions,
  schema handling, configuration paths, and CLI errors.
- Installed entry-point retrieval ran outside the repository with fixture HTTP,
  temporary TOML/SQLite files, and no live network access.
- `uv build`: built the source distribution and wheel successfully.
- Installed the wheel as a uv tool in temporary tool/bin directories using Python
  3.12 and cached dependencies; `slothxiv scrape --help` passed outside the checkout.
- `uv run --group docs zensical build --strict`: passed with no issues.

Live arXiv checks were not performed. Source result changes can affect pagination;
detected inconsistencies fail the run. Evaluation and digest work remain outside
this milestone.

## Later milestones

Evaluation of stored candidates with preserved evaluation history, followed by
digest selection and rendering, are proposed next steps. Their concrete scopes
and policies have not yet been agreed.
