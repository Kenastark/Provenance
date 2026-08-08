# Trust Score methodology — v1.2 (weight endorsement)

**Status:** Current. **Supersedes** `trust-score-methodology-v1.1-invariants-and-series.md`.
**Scope:** Unchanged — the phase-2 statistics-only Trust Score. This revision records
one governance change: the v1 weights are now **endorsed**, and it carries the
evidence and the caveat behind that endorsement. The score's definition, components,
and constants are exactly as in v1.1.

## The weights are endorsed (not yet fitted)

v1.1 said the elicited weights "still need a domain-expert sign-off." They now have
one: `trust_weights.yaml` carries `status: endorsed`, `endorsed_by: project lead`,
`endorsed_on: 2026-08-08`. **Endorsement is a governance sign-off on the elicited
values for the demo — not a logistic refit.** A refit against labelled events remains
the v2 plan (§7.8); there are still no labels.

### Evidence reviewed (on the real export, not fixtures)

The weights were reviewed against the network's documented real events
(149,683 readings, 16 stations, 2026-05-21 .. 06-19):

- **Physical-impossibility event, correctly timed.** DEB-KER11's trust drops from
  **0.577 → 0.275** at the 4100.7 µg/m³ PM10 reading on 2026-06-02 20:00
  (PhysicalPlausibility → 0, code T04) and recovers to ~0.565 once the event leaves
  the 7-day window. This is the load-bearing demonstration that the weights flag a
  known real fault — and that the flag lives in the **series**, at the event's own
  time, not in the window-end snapshot.
- **Frozen sensors** reproduce (R12: 12,194 flags across 13 stations) and depress
  HealthConf on the affected series.
- **NO detection-limit floor** reproduces (R11: 2,111 flags).

### Caveat recorded with the endorsement

The **point-in-time distribution is pessimistic and compressed** on real data: all
16 stations sit in ~0.26–0.58 at the window end. That is because the network really
does carry pervasive frozen sensors and cross-sensor disagreement — which is exactly
the product's thesis ("looks healthy, isn't") — but it means:

1. **Discrimination lives in the trajectory, not the snapshot.** Present the trust
   *series* in the demo, not a single number, or the 4100 event is invisible (it is
   17 days before the window end, outside the trailing window).
2. **A logistic refit should widen the spread.** The compression is the clearest
   signal that the elicited weights are a floor, not a finished calibration.

This caveat is stored in `trust_weights.yaml → endorsement_caveat` so it travels with
the config, not just this document.

## Related: station zone_type is now populated (curated, provisional)

Not a trust change, but recorded here for completeness because it came out of the same
review. `zone_type` has no source column in the export, so it is populated from
`config/station_zones.yaml` — a **curated, provisional** classification of the 16
stations into urban/suburban/industrial/background, reasoned from site names and
coordinates, each row carrying a rationale and confidence. It is human curation, not a
measurement, is marked `status: provisional`, and needs municipal/expert confirmation
before it drives anything beyond display. It does not touch the trust score, the
defect rate, or any physical detector.

## Unchanged from v1.1 / v1.0

The score, components, weight magnitudes, ImputationUncertainty placeholder, reason
codes, Risk (with stubbed PopulationExposure), the daily scoring series, the pinned
invariants, and graceful degradation are all as previously described. Read v1.1 and
v1.0 for those; this file records only the endorsement and its caveat.
