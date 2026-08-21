# KER11 ~4,100 µg/m³ PM10 — evidence assembly (v1.0)

Branch: `update-8-ker11`. Data drop: `data/raw` (Green Sentinel export,
`monitoring_2026-05-21_2026-06-19`, checksum `8f8efeedfabdccaa`, 149,683 readings,
16 stations, 18 parameters, window 2026-05-21T00:00 → 2026-06-19T11:00 — from
`prov data profile --data data/raw` / `prov schema observe --data data/raw`,
manifest `data/manifests/observed-schema-8f8efeedfabdccaa.json`).

**This document reaches no verdict.** It assembles evidence only: every number
below is either the direct output of a `prov` CLI command run against this data
drop, or the output of a short, quoted read against the same public library
functions the CLI itself calls (used where a CLI command exists but its written
report deliberately omits a per-cell drill-down — e.g. `audit run`'s `audit.json`
carries aggregate counts, not the full per-cell defect list, so that list is read
directly off the `AuditResult` the command produces in memory). Every code block
below is either a `$ prov ...` invocation or a labelled Python read; nothing is
retyped or rounded by hand beyond what the tool itself rounds. Per the standing
rules, no headline accuracy figure is reported for the propagation adjudicator
(rule 4), and this document does not adjudicate the event (that is explicitly
reserved for the person reading it, per the brief this document was written to).

---

## 1. The reading itself

    $ prov data profile --data data/raw
    $ prov audit run --data data/raw --out reports

```
149,683 readings across 16 stations, 18 parameters
window 2026-05-21T00:00:00 -> 2026-06-19T11:00:00  checksum 8f8efeedfabdccaa
[... 17 other parameter rows from the same table elided ...]
PM10  µg/m3  11,022  515  0.5  4100.7
[... audit run's own console output continues ...]
149,683 readings  conventional completeness 100.0000%
50,843 defective cells  defect rate 29.1225%
  R01  ROW_ABSENT                   24,900
  R02  COMM_GAP                     939
  R07  EXCEEDS_PHYSICAL_MAX         1
  R09  CROSS_PARAM_INVERSION        100
  R10  UNIT_INCONSISTENT            10,627
  R11  DETECTION_LIMIT_FLOOR        2,111
  R12  ZERO_VARIANCE                12,194
  R13  LOW_VARIANCE_DEGRADED        5,622
  R14  STEP_CHANGE                  236
  R18  PARAMETER_ABSENT_STRUCTURAL  2
  R19  SOURCE_ABSENT                3
  R21  SENSOR_DEAD                  3
```

The network-wide `R07 EXCEEDS_PHYSICAL_MAX` count is **exactly 1** — this reading
is the only physical-maximum exceedance anywhere in the 30-day, 16-station, 18-
parameter corpus.

The raw row, from the canonical frame (`provenance.io.loaders.load_data`):

| station_id | parameter | timestamp_utc | value | unit | source_file | row_hash |
|---|---|---|---|---|---|---|
| DEB-KER11 | PM10 | 2026-06-02T20:00:00 | **4100.7** | µg/m3 | `DEB-KER11_Levego.xlsx` | `15d524b4b6c77ef3a6f4ef629953feaad137ad37` |

Station identity, from the `Location` column the loader parses (`StationLocation`,
`provenance.io.loaders.load_station_metadata`): `DEB-KER11` = **"Petőfi tér"**,
lat `47.52324542`, lon `21.6337404`.

### Every reason code attached to this cell

Read directly off the `AuditResult.defects` the `audit run` command above
produced in memory (`provenance.audit.orchestrator.run_audit(...).defects`,
filtered to `station_id == "DEB-KER11" and parameter == "PM10"`):

| timestamp_utc | reason_code | severity | evidence |
|---|---|---|---|
| 2026-06-02T20:00:00 | **R07** `EXCEEDS_PHYSICAL_MAX` | critical | `value=4100.7, limit=2000.0, unit=µg/m3, basis="Extreme Saharan-dust ambient PM10 tops ~1000-1500 µg/m3; 2000 is a hard sensor ceiling. The 4100.7 reading at KER11 exceeds it."` |

That is the **only** row. The detector: `provenance.detectors.physical_bounds.ExceedsMaxDetector`
(code R07), threshold source `config/thresholds.yaml: physical_bounds.PM10.max = 2000.0`.

Widening the same query to every reason code on `(DEB-KER11, PM10)` for ±24 hours
around the event returns the same single row — no other detector (step-change,
zero/low-variance, unit-inconsistency, cross-parameter inversion, detection-limit
floor) fires on this station/parameter in the surrounding two days. The spike is,
by the audit engine's own detectors, a single isolated hour.

---

## 2. DEB-KER11's other parameters, same window

    # provenance.io.loaders.load_data(...) pivoted on (timestamp, parameter) for
    # DEB-KER11, 2026-06-02T14:00 through 2026-06-03T02:00 (±6h around the event)

| timestamp_utc | CO | CO2 | Conductivity | Humidity | NO2 | O3 | **PM10** | PM2.5 | Pressure | WaterLevel | WaterTemp | Wind_Dir | Wind_Spd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14:00 | 300.7 | 741.3 | 1.8 | 52.3 | 8.0 | 138.3 | 13.3 | 6.4 | 999.2 | 3.4 | 15.6 | 125.0 | 6.0 |
| 15:00 | 303.4 | 737.8 | 1.8 | 48.3 | 7.5 | 145.5 | 15.4 | 7.7 | 999.2 | 3.4 | 15.6 | 145.6 | 6.1 |
| 16:00 | 326.7 | 731.4 | 1.8 | 47.5 | 6.5 | 149.5 | 17.5 | 8.7 | 998.6 | 3.4 | 15.6 | 168.1 | 4.5 |
| 17:00 | 318.6 | 732.1 | 1.8 | 45.4 | 6.4 | 157.3 | 18.8 | 9.1 | 998.3 | 3.4 | 15.6 | 173.2 | 4.9 |
| 18:00 | 324.1 | 728.5 | 1.8 | 44.8 | 6.0 | 155.7 | 21.2 | 9.6 | 998.2 | 3.4 | 15.6 | 93.3 | 3.6 |
| 19:00 | 322.3 | 728.9 | 1.8 | 43.7 | 5.8 | 154.8 | **321.4** | 16.3 | 998.2 | 3.4 | 15.6 | 197.7 | 2.9 |
| **20:00** | 342.4 | 724.6 | 1.8 | 44.5 | 7.5 | 149.6 | **4100.7** | 86.4 | 998.0 | 3.4 | 15.6 | 153.1 | 2.7 |
| 21:00 | 389.8 | 738.8 | 1.8 | 47.5 | 19.2 | 117.3 | **1214.0** | **170.3** | 998.4 | 3.4 | 15.6 | 56.5 | 1.1 |
| 22:00 | 413.2 | 754.1 | 1.8 | 52.5 | 25.1 | 107.8 | 117.6 | 96.8 | 998.4 | 3.4 | 15.6 | 47.6 | 1.4 |
| 23:00 | 389.5 | 756.3 | 1.8 | 56.7 | 25.1 | 131.7 | 67.5 | 42.0 | 998.2 | 3.4 | 15.6 | 129.3 | 3.3 |
| 00:00 | 389.4 | 762.7 | 1.8 | 62.1 | 24.8 | 138.7 | 18.5 | 10.3 | 998.3 | 3.4 | 15.6 | 140.2 | 3.3 |
| 01:00 | 388.4 | 765.9 | 1.8 | 66.1 | 20.1 | 137.6 | 15.6 | 8.7 | 998.2 | 3.4 | 15.6 | 155.6 | 3.3 |
| 02:00 | 383.9 | 764.1 | 1.8 | 68.7 | 22.2 | 133.0 | 13.3 | 7.6 | 998.1 | 3.4 | 15.6 | 160.7 | 4.3 |

