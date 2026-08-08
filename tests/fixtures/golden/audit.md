# Provenance audit

- Code version: `0.1.0`
- Config hash: `4e82d99631fe8099`
- Data checksum: `0bd9c4dcc414f379`
- Window: 2026-05-01T00:00:00 to 2026-05-14T23:00:00

## Headline

- Readings ingested: **7,041**
- Conventional completeness (non-null share): **100.0000%**
- Grid completeness (observed / covered cells): **99.7591%**
- Defective cells: **1,045** of 7,056 covered
- **Defect rate: 14.8101%**

> defect rate = defective covered cells / covered cells, where a covered cell is one (station, parameter, hour) the station actually measures, and a defective cell is one on which at least one defect-counting reason code fired. Structural absences (sensors a station never carried) are excluded from both the numerator and the denominator.

## Defects by reason code

| Code | Name | Category | Counts toward rate | Count |
| --- | --- | --- | --- | ---: |
| R01 | ROW_ABSENT | structural | yes | 17 |
| R02 | COMM_GAP | structural | yes | 1 |
| R03 | DUPLICATE_TIMESTAMP | structural | yes | 2 |
| R07 | EXCEEDS_PHYSICAL_MAX | physical | yes | 3 |
| R08 | BELOW_PHYSICAL_MIN | physical | yes | 2 |
| R09 | CROSS_PARAM_INVERSION | physical | yes | 4 |
| R10 | UNIT_INCONSISTENT | physical | yes | 336 |
| R11 | DETECTION_LIMIT_FLOOR | physical | yes | 8 |
| R12 | ZERO_VARIANCE | statistical | yes | 336 |
| R13 | LOW_VARIANCE_DEGRADED | statistical | yes | 336 |
| R14 | STEP_CHANGE | statistical | yes | 1 |
| R18 | PARAMETER_ABSENT_STRUCTURAL | coverage | no | 1 |
| R19 | SOURCE_ABSENT | coverage | no | 2 |

## Coverage

| Quantity | Cells |
| --- | ---: |
| Observed | 7,039 |
| Absent (R01) | 17 |
| Covered (observed + absent) | 7,056 |
| Structurally excluded | 1,008 |
| Expected (covered + structural) | 8,064 |

## Structural absences (coverage facts, not defects)

| Station | Parameter | Domain | Code | Excluded cells |
| --- | --- | --- | --- | ---: |
| STA-03 | NO | air | R18 | 336 |
| STA-04 | WaterLevel | water | R19 | 336 |
| STA-04 | WaterTemp | water | R19 | 336 |

## Notable events

| Rank | Code | Station | Parameter | Timestamp | What |
| ---: | --- | --- | --- | --- | --- |
| 1 | R07 | STA-03 | PM10 | 2026-05-01T12:00:00 | Value of 3000.0 µg/m3 exceeds the physical maximum for PM10. |
| 2 | R07 | STA-03 | PM10 | 2026-05-02T12:00:00 | Value of 3000.0 µg/m3 exceeds the physical maximum for PM10. |
| 3 | R07 | STA-03 | PM10 | 2026-05-13T12:00:00 | Value of 3000.0 µg/m3 exceeds the physical maximum for PM10. |
| 4 | R09 | STA-01 | PM2.5 | 2026-05-01T10:00:00 | PM2.5 (24.6077) exceeds PM10 (19.6077), which is physically impossible. |
| 5 | R09 | STA-01 | PM2.5 | 2026-05-03T22:00:00 | PM2.5 (24.6077) exceeds PM10 (19.6077), which is physically impossible. |
| 6 | R09 | STA-01 | PM2.5 | 2026-05-06T10:00:00 | PM2.5 (24.6077) exceeds PM10 (19.6077), which is physically impossible. |
| 7 | R09 | STA-01 | PM2.5 | 2026-05-08T22:00:00 | PM2.5 (24.6077) exceeds PM10 (19.6077), which is physically impossible. |
| 8 | R02 | STA-04 | NO | 2026-05-09T12:00:00 | No readings for 12h - the station stopped transmitting. |
| 9 | R12 | STA-01 | WaterLevel | 2026-05-01T00:00:00 | Reading has not changed for 14d - likely a frozen sensor. |
| 10 | R12 | STA-01 | WaterLevel | 2026-05-01T01:00:00 | Reading has not changed for 14d - likely a frozen sensor. |
| 11 | R12 | STA-01 | WaterLevel | 2026-05-01T02:00:00 | Reading has not changed for 14d - likely a frozen sensor. |
| 12 | R12 | STA-01 | WaterLevel | 2026-05-01T03:00:00 | Reading has not changed for 14d - likely a frozen sensor. |
| 13 | R12 | STA-01 | WaterLevel | 2026-05-01T04:00:00 | Reading has not changed for 14d - likely a frozen sensor. |
| 14 | R14 | STA-02 | NO | 2026-05-01T11:00:00 | The series shifted by 6.798 µg/m3 and did not return. |

## Defects by station

| Station | Defective flags |
| --- | ---: |
| STA-01 | 355 |
| STA-02 | 337 |
| STA-03 | 5 |
| STA-04 | 349 |

## Appendix: thresholds used

