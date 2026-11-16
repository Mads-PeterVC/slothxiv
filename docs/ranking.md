# Evaluating and ranking papers

Milestone 2 evaluates stored titles, abstracts, and metadata against a named
profile's research interests. It preserves evaluations in SQLite and prints a
ranked list. It does not fetch PDFs or construct digests.

## Prerequisites and configuration

Install [Claude Code](https://code.claude.com/docs/en/setup) separately and
authenticate before running unattended evaluations. Check your installation with
`claude --version` and `claude auth status`. The adapter contract was checked
against Claude Code 2.1.325 help and the official
[CLI reference](https://code.claude.com/docs/en/cli-reference) and
[structured output guide](https://code.claude.com/docs/en/headless#get-structured-output).
Your CLI must support the documented flags, including `--safe-mode` and
`--json-schema`; older incompatible versions fail with the CLI's diagnostic.

Add an evaluation section to the same profile used for retrieval:

```toml
[profiles.graphs]
lookback_days = 15

[profiles.graphs.arxiv]
categories = ["cs.LG", "stat.ML"]
keywords = ["graph learning", "graph neural networks"]

[profiles.graphs.evaluation]
instructions = """
Prioritize graph representation learning methods with clear methodological
contributions. Applications are relevant when they introduce reusable methods.
Papers that merely apply a standard GNN to one dataset are less relevant.
"""
model = "sonnet"
timeout_seconds = 120
```

`instructions` is required for ranking. Retrieval still works for profiles with
no evaluation settings. `model` defaults to `sonnet`; change it to `opus` or a
supported full model identifier without changing code. `timeout_seconds` defaults
to 120 and must be a positive integer up to 86400. Model aliases can resolve to
new model versions over time; use a full identifier when you need version control.

## Run a small trial

First retrieve candidates using [scrape](retrieval.md), then rank a few of them:

```sh
uv run slothxiv rank --config dev/test-profile.toml --profile graphs --limit 3
```

This command requires the evaluation section above in your local configuration.
For an installed uv tool, use `slothxiv rank` without `uv run`. The configuration
and database path rules, including `--database`, are identical to `scrape`.

`rank` works entirely from stored candidates and does not scrape again. It selects
the latest stored revision of every paper associated with the profile, ordered by
source update time descending and source-qualified paper identity ascending.
The trial limit applies to this candidate list **before evaluation reuse**. If
the newest three are already evaluated, another `--limit 3` run reuses those
results rather than selecting three older unevaluated papers. Remove the limit
to rank all candidates.

Latest revision is determined by source update time; ties use numeric revision
order for decimal revisions (so 10 follows 9), otherwise lexical revision order.
There is no additional ranking lookback window in this milestone.

Each candidate is evaluated in its own invocation, sequentially. The terminal
prints the database's absolute path, run ID/status, titles, identifiers, scores,
justifications, links, generated keywords, and whether evaluations were reused.
Scores order the results descending, then source update time descending, then
source-qualified identifier ascending. Weak matches are shown with their scores;
digest thresholds and entry limits belong to a later milestone.

## Scores and evaluation reuse

Scores are integers from 0 to 100, with these relevance anchors:

| Score | Meaning |
| --- | --- |
| 0 | Unrelated |
| 25 | Tangential |
| 50 | Moderately relevant |
| 75 | Strongly relevant |
| 100 | Directly addresses the profile's central interests |

The prompt asks for relevance to your instructions rather than research quality
or popularity. Results include an explicit paper identity and revision, a
nonempty justification, and a separate generated-keyword list. Source keywords
are preserved in the paper record. Scores are estimates; evaluation may vary
between invocations.

Successful evaluations are reused when paper content, evaluation instructions,
prompt/version, and agent configuration match. Agent configuration includes model,
timeout, and adapter contract version. A switch from Sonnet to Opus requires new
evaluations. Merely changing retrieval keywords does not invalidate evaluations
of unchanged papers against unchanged evaluation instructions.

To evaluate the selected candidates again while preserving previous results:

```sh
slothxiv rank --config /path/to/config.toml --profile graphs --limit 3 --force
```

Reuse matches configured model names; it cannot detect a provider changing the
model behind an alias without a fresh invocation. The reported model identities
from Claude's `modelUsage` metadata are stored when available, separately from
the configured model.

## Execution and failures

The adapter runs `claude --print` with explicit model selection, JSON output,
and the evaluation JSON schema. A custom system prompt separates evaluation
instructions from untrusted paper data; a Markdown user prompt contains criteria
and JSON-encoded candidate metadata. Paper content is passed through stdin,
without shell interpolation. Safe mode disables local customizations while
retaining Claude authentication; an empty built-in tool list, strict empty MCP
configuration, disabled slash commands, and `dontAsk` permission mode prevent
interactive tool workflows. Each process runs in a temporary directory and uses
`--no-session-persistence`. Administrator-managed Claude policies still apply.

Missing CLI, authentication errors, timeouts, nonzero exits, malformed JSON,
missing structured output, duplicate response fields, invalid scores, or
mismatched paper identities are recorded as failed evaluations. Other candidates
continue. The run is marked failed and the command exits 1 if any candidate fails;
successful evaluations remain stored and usable. There are no automatic retries
in slothxiv; the installed Claude CLI may perform its own internal retries.
Running again reuses successes and attempts failed candidates again.

An empty candidate set completes without invoking Claude. Ctrl-C attempts to
mark the active evaluation and run failed, then exits 130. Abrupt termination or
storage failure can leave a run or evaluation `running`; this does not mean it
completed successfully. Storage errors stop the workflow rather than continuing
with uncertain persistence.

## History and library use

Schema version 2 adds `evaluation_runs`, `evaluations`, and
`evaluation_run_entries` without changing retrieval history. Opening an existing
milestone 1 database applies the ordered transactional migration. Close all
slothxiv processes before copying a database for backup.

Runs preserve profile and agent configuration snapshots, prompt version,
candidate count, selection options, timestamps, status, and error. Each attempt
preserves its exact request and reuse key; successful results include the paper
snapshot, response, reported model identities, and start/finish times. Run entries
link new or reused evaluations to the run presenting them. Old evaluations are
never overwritten by forced re-evaluation.

```python
from pathlib import Path

from slothxiv.config import default_database_path, load_config
from slothxiv.evaluation.workflow import rank
from slothxiv.storage.sqlite import SQLiteStore

config = load_config(Path("/path/to/config.toml"))
with SQLiteStore(config.storage.database or default_database_path()) as store:
    result = rank("graphs", config.profiles["graphs"], store, limit=3)
    print(result.run.status, result.failures)
    for entry in result.entries:
        print(entry.evaluation.paper.title, entry.evaluation.response.result.score)
    history = store.list_evaluation_runs()
    successful_evaluations = store.list_evaluations("graphs")
```

Individual agent failures return a `Ranking` with failures and a failed run.
Fatal workflow/storage failures raise `RankError` carrying the run ID when a run
has started. Interruptions propagate. Tests and other callers can supply an
`EvaluationAgent`; persistence is isolated behind `EvaluationStore`.

For read-only inspection of failures and exact run snapshots, use SQLite:

```sh
sqlite3 -readonly -header -column /path/to/slothxiv.sqlite3 \
  "SELECT run_id, profile_name, status, candidate_count, error FROM evaluation_runs;"
```

A dedicated history command, generated digest files, and user read/rating state
remain outside this milestone. Live checks are opt-in; default tests use fixture
subprocesses and temporary storage without Claude credentials or paid calls.
