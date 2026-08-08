# 0003 - Ingestion abstraction

**Status:** Accepted (2026-08-08)

## Context

Provenance has to ingest four very different sources: the Green Sentinel Excel
export (the one confirmed source today), Enclod cumulative traffic counters,
HungaroMet weather, and GTFS static transit data. More will follow — the pitch
explicitly promises that a streaming feed (Kafka/Redpanda) can be added later
without a rewrite. The risk is that source-specific parsing leaks upward into the
detectors, the audit, or the trust layer, so that adding a source means touching
half the codebase and the layering guarantee (`tests/architecture/test_layering.py`)
quietly rots.

The pipeline is already built on a single canonical long frame: everything
downstream of the loaders speaks one shape, `(station_id, parameter, timestamp_utc,
value, unit, instrument_id, source_file, row_hash)`. That frame is the natural
seam to hang ingestion off.

## Decision

**Every source enters through one `IngestAdapter` Protocol** (`io/ingest/base.py`)
whose job is total and narrow: turn its source into the canonical frame, or declare
itself a reference/covariate source consumed later. Three methods:

- `discover(root) -> list[Path]` — which files under a drop this adapter recognises.
  Always safe to call; commits to no schema.
- `read(root) -> DataFrame` — the canonical frame, or a loud failure.
- `source` / `kind` attributes — a stable source key recorded on every ingest
  batch, and whether the source yields `readings`, a `covariate`, or `reference`.

A registry (`io/ingest/__init__.py`) is the single place that knows the set of
sources. `resolve(source)` returns an adapter; `discover(root)` maps a drop to the
adapters that have data in it.

**Standing rule 2 is enforced at the adapter boundary.** An adapter for a source
whose schema is not yet confirmed (`schema_assumptions.yaml` marks Enclod and
weather `unconfirmed`) raises `SchemaDriftError` from `read()` rather than inventing
column names. A source that is confirmed to exist but is not yet parsed (GTFS
static, wired up in phase 7) raises `SourceNotReady`. Only Green Sentinel is fully
wired in phase 2; it delegates to the phase-1 loaders unchanged.

## How a streaming adapter slots in later

A `KafkaAdapter` (or Redpanda, or any queue) is a **new class in `io/ingest/` and
nothing else**. It implements the same Protocol: `read()` drains the topic into the
same canonical frame, `discover()` reports topic availability, `source="kafka"`.
Because detectors, audit, and trust consume only the canonical frame — never a
source — they do not change, and the architecture import-graph test continues to
pass. The registry gains one entry. This is the property the abstraction exists to
guarantee, and it is checked by `tests/unit/test_ingest.py`
(`test_all_adapters_satisfy_the_protocol`).

## Consequences

- Adding a source is a local change with a mechanical test, not a cross-cutting one.
- Provenance of data is preserved end to end: the adapter's `source` key is written
  onto the `ingest_batches` row, and every reading carries that batch id.
- The cost is one indirection and the discipline that no loader may skip the
  canonical frame. That discipline is exactly what the layering test already guards.
- Enclod/weather/GTFS ship as discover-only adapters until their schemas are
  confirmed; this is deliberate honesty, not an omission, and the loud failures
  point at the exact config to update.