```yaml
comm_gap:
  basis: Six consecutive missed hourly transmissions is beyond routine sample loss
    and indicates the station stopped reporting.
  min_consecutive_hours: 6
cross_parameter:
  pm25_le_pm10:
    basis: 'definitional: PM2.5 particles are a subset of PM10 particles'
    enabled: true
    tolerance: 0.0
detection_limit:
  min_consecutive_hours: 6
  parameters:
    'NO':
      basis: 'Confirmed floor: 2413 NO readings sit at exactly 0.7 µg/m3, the instrument
        detection limit.'
      limit: 0.7
      unit: µg/m3
low_variance:
  basis: A sensor with under 10% of its peers' variability is degraded relative to
    the network; a uniformly stable parameter has a low median too, so its normal
    sensors are not flagged.
  degraded_fraction: 0.1
  min_peers: 3
physical_bounds:
  CO:
    basis: ~87 ppm; acute urban CO. Ambient rarely exceeds 10000 µg/m3.
    max: 100000.0
    min: 0.0
    unit: µg/m3
  CO2:
    basis: Ambient CO2 300-2000 ppm; poorly ventilated interiors reach ~5000 ppm.
      Bounds evaluated after unit correction to ppm.
    max: 10000.0
    min: 300.0
    unit: ppm
  Conductivity:
    basis: Fresh groundwater <5 mS/cm; 50 covers brackish contamination without admitting
      sensor faults.
    max: 50.0
    min: 0.0
    unit: mS/cm
  Humidity:
    basis: Relative humidity is a fraction; >100% is physically impossible for a non-supersaturated
      sensor.
    max: 100.0
    min: 0.0
    unit: percent
  LAEQ nappali:
    basis: Ambient LAeq day; 140 dB is the threshold of physical pain / sensor full-scale.
    max: 140.0
    min: 20.0
    unit: dB
  LAEQ éjszakai:
    basis: Ambient LAeq night; same sensor full-scale.
    max: 140.0
    min: 20.0
    unit: dB
  'NO':
    basis: Roadside NO ceiling; left-censored at a detection floor (see detection_limit).
    max: 1000.0
    min: 0.0
    unit: µg/m3
  NO2:
    basis: Acute NO2 ceiling; ambient episodes stay under ~200 µg/m3.
    max: 1000.0
    min: 0.0
    unit: µg/m3
  NOx:
    basis: Sum of NO + NO2 expressed as NO2; roadside ceiling.
    max: 2000.0
    min: 0.0
    unit: µg/m3
  O3:
    basis: Extreme photochemical smog ~600 µg/m3; 1000 is a hard ceiling.
    max: 1000.0
    min: 0.0
    unit: µg/m3
  PM10:
    basis: Extreme Saharan-dust ambient PM10 tops ~1000-1500 µg/m3; 2000 is a hard
      sensor ceiling. The 4100.7 reading at KER11 exceeds it.
    max: 2000.0
    min: 0.0
    unit: µg/m3
  PM2.5:
    basis: PM2.5 is a subset of PM10; worst wildfire-smoke ambient ~1000 µg/m3.
    max: 1000.0
    min: 0.0
    unit: µg/m3
  Pressure:
    basis: Record sea-level pressure extremes are 870-1085 mbar.
    max: 1085.0
    min: 870.0
    unit: mbar
  TVOC:
    basis: Total VOC sensor full-scale for ambient monitoring.
    max: 20000.0
    min: 0.0
    unit: µg/m3
  WaterLevel:
    basis: Depth-to-water for these wells sits 1-14 m; 100 m is a hard ceiling.
    max: 100.0
    min: 0.0
    unit: m
  WaterTemp:
    basis: Shallow groundwater temperature; never near freezing or 40 C in this basin.
    max: 40.0
    min: -5.0
    unit: celsius
  Wind_Direction:
    basis: Compass bearing wraps at 360 degrees.
    max: 360.0
    min: 0.0
    unit: degrees
  Wind_Speed:
    basis: Surface wind; 200 km/h exceeds any Debrecen-basin gust on record.
    max: 200.0
    min: 0.0
    unit: km/h
sensor_dead:
  basis: 672 fifteen-minute intervals is one week of zero throughput on a roadside
    counter that should never be idle that long.
  dead_min_consecutive_intervals: 672
status: calibrated
step_change:
  basis: Montgomery SPC defaults; tuned to flag sustained shifts, not transient spikes.
  cusum_h: 5.0
  cusum_k: 0.5
  ewma_lambda: 0.3
  min_points: 24
unit_inference:
  CO2:
    basis: CO2 in µg/m3 at ambient concentration is ~1.8 g/m3 (>1e6 µg/m3); observed
      values are 3 orders of magnitude too small for the declared unit.
    conversion_note: Values are ppm mislabelled as µg/m3; flagged, not silently converted.
    declared_unit: µg/m3
    inferred_range:
      max: 10000.0
      min: 300.0
    inferred_unit: ppm
version: 1
zero_variance:
  basis: No parameter in this network legitimately holds a bit-identical value for
    a full 24h; genuine sensors resolve at least last-digit noise across a day.
  min_consecutive_hours: 24
```
