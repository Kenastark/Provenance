# Demo script — "Is This Real?" (v1.0)

Version 1.0. Supersedes nothing; first version.
Track 2B, DEIK.AI Challenge 2026. Runtime budget: **7 minutes**, timed to the second below.

## Numbers in this script

Every figure here is a **computed output**, not a slide constant (standing rule 1).
Two number sets exist and the script says which is on screen:

- **Real export** — the audit run over the real Green Sentinel export (149,683 readings,
  16 land stations + 2 water points, 2026-05-21 → 06-19). These are the figures the
  endorsed trust weights were reviewed against (see
  `docs/trust-score-methodology-v1.2-endorsement.md` and
  `src/provenance/trust/config/trust_weights.yaml`). This is the on-stage story.
- **Offline synthetic corpus** — the 18-station seeded corpus (`prov fixtures make
  --stations 18`), used when the real export cannot be loaded and by CI. `prov demo
  rehearse` writes the exact on-screen numbers for every scenario; the current build
  produces 75,585 readings, a 2.906% defect rate, and routes its top event to review.

If conference wifi and the real export are both unavailable, run
`prov demo run --scenario <name>` — it is deterministic and fully offline (basemap
tiles are vendored for the Debrecen bbox). The story below is identical; only the
digits change, and the script flags where.

---

## 0:00–0:40 — Cold open (title card)

*Title card: the mark, the product line "AI Trust Layer for Environmental Data", the
spoken hook "Is This Real?".*

> "This is the Green Sentinel network — 16 stations and two water points around
> Debrecen. Thirty days, **149,683 readings**, **99.95% complete**. By every
> conventional measure this network is perfectly healthy."

*(Beat. Switch to the defect-rate reveal.)*

> "It isn't. And a number on a screen looks exactly the same whether it is true or
> broken. Provenance is the second screen that scores every reading for whether it is
> **genuine** — present, well-formed, plausible, and still wrong."

`prov demo run --scenario audit-headline` drives this block.

---

## 0:40–3:00 — Block B1: the audit (the headline)

*Dashboard: network map, the Data Quality Monitor, the defect ledger.*

> "Conventional completeness says 99.95%. Our audit says something the completeness
> number cannot: of the cells that are **present**, a real fraction are defective —
> frozen sensors repeating the same value, readings pinned at a detection limit,
> physically impossible spikes. On the real export that is **12,194 frozen-sensor
> flags across 13 stations** (code R12) and **2,111 detection-limit flags** on NO
> (R11) — none of them missing data, all of them wrong."

Key on-screen figures (real export): defect ledger by code; the frozen-sensor and
detection-limit counts above. *(Offline corpus: 2.906% defect rate, top codes R10/R12/R13
at 720 flags each — say "roughly three percent" and move on.)*

> "One rule we never break: a station that never carried a wind sensor is **not** a
> defect — it is a coverage fact, excluded from both sides of the rate and reported
> separately. Getting that wrong would inflate the most scrutinised number in this
> pitch, so a test enforces it."

*(Point at a structural-exclusion row.)* Transition to B3 on the KER11 spike.

---

## 3:00–5:00 — Block B3: graph adjudication (the KER11 event)

*Dashboard: zoom to DEB-KER11 (Petőfi tér). The wind-conditioned graph overlays.*

> "2 June, 20:00. KER11 reports **4,100.7 µg/m³ of PM10** — an order of magnitude
> over anything around it. The trust score for that reading drops from **0.577 to
> 0.275** the moment it lands: PhysicalPlausibility goes to zero, reason code **T04**.
> That is deterministic and the ML classifier can **never** override it."

> "But is it a real plume or a broken sensor? The number alone can't tell you. So we
> ask the neighbours **downwind**. Provenance builds a wind-conditioned graph and looks
> for corroboration along the direction the air was actually travelling."

**The verdict, as the system actually returns it:** there is no downwind corroboration
for a physically impossible magnitude, so the adjudicator returns **AMBIGUOUS** and
**routes the event to human review** — it does not guess, and it does not silently call
it genuine. *(Offline corpus: the analogous top event, STA-03 at ~3,000 µg/m³, likewise
adjudicates AMBIGUOUS with zero usable downwind neighbours — the same honest outcome.)*

> "This is the important part. We report **per-case evidence and a calibrated interval**,
> never a headline accuracy number — with this few real corroborated events, an accuracy
> figure would describe our injection process, not the world. And a reading routed to
> review can never reach a public alert without a recorded human sign-off. That is an
> ethical commitment we made **mechanical**: a test proves no code path reaches a
> dispatch without one."

---

## 5:00–6:40 — Block B2: deweathering (separating weather from fault)

*Dashboard: a station's raw PM series, then the deweathered residual.*

> "Not every anomaly is a fault, and not every calm reading is fine. A cold, still night
> traps pollution; a windy afternoon scours it. If you don't remove the weather, you
> chase ghosts. Provenance deweathers each series — strips the weather-explained part —
> and scores the **residual**. The suspicious spike that was really just a temperature
> inversion falls away; the genuine fault stays lit."

> "Every score you've seen carries its **component breakdown and at least one reason
> code** — that is what separates a trust layer from a black box that says 'trust me'.
> And if a model artefact is missing, the system still scores from the statistics layer
> and **says so**. It degrades; it never goes dark."

*(20-second closing slide — no live query.)*

> "One more angle we don't demo live: the same graph, pointed at the industrial ring
> road and the transit corridors, is how we weight **risk** by who is exposed — a broken
> reading in a busy corridor outranks the same fault at a rural background site."

---

## 6:40–7:00 — Close

> "A number looks the same whether it's true or broken. Provenance is how an operator
> tells the difference — and has to sign their name before the public ever hears about
> it. *Is this real?* Now you can answer."

*Title card returns.*

---

## Operator runbook (not spoken)

- **Primary:** real export loaded locally, API + dashboard up (`make demo`).
- **Fallback 1:** offline synthetic corpus — `make demo-data` then the dashboard; every
  scenario is deterministic.
- **Fallback 2:** the recorded video and the replay sequences from `make demo-record`
  (`reports/demo/*.json`) — no machine required.
- The basemap is vendored (`scripts/fetch-basemap.sh`); with no tiles the map falls back
  to the token-coloured ground and the demo still runs.
