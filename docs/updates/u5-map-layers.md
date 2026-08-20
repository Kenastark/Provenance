# Update 5 — map layers: BusStop and TrafficCounter

Branch: `update-5-map-layers`. Tag: `v1.0.6-update`.

## Step 2 finding: real Enclod coordinates exist in the drop

The prompt's instruction was to check whether real coordinates for the 42 Enclod
counters exist anywhere in the drop, and escalate rather than render placeholders
if they don't. They do exist, and they are not hidden: `schema_assumptions.yaml`
(`enclod_traffic.latitude_column` / `.longitude_column`) and ADR 0005 already
record that the real archive CSV is wide — `time, uuid, nick, lat, lng,
cars_60+, ...` — one row per (counter, 15-minute tick), with `lat`/`lng` carried
on every row. Confirmed directly against the real drop at
`data/raw/enclod_traffic/DKV databases/Enclod archive data/`: reading just
`uuid, nick, lat, lng` from all 17 monthly files (skipping every cumulative
measure column) takes ~1.2s and resolves cleanly to 42 distinct counters, each
with a single stable coordinate across the corpus.

This is a real *location column*, exactly the shape the prompt anticipated as
"real coordinates exist." It is not the same fact as `enclod_traffic.status:
observed` (not `confirmed`) — that status gates the *cumulative-counter parse*
(the vehicle-class differencing ADR 0005 decided but did not implement), which
`io/ingest/enclod.py`'s `read()` still correctly refuses. Coordinates don't need
that parse: `counter_locations()` is a new, narrow function, sibling to
`gtfs.stops_with_route_counts()`, that reads only the four observed columns and
never touches `read()`'s gate. So TrafficCounter ships **enabled** (default off),
not escalated - it is the "if real coordinates exist" branch of the prompt, not
the "leave disabled and escalate" one.

None of this is the same subsystem as `graph/topology.py`'s
`traffic_counter_nodes()`, which places `synthetic-provisional` counter nodes for
the phase-4+ message-passing graph. That module's own docstring already explains
why it's provisional (unconfirmed schema) and is unaffected by this update - it
is a different consumer of "a counter" for a different purpose, and this update
does not touch it. The map only ever draws what `counter_locations()` returns.

## What was built

1. **`GET /v1/reference/bus-stops`** and **`GET /v1/reference/traffic-counters`**
   (new `api/routers/reference.py`), both public-read, both plain `def` (sync,
   FastAPI runs them off-thread) since they do direct file I/O rather than a DB
   query. Each returns `{available: bool, stops|counters: [...]}` — `available:
   false` with an empty list when the source drop is absent, never a silently
   empty list indistinguishable from "loaded, but nothing here" (standing rule
   3). `bus-stops` wraps the existing `gtfs.find_gtfs_bundle` /
   `stops_with_route_counts`; `traffic-counters` wraps the new
   `enclod.counter_locations()`.
2. **`data_raw` is now request-scoped**, not a global settings singleton read at
   call time: `create_app(engine=None, data_raw=None)` takes an optional root
   and stores it on `app.state.data_raw`; a new `get_data_raw` dependency reads
   it per-request. Production still defaults to `get_settings().data_raw`. This
   exists because the reference endpoints hit the filesystem directly, and
   without it every API test would nondeterministically pick up whatever the
   developer's real `data/raw` happens to contain (rule 7) - fixed by pointing
   `api_client` at a freshly-minted empty directory, and `ops_client`/
   `rbac_client` at `_build_ops_db`'s own synthetic GTFS drop, so the bus-stops
   "available" path gets real fixture coverage too.
3. **`enclod.counter_locations()`** (`io/ingest/enclod.py`): reads
   `uuid`/`nick`/`lat`/`lng` from every discovered archive file, coerces and
   drops unparseable coordinates, dedupes to one row per counter. Raises
   `SourceNotReady` when no Enclod files are found, exactly like
   `find_gtfs_bundle` returning `None` - the router turns both into
   `available: false`.
4. **Frontend**: `useBusStops` / `useTrafficCounters` (`api/queries.ts`);
   `resolveMapLayers` (`stationMarkers.ts`) overlays the live `available` answer
   onto the static `MAP_LAYERS` list, so `LayerToggles` never has to know the
   difference between "not built yet" and "no data today" - both render as a
   disabled checkbox with an honest tooltip. `buildBusStopMarkers` /
   `buildTrafficCounterMarkers` are pure mapping functions, same shape as
   `buildStationMarkers`. `ReferenceMarkerLayer` (`MapOverlays.tsx`) renders
   both as small (6px), low-contrast dots in `border-border-strong` /
   `bg-bg-raised` - the neutral token pair, never a `prov-state-*` trust colour,
   so Sentinel Green stays reserved for verified readings.
