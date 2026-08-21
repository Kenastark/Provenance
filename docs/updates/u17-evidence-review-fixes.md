# Update 17 — ten Evidence-tab fixes from a real-drop review, plus one crash

Branch: `update-17-evidence-review-fixes`. Tag: `v1.0.18-update`.

## What was built

A user review of the Evidence tab against the real `DEB-KER03 · CO2` defect (the
same one update-16 fixed the residual card for) raised ten items. Each was
investigated against the real drop before touching code; nine were real, one
("info" severity) was confirmed as-designed. Fixing the attention card's real
data also flipped a previously-optional crash into a near-certain one, caught by
this update's own live verification and fixed in the same pass.

### 1. SHAP explaining a defect weather has nothing to do with

`explain_defect` (`explain/service.py`) ran the weather-SHAP explanation for
*any* defect whose pollutant is deweather-covered, regardless of reason code.
R07-R09 (physical-bound violations) legitimately benefit from this - "how far is
this from what weather predicts" is itself informative for a magnitude anomaly,
and that design is deliberate and already tested
(`test_explain_api.py::test_explain_is_model_backed_when_artefacts_present`,
comment: "the impossible PM10 reading is classed by rule, not the ML
(precedence)"). R10 (declared-unit mismatch) and R11 (detection-limit floor) are
different: they flag the reading's *metadata*, not its magnitude. Confirmed
against the live API: `DEB-KER03`'s R10/CO2 defect had residual 1.8 against an
actual of 771 - weather explains it almost perfectly, because there is nothing
physically wrong with the number, only its declared unit. Showing "driven
primarily by the boundary layer, humidity..." for that is a non-sequitur that
looks like an explanation but explains a different question.

- New `_METADATA_ONLY_CODES = {"R10", "R11"}` in `explain/service.py`: these two
  now always take the `method="rule"` path with a specific note, never the model
  path, independent of pollutant coverage.
- `tests/unit/test_explain_service.py` (new): pins R10 and R11 to `method="rule"`
  with `shap is None`, and separately pins R07 to `method="model"` with
  `shap is not None` - a direct regression guard that the existing design for
  magnitude anomalies is untouched.
- Verified against `tests/integration/test_explain_api.py` (unchanged, still
  green) and live: `GET /v1/explain/6809` (the real `DEB-KER03` R10/CO2 defect)
  before this fix returned `method: model`; after, `method: rule`, `fault_class:
  unit_inconsistency`, and the note "R10 flags the reading's declared unit or
  detection limit, not its magnitude; weather does not explain that, so the
  deterministic reason is shown instead of a model attribution."

### 2-3. The network-wide CO2 finding, and attention's parameter mismatch

Both re-confirmed but **not built**: the user's FLAGS list for this session
covered items 1 and 4-10 explicitly; items 2 (surface the network-wide CO2
finding somewhere aggregate) and 3 (a visual cue when the attention card's
target parameter doesn't match the viewed defect's) were flagged in the prior
turn's review but not included in this session's action list. Left alone,
noted here so they aren't lost.

### 4. The wrongly-labelled degraded-SHAP text

`ShapAttribution`'s degraded branch used
`` `...(${data.fault_class ?? "physical"})...` `` - a hardcoded filler word for
whenever `fault_class` is `null`. This is wrong for anything that isn't a
physical-bound code: the real case that exercises it is a non-deweather-covered
parameter (e.g. `Wind_Speed`, R12 frozen-sensor) hitting the `method="rule"`
pollutant-not-covered path, where `(physical)` is simply false. Now uses
`data.notes?.[0]` - the backend already computes a specific, accurate note for
every rule path (both the pre-existing "not covered by the deweather model" one
and the new metadata-only one from item 1); the frontend just wasn't reading it.
New fixture `explainRuleFallback` and test in `EvidencePanel.test.tsx`.

### 5. The SHAP bar overflow

`ShapBars` computed each bar's width as `(|value| / maxAbs) * 100%`, then
positioned it with `marginLeft: 50%` (positive) or `calc(50% - width)`
(negative) - drawn from a centreline that only owns half the track each side.
The largest attribution (ratio 1.0) produced a 100%-wide bar starting at the
50% mark, i.e. a box needing 150% of the row's second grid column, overflowing
the card's right edge and (per the user's screenshot) pushing the label column
out of view to the left. Halved the width formula (`* 50`, not `* 100`).
New assertion in the existing "populates the SHAP slot..." test: the widest bar
(boundary_layer_proxy, -6.2 of a 6.2 max) must render at exactly `width: 50%`.

