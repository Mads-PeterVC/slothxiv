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

## Milestone 2 — Evaluate and rank stored papers for a named profile

Completed on 2026-11-16. The behavior below is implemented and validated offline.
See the [ranking guide](ranking.md) for configuration, execution, and history.

### Intended outcome

`slothxiv rank --config /path/to/config.toml --profile graphs` evaluates stored
candidates against profile research interests, preserves results in SQLite, and
displays a ranked list with scores and justifications. The terminal output also
identifies the database path. The same workflow is callable through the library.

### Included work

- Profile evaluation instructions distinct from retrieval keywords.
- A provider-independent interface with structured requests and results, and
  Claude CLI as the first and only agent adapter in this milestone.
- Pydantic-validated results with explicit paper identity, integer relevance
  score, justification, and generated keywords distinct from source keywords.
- SQLite migrations and evaluation history preserving paper revision, profile
  settings, prompt version, agent/model identity where available, execution
  timestamps, completion status, and failures.
- A thin rank command, readable terminal results, library orchestration,
  documentation, and offline unit/integration tests.

### Agreed behavior

| Decision | Agreement |
| --- | --- |
| Candidates | Latest stored source revision of each paper associated with the selected profile; no additional date window initially |
| Scores | Integer 0–100: 0 unrelated, 25 tangential, 50 moderately relevant, 75 strongly relevant, 100 directly addresses the profile's central interests |
| Model | Sonnet initially; model selection is configurable so users can switch to Opus or another supported Claude model without code changes |
| Prerequisites | Claude CLI installed and authenticated beforehand; unattended runs fail clearly when authentication is needed |
| Execution | Noninteractive execution with no agent tools and a configurable per-paper timeout |
| Batching | One paper per agent invocation, processed sequentially |
| Reuse | Skip successful evaluations when paper content, evaluation instructions, prompt version, and agent/model configuration match |
| Re-evaluation | An explicit option forces new evaluations while preserving earlier results |
| Failures | Continue with other papers after an individual evaluation fails, preserve successes, record failures, and exit nonzero if any candidate fails; no automatic retries |
| Ordering | Score descending, source update time descending, then source-qualified identifier |
| Trial runs | Optional candidate limit; select by source update time descending, then source-qualified identifier before applying the limit |

External paper metadata is untrusted content, separated from instructions.
Results must identify the requested paper explicitly; response ordering is not
an identity mechanism. Python owns candidate selection, persistence, and ranking;
the adapter owns subprocess execution and response translation.

### Exclusions

Digest construction and output writers, full-paper/PDF retrieval, the GUI,
additional agent adapters, parallel evaluation, automatic retries, and user
ratings are outside this milestone. Terminal ranking output does not establish
future digest selection or repeat-inclusion policies.

### Implemented execution contract

- Verified flags against Claude Code 2.1.325 help and official documentation.
  The adapter uses noninteractive JSON/schema output, safe mode, an empty tool
  set and strict empty MCP configuration, disabled slash commands, `dontAsk`,
  no session persistence, a custom system prompt, stdin paper data, and a
  temporary working directory. Existing authentication remains available.
- Profiles have an optional `evaluation` section with required `instructions`,
  configurable `model` (default `sonnet`), and positive integer `timeout_seconds`
  (default 120, maximum 86400). Retrieval-only profiles remain compatible.
- `rank` supports `--profile`, `--config`, `--database`, `--limit`, and `--force`.
  Model selection is explicit in the invocation, preserved in provenance, and
  included in reuse matching. Reported model identities are preserved when
  available. Aliases do not guarantee fixed underlying model versions.
- Latest stored revision is selected by source update time, with numeric revision
  tie-breaking for decimal revisions and lexical tie-breaking otherwise. Trial
  selection limits apply before reuse. Ranking returns successful selected
  candidates, including weak scores; digest thresholds remain outside scope.

### Acceptance criteria

- Stored profile candidates can be evaluated and ranked without another scrape.
- Validated evaluations persist across process invocations and remain associated
  with their exact paper revision, profile, and evaluation run.
- Matching successful evaluations are reused; changed evaluation inputs and
  forced re-evaluation create new history without overwriting earlier results.
- Invalid, missing, duplicate, or mismatched paper results cannot become
  successful evaluations. Agent failures, interruptions, and partial runs are
  distinguishable from successful completed runs.
- Scores and tie-breaking determine ranking in Python, with useful terminal
  results and an explicit database path.
- Installed usage remains independent of the working directory; milestone 1
  data remains usable after schema migration.

### Validation

- Offline unit tests cover prompt construction, structured result validation,
  subprocess failures/timeouts, reuse rules, candidate selection, and ordering.
- Offline integration tests use fixture agent subprocess responses and real
  temporary SQLite storage for persistence, migrations, re-evaluation, partial
  failures, and CLI behavior. No credentials, installed agent, network access,
  or paid calls are required by the default suite.
- Run `uv run --group dev pytest` and
  `uv run --group docs zensical build --strict`; verify installed CLI usage.
- A small live Claude CLI trial may be explicitly requested after offline
  validation; it is separate from the default tests.

### Completion evidence

- `uv run --group dev pytest`: 112 passed in 2.49 seconds. Includes fixture
  executable subprocesses, installed entry-point ranking outside the checkout,
  model changes, re-evaluation, malformed results, partial failures, interruptions,
  abandoned runs, fatal storage errors, provenance, and migration from schema 1.
- `uv build`: source distribution and wheel built successfully.
- Installed the wheel as a uv tool using temporary tool/bin directories, Python
  3.12, and cached dependencies; `rank --help` passed outside the repository.
- Strict documentation build and whitespace validation are recorded in the
  development log.

No live Claude evaluation was performed. Installed CLI help and official docs
establish the supported invocation contract; actual provider execution and score
quality remain to be checked in an explicitly requested live trial. Alias reuse
cannot detect an underlying provider model change without a fresh invocation.

## Later milestones

Digest selection and rendering follow evaluation. Their concrete scope, timestamp
semantics, output writers, and repeat-inclusion policies remain to be agreed.
