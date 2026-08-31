# Changelog

All notable changes to this project are recorded here.
Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]
### Added
- **Sign-in hero visual, seventh pass.** `DEB-KER18` sized down to
  `text-subhead` (half of its previous `text-display-l`); "180 µg/m³" moved
  from amber to the default text colour. Fixed a real misalignment rather
  than the one requested literally: card 1's "Physical Sensor" caption and
  card 2's "Anomalies detection" line looked unrelated but sat 47px apart,
  because the free space every card accumulates (from `mt-auto` pinning its
  pill to the bottom) lands entirely *between the caption and the pill*, not
  distributed above - so pills aligned but captions never did, on any pass
  that touched card content. Fixed at the root: each card's graphic now sits
  in a shared fixed-height zone (`GRAPHIC_ZONE_HEIGHT`, 112px, matching the
  dial) before its caption, so the caption row lines up across all three
  cards regardless of graphic size, with no further per-card tuning needed
  if content changes again. Headline: dropped the trailing period, and
  wrapped the lockup + headline in their own `gap-3` flex column (half of
  the block's `gap-5`) so only the space between them tightened.
- **Sign-in hero visual, sixth pass.** Headers are now just the layer label
  ("LAYER 1" / "LAYER 2" / "OUTPUT"); the descriptive name ("Green Sentinel
  Network" / "Provenance AI Engine" / "Trust Score") moved to the
  sub-header. Card 1's station id and reading moved out of the sub-header
  into the card's centre, both bumped up to `text-display-l`, with the
  reading now in the ambiguous/amber colour rather than the default text
  colour; "Physical Sensor" and "Unverified spike" swapped order (caption
  first, pill pinned to the bottom). Card 2's "HST-GAT model" pill gained
  the same tinted-background treatment the other two cards' pills already
  had. Card 3's reason code and "Human Sign-off" pill swapped order to
  match card 1's new pattern. The eyebrow line above the lockup is now
  "Green Sentinel's Layer 2 AI Verification Engine" (was "Green Sentinel
  Network · Layer 2"). The gap between "Data without trust is just noise."
  and the paragraph beneath it is now `gap-1`, down from the `gap-5` it
  inherited from the rest of the intro block — the two lines are now
  wrapped in their own flex column so only that one gap changed.
- **Sign-in hero visual, fifth pass: header/sub-header hierarchy flipped, and
  the per-card status content restored.** Headers are now bold and larger
  (`text-caption`, up from `text-micro`); sub-headers are now smaller
  (`text-micro`, down from `text-subhead`) — reversing which line reads as
  the more prominent one. Card 1 gets its "Unverified spike" pill back above
  a plain-text (no background) "Physical Sensor" caption. Card 2 gains a
  two-line caption ("Spatial + Wind Adjudication" / "Anomalies detection")
  between the graph and its pill, and its two green nodes are a touch bigger
  (still smaller than the blue centre node). Card 3 gets its `R22 —
  PLUME_CORROBORATED` reason code back below the "Human Sign-off" pill.
  Tightened each card's internal gap to keep all three comfortably within
  their fixed 240px height with the extra content (measured, not eyeballed:
  15-17px of spare room per card).
- **Sign-in hero visual, fourth pass: restructured card text, shrunk the
  cards, aligned the write-up.** Each card now reads header ("LAYER 1: Green
  Sentinel Network" / "LAYER 2: Provenance AI Engine" / "OUTPUT") then
  sub-header (identity: "DEB-KER18" / "Provenance AI Engine" / "Trust Score")
  then its graphic, then a status pill pinned to the card's bottom edge via
  `mt-auto` — so all three headers land on the same line and all three pills
  land on the same line regardless of how tall each card's own graphic is.
  Cards shrank from 320px to 240px square. The write-up paragraph's
  `max-width` now equals the card row's own rendered width
  (`HERO_ROW_WIDTH`, exported from `HeroFlowVisual.tsx`) so both blocks share
  the same left/right edges instead of drifting to different margins. The
  Trust Score dial's fill animation now loops continuously (fill, hold,
  drain, repeat) rather than running once on mount and freezing. Fixed a
  stray em dash in the write-up ("trust scores—ensuring" -> "trust scores,
  ensuring").
- **The sign-in screen now illustrates the Layer 1 -> Layer 2 -> trust score
  flow instead of only describing it in prose.** The headline is now "An AI
  trust layer for Environmental Sensor Networks." (was "AI Trust Layer for
  Environmental Data") on a single line, and the intro copy is a wider,
  shorter-in-height write-up ("Data without trust is just noise." plus one
  paragraph on the HST-GAT model) rather than the previous narrower two-sentence
  block. Below it, a new `HeroFlowVisual.tsx` renders three same-size cards —
  a DEB-KER18 reading flagged unverified (amber), the Layer 2 engine's
  rotated mini graph (a Trust-Blue node among two Sentinel-Green ones), and a
  Trust Score dial that animates its ring from empty up to 98.4% on mount,
  tagged with the registry's real R22 (`PLUME_CORROBORATED`) reason code —
  connected by animated connector lines, entirely in `var(--prov-*)` tokens
  per the brand guardrail. It is `aria-hidden` and decorative: the reading
  and score are a worked example for the graphic, not live data. Also fixed a
  layout bug the first pass introduced: `justify-center` on an overflowing,
  `overflow-y-auto` flex container makes the content *above* centre
  permanently unreachable (a scrollbar can't reach negative offsets) — the
  eyebrow line and lockup were silently clipped off. Switched to `margin:
  auto` centring, which degrades to fully-scrollable top-aligned flow the
  moment content doesn't fit.
- **The product descriptor is renamed everywhere it's quoted**, from "AI
  Trust Layer for Environmental Data" to "An AI trust layer for Environmental
  Sensor Networks." — `CLAUDE.md`, `README.md`, and `ops/demo.py`'s
  title-card tagline updated in place; the three `docs/demo/*-v1.1-real-data.md`
  files that quoted it are superseded by new `*-v1.2-descriptor-rename.md`
  versions (wording only — no figure or verdict changed) per standing rule
  10's "never edit a versioned doc in place."
- **The Timescale-independence claim is now actually tested.** ADR 0012 dropped
  the dependency, but nothing proved the schema runs on an engine *lacking* the
  extension: both local Compose and CI used `timescale/timescaledb-ha:pg16`,
  where `CREATE EXTENSION timescaledb` and `create_hypertable` succeed whether or
  not anyone asked. Two guards close that. CI's `e2e` service is now
  `postgis/postgis:16-3.5`, so the migrations, the loader and the audit run on an
  engine where the extension does not exist. And
  `tests/architecture/test_no_timescale_dependency.py` fails the default gate if
  any migration names `timescaledb`, `create_hypertable` or `time_bucket` - no
  database needed, so it runs everywhere. The round-trip test additionally
  asserts zero hypertables when the extension happens to be present.
- **Trained models are loaded once at startup instead of on every request.**
  `registry.load_bundle_cached()` and `hstgat/store.load_latest_cached()` put a
  module-level cache in front of the existing loaders, and the API's `lifespan`
  warms both before serving traffic, so `/v1/explain` no longer pays a
  `joblib.load` and `/v1/graph/attention` no longer pays a `torch.load` per call.
  Deliberately not `functools.lru_cache`: only a successful load is remembered, so
  a `None` (no artefact yet - a normal state under standing rule 6) is never
  cached and a model trained after the process started is still picked up. The
  warm-up is best-effort: a missing or corrupt artefact logs and degrades exactly
  as before rather than blocking startup.
- **An event with no plume question to answer now says so, instead of reading as
  "pending adjudication" forever.** A stored event whose own cell has no reading
  (a communication outage has no rise for the wind to carry) keeps a null verdict
  but now records **why**, under
  `Event.evidence["adjudication_not_applicable"]`, so the dashboard can tell
  "adjudicated over, does not apply" from "not adjudicated yet" - previously it
  told the operator to run a command they had already run. The reason is derived
  from the frame (is the parameter carried? is there a reading at that
  timestamp?), mirroring `graph/replay.py::build_candidate`'s own two `None`
  paths, never keyed off a reason code. `adjudicate_stored_events` now returns
  `SweepResult(adjudicated, not_applicable)` instead of a bare int, and
  `prov graph adjudicate-db` reports both counts. AMBIGUOUS was deliberately
  **not** reused: it means "we are unsure, route to a human", and an outage is not
  an unsettled call. Frontend: `parseNotApplicable()`, a `not_applicable` verdict
  kind, and a detail pane that states the recorded reason. No API contract change
  (`evidence` was already a free-form map). Known gap: the Alert Centre still
  shows "pending" for such an event, since `AlertItem` carries no `evidence`.

### Fixed
- **The `e2e` job no longer runs out of disk pulling the Playwright image.** A
  free-space step reclaims the hosted runner's unused Android/dotnet/GHC/Swift
  toolchains and prunes Docker before the visual-regression step, which had
  failed twice consecutively on `no space left on device` mid-layer (PR #38) -
  a red job caused by nothing in the diff. Best-effort throughout: the step
  cannot itself fail the job.

### Removed
- **TimescaleDB.** The `timescaledb` extension and the three `create_hypertable`
  calls (`readings`, `trust_scores`, `residuals`) are gone from the migrations;
  the schema is now plain PostgreSQL 16. Nothing used a hypertable feature - no
  continuous aggregate, compression, retention policy or `time_bucket` - and
  managed Postgres (Cloud SQL) does not offer the extension. PostGIS and the
  `geom` generated column on `stations` are untouched. The local Compose `db`
  image stays `timescale/timescaledb-ha:pg16`, a known-good multi-arch pg16 build
  whose extension nothing now enables. See ADR 0012.
- **Redis.** The `cache` service, the `api` service's `depends_on` entry for it,
  the `redis_url` setting and `REDIS_URL` in `.env.example`. It was never wired
  up: no client was imported, nothing read or wrote a cache, and `redis` was not
  a dependency. The caching that was actually wanted is the in-process model
  cache above.

### Changed
- **The sign-in screen now introduces the product instead of opening straight on
  role cards.** The lockup grew from 96px to 152px tall (the wordmark stays the
  fixed SVG asset per the token file's rule - never re-set "Provenance" in a live
  face), and the tagline moved from a 16px secondary line to a 32px
  `text-display-l` headline. A new eyebrow ("Green Sentinel Network · Layer 2")
  and a two-sentence intro frame Provenance explicitly as the second layer over
  Green Sentinel's physical sensor network - Layer 1 reports readings, Layer 2
  audits and scores them - reusing the project's own standing thesis line ("a
  number on a screen looks exactly the same whether it is true or broken")
  rather than inventing new claims. No stats are hardcoded into the copy (rule 1):
  the intro is qualitative only. A subtle radial glow behind the lockup uses a
  single brand blue at low opacity via `color-mix`, not the brand gradient, which
  the token file reserves for the logo mark only.
- **The defect-rate definition string no longer calls every cell an "hour".** 300
  of the 174,583 covered cells in the real drop are daily (the two LAEQ noise
  series); the grid always reindexed each series at its own inferred cadence, but
  `DEFINITION` said "(station, parameter, hour)" and rendered that verbatim into
  `audit.md`, `audit.html` and the `/v1/export` payload. Now "(station, parameter,
  tick) ... that series' own measured cadence, hourly or daily, never assumed",
  pinned by a regression test. The golden `audit.md` snapshot was regenerated:
  exactly one line changed, and no computed number moved (`config_hash` hashes
  YAML, not Python source).
- **The pitch material now uses measured completeness, and the KER11 verdict it
  actually returns.** `CLAUDE.md`'s thesis paragraph drops "roughly 99.95%
  completeness" - which was the *synthetic* corpus's grid completeness - for the
  measured **100.00% conventional** figure, and states both completeness measures
  with their denominators. Four demo documents are revised as new versions per
  standing rule 10 (`demo-script-v1.1-real-data.md`,
  `judge-questions-v1.1-real-data.md`, `one-page-description-v1.1-real-data.md`,
  `video-storyboard-v1.1-real-data.md`; the v1.0 files are untouched). Beyond the
  completeness figure this corrects two real errors found while editing them: the
  script and storyboard stated the **wrong verdict** for the KER11 event
  (AMBIGUOUS/routed to review; it is LIKELY_FAULT and does not route to review),
  and quoted synthetic trust figures (0.577 -> 0.275) where the real stored series
  is 0.7347 -> 0.4308 with T04 appearing. The B1 block now volunteers the R01
  split (48.97% of the headline is data that never arrived) and presents the CO2
  unit finding as one network-wide fact rather than 10,627 independent ones;
  `judge-questions-v1.1` rewrites its Q2 (whose v1.0 answer was factually wrong
  about the rate's own numerator) and adds Q14-Q17. Details:
  `docs/updates/u23-headline-decisions.md`.
- **Headline reconciliation: the defect rate, pinned down to what it is a rate
  *of*, and the KER11 verdict restated as evidence.** Documentation only - no
  detector, threshold, configuration value, or audited number changed. Traces
  29.1225% to its exact code path (`grid/coverage.py::n_covered_cells` ->
  `audit/orchestrator.py::run_audit` -> `grid/defect_rate.py::DefectRate.rate`),
  states numerator (50,843 distinct defective cells) and denominator (174,583
  covered cells = expected-cells-after-reindexing over the 261 covered
  (station, parameter) pairs at each series' own inferred cadence), and answers
  explicitly that the 24,900 R01 `ROW_ABSENT` cells sit on **both** sides of the
  ratio - 48.97% of the headline is missing data, not wrong data. Re-run against
  `data/raw` reproduces 29.1225% exactly. Recomputes completeness from the drop
  (100.0000% conventional, 85.7374% grid) and reports **prominently** that
  neither matches CLAUDE.md's "roughly 99.95%", which is the synthetic corpus's
  grid completeness (99.9518%) - a contradiction first flagged in update 6 and
  still open, escalated rather than resolved. Adds cell-level breakdowns by
  reason code, station and parameter: defects are distributed across stations
  (top three = 23.65%, every station 17.69%-39.96% defective) but concentrated by
  parameter (top three = 54.11%, CO2 100% defective), with four single-parameter
  codes flagged as "your headline is really about one channel" objections. The
  KER11 4,100.7 ug/m3 PM10 `LIKELY_FAULT` verdict is reproduced from both
  `adjudicate-db` and `adjudicate`, traced to the third branch of
  `graph/adjudicate.py::_decide`, and shown to be far from its boundary
  (match_score 0.0 against a 0.2 fault threshold; the closest of five downwind
  neighbours falls 498x short of corroborating), with byte-identical output across
  runs. Confirms the HST-GAT attention overlay describes the same station,
  parameter, hour and data checksum as the verdict. Six decisions escalated,
  including that the "Is This Real?" blueprint v1.0-v1.2 is not in this repo or
  anywhere on this machine, so the requested v1.3 was **not** written rather than
  fabricated. Details: `docs/updates/u22-headline-reconciliation.md`.
- **A real graph-conditioned imputation model (§7.2), replacing the raw
  absent-fraction placeholder in the Trust Score's `ImputationUncertainty` term
  wherever it is trained.** `prov models train-imputation --source <path>` trains
  one HST-GAT-architecture model per parameter with 2+ carrying stations
  (`imputation-<PARAMETER>`, same masked-autoencoder Gaussian-NLL mechanism and
  graph-building code as `train-hstgat`, a separate artefact from the
  fault-adjudication PM10 model), evaluated by held-out RMSE/MAE and split-conformal
  coverage. The trust engine now threads a live per-station/window model inference
  (`provenance.trust.imputation.ImputationLookup`, one graph batch per parameter per
  load, not per station) into `ImputationCertainty`'s value where a model is
  available; the raw absent-fraction figure is kept alongside it (`evidence.pct` vs.
  `evidence.modelled_pct`), never replaced silently. Model selection is scoped to
  the currently-loaded drop's content checksum (`available_imputation_models`,
  a real bug caught during verification: without it, a model trained on one
  corpus silently ran inference against a different one sharing a parameter
  name). New reason code **T06**
  (`TRUST_IMPUTATION_MODELLED`); T02's placeholder path is unchanged for any
  station/parameter without a model. `demo-real` now pre-flights and
  auto-trains-or-skips both HST-GAT and the imputation models (reversing part of
  update 14's "kept as a separate manual step" call, now that a cheap
  checksum/card-existence check removes that trade-off); `demo-real-hstgat` and the
  new `demo-real-imputation` remain as explicit forced-retrain targets. Synthetic
  `make demo`/`demo-data`/`demo-models` still never train anything. Components
  sidebar and station-detail panel show both figures, separately labelled. Details:
  `docs/updates/u21-imputation-uncertainty.md`.
- **A whole-network "Data as of" freshness indicator in the top bar**, measured
  against the real wall clock (`formatTimestamp`/`formatRelative` over
  `useWindowState().anchor`, deliberately not anchor-overridden here). Answers
  a different question than the station drawer's per-station "last reading",
  which stays anchor-relative on purpose (update 19): "is the pipeline itself
  live right now" (whole-network, real-time) versus "did this station fall
  behind its peers" (per-station, relative). Follow-up from update 19, after
  the user asked whether anchoring per-station freshness on the dataset
  defeated the point of detecting a sensor that stopped transmitting - it
  didn't for the per-station case (all 16 stations in the current drop share
  one last-reading timestamp, so there's no per-station variance to lose), but
  exposed a real gap for the whole-deployment-liveness question, which this
  closes. `data-testid="data-freshness"`. Details:
  `docs/updates/u20-data-freshness-indicator.md`.
- **`prov models train-hstgat --skip-if-cached`, and `make demo-real` uses it.**
  The flag computes the current data drop's content checksum and reuses an
  already-trained, card-verified artefact for that exact checksum instead of
  retraining, falling through to a normal train on any mismatch (different
  drop, corrupted artefact, missing card). `demo-real-hstgat` is unchanged
  (always retrains, for a deliberate refresh); `demo-real` now runs
  `train-hstgat --skip-if-cached` automatically after its other model-training
  steps, so a first-time run against a drop trains the HST-GAT once and every
  later re-run against the same drop reuses it - the Attention overlay no
  longer needs a separate, easy-to-forget `make demo-real-hstgat` step to
  become live. New `tests/unit/test_models_cli.py` integration test. Details:
  `docs/updates/u19-network-map-review-fixes.md`.
- **A "Network-wide findings" section on the Audit report**, closing the first of
  update-17's two open items. The audit engine now computes, generically (never a
  hardcoded code or parameter), which (reason_code, parameter) pairs fire on
  *every* station carrying that parameter and on at least `thresholds.yaml`'s new
  `network_wide_finding.min_fraction` (0.95) of that parameter's actual readings -
  a single systemic fact about a whole channel (a mislabelled unit, confirmed:
  R10/CO2 on the real drop, 10,627 of 10,627 readings, all 16 stations) rather
  than thousands of individual per-reading defects. New `AuditResult
  .network_wide_findings` field (`audit/result.py`,
  `audit/orchestrator.py::_network_wide_findings`), a matching section in
  `report/render.py`'s markdown output (golden `audit.md` regenerated), and a new
  panel on `AuditReportView.tsx` linking each finding to its evidence. Explicitly
  excludes absence-pattern codes like R01 (checked generically by set membership
  against the frame's present cells, not a hardcoded code list) - an absent cell
  has no reading to compare against, so "what fraction of readings are flagged"
  does not apply to it; that is a completeness story the coverage summary already
  reports separately. Caught and fixed during this update's own verification
  against the real drop: an earlier version divided by expected-cell counts
  uniformly, which put R01/NOx and R01/NO's defect counts *above* their
  denominators (a nonsensical fraction over 1) - now guarded by a regression test.
  `tests/unit/test_network_wide_findings.py` (5 tests).
- **A visual cue when the attention card's target parameter doesn't match the
  viewed defect's**, closing update-17's second open item.
  `GraphAttention` (`EvidencePanel.tsx`) now checks
  `data.target_parameter !== defect.parameter` and, when they differ, shows an
  amber (`prov-state-degraded`) note - "This overlay is trained to reconstruct
  {target}, not {parameter} - read it as {target} network structure, not evidence
  about this {parameter} reading" - instead of leaving the mismatch to the small
  "target X" caption alone. Only one HST-GAT is ever trained at a time
  (`models.yaml`'s `hstgat.target_parameter`), so this is a real, recurring case,
  not a hypothetical.

### Fixed
- **Seven issues found in a user review of eight Network-map-tab screenshots,
  plus the API's `OMP_NUM_THREADS` crash mitigation hardened beyond the two
  Makefile targets it was previously scoped to.**
  - The per-parameter sparklines in the station drawer (`StationDetailPanel.tsx`)
    didn't resize when the drawer was dragged wider, unlike the trust
    trajectory chart right above them - both use the same `Sparkline`
    component, but only the trajectory chart's call site passed its existing
    `fluid` prop. Added it to the parameter sparklines too, with a `flex-1`
    wrapper so they have a flex-basis to grow into.
  - **The wind overlay's speed always read "0"**: `WIND_SPEED_PARAMETER` was
    exported but never fetched, only `WIND_DIRECTION_PARAMETER` was requested,
    so the speed array was structurally always empty and fell back to its `0`
    default - not a calm reading, a silent missing fetch, masked by the test
    stub mocking `/v1/readings` by path only.
  - **The wind reading was capped at "1 station" by construction**: the fetch
    was scoped to one hardcoded station (`markers[0]?.stationId`) despite an
    adjacent comment claiming network-wide aggregation. `useReadings` gained
    an opt-in `networkWide` flag (existing call sites unaffected); the wind
    overlay now fetches direction and speed network-wide, in a narrow window
    anchored on the dataset's own anchor rather than the operator's selected
    macro time window, to stay well under the API's 200-row page cap.
  - **The wind arrow pointed backwards.** It was drawn at
    `rotate(directionDegrees + 180)` - the reported bearing is the direction
    the wind comes *from* (the same number the adjacent "W"/"278°" text
    shows), and the vane convention points the arrow at that bearing
    directly, not 180° away from it. Removed the inversion.
  - **"Last reading N days ago" drifted further every day the demo sat
    unopened**, comparing the corpus's frozen synthetic timestamps against the
    real wall clock. Both call sites (`StationDetailPanel`, `QualityMonitor`)
    now use `useWindowState().anchor` - the same dataset-anchored "now" the
    time-window selector already uses - instead of `Date.now()`.
  - **The station drawer's Acknowledge/Dispatch buttons wired into the real,
    already-shipped sign-off flow** instead of a browser-local queue with no
    transport and a caption claiming the capability "lands in phase 7" (it
    already had, in the Alert Centre, just never connected here). Resolves an
    `event_id` for the station via `useEvents`, picks the most notable event
    when more than one exists, and renders the same `SignoffPanel` component
    the Alert Centre uses, linking out to it for the full picture. A station
    with no adjudicated event yet says so and links to the Alert Centre rather
    than showing dead buttons. `lib/queue.ts` had no other caller; deleted.
  - The `OMP_NUM_THREADS=1` macOS/arm64 crash mitigation (update-17) covered
    only the `make api`/`api-bg` Makefile targets, leaving the plain `uvicorn`
    command in `docs/api/README.md`, the Docker image, and any IDE run
    config unprotected. `provenance/api/app.py` now sets it itself, as the
    first statement in the module before any router import can pull torch in
    - every way of starting the API is covered now, not just the two targets.
  - Full detail: `docs/updates/u19-network-map-review-fixes.md`.
- **Ten Evidence-tab issues found in a user review of the real `DEB-KER03 · CO2`
  defect, plus one crash the review's own verification surfaced.**
  - `explain_defect` (`explain/service.py`) no longer runs the weather-SHAP
    explanation for R10 (declared-unit mismatch) or R11 (detection-limit floor):
    these flag the reading's *metadata*, not its magnitude, so a residual near zero
    (weather predicts the mislabelled-but-otherwise-ordinary number just fine) would
    make the model look like it "explains" a defect it has nothing to do with. R07-R09
    (genuine physical-bound violations) are unchanged - the existing "impossible
    reading, model-backed context anyway" design stays intact, still pinned by
    `test_explain_api.py`. New `tests/unit/test_explain_service.py`.
  - The SHAP card's rule-decided fallback (`EvidencePanel.tsx`) now shows the
    backend's own `notes[0]` (e.g. "Wind_Speed is not covered by the deweather
    model...") instead of a hardcoded `(physical)` filler that was simply wrong for
    any non-physical rule-decided code (frozen sensor, drift, etc.) - that filler is
    what looked like a missing `fault_class` in the original report.
  - `ShapBars`' bar width was computed up to 100% of the track from a centreline
    that only owns 50% each side, so the largest attribution could run to 150% and
    push the whole label column off-screen. Capped at 50%.
  - `GraphAttention`'s edge list had no cap (a real drop can carry 40+ edges per
    station) and a 10rem label column too narrow for `→ DEB-KER18
    (wind_conditioned)`; capped to the strongest 8 (mirroring `ShapBars`' own top-6,
    with an honest "showing N of M" note when truncated), widened to 14rem, and
    added the numeric weight beside each bar instead of only on hover.
  - `DeweatherChart` gained a `<Legend>` (matching `AdjudicationDetail.tsx`'s
    existing pattern) - the raw/residual lines had no on-chart label at all.
  - The Evidence header (title + Station/Code/Severity filters) is now `sticky`
    with a bottom border, so it stays visible while the rest of the page scrolls.
  - The "Detector evidence" key/value list moved from an even 50/50 grid split
    (which could put a value far from its label on a wide screen) to
    content-sized columns with a divider line per row.
  - **The "neighbouring stations" list was never actually nearest** - it took
    whichever 3 same-parameter stations came first in `/v1/stations`' alphabetical
    order, not by distance. Confirmed against the real drop: for `DEB-KER03` this
    picked `DEB-KER01/02/04` while the true 3 nearest are `DEB-KER04/14/07`
    (3.4/3.7/5.7 km - haversine, reusing `windEdges.ts`'s existing formula). Now
    sorted by real distance when the flagged station has coordinates, each shown
    with its distance; falls back to the previous order otherwise. Header renamed
    "Nearest stations measuring X" when distance-ranked.
  - Severity's "info" option is confirmed by design, not a bug: it's the fifth
    rung of the shared ordinal scale (`ops/severity.py`) and 5 real defects use it.
  - **Wiring the attention card to a real trained artefact (above) made a
    previously-optional crash near-certain.** `GET /v1/graph/attention` SIGSEGVs
    the API process on macOS/Homebrew/arm64 (two conflicting `libomp.dylib` copies
    from torch and scikit-learn colliding inside the real OS thread
    `run_in_threadpool` spawns for the HST-GAT forward pass) - a known, previously
    unfixed risk flagged in update-14, until now only reachable by manually
    toggling the map's attention layer. Reproduced directly (`curl` twice, process
    died both times); `OMP_NUM_THREADS=1` prevents it (`KMP_DUPLICATE_LIB_OK` does
    not - wrong OpenMP implementation). Set for `make api`/`make api-bg` only, not
    the whole Makefile or `infra/docker/api.Dockerfile`'s Linux/glibc image, which
    is not known to share this failure mode.
  - Full detail and live verification (screenshots against the real 16-station
    drop): `docs/updates/u17-evidence-review-fixes.md`.

### Changed
- **The Data Quality Monitor's uptime and last-calibration figures move from the
  frontend into the audit engine.** `QualityMonitor.tsx`'s `buildRows` used to
  compute `1 - (R01 absent cells / expected cells)` and the newest R15
  discontinuity itself, off the `/v1/defects` list - honest, but business logic
  sitting in a presentation layer (flagged in the phase-3 report's flag review).
  `io/db/repository.py::quality_summary` now computes both, windowed by the same
  `start`/`end` `/v1/quality/summary` now accepts as query params (mirroring
  `/v1/defects`); `QualityStationOut` gains `uptime_pct`, `absent_cells`,
  `expected_cells`, `last_calibration_at`. The frontend now only displays what it
  is given. `tests/unit/test_uptime_assumptions.py`'s two pinning tests move to
  naming the repository function instead of the frontend file. Frontend contract
  regenerated; quality-monitor visual baselines regenerated on both platforms.
- **PopulationExposure is now marked provisional wherever it is displayed**, not
  only in `config/graph.yaml`'s own comments. The Alert Centre's Exposure column,
  the alert detail's risk-factor breakdown, and the maintenance queue's "Station
  importance" factor (the same figure, differently named) all gain a "(rel.)"
  label suffix and a tooltip explaining the min-max, relative-to-the-current-drop
  normalisation - a station's exposure factor is not comparable across two
  different networks without renormalising. Also noted in
  `docs/model-cards/propagation-adjudicator-v1.md`. The normalisation method
  itself is unchanged. Alert Centre visual baselines regenerated on both
  platforms.

### Added
- **A sign-in screen in front of the dashboard**, using the same mechanism the
  account menu's dev role switcher already used (`lib/role.tsx`'s
  `setRole`/`canSwitch`) rather than any new authentication. `RoleProvider`
  gains `signedIn`/`signIn`/`signOut`; `SignInGate` (wired into `App.tsx`
  around `AppRoutes`) shows the new `SignInScreen` until a role is chosen —
  four role cards plus a raw-API-key field when `canSwitch` is true, an
  automatic "Signed in as {role}" pass-through when it is false (a pinned
  production key). `TopBar.tsx` gains a "Sign out" action beside the existing
  dev switcher. `RbacMatrix.tsx` now shares its "what does this role grant"
  wording with the new screen via `role.tsx`'s `roleGrants`/`ROLE_HIERARCHY`
  instead of duplicating it. `RequireRole`, `require(Role.X)`, and
  `api/auth.py` are unchanged — this is a presentation layer in front of role
  selection, not a new access boundary. Visual baselines regenerated on both
  platforms (two new: the sign-in screen, dark and light; several existing
  screens re-verified for the Playwright storage-state seeding this required —
  see `docs/updates/u15-signin-screen.md` for exactly which).
- **`make demo-real-hstgat`.** `prov models train-hstgat` worked but was wired into
  no `make` target, so the "Learned attention (HST-GAT)" map layer shipped disabled
  by default even against a real drop. Its own target (not folded into `demo-real` —
  training is the slowest step in the whole path, ~4m20s, and a judge re-running
  `demo-real` to reset state shouldn't pay that every time) trains the HST-GAT and
  conformal-calibrates it against `data/raw`; the trained artefact is picked up live
  by `GET /v1/graph/attention` (`store.latest_stem()`), no restart needed.
  `demo-real`'s help text and closing output mention it as an optional follow-up.
  Verified against the real Green Sentinel drop: 3,299 parameters, `calibrated: true`
  (2,816 calibration points, well above the `min_calibration: 20` floor), and the
  network map's dashed attention edges draw once the toggle is live. See
  `docs/updates/u14-train-hstgat-real.md` — also flags a pre-existing `libomp.dylib`
  duplicate-runtime crash in the attention endpoint on macOS/Homebrew/arm64, first
  surfaced by this update actually exercising it against real data.
- **The HST-GAT's learned attention as a map overlay.** `attention.py`'s per-edge
  attention weights were exported and fully tested but never rendered. `GET
  /v1/graph/attention` now serves them (public-read, computed live off the DB's
  current frame in a worker thread — never a file the frontend reads directly):
  `available: false` with a human-readable reason when no HST-GAT artefact is
  trained, or when the trained model's target parameter is not in the currently
  loaded data (standing rule 6 — never a silent empty overlay, never an error). A
  new "Learned attention (HST-GAT)" map layer, off by default, renders these edges
  dashed rather than solid — line weight and dash carry the attention magnitude, no
  new hue spent (blue is the only interactive colour) — so it can never be mistaken
  for the analytic wind-conditioned edges beside it. The toggle is disabled with the
  backend's own tooltip until a model is trained; `attentionEdgesFromOverlay`
  resolves each edge against the same station-marker lookup `windEdges.ts` projects
  the analytic edges from, so the two layers cannot drift apart geometrically.
  Frontend contract regenerated (`make web-contract`); visual baselines
  regenerated on both platforms (the layer panel gained a row). See
  `docs/updates/u11-attention-overlay.md`.
- **Enclod counter-repair reconciliation.** Phase 1 swept only `cars_60+` and
  reported 0 resets / 0 dead counters against a brief expecting ~80-96 resets
  per column and two dead sensors. Reran `repair_counter` over all ten measure
  columns × all 42 counters (420 series) against the real archive: resets stay
  at 3 (not 80-96) because the data genuinely contains no per-counter reset
  pattern — 83% of all backward-step events land on one calendar date
  (2026-05-24) across 39 counters and all 10 columns, a proportional ~1.5% dip
  at the same instant, the signature of a vendor-side batch correction rather
  than device resets. R21 (whole-series flatline) still finds 0 dead counters,
  but two counters (`nLAUrPvFow5EmokJd4oc8H`, `8zeqGioF5wq6yV6YdzYMzN`) do go
  silently dead by a signature R21 can't see — they stop emitting rows
  entirely partway through the archive and never return, which their own-span
  completeness (0.94, 0.94) doesn't flag since that metric only measures gaps
  within a counter's own observed window. `schema_assumptions.yaml`'s
  `observed_quality_notes` updated to the full-sweep figures; no detector
  retuned, no headline number changed. Two follow-ups escalated rather than
  decided unilaterally: whether a new dropout detector and a cross-fleet
  correction flag are worth building. See `docs/updates/u12-enclod.md`.
- **The Alert Centre (`/alerts`) and Admin (`/admin`) screens** — the phase-7
  operational layer (maintenance queue, risk-ranked alerts, sign-off gate, RBAC,
  admin) existed at the API/CLI only until now. The Alert Centre ranks candidate
  events by consequence-weighted risk with Severity, Verdict, Exposure, and
  Confidence as their own columns (so the ranking's inversion argument is visible
  in the list, not just true in the sort), reuses `TrustChip`/`TrustBreakdown`/
  `AdjudicationDetail` for a selected alert's station trust and adjudication case
  rather than rebuilding them, and gates dispatch on a valid sign-off with the
  block stated in a sentence an operator could read aloud
  (`aria-describedby`-linked to the disabled button) — a UI courtesy over the
  already-enforced server boundary (`gate.dispatch`/`test_signoff_gate.py`,
  unchanged). The maintenance queue's lifecycle transitions are read off
  `ops/maintenance.py`'s own forward-only state machine. Admin adds the RBAC
  matrix (role hierarchy plus a live reachable/blocked column for the signed-in
  role), status (versions, config hashes, audit/dispatch history, a
  request-only retrain action), and the two-plane monitor — infra health parsed
  from `/metrics` kept visually separate from `/v1/admin/model-drift`, which says
  "No history yet" rather than drawing a one-point chart before models are
  trained. `lib/role.tsx` replaces the hardcoded "Operator" stub with the real
  four-role model, mapped to the four dev keys `auth.py` already falls back to;
  a deployment pinning a real key outside those four loses the switcher rather
  than pretending to offer roles it cannot grant. Real-data testing (not just the
  266-test unit suite, all of which passed throughout) caught four bugs invisible
  to unit fixtures: a drift-value double-percent-conversion, a maintenance
  ticket's headline reaching the screen with an unfilled `{placeholder}`, two
  Tailwind classes (`w-80`, `w-24`) silently generating no CSS because this
  project's spacing scale doesn't extend that far (collapsing the maintenance
  detail pane's width and overlapping its list), and a naive local-time parse of
  a sign-off's `expires_at` that misread a valid sign-off as already expired in
  any timezone ahead of UTC. Visual baselines regenerated on both platforms,
  including new baselines for both screens. See `docs/updates/u10-alert-centre.md`.
- **`docs/adjudications/ker11-4100-evidence-v1.1.md`: verdict and demo
  narration for the KER11 ~4,100 µg/m³ PM10 event**, adopted by Ikenna Udeani
  on 2026-08-21 from Claude Code's recommendation over the v1.0 evidence.
  LIKELY_FAULT stands: the reading exceeds the sensor's own physical ceiling
  regardless of anything else, and no neighbouring station shows any response,
  though the hour-long build-up/decay and a delayed PM2.5 echo argue against a
  context-free glitch - the recommended framing is a real local trigger
  producing an invalid reading, not a random malfunction or a genuine citywide
  event. Resolves all seven questions v1.0 left open (confidence framing,
  the PM2.5 delay, nearby outages, the second case's re-framing as "declined
  to guess," the learned-path contrast as a footnote not a pillar, the
  calibration/maintenance gap stated as un-checkable rather than clean, and
  the learned model not changing the call) and drafts suggested stage
  narration. No source file changed; see `docs/updates/u9-ker11-verdict.md`.
- **`docs/adjudications/ker11-4100-evidence-v1.0.md`: evidence assembly for the
  B3 demo's centrepiece event**, the ~4,100 µg/m³ PM10 reading at DEB-KER11
  (2026-06-02T20:00:00). Every reason code the audit engine attaches to the
  reading, DEB-KER11's other parameters and every neighbouring station in the
  surrounding hours (ranked by distance), the wind field at that hour, the full
  analytic propagation-adjudicator bundle, a `--learned` (HST-GAT) contrast
  against a freshly trained artefact, a maintenance/calibration/outage overlap
  check, and a second, independently assembled candidate event
  (DEB-KER06/CO, 2026-06-17T13:00:00) as a backup - each section either a
  `$ prov ...` command's verbatim output or a labelled read against the same
  public library functions the CLI calls. Reaches no verdict by design; see
  `docs/updates/u8-ker11.md`.
- **`prov fixtures make --with-weather --with-plume`: an opt-in wind and
  plume/fault layer for the demo corpus**, so `prov graph adjudicate-db` no
  longer reads AMBIGUOUS for every event on the dashboard timeline and the
  phase-5 deweathering chart is no longer flat. New
  `src/provenance/fixtures/demo_scenario.py`: `add_wind` gives every station but
  one `Wind_Speed`/`Wind_Direction` (the exception mirrors the real network's
  confirmed DEB-KER15 gap) and couples PM10 to wind speed, reusing
  `fixtures/weather.py`'s dilution coefficient; `add_plume` plants one PM10-
  ceiling-exceeding NO excursion corroborated at every station the real
  wind-edge weight (`graph.edges.wind_edge_weight`) calls downwind, raised to
  the exact attenuated excess `graph.propagation.expected_arrival` predicts, plus
  one isolated, uncorroborated excursion of the same magnitude elsewhere - so
  the adjudicator reaches GENUINE_EVENT and LIKELY_FAULT respectively on
  evidence, not by construction. Both `add_wind`/`add_plume` are additive and
  strictly opt-in: `prov fixtures make`'s default output is unchanged (verified
  byte-identical against the pre-existing corpus and pinned by the golden
  recovery ledger). `make demo-corpus` now passes `--with-weather --with-plume
  --days 60` (up from 14 - the deweather regressor's forward-chaining CV needs
  the extra rows to converge past the golden-4's fixed-hour R07 outlier without
  overfitting around it). Visual baselines regenerated on both platforms: the
  event timeline, station detail and data quality monitor screens all change.
  See `docs/updates/u7-demo-corpus-wind.md`.
- **Street and place labels on the fetched basemap** (ADR 0011). ADR 0006
  stripped every symbol layer from the map style so it needed no glyph fonts
  and could stay fully offline; `scripts/fetch-fonts.sh` (new `make fonts`
  target, called from `make demo`/`make demo-real` alongside `make basemap`,
  same non-fatal contract) fetches the PBF glyph ranges the style actually
  needs — Noto Sans Regular/Medium/Italic, Unicode ranges `0-255` and
  `256-511` (covers Hungarian's ő/ű, one range past Latin-1) — from the same
  publisher as the `@protomaps/basemaps` package. `buildBasemapStyle` gains a
  `glyphsAvailable` flag (default `false`, unchanged behaviour); `useMapEngine`
  probes for the fonts the same content-sniffed way it already probes for the
  tile archive (a glyph PBF's first byte is reliably the protobuf tag `0x0a`;
  an SPA-fallback 200 starts with `<`), so absence degrades silently to the
  pre-existing label-free style. `apps/web/public/fonts/` is gitignored and
  absent by default; the pinned-Linux visual-check container now drops it
  before building, alongside `public/basemap`, so the CI/fresh-clone
  token-ground visual gate is unaffected either way.
- **`make demo-real`: run the whole stack against the real Green Sentinel drop
  instead of the synthetic fixtures.** Mirrors `make demo` (stack up, DB loaded,
  audited, adjudicated, models trained, API up, dashboard open) but points every
  step at `data/raw` and resets the local dev database first, rather than
  upgrading it in place — `station_id` and parameter `name` are global primary
  keys shared by every batch ever loaded, and the synthetic demo corpus and the
  real export use overlapping ids and pollutant vocabulary, so a bare upgrade
  leaves leftover synthetic markers mixed onto the real map. A new
  `check-real-drop` target fails loudly, before touching the database, if
  `data/raw` holds nothing but its `.gitkeep` placeholders — this target never
  silently falls back to the synthetic corpus; `make demo` remains the offline
  fallback and is unchanged. See `docs/updates/u6-real-drop.md` for the full
  real-vs-synthetic comparison this produced.
- **BusStop and TrafficCounter map layers, gated on real coordinates.** New
  `GET /v1/reference/bus-stops` and `GET /v1/reference/traffic-counters` endpoints
  serve real GTFS stop and Enclod counter coordinates read directly from the data
  drop (`gtfs.stops_with_route_counts`, and the new
  `enclod.counter_locations` — the observed `uuid`/`nick`/`lat`/`lng` columns from
  ADR 0005, independent of the still-gated cumulative-counter parse). Each endpoint
  reports `available: false` rather than an empty list when its source drop is
  absent, so the map layer toggle can tell "nothing here" from "not loaded"
  (standing rule 3) instead of silently rendering an empty layer. Both layers
  render as a small, low-contrast, subordinate marker class outside the trust
  palette, and every marker (station, bus stop, traffic counter) now carries a
  `data-provenance` attribute ("measured"; "provisional" is reserved but never
  drawn) with a matching legend section, so nothing on the map canvas can be
  mistaken for a measurement it isn't. TrafficCounter ships enabled (default off)
  because the 42 Enclod counters' coordinates are real, observed columns in the
  archive CSV itself, not an assumption.
- `AGENTS.md`: a short pointer at the repo root so agents that look for that
  filename by convention land somewhere useful, without becoming a second copy of
  CLAUDE.md's rules. `tests/architecture/test_agents_md.py` guards its length and
  bans a numbered rules list, so it cannot silently grow into a duplicate that
  drifts out of sync with CLAUDE.md.
- `tests/architecture/test_brand.py`: every `.svg` under `design/logo/` and
  `apps/web/public/` is now parsed with a strict XML parser. This is the guard that
  should have caught the dark-mode lockup shipping as an unparseable file.

### Fixed
- **`DEB-KER12` rendered on blank grey tiles on the network map.** `scripts/fetch-basemap.sh`'s
  extracted bounding box (`21.45,47.45,21.75,47.65`) predated the real Green
  Sentinel export's confirmed `Location` coordinates and didn't cover all of
  them: `DEB-KER12` sits at `lon 21.838`, about 0.09° east of the box's edge,
  so the fetched archive simply had no tiles there. Widened to
  `21.40,47.38,21.90,47.68` (covers all 16 real stations and the synthetic demo
  corpus, with a panning margin); verified by re-extracting and checking the
  archive's own bounds cover `DEB-KER12`, then a real-browser screenshot with
  the station in frame.
- **Loading a second, differently-checksummed data drop into an already-loaded
  database crashed on a duplicate-key error.** `stations.station_id` and
  `parameters.name` are global primary keys, not scoped to the `ingest_batch`
  that loaded them, so `_insert_stations`/`_insert_parameters` re-inserting a
  station or parameter name already on record from an earlier batch raised
  `IntegrityError`. Hit in practice loading the real Green Sentinel export
  (`DEB-KER*`, shares pollutant names like `CO2`/`PM10` with the synthetic demo
  corpus) into a database that already held the synthetic corpus's rows. Both
  functions now query the names already on record and skip re-inserting them;
  `tests/unit/test_db_loader.py::test_a_second_batch_sharing_stations_or_parameters_does_not_collide`
  pins it.
- **The dark-mode top-bar lockup did not render at all.** The generator at
  `scripts/gen_reversed_lockup.py` wrote a comment containing `--prov-white`, and a
  double hyphen is illegal inside an XML comment. Browsers parsing SVG-in-`<img>`
  are strict and reject the whole file, so the dashboard's default (dark) theme
  showed a broken image where the lockup belongs; the light theme was unaffected,
  since it uses the unreversed asset. Fixed at the source by rewording the
  generator's note, then regenerating both `design/logo/` and its
  `apps/web/public/` mirror. All sixteen visual baselines had been captured with
  the broken image in place on every dark-theme screen, so the visual-regression
  gate had been blessing the bug rather than catching it.
- **Trust Score: `HealthConf` was a constant zero for every station.** It summed one
  severity weight per defect *flag row*, and detectors flag every defective cell, so
  load scaled with window length and flag volume rather than with how broken a
  station was. Measured on the real export it ranged 8.7e-25 .. 5.8e-88 across all
  sixteen stations - w1 (35% of the score) contributed nothing, uniformly, and no
  test noticed, because the phase gates (`perfect > 0.95`, `frozen < 0.5`) are
  satisfied by saturation exactly as well as by calibration. Load is now the
  severity-weighted **fraction** of a station's cells that are defective, bounded by
  1.0 by construction; `decay_scale` moves 3.0 -> 0.3 with the unit change. The
  real-data range is now 0.468 .. 0.793. See
  `docs/trust-score-methodology-v1.1-bounded-health-load.md`.
- **R14 STEP_CHANGE reported the wrong instant and the wrong size.** Reading the
  changepoint off the CUSUM crossing put it inside the *stable* stretch, because
  standardising against the whole-series mean makes the pre-shift half look like a
  sustained deviation in its own right. On the fixture's known +15.0 step at hour
  168, it reported hour 11 and a magnitude of 6.798, and labelled the rise
  "downward". Detection (CUSUM, unchanged) is now separated from localisation (the
  split maximising the difference of means), and the injected step is recovered
  exactly. The ambiguous `direction` field is removed in favour of
  `signed_magnitude`, `level_before` and `level_after`. No defect count changes. See
  `docs/audit-methodology-v1.1-step-change-localisation.md`.

### Added
- `detectors/episodes.py`: collapses per-cell flags into distinct fault episodes
  (maximal runs of one code on one series, at that series' own cadence). Used to
  explain a trust score in operator terms - "31 active fault(s) spoiling 41.6% of
  readings".
- Trust tests now assert *discrimination*, not just threshold crossing: `HealthConf`
  must rank clean above spiked above frozen with a usable spread, load must not
  scale with window length, and a station losing one parameter must stay more
  trusted than one wholly frozen. These are the properties the existing gates could
  not see.
- Golden recovery asserts R14's injected step *size and instant*, not only that one
  R14 fired. A count-only assertion could not see the localisation bug, and did not.
- ADR 0005: the Enclod canonical mapping - a counter (`uuid`) is a station, a vehicle
  class is a parameter - with the reset discrepancy against the competition brief
  recorded as an open question and a plan rather than a footnote.

### Changed
- `schema_assumptions.yaml` v2: the Enclod block's `counter_column` / `value_column`
  keys described a narrow file shape that does not exist. The real archive is wide
  (one row per counter-tick, ten cumulative measure columns, 42 counters, ~1.53M
  rows); the observed schema is now recorded as such. Per-source `status` gains
  `observed` - columns known, parse not written - and only `confirmed` opens the
  adapter gate, pinned by a test so a config edit alone can never route callers into
  code that does not exist.
- The top-bar lockup renders at 56px (was 28px). `--prov-topbar-height` moves
  56px -> 72px in both `design/tokens/tokens.css` and its `apps/web` mirror so the
  larger mark keeps breathing room against both edges. No artwork, gradient, or
  palette value changed. All sixteen visual baselines regenerated on both
  platforms.
- The primary nav in `TopBar.tsx` gains `ml-6` (`--prov-space-6`, 32px) so the tab
  group reads as its own region rather than sitting against the lockup. No nav
  item, route, or ordering changed. No visual baseline changed - the shift falls
  within the visual gate's pixel-diff tolerance on both platforms.
- **Station detail panel is now resizable, and its default width no longer clips
  the trust-component table.** `--prov-drawer-width` moves 380px -> 520px in both
  `design/tokens/tokens.css` and its `apps/web` mirror - measured, not guessed,
  against the longest realistic content (a full 4-component breakdown, 5 reason
  codes, 7 parameter rows): below ~516px the `<table>` in `TrustBreakdown.tsx`
  (unconstrained auto layout) overflows its container rather than wrapping, which
  is what was cutting off the Value/Weight/Contribution columns. A new drag
  handle (`DrawerResizeHandle.tsx`, `lib/drawerWidth.ts`) sits on the panel's left
  edge from the `lg` breakpoint up: `role="separator"`, keyboard-operable
  (arrow keys, Home/End), double-click resets to the token default, and the
  chosen width persists to `localStorage` (clamped to [360px, 60% of the
  viewport]) and restores on load. The trust-trajectory `Sparkline` now takes a
  `fluid` prop so it scales with the panel instead of staying pinned at a fixed
  320px. Visual baselines regenerated on both platforms: the network map, the
  station detail panel, and the data quality monitor all shift a few px, since
  the resize handle occupies space even in the empty (no station selected)
  state and its neighbouring flex-1 region narrows to match; the event timeline,
  which never renders the drawer, is unchanged.
- **The network map never rendered under `pnpm dev`.** `useMapEngine.ts` carried
  a redundant `useEffect(() => () => engineRef.current?.destroy(), [])` beside
  the callback ref that already owns teardown. React 18 StrictMode
  double-invokes an effect's cleanup once in development, which destroyed the
  engine the ref had just created, with nothing to recreate it - the map was
  stuck on `data-map-state="moving"` forever, bare marker dots over the
  container's own background colour. Removed; the ref callback was always the
  correct sole owner of destroy. A second, independently-found bug: the
  token-ground fallback never re-themed on a dark/light switch, because
  `ThemeProvider` set `data-theme` from a plain `useEffect` and React fires
  passive effects child-before-parent, so the map's style-reapply effect (a
  descendant) always ran before the attribute was written. Fixed by moving that
  one effect to `useLayoutEffect`. Each marker now carries an offset,
  token-styled station-id label beside it, hidden on a genuine screen-space
  collision with a neighbour rather than a guessed zoom cutoff
  (`visibleStationLabels`). The "basemap unavailable" notice now distinguishes
  MapLibre-could-not-start (a browser problem) from tiles-not-fetched (a
  `make basemap` problem) with different wording and a `data-testid` each.
  Visual baselines regenerated on both platforms: only the network map moves:
  the pre-existing `map-*` baselines were themselves showing the fetched
  streets rather than the token ground ADR 0006 says the gate should test,
  because the darwin capture path has no equivalent of the Linux container's
  automatic `public/basemap` removal - recaptured correctly with the archive
  moved aside.

### Fixed
- **The Evidence tab's "Graph attention over neighbouring stations" card always read
  "Not yet computed... lands in phase 6", even after update-14 trained the HST-GAT
  and wired its attention overlay into the Network Map layer.** The card
  (`EvidencePanel.tsx`) was a static placeholder left over from phase 3 that never
  called `useAttentionOverlay()` - a wiring gap, not a missing backend (the
  `/v1/graph/attention` endpoint and the trained artefact both already worked, and
  still do; the map's "Learned attention (HST-GAT)" layer was reading them fine the
  whole time). `GraphAttention` now calls the same hook, filters the returned
  relations to the edges touching the flagged reading's station, and renders them as
  signed bars (mirroring `ShapBars`) with the model's own target parameter and
  snapshot time; when no trained artefact exists yet it shows the backend's own
  `reason` string instead of a hardcoded one, and when the artefact exists but has no
  edges touching this particular station it says so as a graph-topology fact rather
  than a missing computation.
- **The Evidence tab's "Deweathered residual for CO2" card could never resolve, no
  matter how many times an operator ran the `prov models train` /
  `prov models residuals` the card itself recommended.** Unlike the attention card,
  this one was already correctly wired to `/v1/deweather/{station_id}` - the gap was
  upstream: `CO2` (a confirmed parameter in `schema_assumptions.yaml` and, on the
  real drop, the single most common defect parameter) was never in
  `models.yaml`'s `deweather.pollutants` list, so no CO2 regressor had ever been
  trained and no CO2 residual could ever be stored. Added CO2 to that list ([PM10,
  NO2, O3, CO, CO2] - like the other three combustion-linked pollutants, its local
  concentration is also driven by dispersion conditions); retrained
  (`prov models train --source data/raw`) and restored residuals
  (`prov models residuals --source data/raw`) against the real drop. CO2's held-out
  R² (0.26) sits inside the configured sanity band (0.15-0.90); the synthetic demo
  corpus used by the unit test gate does not carry a CO2 series, so
  `test_only_present_pollutants_are_trained` is unaffected, and the demo corpus
  itself is unchanged. **Flagged, not fixed here:** retraining surfaced that CO
  (R²=-0.15), NO2 (R²=0.11), and PM10 (R²=-1.96) already fail the configured R²
  floor (0.15) on the real drop - a pre-existing condition (their residuals were
  already trained and stored under this model version before this update), never
  caught by CI because `test_r2_band_per_pollutant` only exercises the synthetic
  fixture corpus (standing rule 7). See `docs/updates/u16-wire-evidence-tab.md`.

## [1.0.0-demo] - 2026-08-09
Phase 7: the operational layer and the submission build — the freeze tag. Adds the
maintenance queue and Alert Centre, the human sign-off gate on public dispatch, the
completed regulatory export, four-role RBAC, two-plane monitoring, and deterministic
offline demo mode.

### Added
- **PopulationExposure is computed, not stubbed** (`grid/exposure.py`, §7.8). The Risk
  factor is now derived per station from a GTFS static bundle — every stop within a
  ~500 m corridor contributes its distinct-route count, min–max normalised into a bounded
  multiplier — so a broken reading in a busy transit corridor outranks the same fault at a
  rural background site. A station with no coordinate or a drop with no GTFS bundle keeps
  the neutral 1.0 and reports `population_exposure_stubbed=true` (graceful degradation):
  the flag is no longer permanently true. A synthetic GTFS fixture (`fixtures/gtfs.py`)
  gives tests and the offline demo a real bundle to aggregate.
- **Maintenance queue** (`ops/maintenance.py`, `ops/store.py`, §9.5): tickets auto-raised
  from the deterministic fault flags, ranked by **severity × station importance**
  (importance = PopulationExposure), with an `open → acknowledged → dispatched → resolved`
  state machine and a full, append-only transition history. Idempotent rebuild.
- **Alert Centre ranked by RISK, not certainty** (`ops/alerts.py`, §9.5):
  `genuineness × exposure × hazard × confidence`, so a high-exposure **genuine event**
  outranks a confident low-exposure **sensor fault**. Asserted with a constructed pair.
- **Human sign-off gate + idempotent dispatch** (`api/decision/`, §2, standing rule 5):
  every public dispatch passes through one choke point that refuses to send without a
  valid, non-expired operator sign-off (who / when / evidence hash / model version) and
  is idempotent on `(event, channel, sign-off)` — retries and concurrent calls never
  double-send. A **static call-graph test** proves the senders are unreachable except
  through the validated gate.
- **Completed regulatory export** (`report/regulatory.py`, §2): reading accounting, the
  itemised defects and structural exclusions, model versions, sign-off records, and a
  **reproducible verification hash** over the certified content — rendered as CSV, JSON,
  and a dependency-free printable **PDF** summary, all from one bundle. `?format=pdf` and
  an `X-Verification-Hash` header added to `/v1/export/audit-trail`.
- **Four-role RBAC** (`api/auth.py`, §11): adds `admin` above `operator`; a full endpoint
  × role matrix test pins the policy (ADR 0010). An **admin dashboard** surface exposes
  model versions, config hashes, retraining triggers, and export/dispatch history.
- **Two-plane monitoring** (§11): Prometheus service-health metrics at `/metrics` (infra
  plane) and a separate **model-drift monitor** at `/v1/admin/model-drift` (deweathering
  R², conformal coverage, fault confusion, defect-rate drift by station). Grafana
  dashboards and the rationale for the split in `docs/monitoring-v1.0-two-planes.md`.
- **Deterministic offline demo mode** (`cli/demo.py`, `ops/demo.py`, §demo-critical):
  `prov demo run --scenario <name>` replays a fixed window at a controllable speed as an
  ordered sequence of screen states with computed numbers; five scenarios
  (`audit-headline`, `ker11-adjudication`, `contrast-fault`, `deweathering-reveal`,
  `explainability`). Two runs are byte-identical; the suite runs with the network blocked;
  basemap tiles are vendored for the Debrecen bbox. `scripts/record-demo.sh` captures the
  fallback recording.
- **Submission artefacts** (`docs/demo/`): the timed 7-minute `demo-script-v1.0.md`, a
  one-page description, a 3-minute video storyboard, and `judge-questions-v1.0.md`
  (prepared answers to the §16 critiques).

### Tests
- Sign-off architecture (static call-graph), alert risk ordering, dispatch idempotency
  under retry **and** concurrency, the RBAC matrix, audit-export reconciliation + hash
  reproducibility, demo-mode determinism, a full network-blocked offline run, a
  scenario-layer full-script rehearsal, and a 50-client load smoke.

### Fixed
- **A huge integer path parameter no longer 500s.** The maintenance detail/transition
  endpoints are the API's first `int` path params; an id larger than SQLite's 64-bit
  `INTEGER` raised `OverflowError`. A global `OverflowError → 400` handler
  (`api/errors.py`) maps it to a client error, found by the schemathesis fuzz and pinned
  by a regression test.
- **Test databases no longer leak an aiosqlite worker thread.** `io/db/engine.make_engine`
  now backs file-based SQLite (the test path) with a `NullPool`, which closes each
  connection on return, and keeps a `StaticPool` for `:memory:`. This removes at source the
  leftover `_connection_worker_thread` that could race the native OpenMP math pools of a
  later torch-heavy test and segfault the process on macOS (surfaced by the HST-GAT
  "real corpus shape" test once it was included in the full local run; CI-Linux was
  unaffected). Torch is also pinned to a single intra-op thread (`train.py`,
  `tests/conftest.py`) for the CPU determinism the repo already requires (ADR 0009).
- **Phase-6 flag review — the attention export and the calibrated interval are now
  produced in the product flow, not only in tests.** Two capabilities that phase 6 built
  and coverage-tested were reachable only from unit tests:
  - The **attention overlay** (§8) is now written by `prov graph adjudicate --learned`
    (via `models/hstgat/attention.py:write_overlay_for_drop`) as
    `attention_overlay.json` for the top-ranked event — the map-ready "which neighbours
    influenced this call" export. The live MapLibre rendering remains a deliberate
    frontend follow-up (would drift the pinned visual baselines).
  - The **split-conformal calibrator (`q`) is now persisted with the artefact** and
    loaded at inference, so a learned adjudication attaches a **calibrated interval on
    the expected excess of every downwind neighbour** (`NeighbourEvidence.sigma` /
    `expected_interval`) — the "calibrated confidence intervals on every score" the demo
    checkpoint asks for. Previously the model's predictive σ was computed and dropped and
    the `q` was discarded after coverage was recorded. The analytic path is unchanged
    (both fields are `None`; the KER11 characterization still passes byte-for-byte).

## [0.6.0] - 2026-08-09
Phase 6: the research contribution — a heterogeneous spatio-temporal graph-attention
network (HST-GAT), split-conformal intervals, a learned propagation validator behind a
feature flag, and inspectable attention. Sequenced last on purpose: it converged, so it
ships; had it not, Phase 5 would have shipped unchanged.

### Added
- **PyTorch Geometric adaptation** (`graph/pyg.py`) — `GraphSnapshot.to_hetero_data()`
  materialises the same node/edge tables as a PyG `HeteroData` **without any caller
  changing**, with torch imported lazily so the statistics layers still run on a machine
  with no torch. The exact working install (CPU-first, MPS-optional, no compiled
  `torch-scatter`) is recorded in **ADR 0009**.
- **HST-GAT** (`models/hstgat/`, §6.4): `h_i(t) = GRU(h_i(t-1), HetGAT({h_j(t)}, edge_weights(t)))`.
  A hand-rolled heterogeneous graph-attention layer over all five edge types with a
  per-`EnvStation` GRU memory, predicting a **mean and a variance** per station-hour. The
  wind-conditioned weight enters attention as an **additive pre-softmax bias**: zeroing it
  recovers a plain HetGAT (tested), and raising it monotonically shifts attention to the
  wind-connected neighbour (tested). Deliberately small — **3,299 parameters** against 720
  timesteps/station (§5.1) — justified in the model card. A **GCN baseline** is included
  for comparison, as the blueprint specifies.
- **Masked-autoencoder training** (`models/hstgat/train.py`): hide known values,
  reconstruct from wind-weighted neighbours, score with **masked Gaussian NLL**.
  Time-blocked splits (never random K-fold, standing rule 7), full seeding
  (byte-identical reruns on CPU, standing rule 8), and a **run manifest** per training —
  seed, config hash, data checksum, git sha, metrics and parameter count.
- **Split conformal prediction** (`models/conformal/`, §7.7): a small, hand-rolled,
  distribution-free interval with the exact finite-sample quantile and adaptive
  (σ-normalised) width. Every model output gains a calibrated interval; the calibration
  set is always a held-out **time** block. Empirical coverage on held-out data lands
  inside the nominal band (90% nominal → 85–95% empirical, tested).
- **Learned propagation validation, behind a feature flag** (`models/hstgat/forecast.py`).
  The Phase-4 adjudicator's analytic expectation is swapped for the HST-GAT forecast via a
  `graph.ExpectationProvider` Protocol (dependency injection — `graph` never imports
  `models`, so the layering holds). If the artefact is absent or fails to load, the
  adjudicator **falls back to the analytic prior automatically** and the evidence bundle
  records which path produced the verdict (`expectation_provenance`). Both paths stay
  tested and demoable. Flag: `PROVENANCE_LEARNED_PROPAGATION`; CLI: `prov graph adjudicate --learned`.
- **Attention explainability** (`models/hstgat/attention.py`, §8): per-prediction
  attention exported as weighted, highlighted edges — "which neighbours most influenced
  this call" — ready for the network map.
- **Model card** `docs/model-cards/hst-gat-v1.md` (hand-written, committed): parameter
  count, small-data justification, achieved conformal coverage, GCN-baseline comparison,
  honest limitations. Auto-generated per-training cards (checksum-suffixed) are gitignored,
  like the tree models'. New CLI: `prov models train-hstgat`.

### Changed
- The propagation adjudicator (`graph/adjudicate.py`) now takes an optional injected
  expectation provider; the default `AnalyticExpectation` reproduces Phase-4 verdicts
  **byte-for-byte** (the KER11 characterization test is unchanged).

### Explicitly not done (standing rule 4)
- **No headline accuracy or F1 for the propagation validator.** With this few real
  corroborated events such a number would describe the synthetic injection process, not
  the world. The model reports reconstruction NLL/RMSE, per-case evidence, and calibrated
  intervals instead — enforced by a test that scans the metrics for "accuracy"/"f1".

## [0.5.0] - 2026-08-09
Phase 5: meteorological normalization, the supervised fault classifier, and the
explainability layer — completing the B1 → B3 → B2 demo order.

### Added
- **Deweathering (B2)** — one gradient-boosted regressor per pollutant predicts the
  reading from meteorology and time alone; the residual (actual − weather-predicted)
  is what anomaly detection sees downstream. Trained forward-chaining only
  (`models/cv.py`), never random K-fold, and held to a **0.15–0.90 R² sanity band**
  whose two failure modes are named. Residual series are stored in the database
  (`residuals` hypertable) alongside the model version that produced them.
- **Feature layer with honest provenance** (`models/features/`). Wind direction is
  encoded as `(sin, cos)` so 359° and 1° are neighbours, not a cliff at north — a
  property the test gate pins. Temperature/precipitation come from HungaroMet (flagged
  imputed until the feed is confirmed), the boundary-layer height is a documented
  time-of-day/season **proxy** (§5.3), and every feature column carries its provenance.
- **Hybrid fault classifier** (`models/fault/`, §7.3). The deterministic Phase-1
  detectors run **first and short-circuit**; LightGBM only ever chooses among the
  subtle classes (`none`, `calibration_drift`, `meteorological_artefact`). A test
  proves the ML can never override a physical-impossibility flag. Class-weighted
  cross-entropy, a per-class confusion matrix, per-signature recall floors, and a
  watched `meteorological_artefact` precision — **no headline accuracy figure**
  (standing rule 4).
- **Explainability (`explain/`, §8)** — SHAP over the tree models with a stable
  feature-name mapping; the additivity invariant (base + attributions reconstruct the
  prediction) is asserted. A renderer turns attributions into the operator sentence
  ("driven primarily by the shallow overnight mixing layer, then wind speed").
- **`GET /v1/explain/{defect_id}`** serves per-defect SHAP attributions, the fault
  class, the residual and the sentence — degrading to the statistics-layer reason,
  flagged `degraded`, when no model artefact is loaded. **`GET /v1/deweather/{station}`**
  serves the raw-vs-predicted-vs-residual series behind the before/after chart.
- **Model cards, auto-generated at training** (`models/cards.py`, §5): data window,
  feature list with provenance, CV scheme, metrics, class balance, limitations and the
  training-data checksum. A model without a card sidecar (or with a mismatched
  checksum) **refuses to load** (`models/registry.py`).
- **Graceful degradation, end to end** (standing rule 6): with every model artefact
  deleted the API still returns trust scores from the statistics layer, flagged
  `degraded` and complete with their breakdown — pinned by a `demo_critical` test.
- **Dashboard**: the evidence panel's SHAP slot now populates (signed attribution bars
  + the operator sentence), and a toggleable **before/after deweathering chart** (raw
  vs residual) is drawn beside it. Both degrade honestly when no model is loaded.
- **`prov models train` / `prov models residuals`** CLI, and `make demo-models` wires
  training into `make demo` (deliberately not into `make demo-data`, so the pinned
  visual baselines keep their statistics-only state).
- **Real street basemap for the demo map** (ADR 0006, resolving the flag-review
  escalation). `make basemap` extracts the Debrecen region (~6 MB) from a Protomaps
  planet build into a gitignored path; the dashboard renders it under the markers
  when present and falls back to the token ground otherwise. Offline after the first
  fetch, never committed, neutral palette so it never competes with the state colours.

### Fixed
- Second phase-3 flag-review pass:
  - **Defect list truncation is surfaced.** The cursor walk reports when it stops at
    its page cap; the evidence panel shows a banner instead of presenting a prefix as
    the whole set.
  - **The defect table's dense code chip carries its row's evidence**, so its tooltip
    and screen-reader text read the full sentence, not "Value of — — exceeds the
    physical maximum for —".
  - **Trust component evidence keys are pinned pairwise-disjoint** by a test.
  - **The map re-themes on a theme switch** (a latent bug: the token ground never
    repainted), surfaced while wiring the basemap.
- Phase-3 flag-review resolutions:
  - **Trust reason codes carry their figures.** `TrustComponent` gains an `evidence`
    dict keyed by the placeholder names the registry sentences use, and `TrustScore`
    merges them into the substitution map the API now serves as
    `TrustScoreOut.evidence`. No migration: `components` is already a JSON column of
    arbitrary dicts. T03 reads "disagreement with 15 neighbouring station(s)" instead
    of an em dash with a prose fallback beneath it.
  - **The audit report's per-code breakdown is complete.** It read one 500-row page
    and counted it, which on the 18-station demo corpus showed 6 of 13 reason codes
    with R10 at 145 instead of 336. It now reads `summary.defects_by_code`, computed
    by the engine over every row, and `useDefects` follows the cursor so no windowed
    count can silently truncate.
  - **The defect table's code chip carries its row's evidence**, so its tooltip and
    screen-reader text no longer read "Value of — — exceeds the physical maximum
    for —" beside a row holding every one of those numbers.
  - **The contract drift check moved to `ci.yml`**, which has no `paths:` filter and
    therefore cannot be skipped by a change nobody thought to list.
  - **CI starts the API through `make api-bg`**, the same target `make demo` uses, so
    a `make demo` that does not start the API fails a check.
  - Uptime and last-calibration stay derived in the dashboard but are tethered by
    backend tests asserting the two properties their formula assumes.

### Documentation
- `dashboard-v1.1-operator-screens.md` supersedes v1.0.
- `docs/demo/checkpoint-3-capture-checklist-v1.0.md` records the outstanding human
  demo-capture task durably.

## [0.4.0] - 2026-08-09
### Added
- **The heterogeneous graph (`graph/`).** A `GraphSnapshot` value object carries
  node tables (EnvStation, TrafficCounter, BusStop, WeatherNode) and edge tables
  (spatial_proximity, wind_conditioned, road_adjacency, transit_corridor,
  weather_influence) at one timestamp, backed by numpy/pandas today and designed as
  the exact seam phase 6 will back with a PyG `HeteroData` without changing a caller.
  BusStop nodes are **aggregated to a bounded number of corridors** (§16 critique 6),
  enforced by a test. Traffic/bus/weather geometry is honest, clearly-labelled
  `synthetic-provisional` placeholder topology until the Enclod/GTFS feeds are
  confirmed; env-station coordinates and the weather-node centroid are real/computed.
- **Wind-conditioned edge weights** (ADR 0007): `w = exp(-Δθ/sigma_angle) · f(speed)
  · g(distance)`, a lightweight, differentiable **plume approximation, not a
  dispersion model**. Geodesic bearings and haversine distance on a sphere; correct
  angular wraparound at the 0/360 seam; a saturating speed response and a distance
  decay. Zero wind produces a degenerate but finite graph (no NaN, no division by
  zero). Station-local wind with a **city-level HungaroMet fallback** (KER15 carries
  no wind sensor), provenance tracked per edge.
- **Analytic propagation expectation**: expected arrival delay, attenuated
  magnitude, and an expected series over a 15–60 min horizon, bucketed to the hourly
  cadence (documented, not interpolated).
- **The propagation adjudicator (`graph/adjudicate.py`)**: `validate_event()` returns
  `GENUINE_EVENT` / `LIKELY_FAULT` / `AMBIGUOUS` with a confidence and a full
  `EvidenceBundle` (wind, downwind neighbours + weights, expected vs actual, match
  score, covariate state, reason codes). **AMBIGUOUS is first-class** — it routes to
  human review and can never render as high confidence, enforced in the value object.
  Reason codes R22 (PLUME_CORROBORATED) and R23 (ADJUDICATION_AMBIGUOUS) join the
  registry under a new `adjudication` category; the fault case surfaces R17. **No
  headline accuracy figure is reported** (standing rule 4) — see the model card.
- **Replay harness (`graph/replay.py`)** and `prov graph adjudicate` / `snapshot` /
  `adjudicate-db`: rank the corpus's candidate events by magnitude and anomaly,
  adjudicate each, and write evidence bundles to `reports/adjudications/`. Pointed at
  the real drop the top event is the ~4,100 µg/m³ KER11 spike, surfaced by ranking —
  no station or verdict is hardcoded, hinted at, or assumed anywhere.
- **Dashboard**: the wind-conditioned edge layer is enabled on the map (opacity/width
  by weight, direction shown); the event timeline colours each verdict and opens a
  full **event detail** — expected vs actual downwind series, verdict + confidence,
  downwind neighbours, and the covariate stubs; verdict labels populate for
  adjudicated events. Stored events are adjudicated back into `Event.verdict` and
  `Event.evidence.adjudication` by a graph-layer persister (io/db stays upstream of
  graph), so the API serves them with no contract change.

### Documentation
- ADR 0007 (wind edges), `docs/model-cards/propagation-adjudicator-v1.md`.

## [0.3.0] - 2026-08-08
### Added
- **Dashboard v1** (`apps/web`) — the operator-facing second screen, and the first
  complete demoable product. Vite + React 18 + TS strict, TanStack Query, React
  Router, MapLibre GL, Recharts, Tailwind reading the design tokens.
  - **Network map**: 18 station markers coloured by trust (green > 0.85, amber
    0.5–0.85, red < 0.5) and *shaped* by trust as well, so colour is never the only
    channel. Wind vector overlay (circular mean, so the 360/0 wrap does not point
    the arrow backwards), event glyphs on actively-flagged stations, layer toggles
    with the wind-conditioned-edge layer built disabled and explained.
  - **Station detail**: trust score with its component breakdown and its reason
    codes as plain-language sentences, per-parameter sparklines that break at gaps
    rather than interpolating, structural-absence coverage notes, and
    [View evidence] / [Acknowledge] / [Dispatch] — the last two writing to a local
    queue that has no transport out of the browser (standing rule 5).
  - **Data quality monitor**: dense, sortable, filterable, virtualised table.
    Uptime is derived as 1 − (R01 absent cells ÷ expected cells) and the last
    calibration epoch from the newest R15 discontinuity; both derivations are
    stated on screen next to the number.
  - **Event timeline**: events on a time axis, coloured *and* shaped by
    classification. Every verdict reads "pending adjudication" until phase 4.
  - **Evidence panel**: reason-code sentence, the detector's own evidence numbers,
    the raw series ±24h with the flagged point marked, and the neighbouring
    stations measuring the same parameter. SHAP and attention render as explicit
    "not yet computed" slots.
  - **Audit report**: the phase-1 report rendered natively, with the defect-rate
    definition displayed beside the number and drill-down by reason code.
- Generated frontend contract (`scripts/gen_frontend_contract.py`): OpenAPI schema,
  the reason-code registry including every operator sentence, and the numeric design
  tokens the UI branches on. `--check` is the CI drift gate — nothing about the API,
  the registry, or the palette is restated by hand in TypeScript.
- 18-station demo corpus: `prov fixtures make --stations N` appends clean stations
  beyond the four the injection layout targets, and writes a `stations.json` sidecar
  carrying synthetic coordinates. `make demo` loads it, audits it, and opens the
  dashboard; the four-station test corpus and its golden ledger are unchanged.
- Reversed horizontal lockup (`design/logo/provenance-lockup-horizontal-reversed.svg`),
  generated from the approved lockup by substituting only the wordmark's ink for
  `--prov-white`. The approved lockup's near-black wordmark is invisible on the dark
  theme, which is the default. Geometry equality is asserted by a brand test.
- CORS on the API (`PROVENANCE_CORS_ORIGINS`, an allow-list, never `*`). The
  dashboard is a browser client on another origin; without this every request fails
  preflight and every screen renders empty against a perfectly healthy API.
- Test gate: 152 Vitest component tests (94.7% line coverage on `apps/web/src`,
  gate 80%), and 51 Playwright end-to-end tests covering the demo path, axe-core
  scans of every route in both themes with zero critical violations, keyboard-only
  traversal, visual regression baselines for four screens in both themes, and the
  390px responsive floor.

### Changed
- Phase-2 flag-review escalation decisions (both Option A):
  - **Trust weights endorsed.** `trust_weights.yaml → status: endorsed` (project lead,
    2026-08-08), backed by real-event evidence: on the real export the weights drop
    DEB-KER11's trust 0.577 → 0.275 at the 4100.7 µg/m³ PM10 event (T04), recovering
    once it leaves the window. Endorsement ≠ logistic refit; the compressed real-data
    distribution and "discrimination lives in the series" caveat are recorded in the
    config and in methodology **v1.2** (supersedes v1.1).
  - **zone_type populated** from a curated, provisional `config/station_zones.yaml`
    (16 stations classified urban/suburban/industrial/background from site names, each
    with a rationale + confidence, `status: provisional`). Never inferred from
    readings; fixtures stay null.
- Phase-2 flag-review resolutions:
  - Trust scores are persisted as a **daily series** across the ingest window, not a
    single instant, so `/v1/trust/{id}?series=true` returns a real trajectory
    (`trust_weights.yaml → scoring`). Superseding methodology doc
    `trust-score-methodology-v1.1-invariants-and-series.md`.
  - Station **name and coordinates** now populate from the Green Sentinel `Location`
    column (verified real format `"<name> (lat, lon)"`, parsed by
    `io/loaders.parse_location`, failing loudly otherwise); the PostGIS `geom` point
    is now a STORED generated column derived from lat/lon. `zone_type` stays null —
    it has no source in the export (recorded in `schema_assumptions.yaml`).
  - `quality/summary.last_reading_at` now reports the real per-station max reading
    time instead of null.
  - The engineering-judgement trust formulas are pinned by invariant tests
    (`tests/unit/test_trust_invariants.py`): HealthConf monotonicity, plausibility
    ceiling-softening, Trust = weighted sum, scoring-instant cadence/cap/anchor.

## [0.2.0] - 2026-08-08
### Added
- Persistence layer (`io/db/`): SQLAlchemy 2.0 async ORM for stations, parameters,
  readings, defects, audit_runs, coverage_facts, trust_scores, events, and
  ingest_batches. Every persisted row carries the `ingest_batch_id` / `audit_run_id`
  that produced it — provenance of the data is the schema.
- Alembic migrations against TimescaleDB + PostGIS: `readings` and `trust_scores`
  are hypertables chunked by day; `stations` carries a `geometry(Point,4326)`
  column. The ORM stays portable (SQLite for the fast test path); the
  Postgres-specific DDL lives in the migration and is proven by a Dockerised
  up/down/up round-trip test.
- Idempotent loader keyed on the data checksum: re-loading the same file changes
  nothing (asserted by test). `prov db upgrade`, `prov db load`, `prov db reset`.
- Trust Score v1 (`trust/`), statistics-only, implementing §7.8:
  `Trust = w1·HealthConf + w2·(1−ImputationUncertainty) + w3·CrossSensorConsistency
  + w4·PhysicalPlausibility`. Weights in `config/trust_weights.yaml`, elicited and
  documented as pending a logistic refit. ImputationUncertainty is an explicit,
  flagged placeholder. `Risk = Trust × SeverityVsThreshold × PopulationExposure`
  with PopulationExposure stubbed at 1.0 and flagged, not silently defaulted.
- A `TrustScore` cannot be constructed without its component breakdown and a reason
  code; `TrustScoreOut` requires both non-empty; an architecture test proves no
  response model exposes a station trust value without them (standing rule 9).
- Trust reason codes T00–T05 in the registry (category `trust`, non-counting).
- FastAPI application (`api/`), async, auto OpenAPI: stations, readings (raw and
  quality-flagged), defects, trust (point-in-time and series), quality summary,
  events (verdict null until Phase 4), audit runs, the regulator-facing
  audit-trail export (CSV + JSON, reproducible and reconciled), and healthz/readyz/
  version. Cursor pagination, RFC 7807 problem responses, structured request
  logging with a request id, and API-key auth with three roles
  (operator/researcher/public_read).
- Ingestion abstraction (`io/ingest/`): an `IngestAdapter` Protocol with the
  Green Sentinel adapter fully wired and Enclod/HungaroMet/GTFS as discover-only
  adapters that fail loudly while their schemas are unconfirmed. A streaming adapter
  can be added with zero changes downstream (ADR 0003).
- Tests: trust component units, the perfect-station >0.95 / frozen-station <0.5
  gate, an endpoint × role auth matrix, pagination traversal invariants, byte-for-
  byte audit-trail reproducibility with defect-count reconciliation, a schemathesis
  fuzz asserting no endpoint 5xxs, idempotent-load, and Dockerised migration and
  full-stack integration tests. Coverage gate raised to 88%.
- ADR 0003 (ingestion abstraction), ADR 0004 (API-key auth now, OIDC deferred to
  phase 7), `docs/api/README.md` with worked curl examples, and
  `docs/trust-score-methodology-v1.0.md`.

## [0.1.0] - 2026-08-08
### Added
- The statistics-only audit engine (B1) — the demo's opening block and the
  no-ML fallback the whole project rests on. No machine learning.
- Canonical long frame (`schema/`): pandera-validated, deterministic `row_hash`,
  observed-schema discovery writing a manifest per data drop.
- Green Sentinel loader (`io/`): reads the real Hungarian-schema Excel export,
  fails loudly on schema drift, never invents a field name or unit.
- Cumulative traffic-counter repair (`io/counter_repair.py`): reset-aware
  differencing with an exact difference/cumulate round-trip; detects resets
  (R05), non-monotonic runs (R06), duplicate timestamps (R03), out-of-order
  rows (R04), and dead sensors (R21).
- Coverage model (`grid/`): per-series cadence inference and four separately
  reported quantities — observed, absent, structurally-excluded, expected — with
  `expected == observed + absent + structurally_excluded` enforced by property
  tests. Structural absence is inferred from the data, not hardcoded.
- `DefectRate` — the single defect-rate definition in the codebase, rendered
  next to every number it produces.
- Detectors R01–R14, R18, R19, R21, each a pure function over the canonical
  frame with a JSON-serialisable evidence dict; all thresholds live in
  `config/thresholds.yaml` with a cited physical or statistical basis.
- Audit orchestrator (`audit/`) producing an `AuditResult` with run metadata,
  coverage summary, by-code/station/parameter/day breakdowns, structural
  section, and a ranked `notable_events` list.
- Reporting (`report/`): deterministic `audit.json`, `audit.md`, and a
  self-contained printable `audit.html` that inlines the design tokens.
- Seeded synthetic corpus generator (`fixtures/`) with a ground-truth ledger;
  the golden recovery test asserts the audit reproduces every injected count
  exactly, and the clean corpus trips no detector.
- CLI: `prov data profile`, `prov schema observe`, `prov audit run`,
  `prov audit report`, `prov fixtures make`.
- `docs/audit-methodology-v1.0.md`: every detector, its threshold, its
  justification, and the defect-rate definition.

### Changed
- Config confirmed against the real export: `schema_assumptions.yaml` status is
  now `confirmed`; `thresholds.yaml` status is now `calibrated`.

## [0.0.2] - 2026-08-08
### Added
- CI: dedicated `architecture` job running the structural-invariant tests on
  their own, so a layering violation surfaces as its own PR check.
- Brand guardrail: `tests/architecture/test_brand.py` fails if the app's token
  file drifts from the authoritative `design/tokens/tokens.css` (byte-identical).
- Brand guardrail: frontend `no-inline-hex` test fails if any hex colour literal
  appears in `apps/web/src` outside `styles/tokens.css`.
- ADR 0002: licensing recorded as provisional (MIT), with the triggers that would
  force a change and who decides.

### Changed
- `test_no_data_files_are_tracked` now checks git's index rather than the
  filesystem, so it passes with untracked real data present locally (required
  from phase 1) while still failing if data is ever committed.

## [0.0.1] - 2026-08-07
### Added
- Repository scaffold: src-layout Python package, monorepo directory structure.
- Tooling: uv, ruff, mypy (strict), pytest with coverage gate, pre-commit.
- CI: GitHub Actions for backend, frontend, and CodeQL.
- Docker Compose stack: TimescaleDB (Postgres 16 + PostGIS), Redis, api, web.
- Reason-code registry (R01-R21) seeded from the dataset profiling findings.
- Brand assets: the approved logo rebuilt as vectors (mark, small-size
  reduction, one-ink, horizontal and stacked lockups, app icon).
- Design tokens carrying the agreed Trust Blue / Sentinel Green / Alert Amber
  palette, unchanged by the logo. The mark's own artwork values are scoped
  separately as `--prov-brand-*` and are not usable in the interface.
- ADR 0001: monorepo and stack.
