# End-to-end tests

Playwright specs live in `apps/web/e2e`. This directory holds Python-side
full-stack tests (compose up -> load fixtures -> audit -> serve -> assert),
marked `needs_docker` so they stay out of the default run.

Phase 7 adds the demo rehearsal test: one run that walks the full 7-minute script
and asserts each key screen state appears.
