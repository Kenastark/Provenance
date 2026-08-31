# Demo script — "Is This Real?" (v1.2)

Version 1.2. **Supersedes `demo-script-v1.1-real-data.md`**, which is left untouched per
standing rule 10. Track 2B, DEIK.AI Challenge 2026. Runtime budget: **7 minutes**.

## What changed from v1.1, and why

Wording only: the cold-open title card's product descriptor, "AI Trust Layer for
Environmental Data" → **"An AI trust layer for Environmental Sensor Networks."**, matching
`CLAUDE.md`'s updated definition. No figure, verdict, or spoken line below the title card
changed — see v1.1 for the real-drop reconciliation
(`docs/updates/u22-headline-reconciliation.md`) that document still covers.

## Numbers in this script

Every figure is a **computed output**, not a slide constant (standing rule 1). The
on-stage story is the **real export**: `data/raw`, checksum `8f8efeedfabdccaa`, 149,683
readings, 16 stations, 18 parameters, 2026-05-21 → 2026-06-19.

Offline fallback is the seeded synthetic corpus; `prov demo rehearse` writes the exact
on-screen numbers. The story is identical, only the digits change, and the script flags
where.

---

## 0:00–0:40 — Cold open (title card)

*Title card: the mark, "An AI trust layer for Environmental Sensor Networks.", the hook
"Is This Real?".*

> "This is the Green Sentinel network — 16 stations and two water points around
> Debrecen. Thirty days, **149,683 readings**. By the standard completeness measure it
> scores **one hundred per cent** — every row this network delivered carries a value.
> By every conventional measure it is perfectly healthy."

*(Beat.)*

> "It isn't. And a number on a screen looks exactly the same whether it is true or
> broken. Provenance is the second screen that scores every reading for whether it is
> **genuine** — present, well-formed, plausible, and still wrong."

**If asked "complete by what measure?"** — answer immediately, do not deflect:

> "Conventional completeness — of the rows delivered, how many carry a value. There is a
> second measure: of the readings this network *should* have produced on its own
> schedule, 85.7% arrived. Both are on the audit report. The gap between them is part of
> what we're about to show you."

`prov demo run --scenario audit-headline` drives this block.

---

## 0:40–3:00 — Block B1: the audit (the headline)

*Dashboard: network map, the Data Quality Monitor, the defect ledger.*

> "Our audit puts the defect rate at **29.1%** — that is 50,843 of the 174,583 readings
> this network owed us over thirty days, each one either missing or wrong."

**Volunteer the split immediately. Do not wait to be asked.**

> "And I want to break that in half for you before you ask me to. About half of it —
> 48.97% — is data that never arrived at all. The other half, **15.4%**, is the
> interesting half: readings that did arrive, are well-formed, are plausible, and are
> wrong. Sensors frozen on a repeated value. Readings pinned at a detection limit.
> Physically impossible spikes. Nothing about those is missing."

Key on-screen figures (real export): the defect ledger by code — R01 `ROW_ABSENT`
24,900 · R12 `ZERO_VARIANCE` 12,194 · R10 `UNIT_INCONSISTENT` 10,627 · R13
`LOW_VARIANCE_DEGRADED` 5,622 · R11 `DETECTION_LIMIT_FLOOR` 2,111.

**Then pre-empt the two objections, in this order.**

*(1) "Is that just one broken sensor?" — point at the by-station panel.)*

> "It isn't one sensor. Every one of the sixteen stations is between **18 and 40 per
> cent** defective. The worst three together account for under a quarter of it. There is
> no station you can remove to make this go away — this is a condition of the network,
> not a faulty box."

*(2) The CO2 finding — point at the network-wide findings row.)*

> "The single biggest contributor is one **mislabelled CO2 unit**, affecting every CO2
> reading at all sixteen stations — 10,627 readings, six points of that 29%. Notice what
> the system does with it: it reports it as **one network-wide finding**, not as 10,627
> separate problems. Distinguishing one systemic fact from many local faults is the
> difference between a ledger and a diagnosis."

