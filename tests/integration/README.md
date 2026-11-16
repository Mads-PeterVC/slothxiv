# Integration tests

Place offline tests that exercise multiple components together here. For example,
test a retrieval-to-storage workflow with fixture source responses, a temporary
database, and a fake agent. These tests run with the default suite in CI.

Retrieval tests exercise the arXiv adapter, application workflow, SQLite history,
and CLI with fixture HTTP responses. Installed entry-point checks run from a
temporary directory outside the repository. The default suite blocks socket
connections, and child-process checks replace HTTP and block sockets explicitly.

Tests requiring real services, credentials, or installed agent CLIs must live in a
separate, explicitly invoked location outside the default `tests/` collection.
