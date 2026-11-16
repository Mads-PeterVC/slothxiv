# Development log

This log preserves context beyond Git history. Add an entry for every change set,
including documentation, configuration, dependency, and instruction changes.
Use newest-first order and add separate descriptive headings for distinct changes
on the same date. One entry may cover a coherent set of related edits; an entry
does not require another entry solely to describe itself.

Each entry must explain what changed, why, how it was validated, and any remaining
questions or limitations. Record actual results rather than planned checks. Keep
earlier entries intact; describe later decisions in new entries and explicitly
correct factual mistakes when necessary. Never include credentials or private
profile contents.

## 2026-11-16 — Complete milestone 1 retrieval and SQLite history

### Changes and rationale

- Implemented Pydantic TOML profiles, platform user paths, explicit profile and
  lookback settings, and CLI/configuration database overrides. Relative TOML
  database paths resolve against the configuration file.
- Added source-independent paper, window, and run models, a small source protocol,
  and an arXiv adapter with phrase queries, Atom validation, preserved original
  metadata, explicit revision identity, pagination, request pacing, and timeout.
- arXiv documents update-time sorting but only submission-date filtering. The
  adapter scans by descending update time and applies the agreed UTC window
  locally, preserving eligibility of updates to older papers. Result caps and
  detected pagination inconsistencies fail rather than silently truncate a run.
- Added a SQLite store protocol/implementation and ordered transactional schema
  migrations. Paper revisions are deduplicated while per-run observation snapshots,
  stable profile associations, configuration snapshots, and failure history persist.
  Each observation commits atomically; later failures retain earlier observations.
- Added library orchestration and the thin `slothxiv scrape` CLI. Empty retrievals
  complete successfully; failures exit nonzero and preserve run identity. Abrupt
  termination can leave a run running, never falsely completed.
- Added fixture-based unit/integration tests with blocked network connections,
  an installed-entry-point subprocess check, and a retrieval guide. Updated the
  README, documentation site, milestone status, and package description. Added
  Pydantic, platformdirs, and defusedxml runtime dependencies through uv.

### Validation

- `uv run --group dev pytest`: 62 passed in 1.04 seconds. Earlier test iterations
  exposed two test-harness errors (exception run-ID access and a subprocess HTTP
  fixture path); both were corrected before the passing full run.
- `uv build`: source distribution and wheel built successfully.
- Installed the built wheel using `uv tool install --offline --python` with the
  project's Python 3.12, temporary tool/bin directories, and cached dependencies;
  the installed `slothxiv scrape --help` succeeded outside the repository. The
  initial offline attempt without a pinned interpreter lacked cached compatible
  dependency wheels; selecting Python 3.12 resolved that validation limitation.
- `uv run --group docs zensical build --strict`: passed with no issues.
- `git diff --check`: passed.
- uv workflows required access to the cache outside the sandbox and ran with
  approval. No personal configuration, database, or tool installation was created.

### Remaining questions and limitations

- Milestone 1 is complete; the overall ranking/digest project is not complete.
- No live arXiv requests were made. Broad searches can require many requests,
  remote pagination is not a transactional snapshot, and request pacing is local
  to each adapter instance. Retrieval has no automatic retries.
- History inspection is available through library run/paper methods and SQLite;
  a history CLI, live backups, and recovery of abandoned runs are not included.
- Later milestones still need scope and decisions covering LLM execution,
  evaluation policies, score calibration, digest selection, and output writers.

## 2026-11-16 — Finalize retrieval query and window rules

### Changes and rationale

- Recorded the user's approval of any-category AND any-keyword matching, with
  keyword searches over titles and abstracts and either group usable alone.
- Recorded the UTC window `[run_started_at - lookback, run_started_at)`, anchored
  once per run, including its start and excluding its end.
- Updated `AGENTS.md` and `docs/milestones.md` to remove the corresponding open
  decisions. This completes the behavior decisions identified for milestone 1.

### Validation

- `uv run --group docs zensical build --strict`: passed with no issues after
  approval to access uv's cache outside the workspace.
- `git diff --check`: passed.

### Remaining questions and limitations

- Milestone 1 implementation and acceptance validation remain outstanding.
- Digest window semantics and other later milestone policies remain undecided.

## 2026-11-16 — Agree remaining concrete retrieval proposals

### Changes and rationale

- Recorded approval of TOML, platform-appropriate directories and path overrides,
  ordered SQLite migrations, explicit profile selection and configured lookback,
  source update timestamps with UTC boundaries, and observed revision preservation.
- Updated `AGENTS.md` and `docs/milestones.md` to distinguish these agreements
  from behavior not actually specified in the earlier proposals: query composition
  and exact time-boundary inclusion.