Units (from the same frame): CO/CO2/NO2/O3/PM10/PM2.5 = µg/m3, Conductivity =
mS/cm, Humidity = percent, Pressure = mbar, WaterLevel = m, WaterTemp = celsius,
Wind_Direction = degrees, Wind_Speed = km/h.

Facts visible directly in this table, no interpretation:

- PM10 is not a single-hour blip in the raw series: it rises at 19:00 (321.4, ~14×
  the 22.1 baseline used below), peaks at 20:00 (4100.7), then decays over the next
  three hours (1214.0 → 117.6 → 67.5) back to the 13–19 range by 00:00–02:00.
- PM2.5 moves with a smaller, **delayed** peak: 16.3 (19:00) → 86.4 (20:00) →
  **170.3 at 21:00** — one hour after PM10's own peak — then 96.8 → 42.0. PM10 >
  PM2.5 at every hour shown (no R09 cross-parameter inversion here).
- CO, CO2, NO2, O3, Pressure, WaterLevel and WaterTemp show no sharp move
  time-locked to 20:00. NO2 and CO drift upward starting an hour or two *after*
  the PM10 peak (NO2: 5.8 → 7.5 → 19.2 → 25.1 across 19:00–22:00; CO similarly
  322 → 342 → 390 → 413), a much smaller relative rise on a much slower clock.

---

## 3. Every neighbouring station, same window, ranked by distance

    # provenance.graph.geometry.haversine_km / initial_bearing_deg between
    # DEB-KER11 (47.52324542, 21.6337404) and each other station's coordinate
    # (provenance.graph.build.station_points_from_metadata)

| rank | station_id | distance_km | bearing_deg (KER11→station) |
|---|---|---|---|
| 1 | DEB-KER06 | 1.3889 | 37.70 |
| 2 | DEB-KER07 | 2.0240 | 175.67 |
| 3 | DEB-KER10 | 2.2730 | 275.11 |
| 4 | DEB-KER15 | 2.4044 | 340.43 |
| 5 | DEB-KER09 | 2.7829 | 332.63 |
| 6 | DEB-KER05 | 3.8544 | 43.94 |
| 7 | DEB-KER08 | 4.2022 | 0.50 |
| 8 | DEB-KER13 | 4.7481 | 323.52 |
| 9 | DEB-KER04 | 6.8510 | 180.48 |
| 10 | DEB-KER03 | 7.3678 | 207.42 |
| 11 | DEB-KER14 | 8.4343 | 181.58 |
| 12 | DEB-KER18 | 9.2062 | 334.14 |
| 13 | DEB-KER02 | 10.8688 | 313.66 |
| 14 | DEB-KER01 | 11.5505 | 301.33 |
| 15 | DEB-KER12 | 15.8145 | 75.73 |

PM10 at every station, same ±6h window, ordered by the ranking above:

| timestamp_utc | KER11 | KER06 | KER07 | KER10 | KER15 | KER09 | KER05 | KER08 | KER13 | KER04 | KER03 | KER14 | KER18 | KER02 | KER01 | KER12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14:00 | 13.3 | 3.8 | 8.1 | 9.8 | 7.3 | 9.2 | 7.7 | 4.2 | 10.0 | 6.3 | 8.2 | 6.8 | 7.4 | 6.1 | 9.2 | 9.5 |
| 15:00 | 15.4 | 4.9 | 9.9 | 11.7 | 7.7 | 10.8 | 9.2 | 5.4 | 11.8 | 6.7 | 8.1 | 7.4 | 8.5 | 6.9 | 10.4 | 9.1 |
| 16:00 | 17.5 | 5.1 | 11.1 | 11.3 | 9.6 | 11.2 | 9.5 | 6.3 | 12.5 | 8.1 | 9.8 | 7.4 | 9.5 | 7.7 | 11.4 | 10.3 |
| 17:00 | 18.8 | 5.7 | 11.7 | 12.0 | 9.3 | 11.4 | 10.1 | 6.4 | 12.4 | 7.8 | 9.6 | 7.8 | 9.7 | 8.3 | 11.0 | 12.1 |
| 18:00 | 21.2 | 5.6 | 12.2 | 12.5 | 9.5 | 12.2 | 12.1 | 5.6 | 11.4 | 8.6 | 10.7 | 7.9 | 9.1 | 7.9 | 12.1 | 12.4 |
| 19:00 | 321.4 | 5.6 | 12.6 | 12.9 | 9.3 | 11.9 | 10.3 | 6.7 | 12.8 | 9.0 | 10.4 | 8.2 | 9.4 | 8.1 | 12.6 | 13.6 |
| **20:00** | **4100.7** | 5.3 | 14.3 | 12.4 | 9.8 | 12.5 | 12.0 | 9.1 | 13.0 | 10.8 | 10.7 | 7.2 | 9.2 | 9.1 | 11.0 | 14.1 |
| 21:00 | 1214.0 | 5.8 | 18.9 | 14.8 | 13.7 | 13.1 | 13.8 | 7.1 | 14.1 | 8.6 | 18.9 | 12.2 | 9.7 | 9.0 | 11.9 | 13.3 |
| 22:00 | 117.6 | 6.8 | 16.2 | 15.6 | 13.0 | 17.1 | 12.7 | 8.4 | 19.7 | 8.9 | 15.3 | 10.2 | 10.4 | 12.4 | 15.8 | 18.2 |
| 23:00 | 67.5 | *n/a* | 12.8 | 16.2 | 12.9 | 15.0 | 14.7 | *n/a* | 16.6 | 11.0 | 12.8 | 9.8 | 12.3 | 12.4 | 16.9 | 16.9 |
| 00:00 | 18.5 | 5.7 | 11.9 | 13.4 | 10.3 | 13.2 | 10.4 | 4.7 | 12.0 | 7.8 | 11.4 | 6.7 | 10.1 | 10.5 | 14.1 | 15.8 |
| 01:00 | 15.6 | 4.0 | 9.9 | 10.6 | 7.3 | 10.2 | 8.3 | 4.4 | 11.0 | 5.9 | 8.4 | 5.7 | 7.3 | 9.7 | 13.3 | 11.7 |
| 02:00 | 13.3 | 3.6 | 10.2 | 9.8 | 8.0 | 10.2 | 8.6 | 3.9 | 8.7 | 5.8 | 8.8 | 5.8 | 7.2 | 8.6 | 11.7 | 11.3 |

