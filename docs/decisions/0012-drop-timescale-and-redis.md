# 0012 - Drop TimescaleDB and Redis; plain PostgreSQL 16 + PostGIS

**Status:** Accepted (2026-08-27)

Partially supersedes [0001](0001-monorepo-and-stack.md) — specifically its
"TimescaleDB over separate time-series and spatial stores" paragraph, and the
"Redis caches features" sentence in its graph paragraph. Everything else in 0001
stands.

## Context

0001 chose TimescaleDB because "the data is a time series with a geometry
attached" and one engine covering both beats running Influx alongside PostGIS.
That reasoning was about *not adding a second store*. It was never a claim that
the Timescale extension itself was doing work.

Two things are true now that were not when 0001 was written:

1. **Nothing in the codebase depends on a hypertable.** The extension was enabled
   in `0001_initial`, three tables were converted with `create_hypertable`, and
   that was the end of it. No continuous aggregate, no compression policy, no
   retention policy, no `time_bucket` call. Every query the repository layer
   issues is ordinary SQL that a plain Postgres 16 answers identically. The
   corpus is ~150k rows over 30 days across 18 stations — four orders of
   magnitude below where chunking starts to pay for itself.
2. **Redis was never wired up at all.** 0001 says "Redis caches features". No
   client was ever imported, nothing read or wrote a cache, and `redis` is not
   in `pyproject.toml`. What existed was a `cache` service in Compose, a
   `redis_url` setting nothing read, and a line in `.env.example` — an
   aspiration carried in the infrastructure as though it were a component.

The forcing function is the deployment target: managed Postgres (Cloud SQL)
offers PostGIS but not the Timescale extension. Keeping a dependency that costs
a self-managed database and buys nothing is the wrong trade.

## Decision

**Plain PostgreSQL 16 with PostGIS.** The `timescaledb` extension and the three
`create_hypertable` calls come out of the migrations. PostGIS stays exactly as
it was, including the `geom` generated column on `stations` — the geometry is
load-bearing and Cloud SQL supports it.

**Redis is removed rather than implemented.** The `cache` service, the
`redis_url` setting and the `REDIS_URL` environment entry all go.

**Model artefacts are cached in-process instead.** The caching that was actually
needed was never feature caching — it was avoiding a `joblib.load` and a
`torch.load` from disk on every request. That is now a module-level cache in
`models/registry.py` and `models/hstgat/store.py`, warmed once at API startup.
A successful load is remembered; a `None` is not, so an artefact trained after
the process started is still picked up (standing rule 6).

The local Compose `db` image stays `timescale/timescaledb-ha:pg16`. It is a
known-good multi-arch Postgres 16 build; nothing now enables its extension.

## Consequences

- The schema is portable to any managed Postgres with PostGIS. No self-managed
  database is required to deploy.
- Reversible at low cost if the data volume ever justifies it: re-adding
  `create_hypertable` in a new migration is additive, and the composite primary
  keys already lead with `timestamp_utc`, which is what Timescale requires of a
  partition column. Nothing about this change forecloses going back.
- One less service in Compose, and one less moving part in the demo.
- The in-process model cache is per-process. Multiple API workers each hold
  their own copy, which is the correct trade at this artefact size and avoids
  reintroducing a network hop to save a few megabytes of RSS.
