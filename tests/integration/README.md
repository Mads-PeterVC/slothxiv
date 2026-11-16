# Integration tests

Place offline tests that exercise multiple components together here. For example,
test a retrieval-to-storage workflow with fixture source responses, a temporary
database, and a fake agent. These tests run with the default suite in CI.

There are no application workflows to test yet. Add integration tests as those
workflows are implemented; do not add placeholder assertions.

Tests requiring real services, credentials, or installed agent CLIs must live in a
separate, explicitly invoked location outside the default `tests/` collection.