**No other station's PM10 moves.** Every one of the other 15 stations stays in
single digits to the low twenties throughout, including the nearest station by
raw distance (DEB-KER06, 1.39 km) and every station in the wind-downwind set used
in §4/§5 below.

`*n/a*` = absent reading, not a zero. Cross-referencing against the audit's own
defect list (`reason_code` counts, same ±6h window, `R01`/`R02` only, grouped by
station and hour, distinct-parameter count ≥ 5 as a proxy for "most/all of the
station went dark that hour"):

| station_id | timestamp_utc | distinct parameters flagged R01/R02 |
|---|---|---|
| DEB-KER05 | 2026-06-02 14:00 | 6 |
| DEB-KER06 | 2026-06-02 23:00 | 5 |
| DEB-KER08 | 2026-06-02 23:00 | 13 (essentially the whole station) |

DEB-KER08 is one of the five wind-downwind neighbours in §4/§5. Its near-total
data gap is three hours *after* the PM10 peak decayed away (23:00, vs. peak at
20:00), not concurrent with it. DEB-KER05's gap is six hours *before* the peak.
Stated as observed; no causal reading is made here.

---

## 4. The wind field at 2026-06-02T20:00:00

Station-local `Wind_Direction`/`Wind_Speed` readings, every station, at the event
hour (`provenance.io.loaders.load_data`, pivoted):

| station_id | Wind_Direction (deg) | Wind_Speed (km/h) |
|---|---|---|
| DEB-KER01 | 142.9 | 4.8 |
| DEB-KER02 | 223.7 | 2.3 |
| DEB-KER03 | 44.2 | 1.1 |
| DEB-KER04 | 143.5 | 1.6 |
| DEB-KER05 | 199.7 | 1.2 |
| DEB-KER06 | 43.7 | 1.2 |
| DEB-KER07 | 210.4 | 1.4 |
| DEB-KER08 | 75.3 | 1.3 |
| DEB-KER09 | 241.8 | 0.0 |
| DEB-KER10 | 152.0 | 1.5 |
| **DEB-KER11** | **153.1** | **2.7** |
| DEB-KER12 | 219.2 | 1.1 |
| DEB-KER13 | 134.0 | 0.6 |
| DEB-KER14 | 191.8 | 1.0 |
| DEB-KER18 | 264.0 | 0.6 |

(DEB-KER15 carries no `Wind_Speed`/`Wind_Direction` columns at all — a structural
absence, `R18 PARAMETER_ABSENT_STRUCTURAL`, not a gap in this hour specifically.)

Fact visible directly in this table: the 15 station-local readings at this hour
span almost the full compass (43.7° to 264.0°) at mostly sub-5-km/h speeds. This
is the signature of a calm, directionally-incoherent hour network-wide, not a
single coherent regional flow — stated as observed, not interpreted.

`provenance.graph.wind.WindField.from_frame(frame)`, read at the event hour:

    WindField.at(2026-06-02T20:00, "DEB-KER11")
      -> from_deg=153.1, speed=2.7 km/h, provenance=station-local, station_count=1
    WindField.city_at(2026-06-02T20:00)   # circular mean over all 15 reporting stations
      -> from_deg=172.53, speed=1.49 km/h, provenance=city-fallback, station_count=15

The propagation adjudicator (§5) uses the **station-local** reading (153.1°,
2.7 km/h — "from" the SSE, i.e. travelling toward 333.1°, roughly NNW) because
KER11 measured its own wind that hour; the city-level fallback (used only when a
station has no local reading) is close in direction but slower. Wind-downwind
alignment for each neighbour — the cone-weighted edge set the adjudicator derives
from this vector — is in §5's evidence bundle (`downwind_neighbours`), ranked
there by edge weight, not by raw distance.

---

## 5. The full analytic adjudicator output

    $ prov graph adjudicate --data data/raw --out reports/adjudications --limit 10

```
                    Adjudicated events (ranked by magnitude)
┏━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Rank ┃ Station   ┃ Parameter ┃ Timestamp ┃ Excess    ┃ Verdict   ┃ Confiden… ┃
┡━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│ 1    │ DEB-KER11 │ PM10      │ 2026-06-… │ 4,078.6   │ LIKELY_F… │ 1.00      │
│      │           │           │           │ µg/m3     │           │ (high)    │
│ 2    │ DEB-KER06 │ CO        │ 2026-06-… │ 1,145.5   │ AMBIGUOUS │ 0.50      │
│      │           │           │           │ µg/m3     │           │ (moderat… │
│ 3    │ DEB-KER12 │ CO        │ 2026-06-… │ 406.2     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │ µg/m3     │           │ (moderat… │
│ 4    │ DEB-KER10 │ CO        │ 2026-06-… │ 377.2     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │ µg/m3     │           │ (moderat… │
│ 5    │ DEB-KER09 │ CO        │ 2026-06-… │ 365.4     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │ µg/m3     │           │ (moderat… │
│ 6    │ DEB-KER03 │ WaterLev… │ 2026-05-… │ 0.0 m     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │           │           │ (moderat… │
│ 7    │ DEB-KER03 │ WaterLev… │ 2026-05-… │ 0.0 m     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │           │           │ (moderat… │
│ 8    │ DEB-KER03 │ WaterLev… │ 2026-05-… │ 0.0 m     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │           │           │ (moderat… │
│ 9    │ DEB-KER03 │ WaterLev… │ 2026-05-… │ 0.0 m     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │           │           │ (moderat… │
│ 10   │ DEB-KER03 │ WaterLev… │ 2026-05-… │ 0.0 m     │ AMBIGUOUS │ 0.50      │
│      │           │           │           │           │           │ (moderat… │
└──────┴───────────┴───────────┴───────────┴───────────┴───────────┴───────────┘
9 event(s) routed to human review (AMBIGUOUS).
Wrote 10 bundle(s) and an index to reports/adjudications
```

(Verbatim terminal output, including the rich-table's own line-wrapping and
column truncation at this terminal width. Ranks 3–10 are addressed in §8: ranks
3–5 are three more CO spikes at other stations, and ranks 6–10 are a
zero-magnitude `WaterLevel` tie at DEB-KER03 — not five more "large events".)

This reproduces, byte-for-byte, the bundle already recorded in
`docs/updates/u6-real-drop.md` from an earlier run against the same drop
(standing rule 8: determinism) — `reports/adjudications/adj_01_DEB-KER11_PM10_2026-06-02T20-00-00.json`:

```json
{
  "confidence": 1.0,
  "confidence_band": "high",
  "event": {
    "anomaly_score": 1.0,
    "baseline": 22.1,
    "excess": 4078.6,
    "parameter": "PM10",
    "station_id": "DEB-KER11",
    "timestamp_utc": "2026-06-02T20:00:00",
    "unit": "µg/m3",
    "value": 4100.7
  },
  "evidence": {
    "covariates": [
      {
        "name": "traffic",
        "reason": "Enclod counter schema is unconfirmed (ADR 0003); the traffic covariate lands once the columns are read. Until then it neither supports nor excuses a rise.",
        "state": "unavailable"
      },
      {
        "name": "weather",
        "reason": "Only the wind vector is used here. Boundary-layer height and full deweathering (the R20 meteo-artefact test) arrive in phase 5.",
        "state": "wind-only"
      }
    ],
    "downwind_neighbours": [
      {
        "actual_excess": -0.05, "arrival_delay_min": 17.18, "bearing_deg": 332.63,
        "carries_parameter": true, "corroborated": false, "distance_km": 2.7829,
        "edge_weight": 0.323174, "expected_excess": 2337.7072, "expected_interval": null,
        "sigma": null, "station_id": "DEB-KER09", "wind_provenance": "station-local"
      },
      {
        "actual_excess": 1.05, "arrival_delay_min": 14.96, "bearing_deg": 340.43,
        "carries_parameter": true, "corroborated": false, "distance_km": 2.4044,
        "edge_weight": 0.264851, "expected_excess": 2521.5398, "expected_interval": null,
        "sigma": null, "station_id": "DEB-KER15", "wind_provenance": "station-local"
      },
      {
        "actual_excess": -0.4, "arrival_delay_min": 29.72, "bearing_deg": 323.52,
        "carries_parameter": true, "corroborated": false, "distance_km": 4.7481,
        "edge_weight": 0.15149, "expected_excess": 1577.9758, "expected_interval": null,
        "sigma": null, "station_id": "DEB-KER13", "wind_provenance": "station-local"
      },
      {
        "actual_excess": -0.65, "arrival_delay_min": 56.84, "bearing_deg": 334.14,
        "carries_parameter": true, "corroborated": false, "distance_km": 9.2062,
        "edge_weight": 0.087412, "expected_excess": 646.952, "expected_interval": null,
        "sigma": null, "station_id": "DEB-KER18", "wind_provenance": "station-local"
      },
      {
        "actual_excess": 0.1, "arrival_delay_min": 29.22, "bearing_deg": 0.5,
        "carries_parameter": true, "corroborated": false, "distance_km": 4.2022,
        "edge_weight": 0.082841, "expected_excess": 1760.0053, "expected_interval": null,
        "sigma": null, "station_id": "DEB-KER08", "wind_provenance": "station-local"
      }
    ],
    "expectation_provenance": "analytic",
    "match_score": 0.0,
    "n_downwind": 5,
    "n_usable": 5,
    "notes": ["No headline accuracy figure is reported for this method (standing rule 4)."],
    "reason_codes": ["R17"],
    "series": {
      "actual": [0.0, 0.168],
      "expected": [0.0, 2049.6633],
      "timestamps": ["2026-06-02T20:00:00", "2026-06-02T21:00:00"]
    },
    "wind": {
      "from_deg": 153.1, "provenance": "station-local", "speed": 2.7,
      "speed_unit": "km/h", "station_count": 1, "to_deg": 333.1
    }
  },
  "rank": 1,
  "routes_to_review": false,
  "verdict": "LIKELY_FAULT"
}
```

**Every component score, in one place:**

| component | value |
|---|---|
| verdict | `LIKELY_FAULT` |
| confidence | 1.00 (band: high) |
| routes_to_review | false |
| match_score (edge-weighted corroborated fraction) | **0.0** — none of the 5 usable downwind neighbours corroborated |
| n_downwind / n_usable | 5 / 5 — every wind-cone neighbour also carried PM10 and had a computable baseline |
| expectation_provenance | `analytic` (phase-4 plume prior; see §6 for the learned contrast) |
| reason_codes | `R17` `SPATIAL_INCONSISTENCY` |
| wind used | 153.1° / 2.7 km/h, station-local (§4) |

Per-neighbour detail (already ranked by edge weight, i.e. by wind-cone alignment
× distance decay, descending):

| station | dist_km | bearing° | edge_weight | expected_excess | actual_excess | corroborated |
|---|---|---|---|---|---|---|
| DEB-KER09 | 2.7829 | 332.63 | 0.323174 | 2337.7072 | **-0.05** | false |
| DEB-KER15 | 2.4044 | 340.43 | 0.264851 | 2521.5398 | **1.05** | false |
| DEB-KER13 | 4.7481 | 323.52 | 0.151490 | 1577.9758 | **-0.4** | false |
| DEB-KER18 | 9.2062 | 334.14 | 0.087412 | 646.9520 | **-0.65** | false |
| DEB-KER08 | 4.2022 | 0.50 | 0.082841 | 1760.0053 | **0.1** | false |

Every downwind neighbour that the wind-cone model selects was expected (under the
analytic plume prior) to show an excess in the hundreds-to-thousands of µg/m³; all
five instead show an actual excess within ±1.05 µg/m³ of their own baseline —
i.e., no measurable change at all.

**Governing thresholds** (`config/graph.yaml`, `status: provisional` — physically-
reasoned defaults, not calibrated, per ADR 0007 and standing rule 1's carve-out for
modelling choices): `genuine_match_threshold=0.6`, `fault_match_threshold=0.2`,
`min_downwind_neighbours=2`, `corroboration_tolerance=0.5` (±50%),
`downwind_weight_floor=0.05`, `baseline_window_hours=48`,
`ambiguous_confidence_cap=0.5`, `confidence_high_at=0.75`, `confidence_moderate_at=0.5`.
match_score `0.0 ≤ 0.2` (`fault_match_threshold`) routes to `LIKELY_FAULT` with
confidence `1.0 - match_score = 1.00`, per `provenance.graph.adjudicate._decide`.

---

## 6. The learned path (`--learned`) — research contrast, not a better answer

> Per `docs/phase-reports/phase-6-hstgat.md`'s own flag-for-review: *"the learned
> verdict is exercised for its mechanism and fallback, never for accuracy (which we
> are forbidden to quote anyway). The number that matters on stage — the KER11
> verdict — still comes from the analytic path by default; `--learned` is the
> opt-in research demonstration."* Nothing below changes that. It is reported for
> contrast only.

No HST-GAT artefact existed in `src/provenance/models/artefacts/` before this
document was assembled (only `fault-v1-*` and `deweather-v1-*`). To make this
section a genuine contrast rather than a graceful-degradation stub, one was
trained fresh, on this same real drop, exactly as the CLI docstring specifies:

    $ prov models train-hstgat --source data/raw

```
Training HST-GAT on 16 stations x 706 hours (PM10).
HST-GAT v1-8f8efeed: 3299 parameters.
GCN baseline 2018 parameters (comparison).
Conformal nominal 0.9 → empirical 0.8708 (n=2816).
Saved hst-gat-v1-8f8efeed.pt, card docs/model-cards/hst-gat-v1-8f8efeed.md
No propagation accuracy/F1 is reported (standing rule 4).
```

(`target_parameter` for this trained artefact is **PM10** — the CLI's own
default, matching `config/models.yaml: hstgat.target_parameter`. This matters
directly for §8.7 below.)

    $ prov graph adjudicate --data data/raw --out reports/adjudications-learned --limit 10 --learned

The console table (verdict/confidence/excess per ranked event) is **identical**
to §5's analytic table for every one of the 10 ranked events — those three
columns come from the `Adjudication` object regardless of which expectation
provider ran, and for rank 1 the verdict happens not to change (see why below).
What differs is inside each bundle's `evidence.expectation_provenance` and
`evidence.downwind_neighbours[*].expected_excess` — reproduced in full below.

Full learned-path bundle for the KER11 event,
`reports/adjudications-learned/adj_01_DEB-KER11_PM10_2026-06-02T20-00-00.json`:

```json
{
  "confidence": 1.0,
  "confidence_band": "high",
  "event": {
    "anomaly_score": 1.0, "baseline": 22.1, "excess": 4078.6, "parameter": "PM10",
    "station_id": "DEB-KER11", "timestamp_utc": "2026-06-02T20:00:00",
    "unit": "µg/m3", "value": 4100.7
  },
  "evidence": {
    "downwind_neighbours": [
      {
        "station_id": "DEB-KER09", "distance_km": 2.7829, "bearing_deg": 332.63,
        "edge_weight": 0.323174, "expected_excess": -0.2194,
        "expected_interval": [-10.9067, 10.4679], "sigma": 5.5513,
        "actual_excess": -0.05, "corroborated": false
      },
      {
        "station_id": "DEB-KER15", "distance_km": 2.4044, "bearing_deg": 340.43,
        "edge_weight": 0.264851, "expected_excess": -0.0008,
        "expected_interval": [-10.7423, 10.7406], "sigma": 5.5795,
        "actual_excess": 1.05, "corroborated": false
      },
      {
        "station_id": "DEB-KER13", "distance_km": 4.7481, "bearing_deg": 323.52,
        "edge_weight": 0.15149, "expected_excess": -1.7012,
        "expected_interval": [-12.6032, 9.2008], "sigma": 5.6629,
        "actual_excess": -0.4, "corroborated": false
      },
      {
        "station_id": "DEB-KER18", "distance_km": 9.2062, "bearing_deg": 334.14,
        "edge_weight": 0.087412, "expected_excess": 2.7092,
        "expected_interval": [-8.2112, 13.6297], "sigma": 5.6725,
        "actual_excess": -0.65, "corroborated": false
      },
      {
        "station_id": "DEB-KER08", "distance_km": 4.2022, "bearing_deg": 0.5,
        "edge_weight": 0.082841, "expected_excess": 6.1098,
        "expected_interval": [-4.3545, 16.5741], "sigma": 5.4355,
        "actual_excess": 0.1, "corroborated": false
      }
    ],
    "expectation_provenance": "hst-gat",
    "match_score": 0.0, "n_downwind": 5, "n_usable": 5,
    "reason_codes": ["R17"],
    "series": {
      "actual": [0.0, 0.168], "expected": [0.0, 0.4552],
      "timestamps": ["2026-06-02T20:00:00", "2026-06-02T21:00:00"]
    },
    "wind": {"from_deg": 153.1, "speed": 2.7, "provenance": "station-local"}
  },
  "rank": 1, "routes_to_review": false, "verdict": "LIKELY_FAULT"
}
```

| component | analytic (§5) | learned (this section) |
|---|---|---|
| verdict | LIKELY_FAULT | **LIKELY_FAULT** (unchanged) |
| confidence | 1.00 (high) | **1.00 (high)** (unchanged) |
| match_score | 0.0 | **0.0** (unchanged) |
| expectation_provenance | analytic | **hst-gat** — the trained forecast genuinely ran |
| expected_excess at the 5 downwind neighbours | +647 to +2,522 µg/m³ | **-1.7 to +6.1 µg/m³**, each with a calibrated ±~10-16 µg/m³ interval |

The verdict does not change, but *why* the neighbours count as uncorroborated is
now different in kind, not just degree. The analytic prior expected each
downwind neighbour to see a large propagated rise and observed none of it. The
learned model — trained on this corpus's actual graph-conditioned history —
expects **no meaningful rise at all** at any of the five neighbours (its
calibrated interval comfortably contains zero at every one), and the observed
near-zero actual excess sits inside that interval every time. Both paths agree
none of the five neighbours corroborate a propagating plume; they disagree
almost entirely on what a real plume *should* have looked like there. Which of
the two priors is the more trustworthy one to reason from is exactly the kind
of question §9 leaves open — standing rule 4 forbids scoring the method itself,
and the phase-6 report is explicit that this is a research contrast, not a
better answer.

---

## 7. Maintenance window, calibration event (R15), or outage overlap

**R15 (`CALIBRATION_EPOCH_DISCONTINUITY`) cannot fire on any reading in this
corpus.** It is registered in `provenance.config.reason_codes` but has no detector
implementation: `provenance.detectors.registry.default_detectors()` — the list the
audit orchestrator actually runs — does not include it (confirmed by reading the
registry source directly; there is no `$ prov` command that would surface this,
since there is nothing to run). This is a capability gap, not evidence that no
calibration event occurred.

**No maintenance-window or calibration-log data source exists anywhere in
`data/raw`.** Every Green Sentinel file is a single-sheet workbook (sheet name
`export`, confirmed for every `DEB-KER*_{Levego,Zaj,Felszin_alatti_viz}.xlsx` file
in the drop); `enclod_traffic/` is directional counter CSVs (schema unconfirmed,
ADR 0003); `weather/` holds no file at all in this pull (only `.gitkeep`); `gtfs/`
is static transit. None of the four raw sources carries a maintenance or
calibration field of any kind.

**R02 (`COMM_GAP`, the one outage code that does exist) does not fire on
DEB-KER11 anywhere near this event.** Widening the exact-cell query from §1 to
every parameter at DEB-KER11, ±24 hours, returns no `R02` and no `R14` at any
hour but 20:00 itself — every other code present in that window (`CO2`→R10,
`Conductivity`/`WaterLevel`→R12/R13, `TVOC`/`NO`→R01/R11) is a constant background
condition that recurs essentially every hour across the whole 30-day corpus at
this station, not something localised to the event.

The nearest thing to an "outage overlapping this event" found anywhere in this
investigation is the fact already reported in §3: two of DEB-KER11's wind-cone
neighbours (DEB-KER06 and DEB-KER08) went dark across most or all of their
parameters for the single hour of 23:00 — three hours after the PM10 peak, not
concurrent with it, and at neighbouring stations, not the source. Whether that is
relevant is left to §9.

---

## 8. Second candidate event: DEB-KER06 / CO / 2026-06-17T13:00:00

Same command as §5 (`prov graph adjudicate --limit 10`) ranks candidate events by
magnitude across the whole corpus; rank 1 is KER11 (above). Ranks 3–5 are three
more CO spikes (DEB-KER12, DEB-KER10, DEB-KER09, all excess in the 360–410 µg/m³
range); ranks 6–10 are five consecutive-hour `WaterLevel` ties at DEB-KER03, all
with **0.0 m excess** — a step-change/anomaly-ranking degeneracy, not five more
"large events". **Rank 2 is used here** as the second case because it is the
pipeline's own next-ranked non-degenerate candidate, chosen by the same ranking
the demo runs — not hand-picked for a cleaner story.

### 8.1 The reading and its reason codes

| station_id | parameter | timestamp_utc | value | unit |
|---|---|---|---|---|
| DEB-KER06 | CO | 2026-06-17T13:00:00 | **1514.8** | µg/m3 |

Station identity: `DEB-KER06` = **"Karácsony György utcai bölcsőde"**, lat
`47.53312747`, lon `21.64505351` (`Location` column).

Exact-cell defect (`AuditResult.defects`, filtered to this station/parameter/hour):

| timestamp_utc | reason_code | severity | evidence |
|---|---|---|---|
| 2026-06-17T13:00:00 | **R14** `STEP_CHANGE` | medium | `magnitude=217.138, signed_magnitude=217.138, unit=µg/m3, level_before=357.6142, level_after=574.7522, baseline_mean=371.8833` |

Not R07: CO's physical maximum (`config/thresholds.yaml`) is 100,000 µg/m3 —
1514.8 is nowhere near it. `level_after` (574.75, an EWMA-smoothed level) is far
below the raw instantaneous value (1514.8); the detector operates on a smoothed
statistic, not the raw reading — reported as computed, not reconciled here.

±24h widened query on `(DEB-KER06, CO)`:

| timestamp_utc | reason_code |
|---|---|
| 2026-06-17 12:00 | R01 `ROW_ABSENT` |
| 2026-06-17 13:00 | R14 `STEP_CHANGE` |
| 2026-06-17 14:00 | R01 `ROW_ABSENT` |

Unlike KER11, **this event is flanked on both sides by a missing hour**, not a
clean continuous trace.

### 8.2 DEB-KER06's other parameters, ±6h

| timestamp_utc | CO | CO2 | Humidity | NO | NO2 | NOx | O3 | PM10 | PM2.5 | TVOC | Wind_Dir | Wind_Spd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 07:00 | 410.3 | 823.5 | 57.7 | 1.8 | 24.1 | 25.9 | 101.5 | 4.6 | 3.1 | *n/a* | 209.3 | 2.7 |
| 08:00 | 421.8 | 804.1 | 63.6 | 1.7 | 26.4 | 28.1 | 102.1 | 6.2 | 3.4 | *n/a* | 79.7 | 3.3 |
| 09:00 | 399.7 | 798.4 | 63.4 | 1.6 | 21.9 | 23.5 | 86.1 | 7.3 | 3.5 | *n/a* | 174.1 | 5.3 |
| 10:00 | 360.4 | 781.4 | 58.4 | 0.7 | 13.6 | 14.7 | 85.5 | 9.7 | 3.4 | *n/a* | 139.3 | 3.3 |
| 11:00 | 326.9 | 767.6 | 53.3 | 0.7 | 9.1 | 10.0 | 93.8 | 8.6 | 3.1 | *n/a* | 105.3 | 3.6 |
| 12:00 | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* |
| **13:00** | **1514.8** | 1124.6 | 52.0 | 3.1 | 6.6 | 9.6 | 90.3 | *n/a* | *n/a* | 44.7 | 270.0 | **0.0** |
| 14:00 | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* | *n/a* |
| 15:00 | 1529.2 | 1123.2 | 55.0 | 30.0 | *n/a* | *n/a* | 75.9 | 0.5 | 1.1 | 38.3 | 270.1 | 0.0 |
| 16:00 | 961.5 | 1124.6 | 55.1 | 33.1 | *n/a* | *n/a* | 72.5 | 0.5 | 1.0 | 18.2 | 270.0 | 0.0 |
| 17:00 | 739.7 | 1146.6 | 54.6 | 30.8 | *n/a* | *n/a* | 67.3 | 0.5 | 0.5 | 10.2 | 270.0 | 0.0 |
| 18:00 | 1246.4 | 1048.8 | 54.6 | 39.7 | *n/a* | *n/a* | 68.5 | 0.5 | 1.0 | 31.7 | 270.1 | 0.0 |
| 19:00 | 1371.6 | 984.7 | 55.4 | 51.7 | *n/a* | *n/a* | 70.0 | 0.5 | 0.5 | 33.6 | 270.1 | 0.0 |

Facts visible directly: at 12:00 and 14:00 essentially every parameter at this
station is absent — the CO reading at 13:00 sits inside a data gap, not a clean
trace. CO stays elevated for hours afterward (961–1529 through 19:00) rather than
decaying back toward the ~370 baseline the way KER11's PM10 did within 4 hours.
`Wind_Direction`/`Wind_Speed` read the identical `270.0°/0.0 km/h` (or `270.1°`) at
**every one of the five hours from 15:00 through 19:00** — reported as observed;
whether that reflects a genuine calm spell or a stuck wind instrument is not
decided here.

### 8.3 Neighbouring stations, ranked by distance (CO, ±3h)

| rank | station_id | distance_km | bearing_deg |
|---|---|---|---|
| 1 | DEB-KER11 | 1.3889 | 217.71 |
| 2 | DEB-KER15 | 2.0245 | 305.20 |
| 3 | DEB-KER05 | 2.4783 | 47.44 |
| 4 | DEB-KER09 | 2.5328 | 302.82 |
| 5 | DEB-KER07 | 3.1940 | 192.60 |
| 6 | DEB-KER08 | 3.2077 | 345.34 |
| 7 | DEB-KER10 | 3.2398 | 253.95 |
| 8 | DEB-KER13 | 4.5693 | 306.52 |
| 9 | DEB-KER04 | 8.0012 | 186.51 |
| 10 | DEB-KER18 | 8.6774 | 325.91 |
| 11 | DEB-KER03 | 8.7379 | 209.06 |
| 12 | DEB-KER14 | 9.5913 | 186.49 |
| 13 | DEB-KER02 | 10.8132 | 306.33 |
| 14 | DEB-KER01 | 11.7858 | 294.61 |
| 15 | DEB-KER12 | 14.7453 | 79.07 |

| timestamp_utc | KER06 | KER11 | KER15 | KER05 | KER09 | KER07 | KER08 | KER10 | KER13 |
|---|---|---|---|---|---|---|---|---|---|
| 10:00 | 360.4 | 361.0 | 373.6 | 352.0 | 382.9 | 363.9 | 370.2 | 385.1 | 375.9 |
| 11:00 | 326.9 | 306.1 | 315.5 | 298.7 | 333.1 | 317.7 | 328.0 | 337.6 | 337.9 |
| 12:00 | *n/a* | 286.0 | 297.1 | 272.1 | 309.8 | 293.2 | 308.1 | 317.1 | 326.4 |
| **13:00** | **1514.8** | 301.9 | 320.8 | 276.6 | 309.1 | 311.8 | 310.6 | 333.2 | 329.5 |
| 14:00 | *n/a* | 308.2 | 337.5 | 312.0 | 336.1 | 313.0 | 339.7 | 331.5 | 347.7 |
| 15:00 | 1529.2 | 305.1 | 346.4 | 297.0 | 326.6 | 325.8 | 327.5 | 340.0 | 340.5 |
| 16:00 | 961.5 | 257.9 | 309.6 | 246.4 | 283.5 | 268.2 | 305.2 | 304.2 | 295.2 |

No other station's CO shows anything outside its normal 240–390 range at any hour
shown — the rise is spatially isolated to DEB-KER06, same as KER11's PM10.

### 8.4 Wind field at 2026-06-17T13:00:00

| station_id | Wind_Direction (deg) | Wind_Speed (km/h) |
|---|---|---|
| DEB-KER01 | 189.3 | 16.4 |
| DEB-KER02 | 236.9 | 8.7 |
| DEB-KER03 | 117.7 | 7.9 |
| DEB-KER04 | 184.4 | 10.4 |
| DEB-KER05 | 235.0 | 9.9 |
| **DEB-KER06** | **270.0** | **0.0** |
| DEB-KER07 | 161.8 | 7.0 |
| DEB-KER08 | 171.7 | 3.3 |
| DEB-KER09 | 189.2 | 0.0 |
| DEB-KER10 | 148.6 | 5.4 |
| DEB-KER11 | 199.1 | 5.8 |
| DEB-KER12 | 202.9 | 5.7 |
| DEB-KER13 | 236.7 | 5.2 |
| DEB-KER14 | 207.1 | 11.2 |
| DEB-KER18 | 180.5 | 2.7 |

Unlike KER11's hour, most of the network reads a fairly coherent 150–240°
flow at 5–16 km/h this hour. The two exceptions reading exactly calm are
DEB-KER06 itself and DEB-KER09. City-level fallback (circular mean, 15
stations): `195.39°` at `6.64 km/h`.

    WindField.at(2026-06-17T13:00, "DEB-KER06")
      -> from_deg=270.0, speed=0.0 km/h, provenance=station-local, station_count=1
    WindField.city_at(2026-06-17T13:00)
      -> from_deg=195.39, speed=6.64 km/h, provenance=city-fallback, station_count=15

### 8.5 Full analytic adjudicator output

`reports/adjudications/adj_02_DEB-KER06_CO_2026-06-17T13-00-00.json`, in full:

```json
{
  "confidence": 0.5,
  "confidence_band": "moderate",
  "event": {
    "anomaly_score": 20.0,
    "baseline": 369.3,
    "excess": 1145.5,
    "parameter": "CO",
    "station_id": "DEB-KER06",
    "timestamp_utc": "2026-06-17T13:00:00",
    "unit": "µg/m3",
    "value": 1514.8
  },
  "evidence": {
    "covariates": [
      {"name": "traffic", "state": "unavailable", "reason": "Enclod counter schema is unconfirmed (ADR 0003); the traffic covariate lands once the columns are read. Until then it neither supports nor excuses a rise."},
      {"name": "weather", "state": "wind-only", "reason": "Only the wind vector is used here. Boundary-layer height and full deweathering (the R20 meteo-artefact test) arrive in phase 5."}
    ],
    "downwind_neighbours": [],
    "expectation_provenance": "analytic",
    "match_score": 0.0,
    "n_downwind": 0,
    "n_usable": 0,
    "notes": [
      "No wind vector at the event hour (calm or unmeasured); propagation cannot be assessed, so the event is routed to review rather than guessed.",
      "No headline accuracy figure is reported for this method."
    ],
    "reason_codes": ["R23"],
    "series": {"actual": [0.0], "expected": [0.0], "timestamps": ["2026-06-17T13:00:00"]},
    "wind": {"from_deg": 270.0, "provenance": "station-local", "speed": 0.0, "speed_unit": "km/h", "station_count": 1, "to_deg": 90.0}
  },
  "rank": 2,
  "routes_to_review": true,
  "verdict": "AMBIGUOUS"
}
```

**Every component score:** verdict `AMBIGUOUS`, confidence `0.50` (band:
moderate, at the `ambiguous_confidence_cap`), `match_score=0.0`, `n_downwind=0`,
`n_usable=0`, reason code `R23 ADJUDICATION_AMBIGUOUS`, `routes_to_review=true`.
`config/graph.yaml`'s calm-wind floor (`wind_edges.min_wind_speed: 0.1`, the
comment in the file says m/s while the reading compared against it is in km/h —
quoted as written, not reconciled here) is not met at 0.0 km/h, so no downwind
cone could be constructed at all — this event was never tested for
corroboration one way or the other, unlike KER11.

