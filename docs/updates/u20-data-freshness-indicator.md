# Update 20 — a whole-network freshness indicator, measured against real time

Branch: `update-20-data-freshness-indicator`. Tag: `v1.0.21-update`.

## What was built

Update 19 fixed the station drawer's "last reading N days ago" so it stopped
drifting against the real wall clock, anchoring it on the dataset's own newest
reading instead. Follow-up question from the user: doesn't that break the
actual point of a freshness display — knowing when a sensor has genuinely
stopped transmitting, measured against *now*?

The answer turned out to be two different, both-legitimate questions that had
collapsed into one measurement:

1. **"Did this station fall behind its peers?"** — relative staleness within
   the network. Anchor-relative is correct here (update 19's fix stands): in
   the currently loaded drop, all 16 stations' last readings are the exact
   same timestamp (`2026-06-19T11:00:00`, confirmed via a live query), so this
   corpus has no genuine per-station staleness variance to show - but if one
   ever did (an R21 dead-sensor case, or a real drop where a sensor died
   early), this is the version that would surface it, since the comparison is
   against what the rest of the network is currently reporting, not an
   arbitrary point.
2. **"Is the pipeline itself live right now?"** — absolute staleness against
   reality. Nothing in the app answered this. Measuring it against the
   dataset's own anchor is circular (a frozen corpus always looks "current"
   relative to itself); it has to be measured against the real clock, and
   showing it per-station would just repeat the same whole-network fact 16
   times with no new information - it belongs once, globally.

Added the second one: `TopBar.tsx` now shows "Data as of 19 Jun 2026, 11:00
UTC (64 days ago)" - `formatTimestamp`/`formatRelative` over
`useWindowState().anchor`, deliberately *not* passing an anchor override to
`formatRelative` (its real-wall-clock default is exactly right here, per the
doc comment update 19 added explaining when to override it and when not to).
Visible on every screen (the header, not buried in one report), since "is the
whole deployment live" is a standing operational fact, not something tied to
whichever screen happens to be open. `data-testid="data-freshness"` for the
new `App.test.tsx` assertion, which pins the fixture's known anchor timestamp
and checks for the relative-time suffix (not an exact "N days ago" string,
since that value is intentionally real-clock-dependent and would go stale in
the test itself otherwise).

No new staleness *threshold* or colour-coded alert state was added - the text
is a plain, neutral caption. Colour-coding "how old is too old" would need a
number derived from the data (per standing rule 1), and no such threshold
exists yet; inventing one unilaterally felt like scope past what was asked.

## Test gate

**Frontend** (`pnpm test:coverage` scope + full suite): 292 passed (up from
291), `pnpm lint` / `pnpm typecheck` clean.

**Live verification**: screenshot of the top bar against the real 16-station
drop confirms "Data as of 19 Jun 2026, 11:00 UTC (64 days ago)" rendering
correctly, distinct from and alongside the per-station "last reading now" the
station drawer shows for the same drop (both correct simultaneously, since
they answer different questions).

## Deviations from the prompt

None - the user was asked which of three options they wanted (add the global
indicator, revert the per-station fix to wall-clock, or leave as-is) via
`AskUserQuestion` given it's a UX fork affecting every station on the map, and
chose the recommended option.

## Flag for review

None.