> "And one rule we never break: a station that never carried a wind sensor is **not** a
> defect — it is a coverage fact, excluded from both sides of the rate and reported
> separately. 3,540 cells are excluded that way here. Getting that wrong would inflate
> the most scrutinised number in this pitch, so a test enforces it."

*(Point at a structural-exclusion row.)* Transition to B3 on the KER11 spike.

---

## 3:00–5:00 — Block B3: graph adjudication (the KER11 event)

*Dashboard: zoom to DEB-KER11. The wind-conditioned graph overlays.*

> "2 June, 20:00. KER11 reports **4,100.7 µg/m³ of PM10**. That is the **only**
> physical-maximum exceedance in the entire corpus — one cell in 174,583. The station's
> trust score drops from **0.73 to 0.43** across that day and picks up reason code
> **T04**, physical implausibility. That is deterministic, and the ML classifier can
> **never** override it."

> "But is it a real plume or a broken sensor? The number alone can't tell you. So we ask
> the neighbours **downwind**."

**The verdict, as the system actually returns it — `LIKELY_FAULT`, high confidence, and
it does *not* route to review.**

> "The wind that hour was blowing from the south-south-east, toward 333 degrees, at 2.7
> kilometres an hour. Five stations sat downwind and all five carry PM10. If this were a
> real plume, one hour later they should have seen an average excess of about **two
> thousand micrograms**. They saw **nought point one six eight**. Three of the five went
> slightly *down*. The closest any of them came to corroborating was a factor of **five
> hundred** short."

> "So the system returns **likely fault** — and it is not a close call. The corroboration
> score is zero against a threshold of 0.2; the entire margin is available. That verdict
> is byte-identical across runs."

**Contrast — this is the point of the block:**

> "Of the ten top-ranked events, this is the **only one** the system was willing to call.
> The other nine came back **ambiguous** and were routed to a human. Five more had no
> plume question to answer at all — an outage has no rise for the wind to carry — and the
> system says exactly that rather than showing you a blank. It does not label what it
> cannot settle."

> "We report **per-case evidence and a calibrated interval**, never a headline accuracy
> number — with this few real corroborated events, an accuracy figure would describe our
> injection process, not the world. And a reading routed to review can never reach a
> public alert without a recorded human sign-off. That is an ethical commitment we made
> **mechanical**: a test proves no code path reaches a dispatch without one."

*(If the attention overlay is on screen — it is trained on PM10 over this same drop, at
this same hour.)* Narrate it as **which neighbours the model leaned on**, never as
evidence the verdict is more accurate (standing rule 4).

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

> "One more angle we don't demo live: the same graph, pointed at the industrial ring road
> and the transit corridors, is how we weight **risk** by who is exposed — a broken
> reading in a busy corridor outranks the same fault at a rural background site."

---

## 6:40–7:00 — Close

> "A number looks the same whether it's true or broken. Provenance is how an operator
> tells the difference — and has to sign their name before the public ever hears about
> it. *Is this real?* Now you can answer."

*Title card returns.*

---

## Operator runbook (not spoken)

- **Primary:** real export loaded locally, API + dashboard up (`make demo-real`).
- **Fallback 1:** offline synthetic corpus — `make demo-data` then the dashboard; every
  scenario is deterministic. **The B3 block's verdict differs on this corpus** (the
  synthetic top event adjudicates AMBIGUOUS, not LIKELY_FAULT) — say "the system routes
  this one to a human" and keep the contrast beat; do not read the real-drop lines.
- **Fallback 2:** the recorded video and the replay sequences from `make demo-record`
  (`reports/demo/*.json`) — no machine required.
- The basemap is vendored (`scripts/fetch-basemap.sh`); with no tiles the map falls back
  to the token-coloured ground and the demo still runs.
- **Never re-key a number by hand.** Read it from the report or the replay sequence.
