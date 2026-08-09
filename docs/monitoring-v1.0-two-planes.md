# Monitoring — two planes, on purpose (v1.0)

Supersedes: nothing (new in phase 7).
Status: current.

Provenance monitors itself on **two separate planes**, with separate metrics, separate
endpoints, and separate Grafana dashboards. Keeping them apart is not incidental — it
is the maturity signal. An SRE and a data scientist are asking different questions, and
a single "is it healthy?" panel that mixes them answers neither.

## Plane 1 — infrastructure health

*The question: is the service up, fast, and error-free?*

- **Source:** the API exposes Prometheus metrics at `GET /metrics` (unauthenticated,
  like the other meta probes, so a scraper needs no key).
- **Metrics:** `prov_up`, `prov_http_requests_total{method,path,status}`,
  `prov_http_request_duration_seconds` (histogram), `prov_http_requests_in_flight`.
  The `path` label is the *route template* (`/v1/trust/{station_id}`), never the raw
  path, so cardinality stays bounded.
- **Collection:** `infra/monitoring/prometheus.yml` scrapes the API every 15 s.
- **Dashboard:** `infra/monitoring/grafana-service-health.json` — up, request rate,
  5xx rate, p95 latency, in-flight. Prometheus datasource.

An infra alarm ("p95 latency is 3 s", "5xx rate is climbing") says nothing about
whether the *models* are still any good. That is the other plane.

## Plane 2 — model health (drift)

*The question: are the models and the data drifting under our feet?*

- **Source:** the API serves the drift report at `GET /v1/admin/model-drift`
  (**admin only** — it exposes model internals). Computed by
  `provenance.ops.drift` + `provenance.ops.store.model_drift_report`.
- **What it watches:**
  - **Deweathering R² over time** — is the weather model still explaining variance?
  - **Fault-classifier confusion matrix over time** — is precision/recall holding?
  - **Conformal empirical coverage over time** — does the 90% interval still cover 90%?
  - **Defect-rate drift by station** — is a specific station degrading? Rate is
    counting-defects ÷ covered cells, in percent, with structural absences excluded
    (standing rule 3), exactly as the network defect rate is computed.
- **Dashboard:** `infra/monitoring/grafana-model-drift.json` — reads the admin endpoint
  via a JSON/Infinity datasource. Deliberately **not** a Prometheus dashboard.
- **Graceful degradation (standing rule 6):** the defect-rate drift is always
  computable from the audit runs. The model-metric series exist only once models have
  been trained (their artefacts are gitignored), so before training they show an empty
  series with a note — never a fabricated trend.

## Why separate, restated

- **Different owners.** Infra is on-call/SRE; drift is the modelling team.
- **Different cadence.** Infra is per-second; drift is per-training-run / per-audit.
- **Different failure modes.** A perfectly healthy service can serve confidently wrong
  numbers if a model has drifted — the exact failure Provenance exists to catch. A
  monitor that hid model drift inside service health would reproduce, internally, the
  very "looks healthy, isn't" problem the product is about.