### 8.6 Maintenance, calibration, outage overlap

Same institutional facts as §7 apply (no R15 detector exists; no
maintenance/calibration data source exists anywhere in `data/raw`). Unlike
KER11, this event **is** flanked by `R01 ROW_ABSENT` on both sides (§8.1,
§8.2) — a two-hour-wide gap (12:00, 14:00) around the 13:00 reading, on
nearly every parameter the station carries. `R02 COMM_GAP` does not fire on
`CO` specifically in this window (a single flanking absent hour on each side
does not meet whatever run-length the detector requires), but does fire on
other parameters at this station within the wider ±24h window (`NO2` ×2,
`NOx` ×1, `TVOC` ×1) — reported for completeness, not adjudicated.

### 8.7 Learned path, second event

`reports/adjudications-learned/adj_02_DEB-KER06_CO_2026-06-17T13-00-00.json`
is **byte-identical** to the analytic bundle in §8.5, including
`"expectation_provenance": "analytic"`. Two independent reasons converge on the
same outcome, both readable directly from the code:

1. The trained artefact's `target_parameter` is **PM10** (§6), and
   `provenance.models.hstgat.forecast` falls back to the analytic provider
   whenever `event.parameter != loaded.target_parameter` (source line quoted
   verbatim: `if event.parameter != loaded.target_parameter:` →
   `AnalyticExpectation`) — this event's parameter is **CO**, so the learned
   forecast was never eligible to run regardless of anything else.
