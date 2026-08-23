# Prepared answers to the hard questions (v1.1)

Version 1.1. **Supersedes `judge-questions-v1.0.md`**, which is left untouched per
standing rule 10.

## What changed from v1.0

v1.0 was written against the synthetic corpus. Its **Q2 answer was factually wrong for
the real drop** and would have collapsed under one follow-up question. Q2 is rewritten;
Q3, Q4 and Q6 are tightened with measured figures; four new questions (Q14–Q17) are
added for the objections `docs/updates/u22-headline-reconciliation.md` identified. The
rest are unchanged and still correct.

> **v1.0's Q2 said:** ~~"Completeness asks 'is the cell present?'; our defect rate asks
> 'of the present cells, how many are *wrong*?'"~~ — This is **not** what the defect rate
> measures. The rate's numerator includes 24,900 `ROW_ABSENT` cells, which are 48.97% of
> it. The old answer denied that, and a judge who read the audit report would have caught
> it. Corrected below.

All figures: real export, checksum `8f8efeedfabdccaa`, 149,683 readings, 16 stations,
30 days.

---

### Q1. "Your propagation validator — what's its accuracy / F1?"

We deliberately **do not report one**, and that is a feature. With this few real
corroborated propagation events, any headline accuracy number would describe our
**synthetic injection process**, not the world (standing rule 4; Never-do #5). Instead we
report **per-case evidence** — the downwind neighbours queried, whether they corroborated,
the wind geometry — and a **calibrated (split-conformal) interval** on the expected excess
at each neighbour. A test fails the build if an accuracy figure is emitted for the
validator. This is the honest answer to §16's "too few events to fit this" critique.

### Q2. "100% complete but a 29% defect rate — is that inconsistent?" *(rewritten)*

**No, because they use different denominators, and I'll give you both.**

Conventional completeness is **100.0000%**: of the 149,683 rows this network delivered,
every one carries a value. That is the measure Green Sentinel itself reports, and the
network passes it perfectly.

Our defect rate is **29.1225%**, and its denominator is different: **174,583** — the
readings the network *should* have produced over thirty days, reindexing each series at
its own measured cadence. 50,843 of those are either absent or defective.

They are not in tension because one counts delivered rows and the other counts owed
readings. And there is a second completeness figure on the same denominator as the defect
rate: **grid completeness, 85.7374%**. On that denominator the two numbers are the same
fact seen twice — the 14.26% that never arrived is exactly the `ROW_ABSENT` share of the
defect rate.

### Q3. "How do you know you're not inflating the defect rate by counting missing sensors?"

We don't count them, and a test enforces it. A station that never carried a wind sensor
is a **structural absence** — a coverage fact excluded from **both** the numerator and
the denominator and reported separately (standing rule 3; Never-do #3). In this drop that
is **3,540 cells** across five (station, parameter) pairs: one station with no wind
sensors, one with no groundwater file. They appear in the report under their own heading
with their own reason codes (R18, R19), and they are in neither side of the ratio. This is
the most scrutinised number in the pitch, so it is pinned by an architecture test, not
left to discipline.

### Q4. "The ML model is more sophisticated — does it override the physics?"

Never. A deterministic **physical-impossibility flag cannot be overridden** by the ML
fault classifier (Never-do #6). Physics is the floor; the model only adds resolution
above it. The KER11 4,100.7 µg/m³ reading is flagged **R07** by the audit and **T04** by
the trust engine, deterministically, and no learned component can un-flag it. It is the
only physical-maximum exceedance in all 174,583 covered cells.

### Q5. "Could a wrong alert reach the public?"

Not without a **recorded human sign-off** — who signed, when, the exact evidence hash they
saw, and the model version behind the call (standing rule 5; Never-do #8). This is not a
policy in a README: a **static call-graph test** proves no code path reaches a dispatch
function without a valid, non-expired sign-off, and dispatch is idempotent on
`(event, channel, sign-off)` so a retry never double-sends. Ambiguous events route to
human review rather than auto-dispatching.

### Q6. "Are these real numbers, or did you hardcode them for the demo?"

Every figure — the defect rate, the completeness, the KER11 verdict, the ~4,100 µg/m³
event — is a **computed output** with a code path that derives it from a dataset
(standing rule 1; Never-do #1). Architecture tests fail the build on a data-derived
constant. There is exactly one definition of the defect rate in the codebase and every
report renders that definition next to the number.

We can also show you the receipts on this one: `docs/updates/u22-headline-reconciliation.md`
traces 29.1225% to the three functions that produce it, states the numerator and
denominator as absolute integers, and re-runs the command. It also records a figure we
got **wrong** — an earlier version of our own material quoted 99.95% completeness, which
turned out to be the synthetic corpus's number, not this network's. We found it, wrote it
down, and corrected it rather than quietly dropping it.

### Q7. "How did you validate on a time series — random cross-validation?"

Never random K-fold on a time series (Never-do #7). All splits are **time-blocked**, so
the model is never scored on its own future. The trust weights themselves are **elicited
and endorsed, not fitted** — the file says so — pending a logistic refit once labelled
events exist.

### Q8. "It's a nice demo — what happens when a model file is missing in production?"

It **degrades gracefully and says so** (standing rule 6). The statistics layer always
produces a trust score without any model artefact; the response carries `degraded: true`
and the reason. The system never goes dark and never pretends a missing model is a
healthy one.

### Q9. "Can I trust a single trust number?"

You never get a single number. A score **cannot render without its component breakdown
and at least one reason code** (standing rule 9; Never-do #4) — that invariant lives in
the value object, so no path (API, CLI, storage) can emit a bare score. That is exactly
what separates a trust layer from a black box that says "trust me".

### Q10. "You've invented field names / units to make this work, haven't you?"

No. If the real schema is unknown we **read it from the file at runtime and fail loudly on
mismatch** (standing rule 2; Never-do #2). Assumptions live in one file
(`schema_assumptions.yaml`), each marked with its status; the ingest adapters raise rather
than invent a column.

### Q11. "Is this reproducible, or will it look different next time?"

Byte-identical. Everything is seeded (standing rule 8); two runs over the same input
produce identical reports, and the regulatory export carries a **reproducible
verification hash** a regulator can diff. We re-ran the KER11 adjudication into two
separate output directories and diffed them: identical, byte for byte.

### Q12. "How is this monitored — how would you even know it's drifting?"

Two **separate planes**, on purpose. Infrastructure health (up, latency, errors) scrapes
Prometheus at `/metrics`; **model drift** (deweathering R², conformal coverage,
fault-classifier confusion, defect-rate drift by station) is a different endpoint and a
different dashboard. Conflating them would hide model drift inside a green service-health
panel — reproducing, internally, the exact failure this product exists to catch.

### Q13. "Why MapLibre, TimescaleDB, an open stack?"

A municipal buyer's story is stronger on an open stack — no per-seat map licence, no
vendor lock on the time-series store. It is a procurement argument as much as a technical
one.

---

## New in v1.1

### Q14. "Half your defect rate is just missing data, isn't it?"

**Yes — 48.97% of it, and we say so before you ask.** 24,900 of the 50,843 defective cells
are `ROW_ABSENT`: readings the network owed and never delivered.

That is a real data-quality defect and it belongs in the rate — an operator who cannot see
a reading is as blind as one seeing a wrong reading. But it is not the interesting half.
Strip it out and the rate is **15.3978%** of the same 174,583 covered cells (17.9593% of
the readings that did arrive). That is the number that carries our actual claim: data that
is present, well-formed, plausible, and wrong.

Anyone can count missing rows. Finding the other 26,882 is the product.

### Q15. "Your biggest defect code is one mislabelled CO2 unit — so it's one problem, not 10,627."

**Both are true, and the system reports both.** R10 `UNIT_INCONSISTENT` fires on 10,627
cells, 100% of them CO2, across all 16 stations, on 100% of CO2 readings. It contributes
6.09 points to the 29.1%.

We count it per reading because the unit of trust is the **reading** — 10,627 CO2 readings
are untrustworthy, and an operator relying on any one of them is misled. But the engine
also emits it as a single **network-wide finding** at fraction 1.0, precisely so nobody
mistakes one systemic fact for 10,627 independent faults. Both views ship; neither is
hidden.

The same shape applies to R11 (2,111 cells, all NO). If you exclude both R01 and R10, the
rate is **9.3199%** — still, in our view, an alarming number for a network reporting
perfect completeness.

### Q16. "Isn't this really about one broken sensor at one station?"

**No, and this is the number I'd point at first.** Across 16 stations the defect rate runs
from **17.69% to 39.96%** — the worst station is 2.26× the best, not 20×. The top three
stations together are **23.65%** of all defects; an even split across sixteen would put
them at 18.75%. Removing the single worst station entirely moves the headline from 29.12%
to 28.36%.

The concentration is by **parameter**, not by station: the top three parameters are 54.11%
of defects, and CO2 is 100% defective everywhere it is measured. That is a channel story,
not a broken-box story, and it is a different and more useful thing for an operator to
know.

### Q17. "The event you demo is PM10 — but PM10 is barely in your defect breakdown."

Correct, and deliberately so. **PM10 is one of the cleanest channels in the network at
2.58% defective.** The KER11 reading is the only physical-maximum exceedance in the entire
corpus — one cell in 174,583.

That is the point of showing it. The headline defect rate is a statistics story about
whole channels; the KER11 event is a single-reading story that statistics alone cannot
settle, which is why it needs the wind graph. If our demo event were in the noisiest
channel we'd have picked an easy one.
