# slothxiv

## Purpose and current phase

slothxiv is a Python tool for finding, evaluating, and ranking research papers
according to a user's research interests. It should support an unattended command
that fetches candidates, evaluates them using an LLM, and produces a digest.

The project is currently in design. This document records the agreed direction;
it does not authorize implementing the entire roadmap. Discuss unresolved product
decisions before implementing behavior that depends on them. Keep this document
current as decisions are made.

## First working version

- Build a potentially publishable Python package, installable as a `uv tool`, with
  a `slothxiv` CLI and independently usable library functions.
- Fetch papers from arXiv using configured categories, keywords, and time windows.
- Support multiple named research profiles with their own retrieval criteria,
  evaluation instructions, and digest settings.
- Evaluate titles, abstracts, and metadata. Full-paper retrieval and evaluation
  are outside the initial scope.
- Produce numerical relevance scores, justifications, and generated keywords.
  Preserve source-provided keywords when available and distinguish them from
  generated keywords.
- Store retrieval and evaluation history from the start.
- Represent digests as Pydantic models and render them through separate output
  writers. Digest prose is optional.
- Provide `slothxiv digest` for the complete workflow and individual commands such
  as `slothxiv scrape` and `slothxiv rank` for its stages.
- Keep user configuration and persistent storage outside the repository, with
  configurable paths. Installed usage must not depend on the working directory.

## Time windows and selection

The tool need not run daily. Retrieval and digest selection must have independent,
configurable lookback windows. For example, a user may fetch only the last two
days of papers while producing a digest of the ten best papers from the last week
already present in storage.

- Retrieval updates persistent storage; digest selection queries stored papers.
- Running `digest` may orchestrate retrieval and evaluation, but its selection
  window must not be implicitly restricted to the papers fetched in that run.
- Support an optional minimum relevance score and optional maximum entry count
  per profile. Apply the threshold before the count limit.
- Never include weak matches merely to fill a quota. An empty digest is valid.
- Record digest membership so future selection policies can account for papers
  already presented. The default repeat-inclusion policy remains to be decided.
- Define which timestamps govern each window before implementing date filtering;
  distinguish source publication/update times from local retrieval times.

## Architecture and boundaries

Keep fetching, evaluation, persistence, digest construction, and output rendering
separate. The CLI and future GUI should call the same application/library
functions. Avoid placing business logic in command handlers or UI callbacks.

### Paper sources

Put paper retrieval behind a source interface. arXiv is the initial implementation;
another source, such as bioRxiv, should be addable without rewriting ranking,
storage, or digest rendering.

- Normalize retrieved papers into a shared model while preserving source identity,
  source-specific identifiers, URLs, and useful original metadata.
- Namespace identifiers by source; do not assume arXiv identifiers throughout the
  application.
- Let adapters translate source-specific query and pagination behavior. Do not
  assume all sources support arXiv categories or identical search capabilities.
- Keep source-specific configuration distinct from common profile settings.
- Make repeated retrieval safe through explicit identity and version handling.
  Cross-source deduplication policy remains an open decision.
- Use a small interface appropriate to actual adapters; a plugin discovery
  framework is not required for the first version.

### LLM agents

Put LLM execution behind an interface with structured requests and results.
The initial approach invokes headless CLI agents through subprocesses, with
`ClaudeCLIAgent` and `CodexCLIAgent` as intended adapters. Direct API adapters,
such as `ClaudeAPIAgent`, may follow later. The first adapter to implement has not
yet been selected.

- Build Markdown prompts containing profile criteria and identified candidate
  papers from the retrieval stage.
- Require structured evaluation results validated with Pydantic. Associate each
  result with an explicit paper identifier; do not rely on response ordering.
- Python owns retrieval, persistence, selection, ordering, and rendering. Agent
  adapters own execution and response translation, not the application workflow.
- Treat titles, abstracts, and other external metadata as untrusted content,
  separate from instructions.
