# Integration tests

Tests that cross a module or service boundary: loader to audit, audit to
database, database to API. Anything needing the compose stack is marked
`needs_docker` so it stays out of the default run and still runs under
`make test-all`.