### 6. Graph attention: cap, label width, and weight text

Three related asks, one component. `GraphAttention` (`EvidencePanel.tsx`):

- Capped the edge list to the strongest 8 (`EDGE_CAP`), mirroring `ShapBars`'
  own top-6 cap - a real station can carry 40+ edges across both relation types
  (confirmed: `DEB-KER03` has 56 touching it), which made the card an unbroken
  wall of near-identical bars. When truncated, an honest
  `data-testid="attention-edges-truncated"` note says "Showing the strongest N
  of M edges..." - the same "truncated, not silent" pattern the defect table's
  own banner already uses.
- Widened the label grid column `10rem -> 14rem` so `→ DEB-KER18
  (wind_conditioned)` renders in full; the old width truncated to
  `wind_condi...` with only a hover tooltip for the rest.
- Added a third grid column with the numeric attention weight
  (`edge.attention.toFixed(3)`) beside the bar, so the value doesn't require
  hovering to read.
- New fixture `attentionOverlayManyEdges` (12 synthetic edges) and test
  asserting exactly 8 list items render plus the "8 of 12" note text.

### 7. Deweather chart legend

`DeweatherChart` already passed `name="raw"`/`name="residual"` to its two
`<Line>`s but never rendered a `<Legend>` to display them - the only line
labelling in the whole chart was the toggle buttons' own text. Added
`<Legend wrapperStyle={{ fontSize: "var(--prov-size-caption)" }} />`, matching
`AdjudicationDetail.tsx`'s existing pattern exactly (same prop, same value);
capitalised the names to "Raw"/"Residual" to match that file's "Expected"-style
casing. New test asserts both legend labels render.

### 8. Sticky evidence header

The `<header>` (Evidence title + Station/Code/Severity filters) scrolled away
with everything else, so a long defect view (raw series, neighbours, SHAP,
deweather, attention) left the station/filter context off-screen by the time an
operator reached the bottom. Made `sticky top-0 z-10`, extended past the panel's
own `p-4` via negative margins so it forms a full-width band with no side gaps,
and given a `border-b` for the "horizontal line" the user pointed at. Verified
live: screenshot after a full-page scroll shows the header pinned with the
neighbours/deweather/attention cards scrolling underneath it.

### 9. Detector-evidence label/value spacing

The `<dl>` used `grid-cols-2` - two equal-width columns spanning the panel's
full width, which is why "declared" (left column) and "µg/m3" (right column)
sat far apart with nothing to string them together, exactly as the user's
screenshot showed. Changed to `grid-cols-[max-content_1fr]` (label sized to its
own content, value fills the rest, closer together) *and* a `border-b` per row
except the last - both of the two options offered, as the user asked for.

### 10. Nearest stations: real distance, not alphabetical

The actual bug behind the user's own visual check. `neighbourIds` filtered
candidate stations by shared coverage, then `.slice(0, 3)` - and
`/v1/stations` orders by `station_id` alphabetically
(`repository.py::list_stations`), so "first 3" was really "first 3
alphabetically", never ranked by anything spatial. Confirmed exactly: for
`DEB-KER03` this produced `DEB-KER01, DEB-KER02, DEB-KER04` (the old
screenshot), while the true 3 nearest by haversine distance are `DEB-KER04`
(3.35 km), `DEB-KER14` (3.68 km), `DEB-KER07` (5.75 km) - precisely the three
the user named from looking at the map.

- Reused `windEdges.ts`'s existing `haversineKm` (already the map's own
  distance kernel) rather than writing a second formula.
- Sorts candidates by distance from the flagged station when it has
  coordinates; falls back to the previous (coverage-filtered, unranked) order
  when it doesn't, so a station without coordinates degrades honestly instead
  of claiming a ranking it can't compute.
- Each neighbour now shows its distance (`distanceKm.toFixed(1)} km`); header
  reads "Nearest stations measuring X" only when the ranking is real, otherwise
  keeps the original "Neighbouring stations measuring X".
- Rewrote the existing frontend test into a precise ordering assertion (was a
  loose `/STA-/` pattern match): given the fixture's real coordinates, STA-01
  (~2.0 km) must sort before STA-02 (~2.4 km) before STA-04 (no coordinates,
  sorts last, shown without a distance).
- Verified live against the real drop: screenshot shows `DEB-KER04 3.4 km`,
  `DEB-KER14 3.7 km`, `DEB-KER07 5.7 km`, in that order.

### The "info" severity: as-designed, not a bug

