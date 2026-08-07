# Data

**Nothing in `raw/`, `interim/`, or `processed/` is ever committed.** The
`.gitignore` and a CI job both enforce this. If you need to share a dataset, share
the manifest and the source, not the bytes.

## Layout

    data/
      raw/                  # exactly as received, never modified in place
        green_sentinel/     # the 30-day export (~149,683 rows, 16 land stations, hourly)
        enclod_traffic/     # 42 directional roadside counters, 15-min, ~16 months
        weather/            # HungaroMet
        gtfs/               # DKV static GTFS via the Volan Egyesules feed
      interim/              # intermediate artefacts; safe to delete and regenerate
      processed/            # canonical frames ready for the audit
      manifests/            # checksums and provenance for each raw drop

## Rules

1. **Raw is immutable.** Every transformation writes somewhere else. If a raw file
   is wrong, that is a finding, not something to fix by hand.
2. **Every drop gets a manifest.** `prov data profile` writes
   `manifests/observed-schema-<checksum>.json` recording the observed columns,
   dtypes, unit strings, station ids, parameter names, and the file checksum.
   Every audit run records which manifest it ran against.
3. **Assumptions live in `src/provenance/config/schema_assumptions.yaml`**, not in
   the loader. The loader validates against that file and raises on drift rather
   than silently coercing.
4. **Tests never read from here.** The suite runs on the seeded synthetic corpus
   in `tests/fixtures`, so CI passes on a fresh clone with this directory empty.

## Getting the data in

Drop the files in and run:

    prov data profile --data data/raw
    prov schema observe --data data/raw

The second command writes the observed schema. Diff it against
`schema_assumptions.yaml` and fill in the nulls there before building detectors on
top of a guess.