- Keep subprocess invocation, timeouts, failure handling, and provider-specific
  output formats inside the adapters. Avoid shell interpolation of paper content.
- Do not couple the core models to one provider's SDK or CLI response format.
- Decide batching, retry, and evaluation reuse policies before implementing them.

### Models and configuration

Use Pydantic for validated configuration and structured application data,
including evaluations and digests. Profiles must be selectable for digest
generation and the eventual GUI.

Keep the following concepts distinct:

- A paper and its source metadata.
- A paper's association with a research profile.
- A retrieval run and its observations.
- An evaluation of a paper against a profile at a particular time.
- A digest containing selected papers and evaluations.
- User read status and user-supplied relevance ratings.

A digest model should carry enough information for output writers to render it
without calling an LLM again. Generated summary prose, when requested, belongs in
the structured digest result. Numerical scores determine ranking in application
code; define deterministic tie-breaking before implementation.

### Persistence and history

Persistence is part of the first working version, even though the GUI follows
later. Preserve enough provenance to inspect which papers were considered, how
they were scored, and how results change over time.

- Preserve previous evaluations when a paper is evaluated again.
- Record the relevant profile configuration, prompt/version information, execution
  time, and agent/model identity where available for each evaluation run.
- Keep user ratings separate from computed scores so they can later be compared.
- Keep read status independent of whether a paper was fetched, ranked, or included
  in a digest.
- Track workflow completion and failures sufficiently to avoid treating partial
  results as successful completed runs.
- Keep storage access behind a clear boundary and plan for schema evolution.

SQLite is the proposed initial storage backend; it has not yet been finalized.

## Future scope

- A lightweight GUI, currently envisaged using Panel, with profile selection,
  ranked paper lists, read markers, and user relevance ratings.
- Analysis comparing user ratings with computed relevance scores.
- Additional paper sources, including potentially bioRxiv.
- Additional CLI or direct API agent adapters.
- Full-paper evaluation if experience shows abstracts and metadata are inadequate.

Prepare sensible boundaries for these features without implementing them early
or introducing speculative frameworks.

## Decisions still to resolve

- Configuration file format and default configuration/data locations. TOML is a
  proposal, not a settled requirement.
- Initial storage backend and migration approach.
- Initial CLI agent adapter, supported invocation contract, and prerequisites.
- Numerical score range and calibration guidance shared with user ratings.
- Default lookback windows, timestamp semantics, and timezone handling.
- Whether digests repeat previously presented papers, and how explicit time-window
  requests interact with that policy.
- Profile selection defaults when multiple profiles exist.
- Initial output writers; Markdown and JSON are proposed.
- Evaluation batching, retries, caching/reuse, and partial-run behavior.
- Source revision handling and cross-source deduplication.

## Development guidance

### Milestones and scope

- Organize implementation into bounded milestones. Each milestone must define
  its intended outcome, included work, exclusions, acceptance criteria, and
  validation.
- Before implementation, identify the milestone being addressed. Use an existing
  agreed milestone when available; otherwise propose one grounded in the user's
  request and current project decisions.
- Broad requests such as "finish the package" express an objective, not unlimited
  scope. Translate them into a finite milestone plan. Resolve ambiguities that
  materially affect behavior or scope with the user before implementing dependent
  work.
- Do not refuse a broad request merely because it needs decomposition. Make
  useful progress on planning and identify the specific decisions needed to
  proceed.
- Match approval to the user's instructions. If the user authorizes completing an
  agreed plan, proceed through its milestones without repeatedly asking
  permission. If the user authorizes only one milestone, complete it and report
  the result before starting another.
- A milestone is complete when its acceptance criteria and required validation
  pass, documentation is updated, and the development log records the outcome
  and remaining work.
- Do not expand scope merely because adjacent improvements become apparent.
  Record them as follow-up work. Include necessary supporting changes within the
  milestone, and discuss changes that materially alter its scope.
- When reporting completion, distinguish the completed milestone from the overall
  project objective.