2. Independently, KER06's own wind speed at 13:00 is exactly `0.0 km/h` (§8.4),
   below the adjudicator's calm-wind floor — `validate_event` routes to
   `_ambiguous_without_neighbours` *before* any expectation provider (learned or
   analytic) is ever consulted, for the same reason it did in the analytic run.

Either fact alone would produce this result; both are true at once. There is
nothing for `--learned` to contrast here beyond confirming the documented
fallback fires exactly as designed (standing rule 6).

---

## 9. What I did not decide

This document assembles evidence and stops there, per the brief. Left
explicitly open, for the person reading this to resolve:

1. **Whether "LIKELY_FAULT, confidence 1.00 (high)" is the right read of KER11**,
   given that the wind reading it depends on (§4) comes from a single
   station-local instrument during a network-wide calm, directionally-incoherent
   hour (15 readings spanning 43.7°–264.0°, mostly under 5 km/h) — versus whether
   the adjudicator should have had less to work with here than its confidence
   number implies. The adjudicator's confidence formula is purely a function of
   corroboration weight; it does not discount for wind-data quality.
2. **Whether PM2.5's smaller, one-hour-delayed echo of the PM10 peak** (§2:
   PM2.5 peaks at 21:00, PM10 at 20:00) points to a real, slower-arriving aerosol
   process inconsistent with an instantaneous sensor fault, or is itself just an
   artefact of whatever produced the PM10 spike (e.g. a shared inlet or shared
   electronics).
