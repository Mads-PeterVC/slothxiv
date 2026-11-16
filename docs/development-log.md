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

## 2026-11-16 — Complete milestone 2 evaluation, ranking, and history

### Changes and rationale

- Added optional validated per-profile evaluation instructions, configurable
  Claude model selection (Sonnet initially), and a configurable 120-second default
  per-paper timeout. Existing retrieval-only configurations remain valid.
- Added provider-independent evaluation requests/results, versioned Markdown
  prompts separating research instructions from untrusted JSON paper metadata,
  integer 0–100 scoring anchors, justifications, and generated keywords.
- Implemented Claude CLI subprocess execution using explicit model and structured
  output/schema flags, stdin content, safe mode, no tools/MCP/session persistence,
  noninteractive permissions, and an isolated working directory. Checked against
  installed Claude Code 2.1.325 help and official CLI/headless documentation.
  Safe mode retains existing authentication; bare mode would require API-key auth.
- Added schema 2 as a separate ordered migration preserving retrieval history.
  Runs snapshot profile/agent configuration, prompt version, candidate count,
  options, timestamps, and status. Attempts preserve requests, reuse keys,
  successes/failures, and reported model identities. Run entries record reused
  and new evaluations without overwriting previous results.
- Added library ranking and the thin `rank` CLI with candidate limits and forced
  re-evaluation. Candidate selection uses latest stored revisions; score ordering,
  reuse, partial failure continuation, interruption handling, and fatal storage
  error handling follow the agreed policies. Both commands show the database path.
- Added the ranking guide, README/site navigation updates, acceptance evidence,
  and current instruction updates. Personal profiles and storage were untouched.

### Validation

- `uv run --group dev pytest`: 112 passed in 2.49 seconds. Tests include fixture
  agent executables through real subprocesses and SQLite, installed entry-point
  ranking outside the checkout, reuse and model changes, forced re-evaluation,
  malformed/mismatched/duplicate output, authentication/nonzero exits, timeouts,
  interruptions, abandoned runs, partial/fatal failures, provenance, and schema 1
  migration. All tests are offline and require no installed Claude or credentials.
- `uv build`: source distribution and wheel built successfully. The initial
  sandboxed build could not acquire uv's cache lock; approved retries succeeded.
- Installed the wheel offline as an isolated uv tool with Python 3.12 and
  temporary tool/bin directories; `slothxiv rank --help` passed outside the repo.
- `uv run --group docs zensical build --strict`: passed with no issues.
- `git diff --check`: passed.

### Remaining questions and limitations

- Milestone 2 is complete; digest generation and the overall project remain
  incomplete. A live Claude trial was not run and must be explicitly requested.
- Model aliases can change underlying versions; reuse compares configured model
  identity and cannot detect a provider alias change without a fresh invocation.
- No slothxiv automatic retries, concurrency, PDF evaluation, history command,
  abandoned-run recovery, or digest output was added. Claude itself may retry
  internally. Scoring quality remains to be assessed with live profile examples.
- Managed Claude policies still apply. Compatible CLI flags are prerequisites;
  older incompatible installations fail with their diagnostics.

## 2026-11-16 — Finalize evaluation policies and configurable Claude model

### Changes and rationale

- Recorded approval of the proposed prerequisites, noninteractive execution with
  no agent tools, configurable per-paper timeout, continuation after individual
  failures, trial candidate ordering, and score calibration anchors.
- Recorded Sonnet as the initial model with configurable model selection so Opus
  or another supported Claude model can be chosen without code changes. Model
  selection belongs in provenance and reuse matching; switching models requires
  evaluations for the newly selected model rather than reusing the old model's
  results. Reported model identity is preserved where available.
- Updated `AGENTS.md` and `docs/milestones.md` to separate agreed policy from CLI
  contract verification and configuration naming during implementation. No runtime
  code was changed; milestone 2 remains unimplemented.

### Validation

- Reviewed documentation against the user's accepted proposals and explicit
  requirement for configurable Sonnet/Opus selection.
- `uv run --group docs zensical build --strict`: passed with no issues.
- `git diff --check`: passed. Runtime tests were not run for this documentation-only
  change.

### Remaining questions and limitations

- Verify concrete Claude CLI flags and structured output before implementing the
  adapter. Exact configuration keys/options and the timeout value are implementation
  details to document. Model aliases do not guarantee fixed underlying versions.
- Digest scope and future user-rating behavior remain undecided.

## 2026-11-16 — Agree milestone 2 evaluation scope and Claude CLI

### Changes and rationale

- Recorded the user's agreement to evaluate and rank stored profile candidates
  as milestone 2, with Claude CLI as the first adapter. Added bounded scope,
  exclusions, acceptance criteria, and validation to `docs/milestones.md`.
- Recorded integer 0–100 scoring, latest stored revisions without an additional
  date window, sequential one-paper invocations, matching-input reuse, explicit
  re-evaluation, preserved history, partial-failure reporting, deterministic
  ranking, and an optional trial limit. Terminal results will show the database
  path to make persistence easier to locate.
- Updated `AGENTS.md` to distinguish agreed evaluation policies from remaining
  decisions. No evaluation implementation or personal data was changed.

### Validation

- `uv run --group docs zensical build --strict`: passed with no issues. The
  initial sandboxed attempt could not acquire the uv cache lock; the approved
  retry with cache access succeeded.
- Reviewed the milestone against the accepted proposal and Claude CLI choice.
  Runtime tests were not run for this documentation-only change.

### Remaining questions and limitations

- Milestone 2 is agreed but not implemented. Claude CLI execution prerequisites,
  model selection, permissions, timeout and response contract, score calibration,
  exact options, trial candidate ordering, and per-paper failure continuation
  still need resolution before dependent implementation.
- Digest policies and subsequent milestone scopes remain undecided.

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
