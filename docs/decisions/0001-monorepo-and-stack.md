# 0001 - Monorepo layout and core stack

**Status:** Accepted (2026-08-07)

> **Partially superseded by [0012](0012-drop-timescale-and-redis.md) (2026-08-27):**
> the TimescaleDB choice and the "Redis caches features" sentence below no longer
> describe the stack. The rest of this record stands.

## Context

Provenance is a solo build against a hard competition deadline (demo entry
25 September 2026), with a research contribution that may or may not converge. The
architecture has to make a slip in the hard weeks survivable.

## Decision

**One repository, src layout.** `src/provenance` for the Python package,
`apps/web` for the dashboard. A single repo keeps the OpenAPI schema, the
generated TypeScript client, and the CI gate in one place. Splitting them would
buy nothing at this size and would cost a synchronisation problem every phase.

**uv for Python environments.** Fast, lockfile-driven, and it means `make install`
is one command on a fresh machine. `make install-pip` exists as a fallback for
anyone without uv.

**TimescaleDB over separate time-series and spatial stores.** The data is a time
series with a geometry attached. Postgres 16 with TimescaleDB and PostGIS covers
both in one engine. Running Influx alongside PostGIS for eighteen stations would
be operational overhead with no return.

**Graph in memory, not in a graph database.** At 18-40 core nodes the graph is
cheaper to rebuild from Postgres each inference cycle than to keep synchronised in
Neo4j. Redis caches features. This is revisited only if the node count grows by an
order of magnitude.

**Docker Compose for the competition build, Kubernetes as the stated production
path.** `infra/k8s` stays deliberately empty. Compose that works beats a cluster
that half-works, and the production story can be told without being built.

**Kafka deferred behind an ingestion interface.** `io/ingest` defines an
`IngestAdapter` protocol with file-drop implementations. A streaming backbone can
be introduced later as another adapter with zero changes to detector or audit
code. Standing up Kafka in week one would be infrastructure theatre.

**Layering enforced by test, not by convention.** `tests/architecture` asserts the
pipeline direction with an import-graph check. Conventions decay under deadline
pressure; tests do not.

## Consequences

- One `make check` gates everything, which is what makes the phase discipline work.
- The frontend depends on a generated client, so a backend schema change that
  breaks the UI fails CI rather than failing in the demo.
- Introducing Kafka later is a contained change, but it is real work that has not
  been done. That is an accepted, recorded debt rather than a hidden one.