5. **`data-provenance` on every marker class** (station, bus stop, traffic
   counter), typed as `MarkerProvenance = "measured" | "provisional"`. Stations
   and reference points are always `"measured"` - the map has no code path that
   draws a `"provisional"` point, by construction (`ReferenceMarkerLayer` only
   ever receives real endpoint data). `MapLegend` gained a "Positions" section
   that lists whichever provenance values are actually present among the
   markers currently on screen, derived rather than a fixed two-row list
   (standing rule 1): in practice this is always exactly one row, "Measured
   position — real coordinates," because nothing else can appear.
6. **Visual regression fix found while capturing baselines**: the taller legend
   (new Positions section) pushed its bottom-right corner into MapLibre's own
   `© OpenStreetMap` attribution control, which is fixed to the same corner.
   Measured with a bounding-box probe (`legend.bottom=888` vs `attrib.top=866`
   at `bottom-3`) before assuming a fix; moved the legend to `bottom-7` (48px,
   an existing spacing token) and re-measured clean (`legend.bottom=852` vs
   `attrib.top=866`).

## Test gate

- `make check` (ruff, ruff format, mypy strict, pytest, contract-drift check):
  green. 666 passed, 90.5–90.7% coverage (floor 88%, run twice, both green).
- `make web-lint` (eslint + `tsc --noEmit`): green, no findings.
- `make web-test` (vitest + coverage): green, 225 passed (217 pre-existing + 8
  new: `resolveMapLayers` loading/enabled states, `buildBusStopMarkers` /
  `buildTrafficCounterMarkers`, the disabled-with-honest-tooltip case, the
  enabled-and-drawing-measured-markers case for both layers, and the legend's
  provenance row).
- `make web-contract-check`: green (`schema.d.ts` regenerated via
  `make web-contract`, required fields tightened from `Field(default_factory=list)`
  so the generated types don't carry a spurious `| undefined`).
- Visual baselines regenerated on both platforms and re-verified green
  (`pnpm e2e:update` on darwin, `make web-visual-linux` in the pinned
  `mcr.microsoft.com/playwright:v1.62.1-noble` container, then
  `make web-visual-check`). Only the 4 `map-*` files changed on each platform (8
  total) — see the deviation below re. `station-detail-*` on Linux.
- Manually verified against the **real** local data drop (not just fixtures):
  brought up `make up` + `make demo-data` + `make api-bg`, then curled both
  reference endpoints directly. `bus-stops` correctly reports `available:
  false` (no GTFS bundle at `data/raw/gtfs/`, only `.gitkeep`).
  `traffic-counters` correctly reports `available: true` with all 42 real
  Enclod counters and their real coordinates. Confirmed the TrafficCounter
  toggle is genuinely clickable end-to-end (not just in the mocked test
  harness) and the legend/attribution fix holds in a real browser.

## Deviations from the prompt

- **TrafficCounter ships enabled**, where the prompt's two branches were
  "enabled" (real coordinates exist) vs. "disabled + escalate" (they don't).
  This is not a deviation from the decision rule, but it's worth flagging
  explicitly since the prompt's own framing leaned toward expecting the
  escalate path: see the Step 2 finding section above for the evidence.
- Tightened `ReferenceStopsOut.stops` / `ReferenceCountersOut.counters` from
  `Field(default_factory=list)` to a plain required `list[...]`. Not asked for,
  but the generated TypeScript types otherwise added `stops?: BusStopOut[]`,
  which fights every call site since the router always populates the field.
- **A second, unrelated visual diff surfaced during the Linux capture pass**:
  `station-detail-{dark,light}-chromium-linux.png` came out different because
  trained model artefacts are present on this machine from earlier session
  work (no "Degraded mode" banner, an extra "Parameters" section) - the same
  contamination `u2-nav-spacing.md`, `u3-resizable-panel.md`, and
  `u4-basemap.md` already recorded. Nothing in this update touches the station
  detail panel or the trust-score response shape (confirmed via `git diff
  --stat` against `features/station/` and the trust schemas), so reverted
  those two files to the committed baseline with `git checkout --` rather than
  regenerating them - out of scope for a map-layers update.

## Flag for review

- `counter_locations()` reads all 17 monthly archive files in full (only 4 of
  the 15 columns, but every row) on every call, ~1.2s measured locally. There
  is no caching - each request re-reads the files. Fine for a demo/single-
  operator deployment where the layer is fetched once per page load and cached
  client-side by TanStack Query (`staleTime: Infinity`), but worth a look
  before this becomes a frequently-polled or multi-tenant endpoint.
- `bus-stops` and `traffic-counters` are unpaginated plain lists, unlike
  `/v1/stations`'s `Page[T]` envelope. Deliberate - these are bounded reference
  sets (42 counters; a real Debrecen GTFS feed still isn't three-digit-station
  large) - but it's an inconsistency with the rest of the API surface if a
  future source turns out to be much larger.
