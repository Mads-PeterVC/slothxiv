# CLI output formats

Both `slothxiv rank` and `slothxiv scrape` accept `--format`:

| Format | Behavior |
| --- | --- |
| `auto` (default) | Rich presentation when stdout is a terminal; plain text when piped or redirected |
| `rich` | Rich layout with panels, spacing, wrapped text, and terminal-aware colors |
| `plain` | Undecorated text without added colors, borders, or line wrapping |
| `markdown` | Markdown source, suitable for saving to a file or rendering elsewhere |
| `json` | One complete JSON object containing structured application data and the database path |

Rich is a runtime dependency. Its colors follow terminal capabilities and
`NO_COLOR`; `--format rich` still uses the panel layout when redirected, but
does not force ANSI colors. Paper titles, justifications, and keywords are
displayed as literal text rather than interpreted as Rich markup. Long values
wrap in the Rich layout. Plain, Markdown, and JSON writers bypass that layout.

## Examples

Interactive ranking uses Rich automatically:

```sh
slothxiv rank --config /path/to/config.toml --profile graphs --limit 3
```

Select an explicit format or save a result:

```sh
slothxiv rank --config /path/to/config.toml --profile graphs --format plain
slothxiv rank --config /path/to/config.toml --profile graphs --format markdown > ranking.md
slothxiv rank --config /path/to/config.toml --profile graphs --format json > ranking.json
slothxiv scrape --config /path/to/config.toml --profile graphs --format json > retrieval.json
```

These commands run the corresponding workflow. Ranking reuses matching successful
evaluations as described in the [ranking guide](ranking.md); choosing an output
format alone does not force new evaluations. These are workflow result writers,
not a digest command or a command for exporting an arbitrary historical run.

## Downstream applications

Use `--format json` for structured data. Ranking stdout has this shape:

```json
{
  "database": "/absolute/path/to/slothxiv.sqlite3",
  "ranking": {
    "run": {},
    "entries": [],
    "failures": {}
  }
}
```

This is a shape illustration: `run` contains the complete `EvaluationRun` model,
including run ID, profile, timestamps, status, candidate count, and error. Each
entry contains `reused` and a complete evaluation record: evaluation/run IDs,
paper snapshot, response with score/justification/generated keywords and reported
model identities, and start/finish timestamps. Failures map paper identities to
diagnostics. No Rich styling, summary preamble, or progress messages are added
to JSON stdout. JSON encoding preserves original field values, including
multiline text; display formatting does not alter the stored evaluations.

Retrieval JSON uses `database` and `retrieval`, where `retrieval` contains the
complete `RetrievalRun` model, including its profile snapshot and observation
count. It does not embed all retrieved paper records.

Diagnostics always go to stderr. On partial evaluation failure, ranking stdout
still contains a complete result (successful entries, failures, and failed run
status), and the command exits 1. A fatal error before a result can be constructed
emits no result on stdout and exits nonzero; Ctrl-C exits 130. Consumers should
check both the exit code and whether stdout contains JSON. Argument parsing
errors retain argparse's normal stderr output and exit code 2.

Markdown contains headings, scores, paper identities and URLs, reuse indicators,
justifications, generated keywords, and a failure section when needed. External
text is escaped so titles and agent prose cannot introduce Markdown headings,
links, or HTML. Use JSON to retain the complete structured data.