- Keep concrete milestone definitions in `docs/milestones.md` once a milestone
  plan is agreed. This section holds the general working policy; the development
  log records outcomes and decision history.

### Documentation and development log

- At the start of a session, read `docs/development-log.md` alongside this file to
  recover prior decisions, validation results, and unresolved work.
- After every change set, add a dated entry to `docs/development-log.md` before
  considering the work complete. This includes code, documentation, configuration,
  dependencies, and changes to this file. A coherent set of related changes may
  share an entry; logging an entry does not itself require a recursive entry.
- Explain what changed, why, the actual validation results, and remaining issues
  or decisions. Preserve historical entries, use newest-first order, and do not
  record secrets or private configuration.
- Maintain the Zensical site in `docs/` with navigation in `zensical.toml`.
  Documentation tooling belongs in the `docs` dependency group, not runtime
  dependencies. Do not commit generated `site/` output.
- Preview with `uv run --group docs zensical serve`. After documentation or site
  configuration changes, run `uv run --group docs zensical build --strict` and
  record the result in the development log.

### Implementation practices

- The existing skeleton uses Python 3.12+, a `src/slothxiv` package, `uv_build`, and
  a `slothxiv` console entry point. Use `uv` for project workflows.
- Keep the package usable without the future GUI; isolate optional integrations
  and their dependencies where practical.
- Prefer small, typed interfaces and explicit validated data models over broad
  frameworks or provider-specific assumptions.
- Prefer short, cohesive modules and subpackages grouped by responsibility over
  many top-level modules. A roughly 700-line module with several functions or
  classes is too large; split by responsibility before reaching that point. There
  is no fixed line-count limit, and trivial wrapper modules are not a goal.
- Keep personal profiles, credentials, databases, and generated digests out of
  version control. Examples must use non-sensitive sample values.
- Update user documentation when adding commands or configuration options.
- Do not present proposed defaults or future features as implemented behavior.

### Testing with pytest

- Keep pytest in the `dev` dependency group. Install with `uv sync --group dev`;
  run the default CI-compatible suite with `uv run --group dev pytest`.
- Unit tests live in `tests/unit/`, mirroring the structure inside
  `src/slothxiv/`. For example, `src/slothxiv/sources/arxiv.py` maps to
  `tests/unit/sources/test_arxiv.py`. Split large test modules by behavior as
  needed. The current package smoke test is `tests/unit/test_package.py`.
- Offline integration tests live alongside unit tests in `tests/integration/`
  and run in the default suite. Exercise real component interactions while
  substituting external boundaries. Use real temporary storage where useful.
- Run focused checks with `uv run --group dev pytest tests/unit` or a specific
  test path; run the full default suite before completing code changes.
- Keep the suite fast, deterministic, and suitable for CI without credentials,
  network access, installed agent CLIs, or paid model calls. Full scrape scenarios
  must use fixture responses rather than querying arXiv or another live source.
- Mock or fake source transport and agent subprocess boundaries rather than
  replacing the business logic under test. Use small representative fixtures,
  including empty and malformed results. Use `tmp_path` for files/databases and
  `monkeypatch` for environment changes; never touch personal configuration/data.
- Keep fixtures near their consumers; use narrowly scoped `conftest.py` files
  when shared setup is actually needed. Avoid broad fixture frameworks and slow
  session setup without a demonstrated need.
- Live checks must be explicit and opt-in, outside the default `tests/`
  collection. Do not silently make the normal suite depend on local credentials
  or skip essential offline coverage when an external service is unavailable.
- Test observable behavior and failure paths, not implementation details.
  Prioritize selection windows, thresholds, identity handling, persistence, and
  malformed agent responses as those features are implemented. Avoid tests that
  merely repeat the implementation or lock in temporary placeholder output.
- Pytest configuration lives in `pyproject.toml`, using importlib import mode and
  strict configuration/marker validation. Import the installed package normally;
  do not add `sys.path` hacks to tests. Register any future markers explicitly.
