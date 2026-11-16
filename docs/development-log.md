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
