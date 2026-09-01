# 0013 - Model artefacts persist via a shared GCS mount; trust scores rescore on demand

**Status:** Accepted (2026-09-01)

Extends [0012](0012-drop-timescale-and-redis.md)'s "model artefacts are cached
in-process instead" - that ADR covers the in-process cache; this one covers where
the artefacts an instance's cache warms *from* actually live in production, and
closes a gap the in-process cache alone cannot: a drop already scored before a
model existed never gets rescored just because the model shows up later.

## Context

Production (`provenance-api`, Cloud Run) was found serving `ImputationCertainty`
as a statistics-only placeholder (reason code `T02`) for every station, despite a
real, checksum-matching graph-conditioned imputation model existing on disk. Two
separate things turned out to be true at once:

1. **Storage was already solved, just undocumented.** `provenance-api` and a
   second Cloud Run resource, `provenance-tasks` (a Job that runs `prov <cli
   subcommand>` with the same `api` image, invoked via `gcloud run jobs
   update --args=... && gcloud run jobs execute --wait`), both mount the same
   GCS bucket (`provenance-506423-provenance-artefacts`) at
   `/app/src/provenance/models/artefacts` via a `gcsfuse.run.googleapis.com`
   CSI volume. Training in the job and reading in the API service share a real
   filesystem. This was set up directly against the GCP project - it has no
   Terraform, no entry in `deploy.yml`, and no prior ADR. `gcloud run services
   describe`/`gcloud run jobs describe` are, right now, the only record of it.
2. **Storage being solved was not sufficient.** `/v1/quality/summary` never
   touches the model artefacts or the in-process cache at request time - it reads
   a `TrustScore` row already persisted in Postgres. That row is computed exactly
   once, synchronously, inside `prov db load` (`io/db/loader.py::load_frame` →
   `_insert_trust_scores` → `ImputationLookup.build`), and nothing ever
   recomputes it afterward. The specific run being served was loaded at
   `2026-08-31T11:59:01Z`; the matching imputation artefacts were not written to
   the bucket until `13:54Z`/`17:02Z` that same day - hours later. The load
   correctly degraded to the placeholder at the time it ran (standing rule 6
   working as designed) and that decision is now permanent for that data
   checksum. `db load`'s idempotency check
   (`session.get(m.IngestBatch, batch_id)`) has no path for "the data is
   unchanged but I'd like this rescored" - it only ever short-circuits.

The in-process cache described in 0012 does not close this gap either: it
governs live inference paths (`explain`, `deweather`, `graph/attention`), all of
which call the model on every request and would naturally pick up a newer
artefact. Imputation-for-trust is different by construction - `available_
imputation_models` reads straight off disk with `load_latest` (not `load_
latest_cached`), because it only ever runs at load/rescore time, not per
request. There was simply no code path, cached or not, that ran a second time
once training finished.

## Decision

**Storage:** keep the GCS-FUSE-mounted bucket as the shared artefact store
between `provenance-tasks` and `provenance-api`. No code changes this bucket -
`registry.py`/`hstgat/store.py` already only know about a local directory
(`PROVENANCE_ARTEFACTS_DIR`), and gcsfuse presents the bucket as exactly that.
Documented here because nothing else in the repository would tell a future
reader it exists.

**Rescoring is a new, explicit, narrow command: `prov db rescore --source
<path>`** (`io/db/loader.py::rescore_frame`, wired through `migrate.rescore`).
It:

- Requires the drop to already be loaded (`IngestBatch` must exist for that
  checksum) - raises `BatchNotLoadedError` otherwise. Rescoring is not a load
  path; it never inserts a reading, a defect, a coverage fact, or an event.
- Deletes and reinserts only the `TrustScore` rows for that exact
  `audit_run_id`, recomputed against whatever models `PROVENANCE_ARTEFACTS_DIR`
  holds right now.
- Never trains anything. "The model only retrains by explicit command or new
  data" (the standing operational rule this ADR is written to keep true) means
  rescoring must not be the thing that quietly triggers a retrain, and it isn't
  one - it is strictly a re-read of whatever is already on disk.

This keeps the three operations distinct and separately invocable, matching how
they are already run against `provenance-tasks`: **train** (`models
train-hstgat`, `models train-imputation`, ...) writes artefacts; **load** (`db
load`) ingests a drop and scores it against whatever existed at that moment;
**rescore** (`db rescore`, new) re-derives trust for an existing drop against
whatever exists *now*. None of the three implies any of the others.

## Consequences

- Fixing a drop that was scored before its models existed is now a single,
  documented command instead of a full `db reset --yes` and a complete reload -
  materially lower-risk for a production database that may by then hold real
  operator sign-offs, dispatches and maintenance state that a reset would
  destroy.
- The training→load ordering still matters for a *fresh* drop's first score:
  `rescore` is a repair path, not a substitute for training before the first
  `db load`. A pipeline that chains these steps should still order training
  before the first load wherever practical; `rescore` exists for when that
  wasn't possible or wasn't done.
- `provenance-tasks` remains outside this repository's IaC. That is an accepted
  gap, not a closed one - flagged for follow-up, not solved by this ADR.
- `rescore`'s reinsert is a full delete-then-insert for the run, not a
  diff/patch. At this corpus's size (149,683 rows, ~120 scoring instants ×
  16 stations) that is milliseconds of work; it would need reconsidering well
  before it became a real cost.
