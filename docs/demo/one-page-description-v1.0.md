# Provenance — AI Trust Layer for Environmental Data (one page, v1.0)

**Track 2B · DEIK.AI Challenge 2026 · Spoken hook: "Is This Real?"**

## The problem

A number on a screen looks exactly the same whether it is true or broken. Debrecen's
Green Sentinel network reports **149,683 readings over 30 days at ~99.95%
completeness** — by every conventional measure, perfectly healthy. It isn't. Buried in
that "healthy" data are readings that are **present, well-formed, plausible, and
wrong**: sensors frozen on a repeated value, readings pinned at a detection limit,
physically impossible spikes. Completeness and uptime dashboards are blind to all of
it, because nothing is *missing* — it is *wrong*.

## What Provenance is

An operator-facing **second screen** that scores every reading for genuineness. Not a
replacement for the public dashboard — the quality-assurance layer behind it. For each
reading it produces a **trust score that never renders without its component breakdown
and at least one reason code**, so an operator sees not just *what* but *why*.

## How it works (three demo blocks)

1. **The audit (B1).** A deterministic engine flags every defective cell against
   physical bounds and statistical signatures, and reports a defect rate that
   **excludes structural absences** (a sensor a station never carried is a coverage
   fact, not a fault). This ships first and stands alone.
2. **Graph adjudication (B3).** For a suspicious spike, a **wind-conditioned graph**
   asks whether stations *downwind* corroborate it. A real plume propagates; a broken
   sensor stands alone. We report **per-case evidence and calibrated intervals, never a
   headline accuracy figure** — there are too few real corroborated events for such a
   number to mean anything but our own injection process.
3. **Deweathering (B2).** Each series is stripped of the weather-explained component and
   the **residual** is scored, so a temperature inversion isn't mistaken for a fault and
   a real fault isn't excused by a windy afternoon.

A research contribution — a heterogeneous spatio-temporal graph-attention network with
conformal intervals and inspectable attention — sits behind an opt-in flag; the analytic
adjudicator is the shipped default.

## What makes it trustworthy

- **No public alert without a recorded human sign-off** — who, when, what evidence, which
  model version. Enforced by a static call-graph test: no code path reaches a dispatch
  without one.
- **The ML classifier can never override a deterministic physical-impossibility flag.**
- **Graceful degradation:** with a model artefact missing, the statistics layer still
  produces a score and says it is degraded.
- **Determinism:** two runs over the same input produce byte-identical reports.
- **Never a hardcoded number:** the defect rate, the completeness, the event verdict are
  all computed; architecture tests enforce it.

## Operational maturity (phase 7)

A maintenance queue auto-ranked by severity × population exposure; an **Alert Centre
ranked by risk, not certainty** (a genuine high-exposure event outranks a confident
low-exposure sensor fault); a regulator-facing audit-trail export (CSV/JSON/PDF) with a
reproducible **verification hash**; RBAC across four roles; and **two separate
monitoring planes** — infrastructure health (Prometheus) and model drift — because
conflating them would hide the very "looks healthy, isn't" failure this product exists
to catch.

## The one-sentence thesis

**Provenance finds the readings that are present, well-formed, plausible, and wrong —
and explains why — so an operator can answer "is this real?" before the public has to.**
