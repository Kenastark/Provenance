# Provenance API

The operator-facing REST API over the audit and the Trust Score. FastAPI, async,
with an auto-generated OpenAPI schema at `/openapi.json` and interactive docs at
`/docs`.

**The one rule that shapes every response:** a trust score never renders without
its component breakdown and at least one reason code. There is no endpoint that
returns a bare number — enforced by `tests/architecture/test_trust_serialisation.py`.

## Running it

```bash
make up                       # TimescaleDB + Redis
prov db upgrade               # apply migrations (Alembic on Postgres)
prov db load --source tests/fixtures   # load the seeded corpus (idempotent)
uvicorn provenance.api.app:create_app --factory --port 8000
# OpenAPI docs: http://localhost:8000/docs
```

## Authentication

API-key auth with three roles (`public_read` ⊂ `researcher` ⊂ `operator`) — see
ADR 0004. Pass the key in `X-API-Key`. The local-dev keys are:

| Role          | Dev key               | Can read                                                    |
|---------------|-----------------------|-------------------------------------------------------------|
| `public_read` | `prov-public-key`     | stations, trust, quality summary, events, meta              |
| `researcher`  | `prov-researcher-key` | the above **plus** readings, defects, audit runs, export    |
| `operator`    | `prov-operator-key`   | everything a researcher can (write/sign-off lands phase 7)  |

Override the keys in any real environment via `PROVENANCE_API_KEYS` (a JSON
`{key: role}` map). The meta endpoints need no key.

Errors are RFC 7807 problem documents (`application/problem+json`) carrying the
request id, so a failed call and its log line are the same incident.

## Endpoints, with curl

Meta (no key):

```bash
curl -s http://localhost:8000/healthz
# {"status":"ok"}

curl -s http://localhost:8000/readyz
# {"status":"ok","database":"ok"}

curl -s http://localhost:8000/version
# {"version":"0.1.0","git_sha":"...","config_hash":"...","trust_config_hash":"...","model_versions":{"trust_score":"v1"}}
```

Stations (public):

```bash
curl -s -H "X-API-Key: prov-public-key" http://localhost:8000/v1/stations
curl -s -H "X-API-Key: prov-public-key" http://localhost:8000/v1/stations/STA-01
```

Trust — always with components and reason codes (public):

```bash
curl -s -H "X-API-Key: prov-public-key" http://localhost:8000/v1/trust/STA-01
# {
#   "station_id": "STA-01",
#   "trust": 0.2565,
#   "components": [
#     {"name":"HealthConf","value":...,"weight":0.35,"contribution":...,"is_placeholder":false,"detail":"..."},
#     {"name":"ImputationCertainty","value":...,"weight":0.15,"is_placeholder":true,"detail":"placeholder, no model"},
#     {"name":"CrossSensorConsistency","value":...,"weight":0.20,...},
#     {"name":"PhysicalPlausibility","value":...,"weight":0.30,...}
#   ],
#   "reason_codes": ["T01","T03","T04"],
#   "risk": {"value":...,"trust":...,"severity_vs_threshold":...,"population_exposure":1.0,"population_exposure_stubbed":true},
#   "degraded": false,
#   "notes": ["PopulationExposure is stubbed at 1.0 until GTFS ridership lands (§7.8)."]
# }
# population_exposure_stubbed is conditional, not permanent: this response is from
# a corpus with no GTFS bundle under data/raw/gtfs, which is the state of the
# bundled demo/fixture corpora. When a bundle is present, `population_exposure` is
# a real transit-corridor factor computed from it and the note names the source
# layer instead (`src/provenance/trust/engine.py`).

# The score history (paginated):
curl -s -H "X-API-Key: prov-public-key" "http://localhost:8000/v1/trust/STA-01?series=true&limit=50"
```

Readings — raw, or quality-flagged with the audit's reason codes (researcher):

```bash
curl -s -H "X-API-Key: prov-researcher-key" \
  "http://localhost:8000/v1/readings?station=STA-03&parameter=PM10&limit=100"

curl -s -H "X-API-Key: prov-researcher-key" \
  "http://localhost:8000/v1/readings?station=STA-03&parameter=PM10&quality_flagged=true"
# each reading gains "reason_codes": ["R07"] on the cells the audit flagged
```

Defects (researcher):

```bash
curl -s -H "X-API-Key: prov-researcher-key" "http://localhost:8000/v1/defects?code=R07"
curl -s -H "X-API-Key: prov-researcher-key" "http://localhost:8000/v1/defects?station=STA-01&severity=critical"
```

Quality summary — the Data Quality Monitor payload (public):

```bash
curl -s -H "X-API-Key: prov-public-key" http://localhost:8000/v1/quality/summary
# one tile per station: trust, health, flag_count, n_parameters — with its reason codes
```

Events — candidate notable events; `verdict` is null until Phase 4 (public):

```bash
curl -s -H "X-API-Key: prov-public-key" http://localhost:8000/v1/events
```

Audit runs (researcher):

```bash
curl -s -H "X-API-Key: prov-researcher-key" http://localhost:8000/v1/audit/runs
curl -s -H "X-API-Key: prov-researcher-key" http://localhost:8000/v1/audit/runs/<run_id>
```

Audit-trail export — the regulator-facing artefact (§2), reproducible and
reconciled (researcher):

```bash
# CSV: one row per defect + one per structural exclusion, byte-for-byte stable
curl -s -H "X-API-Key: prov-researcher-key" \
  "http://localhost:8000/v1/export/audit-trail?format=csv" -o audit-trail.csv

# JSON: defects, structural exclusions, the defect-rate definition, reconciliation
curl -s -H "X-API-Key: prov-researcher-key" \
  "http://localhost:8000/v1/export/audit-trail?format=json"
```

## Pagination

List endpoints return `{"items": [...], "next_cursor": "...", "count": N}`. Follow
`next_cursor` until it is null to traverse every row exactly once (keyset
pagination — no offset drift). A malformed cursor is a 400 problem, not a 500.

```bash
curl -s -H "X-API-Key: prov-researcher-key" \
  "http://localhost:8000/v1/readings?limit=50&cursor=<next_cursor>"
```
