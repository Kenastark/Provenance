# KER11 ~4,100 µg/m³ PM10 — verdict and demo narration (v1.1)

**Adds to:** `docs/adjudications/ker11-4100-evidence-v1.0.md`. v1.0 remains the
complete evidence record and is unchanged — every number, table, and command in
it stands. This document adds the one thing v1.0 deliberately withheld: a
verdict, answers to its "What I did not decide" section, and suggested demo
narration. Per standing rule 10, this is a new file, not an edit to v1.0.

**Decision record:** proposed by Claude Code as an analytical recommendation
drawn from the v1.0 evidence, reviewed and adopted as the operative decision by
Ikenna Udeani on 2026-08-21. Recorded here as adopted, not as an independently
authored verdict — the reasoning below is Claude Code's; the sign-off is
Ikenna's.

---

## The verdict

**LIKELY_FAULT stands, with a specific reading:** the 4,100.7 µg/m³ value is not
a credible measurement — regardless of anything else, it exceeds the network's
own documented hard physical ceiling for PM10 (2,000 µg/m³, v1.0 §1/§5) — but
the surrounding shape (a real one-hour build-up beforehand, a four-hour decay
afterward, and PM2.5 echoing a smaller version one hour later, v1.0 §2) is not
consistent with an instantaneous, context-free glitch either.

The recommended framing for the demo: **something localized very likely
happened at that corner of the city, and the sensor's response to it was not a
valid measurement.** Not "random malfunction," not "a real citywide plume" —
a real local trigger, an invalid reading.

What decides this, in order of weight:

1. The value is physically impossible for the instrument, full stop (v1.0 §1).
   This alone means the number 4,100.7 cannot be reported as a genuine ambient
   reading, independent of every other consideration below.
2. Zero response at any of the five wind-aligned downwind neighbours, **and**
   zero response at the nearest station overall by raw distance (1.39 km,
   v1.0 §3/§5). A real event large enough to produce this value would be
   expected to leave *some* trace somewhere nearby; none exists.
3. The build-up/decay shape and the delayed PM2.5 echo (v1.0 §2) argue against
   calling it a context-free, single-instant glitch — there is a real physical
   process visible in the surrounding hours, even though the peak reading
   itself is not trustworthy.

---

## Resolution of v1.0 §9's seven open questions

### 1. Is "confidence 1.00 (high)" trustworthy, given the calm/incoherent wind field?

**Decision: keep the LIKELY_FAULT call, but do not cite "100% confidence" in the
demo narration.** The confidence number is real (it is what the adjudicator's
own formula produces from zero corroboration), but it does not account for the
wind data's own quality that hour, so it should not be the headline fact on
stage. The headline fact is the flat response at every neighbour, which holds
regardless of the wind-quality caveat.

### 2. Does PM2.5's one-hour-delayed, smaller echo of the PM10 peak matter?

**Decision: recorded as part of the reasoning for "a real local trigger,"
not treated as evidence the reading itself is genuine, and not separately
featured on stage.** It supports "something happened" more than it supports
"the number is trustworthy" — those are different claims, and only the first
one is what this fact can carry.

### 3. Do the near-total outages at DEB-KER06 and DEB-KER08, three hours later, matter?

**Decision: coincidental, excluded from the demo narrative.** They occur three
hours after the event decayed away, and outages of this kind are routine
background noise in this network (939 network-wide over 30 days per v1.0 §1).

### 4. Is DEB-KER06/CO the right second case to feature, given it was never actually tested?

**Decision: keep it as the demo's second case, but change what it demonstrates.**
It is not "a second confirmed fault" — the wind was dead calm at the source
station, so the adjudicator never got to test it either way. Reframed, it is a
demonstration that the system declines to guess when it lacks the evidence to
judge, which is arguably a stronger point about the product than a second
corroborated verdict would have been.

### 5. How should the learned-path (HST-GAT) contrast be presented?

**Decision: footnote, not a pillar of the argument.** Both paths agree nothing
downwind moved; they disagree almost completely on how much movement *should*
have occurred. That disagreement is reported honestly (as v1.0 §6 already
does) rather than presented as the learned model "confirming" the analytic
verdict on deeper grounds — it agrees on the outcome, not on the physics.

### 6. Does the absence of an R15 detector and of any maintenance/calibration data source mean "nothing to find" or "un-checkable"?

**Decision: "un-checkable," and the narration says so plainly.** There is no
calibration-epoch detector implemented and no maintenance-window data source
anywhere in this drop (v1.0 §7). The correct claim is "we could not rule out a
calibration or maintenance event — the data to check for one does not exist,"
not "we checked and found nothing."

### 7. Does the trained HST-GAT change any of the above?

**Decision: no.** It reaches the same bottom line by different reasoning
(question 5). It does not tip the verdict either way and is not treated as a
tie-breaker.

---

## Suggested demo narration

For the stage script. Deliberately does not cite the adjudicator's confidence
number or any headline accuracy figure (standing rule 4), and every claim below
is traceable to a specific section of v1.0.

> "At 8pm on June 2nd, the KER11 station reported a PM10 reading of 4,100
> micrograms per cubic meter — more than double what this sensor is physically
> capable of measuring correctly. That number on its own tells us the reading
> can't be trusted at face value. But it didn't come out of nowhere: PM10 had
> already started climbing the hour before, and the fine-particle channel
> echoed a smaller version of the same rise an hour after. Something local was
> very likely happening at that corner of the city.
>
> What we can say with more confidence is what *didn't* happen. Not one of the
> five stations we'd expect to catch a real plume from that spot — including
> one just over a kilometre away — showed any response at all. A pollution
> event large enough to produce a reading like this would leave a trace
> somewhere nearby. It left none.
>
> An impossible number, a real-looking build-up and decay, and total silence
> from every neighbour: that combination is why we're calling this a sensor
> fault — most likely triggered by something real nearby, rather than either a
> clean instrument glitch or a genuine citywide pollution event. And to be
> fully honest with you: we can't rule out a calibration or maintenance event
> either, because that data doesn't exist yet for this network."

> "Our second example, from a different station two weeks later, shows the
> other side of this. The wind was completely still at that station that
> hour, so there was nothing to check its reading against. Rather than force
> a guess, the system flags it for a human instead. That's the point of a
> trust layer: not just catching what's wrong, but being honest about what it
> can't yet tell you."

---

## What this document does not change

v1.0's evidence, commands, and numbers are untouched. This verdict is scoped to
the demo narrative for the B3 block; it is not a claim entered anywhere in the
codebase, a test, or an alert — no source file changed to produce this
document, and nothing here overrides the deterministic R07 physical-max flag
that any future run of this pipeline would still raise on its own (standing
rule 6: a learned model must never override a deterministic physical-
impossibility flag, and none does here).