- Proposed concrete query rules and a half-open window anchored to run start for
  resolution before dependent implementation. No retrieval code was added.

### Validation

- `uv run --group docs zensical build --strict`: passed with no issues after
  approval to access uv's cache outside the workspace.
- `git diff --check`: passed.

### Remaining questions and limitations

- Query composition/search fields and exact time boundaries await resolution.
- Later milestone scopes and LLM/digest policies remain undecided.

## 2026-11-16 — Agree retrieval milestone and SQLite storage

### Changes and rationale

- Recorded SQLite as the agreed initial backend in `AGENTS.md`; schema migration
  design remains open. SQLite suits the intended local CLI and future lightweight
  GUI without requiring users to operate a database server.
- Added `docs/milestones.md` and site navigation for the agreed first milestone:
  retrieve arXiv papers for a named profile and persist retrieval history.
- Defined scope, exclusions, acceptance criteria, and validation while explicitly
  retaining unapproved configuration, time-window, query, revision, profile
  selection, and migration choices as proposals.

### Validation

- `uv run --group docs zensical build --strict`: passed with no issues after
  approval to access uv's cache outside the workspace.
- Reviewed the documentation diff to distinguish agreed decisions from proposals.

### Remaining questions and limitations

- The application remains a skeleton; no retrieval or storage code was added.
- Milestone behavior choices listed in `docs/milestones.md` remain to be resolved
  before dependent implementation. Later milestone scopes are still proposals.

## 2026-11-16 — Require bounded implementation milestones

### Changes and rationale

- Added the agreed milestone policy to `AGENTS.md`: define outcomes, scope,
  exclusions, acceptance criteria, and validation before implementation.
- Broad requests must be decomposed into finite plans, with material ambiguities
  discussed before dependent implementation. Authorization for an agreed plan
  permits progress through its milestones without repeated permission requests.
- Required completion reports to distinguish milestone completion from overall
  project completion and capture adjacent improvements as follow-up work.
- Reserved `docs/milestones.md` for concrete agreed plans; no implementation
  milestones or application scope were added by this policy change.

### Validation

- Reviewed the policy against existing design-phase, testing, and logging rules.
- `uv run --group docs zensical build --strict`: passed with no issues.

### Remaining questions and limitations

- The concrete implementation milestones still need to be agreed.

## 2026-11-16 — Add pytest and module organization guidance

### Changes and rationale

- Added pytest as a development dependency, with collection under `tests/`,
  importlib import mode, and strict configuration and marker validation.
- Added a smoke test that checks the installed console entry point resolves to
  the package callable, without locking in the skeleton's temporary greeting.
- Established `tests/unit/` for tests mirroring the package and
  `tests/integration/` for offline component workflows. No application integration
  tests are present because the application is still a skeleton.
- Updated `AGENTS.md` to prefer short, cohesive modules and responsibility-based
  subpackages without a rigid line limit. Consolidated testing instructions into
  one section requiring fast, deterministic, offline default tests, fixture scrape
  data, temporary storage, and substitutes at external boundaries.
- Documented local/CI test commands and ignored pytest's generated cache.

### Validation

- `uv run --group dev pytest`: one smoke test passed in 0.01 seconds.
- `uv run --group docs zensical build --strict`: passed with no issues.

### Remaining questions and limitations

- CI workflow configuration is not yet present; the documented default pytest
  command can be used by a future CI workflow.
- Network isolation is a testing requirement, not currently enforced by a plugin.
  Live checks must remain outside default test collection.

## 2026-11-16 — Establish documentation and development memory

### Changes and rationale

- Added a Zensical site, a dedicated `docs` dependency group, and a dependency
  lockfile so documentation builds can be reproduced without adding documentation
  tooling to the package's runtime dependencies.
- Added local preview/build instructions and ignored generated site output.
- Required development-log entries in `AGENTS.md` so future sessions can recover
  the reasoning and validation behind changes.
- Added this initial record of the earlier design discussion. `AGENTS.md` defines
  a publishable Python tool with research profiles, independent retrieval and
  digest windows, score thresholds and count limits, persistent evaluations,
  Pydantic digests, and separate output writers. Source adapters start with arXiv;
  agent adapters are intended for Claude and Codex CLI subprocesses.

### Validation

- `uv run --group docs zensical build --strict` passed with no issues. Generated
  output includes the home page and development log.

### Remaining questions and limitations

- The application remains a skeleton; no retrieval, ranking, or digest workflow
  has been implemented.
- Hosting and deployment are not configured.
- Product decisions such as storage backend, score scale, initial agent adapter,
  and repeat-inclusion policy remain open in `AGENTS.md`.