Checked before touching anything: `ops/severity.py`'s `SEVERITY_WEIGHT`/`HAZARD`
dicts define five rungs - critical/high/medium/low/info - as the shared ordinal
scale the maintenance queue and Alert Centre both key off; the dropdown's list
mirrors it exactly. Queried the real drop: 5 real defects carry `info` severity
(out of ~56,700). Left untouched.

### The crash this update's own verification found

Wiring the attention card to a real trained artefact (this session's item 1,
done alongside these ten) turned a previously-optional crash into a near-certain
one. `GET /v1/graph/attention` had a known, previously-unfixed SIGSEGV risk on
macOS/Homebrew/arm64, flagged (not fixed) in
`docs/updates/u14-train-hstgat-real.md`: torch and scikit-learn each load their
own copy of LLVM's `libomp.dylib`, and the two colliding inside the real OS
thread `run_in_threadpool` spawns for the HST-GAT forward pass SIGSEGVs the
whole API process. Before now, this endpoint was only ever called if an
operator manually toggled the Network Map's "Learned attention" layer; the
attention-card fix means it is now called automatically on every single Evidence
view, immediately turning "possible" into "reliably reproducible" - confirmed by
running this update's own live verification against the real drop, which
crashed the dev API process twice in a row.

- Reproduced directly: `curl .../v1/graph/attention` twice against a freshly
  restarted API - process died both times, no Python traceback (a segfault, not
  a catchable exception), matching u14's diagnosis exactly.
- Confirmed the fix `KMP_DUPLICATE_LIB_OK=TRUE` does *not* prevent (that
  variable is Intel's `iomp5`'s, not LLVM's `libomp`'s - u14 had already found
  this); `OMP_NUM_THREADS=1` does - three repeated calls survived after
  restarting with it set.
- Applied to `Makefile`'s `api` and `api-bg` targets only (`API_ENV :=
  OMP_NUM_THREADS=1`, prefixed onto both uvicorn invocations) - not exported
  Makefile-wide (would also throttle `make check`'s pytest run and any direct
  `prov models train*` CLI invocation for no confirmed benefit there), and not
  `infra/docker/api.Dockerfile` (Debian/glibc's OpenMP runtime, `libgomp`, is a
  different implementation not known to share this exact duplicate-runtime
  failure mode - paying a global single-thread cost in the real deployment
  target without evidence it's needed there felt like the wrong trade).
  `demo`/`demo-real` both already route through `api-bg`, so they inherit the
  fix without a separate change.

## Test gate

**Frontend** (`pnpm test:coverage`): 290 passed (25 files, net +5 over
update-16's 287 - see per-item notes above for which). Coverage 94.75% lines /
84.91% branches / 84.77% functions (gate 80%). `pnpm lint` / `pnpm typecheck`
clean.

**Backend** (`make check`): 686 passed, 2 deselected (+3 for the new
`test_explain_service.py`). Coverage 90.58% (gate 88%). Contract check clean -
`explain_defect`'s routing change touches no response shape, so no regeneration
needed.

**Live verification against the real 16-station drop** (real API, real DB,
`pnpm dev`, headless Chromium via a throwaway Playwright script - no
`chromium-cli` available in this environment): screenshots confirmed all of
items 4-10 rendering correctly, item 1's fixed note text after restarting the
API to pick up the Python change (the first check ran against a stale process
and false-negatived), and the SIGSEGV both before and after the `OMP_NUM_THREADS`
fix.

## Deviations from the prompt

- Items 2 and 3 from the prior turn's flags were not in this session's action
  list and were left alone (see "2-3" above) - not an oversight, the user's own
  message scoped this session to items 1 and 4-10 plus "other" items 6-10 (this
  report's numbering follows the user's, not a renumbering).
- The `OMP_NUM_THREADS=1` fix was not part of the original ask; it was
  discovered during this update's own live-verification pass (wiring the
  attention card to real data made the crash near-certain) and the user was
  asked before it was applied, given it's an infra-level change with a
  performance trade-off, not a UI fix.

## Flag for review

- **`infra/docker/api.Dockerfile` was deliberately left untouched.** If the real
  deployment target ever runs on Apple-Silicon-under-emulation, or if a Linux
  build ever bundles a duplicate OpenMP runtime some other way, the same
  SIGSEGV risk could resurface there with no equivalent fix in place. Worth a
  quick check on that image if it's ever run somewhere other than the CI
  Linux runners this project's e2e suite already uses cleanly.
- Items 2 and 3 (network-wide CO2 finding surfaced as an aggregate callout;
  a visual cue when the attention card's target parameter doesn't match the
  viewed defect) remain open from the prior review, not forgotten.
