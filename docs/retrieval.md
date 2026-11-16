# Retrieving papers

Milestone 1 provides arXiv retrieval and SQLite history. Milestone 2 adds
[evaluation and ranking](ranking.md) through Claude CLI. Digest generation is
planned for a later milestone and is not available yet.

## Install

From a checkout, install the command as an isolated uv tool:

```sh
uv tool install .
slothxiv scrape --help
```

For development, use `uv run slothxiv scrape --help`. Python 3.12 or newer is
required. The tool has no database server or LLM CLI prerequisite.

## Configure a profile

Create a TOML file outside the repository, for example:

```toml
[profiles.graphs]
lookback_days = 2

[profiles.graphs.arxiv]
categories = ["cs.LG", "stat.ML"]
keywords = ["graph learning", "graph neural networks"]

[profiles.statistics]
lookback_days = 7

[profiles.statistics.arxiv]
categories = ["stat.ML"]
```

Run a named profile:

```sh
slothxiv scrape --config /absolute/path/to/config.toml --profile graphs
```

`--profile` is required even with one configured profile. `lookback_days` is a
required positive integer; there is no default duration. Each profile must have
at least one category or keyword. Unknown configuration keys are rejected.

Categories match any listed category. Keywords match any listed keyword in the
title or abstract. When both groups are supplied, both groups must match.
Multiword keywords are sent as quoted phrases; matching follows arXiv's search
semantics. Keywords are search terms, not raw query expressions: quotes,
backslashes, wildcards (`*`, `?`), and control characters are rejected. Categories
use letters, numbers, dots, and hyphens and must begin with a letter.

## Configuration and database paths

Defaults use platform-specific user directories through
[platformdirs](https://platformdirs.readthedocs.io/en/latest/api.html):

| Platform | Configuration | Database |
| --- | --- | --- |
| macOS | `~/Library/Application Support/slothxiv/config.toml` | `~/Library/Application Support/slothxiv/slothxiv.sqlite3` |
| Linux | `~/.config/slothxiv/config.toml` | `~/.local/share/slothxiv/slothxiv.sqlite3` |
| Windows | `%LOCALAPPDATA%\slothxiv\config.toml` | `%LOCALAPPDATA%\slothxiv\slothxiv.sqlite3` |

Linux XDG environment overrides are honored. `slothxiv scrape --help` displays
the resolved defaults on your machine. No default configuration file is created.

Override the database in TOML:

```toml
[storage]
database = "state/papers.sqlite3"
```

Relative database paths in TOML resolve against the configuration file's
directory, independently of the working directory. `~` expands to the home
directory. `--database /absolute/path/to/papers.sqlite3` takes precedence over
TOML and the platform default; a relative CLI path resolves against the current
working directory. Parent database directories are created when storage opens.
Relative `--config` paths also resolve against the current working directory.

Use local storage for the database and keep personal configuration and data out
of version control. To move or copy the database, close all slothxiv processes
first; a live backup command is outside this milestone.

## Time windows and arXiv behavior

At run start, slothxiv calculates one UTC interval:

```text
[run_started_at - lookback_days, run_started_at)
```

A day is 24 hours. A paper is eligible according to its source update timestamp:
the lower boundary is included and the upper boundary excluded. Publication
timestamps and local retrieval timestamps are stored separately. Updated older
papers can therefore be retrieved. This is a retrieval window; future digest
selection will have its own independently defined window.

The [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html) documents
sorting by update time but only filtering by submission date. To avoid excluding
updates to older papers, slothxiv scans matching results in descending update
order, stopping at the lower boundary, and applies exact boundaries locally.
Broad queries may consequently require multiple requests even for a short window.

Requests use pages of 100 and a 30-second network timeout. Repeated requests from
one source instance are separated by a three-second pause. Retrieval does not
automatically retry failed requests. If the API's 30,000-result limit prevents a
complete scan, the run fails with guidance to narrow the query. Invalid Atom
responses, inconsistent pagination, and repeated revisions during pagination
also fail the run. Remote results are not a transactional snapshot; concurrent
changes at the source can still affect pagination. Avoid frequent overlapping
live scrapes; source instances do not coordinate request pacing across processes.

## History and failures

SQLite stores stable paper identities qualified by source (for example,
`arxiv:2611.00001`) and preserves each observed revision separately. Repeated
retrieval does not duplicate revisions. Every run records its profile snapshot,
source, window, start and finish timestamps, status, and observations. Observation
snapshots preserve metadata even if the source later changes it without changing
the revision. The stored revision retains its first observed metadata.

Profile associations refer to stable papers: listing a profile's papers returns
all stored revisions of those associated papers. The observation table records
which precise revisions were seen in each run. Unseen historical arXiv versions
are not fetched. Original entry XML and useful metadata such as DOI, comments,
and primary category are preserved. arXiv categories are not treated as keywords;
the source keyword field is empty because this adapter has no source keyword
field to populate. No generated keywords are produced in this milestone.

Each observation commits atomically with its paper, revision, and profile
association. On a later failure, earlier observations remain available and the
run is marked `failed`; `scrape` exits with status 1 and prints the run ID. A
successful empty run is `completed`. Ctrl-C attempts to mark the run failed and
exits with status 130. Forced termination, power loss, or a storage error can leave
a run `running`; that status must not be interpreted as successful completion.
Partial observations are retained without claiming successful completion.

Schema upgrades run transactionally on storage open, using ordered migrations
and SQLite's `user_version`. A database newer than the installed package is
rejected. Downgrades and a migration command are not provided.

## Library usage

```python
from pathlib import Path

from slothxiv.application import ScrapeError, scrape
from slothxiv.config import load_config, default_database_path
from slothxiv.storage.sqlite import SQLiteStore

config = load_config(Path("/absolute/path/to/config.toml"))
database = config.storage.database or default_database_path()
with SQLiteStore(database) as store:
    try:
        run = scrape("graphs", config.profiles["graphs"], store)
    except ScrapeError as error:
        failed_run = store.get_run(error.run_id)
        print(failed_run.status, failed_run.observation_count)
        raise
    print(run.run_id, run.observation_count)
    papers = store.list_papers("graphs")
    history = store.list_runs()
```

`scrape` accepts an optional `PaperSource` implementation and an aware
`started_at` timestamp for controlled workflows. Source adapters own retrieval;
application code owns the window, persistence, and completion status. The
`RetrievalStore` protocol isolates the application from SQLite. Read the stored
observation snapshots directly through SQLite when inspecting exact per-run
metadata; there is no history inspection CLI yet.
