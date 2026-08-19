# Prepared answers to the hard questions (v1.0)

Version 1.0. Supersedes nothing; first version.

A good judge will ask exactly the questions the blueprint's own §16 critique raises, and
the ones the standing rules in `CLAUDE.md` exist to defend. These are the prepared
answers — each is backed by code and a test, not a promise.

---

### Q1. "Your propagation validator — what's its accuracy / F1?"

We deliberately **do not report one**, and that is a feature. With this few real
corroborated propagation events, any headline accuracy number would describe our
**synthetic injection process**, not the world (standing rule 4; Never-do #5). Instead we
report **per-case evidence** — the downwind neighbours queried, whether they corroborated,
the wind geometry — and a **calibrated (split-conformal) interval** on the expected excess
at each neighbour. A test fails the build if an accuracy figure is emitted for the
validator. This is the honest answer to §16's "too few events to fit this" critique.

### Q2. "99.95% complete but a ~3% defect rate — is that inconsistent?"

No — they measure different things, and that gap **is the product**. Completeness asks
"is the cell present?"; our defect rate asks "of the present cells, how many are
*wrong*?" A frozen sensor repeating one value is 100% complete and 100% wrong. The two
numbers disagreeing is precisely the "looks healthy, isn't" story.

### Q3. "How do you know you're not inflating the defect rate by counting missing sensors?"

We don't count them, and a test enforces it. A station that never carried a wind sensor
is a **structural absence** — a coverage fact excluded from **both** the numerator and
the denominator and reported separately (standing rule 3; Never-do #3). This is the most
scrutinised number in the pitch, so it is pinned by an architecture test, not left to
discipline.

### Q4. "The ML model is more sophisticated — does it override the physics?"

Never. A deterministic **physical-impossibility flag cannot be overridden** by the ML
fault classifier (Never-do #6). Physics is the floor; the model only adds resolution
above it. The KER11 4,100 µg/m³ reading is flagged T04 deterministically, and no learned
component can un-flag it.

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
constant. The demo can run against the real export or a seeded synthetic corpus; the
numbers differ and the code does not.

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
verification hash** a regulator can diff. The demo scenarios are deterministic and a test
asserts two runs are byte-identical.

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
