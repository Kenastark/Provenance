# Provenance — "An AI trust layer for Environmental Sensor Networks." (one page, v1.2)

**Track 2B · DEIK.AI Challenge 2026 · Spoken hook: "Is This Real?"**

Version 1.2. **Supersedes `one-page-description-v1.1-real-data.md`** (untouched, per
standing rule 10). Changed: the product descriptor throughout this document, "AI Trust
Layer for Environmental Data" → **"An AI trust layer for Environmental Sensor
Networks."**, matching `CLAUDE.md`'s updated definition. A wording revision only — every
figure below is unchanged from v1.1; see that file for the completeness/defect-rate
numbers and their derivation.

## The problem

A number on a screen looks exactly the same whether it is true or broken. Debrecen's
Green Sentinel network reports **149,683 readings over 30 days at 100.00% conventional
completeness** — every row it delivered carries a value — and by every conventional
measure it is perfectly healthy. It isn't. Buried in that "healthy" data are readings that
are **present, well-formed, plausible, and wrong**: sensors frozen on a repeated value,
readings pinned at a detection limit, a whole channel recorded in the wrong unit,
physically impossible spikes. Completeness and uptime dashboards are blind to all of it,
because nothing is *missing* — it is *wrong*.

**The measured headline: 29.12% of the 174,583 readings this network owed over thirty days
are absent or defective.** About half of that is data that never arrived; the other half —
**15.40%** of the same denominator — arrived, looks fine, and is wrong. It is spread
across all sixteen stations (every one between 18% and 40% defective), so it is a
condition of the network rather than a faulty box.

## What Provenance is

An operator-facing **second screen** that scores every reading for genuineness. Not a
replacement for the public dashboard — the quality-assurance layer behind it. For each
reading it produces a **trust score that never renders without its component breakdown
and at least one reason code**, so an operator sees not just *what* but *why*.

## How it works (three demo blocks)

1. **The audit (B1).** A deterministic engine flags every defective cell against physical
   bounds and statistical signatures, and reports a defect rate that **excludes structural
   absences** — a sensor a station never carried is a coverage fact, not a fault (3,540
   cells excluded here). It also separates a **network-wide finding** (one mislabelled
   CO2 unit, every station, 10,627 readings) from thousands of independent local faults.
   This ships first and stands alone.
2. **Graph adjudication (B3).** For a suspicious spike, a **wind-conditioned graph** asks
   whether stations *downwind* corroborate it. A real plume propagates; a broken sensor
   stands alone. On the one physical-maximum exceedance in this corpus — 4,100.7 µg/m³ of
   PM10 — all five downwind neighbours stayed flat where a plume should have raised them
   by roughly 2,000 µg/m³, and the system returns **likely fault**. Nine of the ten
   top-ranked events came back **ambiguous and were routed to a human** instead. We report
   **per-case evidence and calibrated intervals, never a headline accuracy figure** —
   there are too few real corroborated events for such a number to mean anything but our
   own injection process.
3. **Deweathering (B2).** Each series is stripped of the weather-explained component and
   the **residual** is scored, so a temperature inversion isn't mistaken for a fault and a
   real fault isn't excused by a windy afternoon.

A research contribution — a heterogeneous spatio-temporal graph-attention network with
conformal intervals and inspectable attention — sits behind an opt-in flag; the analytic
adjudicator is the shipped default.

## What makes it trustworthy

- **No public alert without a recorded human sign-off** — who, when, what evidence, which
  model version. Enforced by a static call-graph test: no code path reaches a dispatch
  without one.
- **The ML classifier can never override a deterministic physical-impossibility flag.**
- **It says when a question does not apply.** An outage has no rise for the wind to carry,
  so it gets a recorded reason, not a guessed verdict and not a blank.
- **Graceful degradation:** with a model artefact missing, the statistics layer still
  produces a score and says it is degraded.
- **Determinism:** two runs over the same input produce byte-identical reports.
- **Never a hardcoded number:** the defect rate, the completeness, the event verdict are
  all computed; architecture tests enforce it. When we found our own pitch material
  quoting a completeness figure that came from test data rather than this network, we
  wrote the correction down rather than quietly restating it.

## Operational maturity (phase 7)

A maintenance queue auto-ranked by severity × population exposure; an **Alert Centre
ranked by risk, not certainty** (a genuine high-exposure event outranks a confident
low-exposure sensor fault); a regulator-facing audit-trail export (CSV/JSON/PDF) with a
reproducible **verification hash**; RBAC across four roles; and **two separate monitoring
planes** — infrastructure health (Prometheus) and model drift — because conflating them
would hide the very "looks healthy, isn't" failure this product exists to catch.

## The one-sentence thesis

**Provenance finds the readings that are present, well-formed, plausible, and wrong —
and explains why — so an operator can answer "is this real?" before the public has to.**