3. **Whether the near-total data outages at DEB-KER06 and DEB-KER08** three hours
   after the peak (§3) are meaningful or coincidental — R02 `COMM_GAP` fires 939
   times network-wide over 30 days, so isolated station outages are not rare in
   this corpus on their own.
4. **Whether DEB-KER06/CO is the right second case to feature** (§8) given it
   never received a real propagation test (calm at the source station) — versus
   featuring a different, further-down-the-ranking event that did get tested, or
   presenting this one explicitly as "the pipeline's next-ranked event happens to
   be one it could not test," which is a different and arguably more honest demo
   beat than presenting a second corroborated verdict.
5. **How to present §6's learned-vs-analytic contrast on stage** without
   implying either path is "more correct" — standing rule 4 forbids a headline
   accuracy number for the adjudicator, and the phase-6 report is explicit that
   the analytic path is the demo default, not a worse alternative to the learned
   one. The two priors reach the same verdict here by agreeing that none of the
   five downwind neighbours moved, while disagreeing almost completely on how
   much they *should* have moved (hundreds-to-thousands of µg/m³ under the
   analytic plume prior vs. a near-zero calibrated band under the trained
   model) — which of those two expectations is the more physically trustworthy
   one is not something either code path or this document decides.
6. **Whether the complete absence of an R15 detector and of any
   maintenance/calibration data source** (§7) should read as "nothing to find"
   or "un-checkable" — this document deliberately reports it as the latter and
   goes no further.
7. **What, if anything, changes about all of the above** once a real HST-GAT
   forecast (not the analytic prior) is asked the same question — §6's numbers,
   not this document, are the answer to that, and even they are explicitly a
   research contrast, not a tie-breaker.

No verdict, headline framing, or demo narration is written here or implied by the
ordering of sections above. That is reserved for the person reading this
document, per the brief: their decision becomes `ker11-4100-evidence-v1.1.md`.
