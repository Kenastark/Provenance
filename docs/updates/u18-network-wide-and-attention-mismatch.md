# Update 18 — the two items update-17 left open

Branch: `update-18-network-wide-and-attention-mismatch`. Tag: `v1.0.19-update`.

## What was built

Update-17's report flagged two items its own action list hadn't covered:
surfacing the network-wide CO2 finding somewhere aggregate, and a visual cue
when the attention card's target parameter doesn't match the viewed defect's.
Both are built here. The user also asked about the Network Map no longer
showing; that turned out to be the same root cause update-17 already fixed,
investigated and reported below rather than re-fixed.

### 1. Network-wide findings on the Audit report

The real finding - R10 fires on literally every one of CO2's 10,627 readings,
across all 16 stations - was, before this update, indistinguishable from any
other reason code's tally: a single number (`defects_by_code.R10`) alongside
four other codes, none of which say whether they're spread thinly across the
network or concentrated in one systemic fact about a whole channel. That
distinction is the difference between "this station has a fault" and "this
measurement channel is mislabelled everywhere" - a materially different, more
important finding, and one this project's own thesis is built around.

**Backend** (`audit/`, generic over both dimensions - never a hardcoded code or
parameter, per standing rules 1/2):

- `audit/result.py`: new `NetworkWideFinding` dataclass (`reason_code`,
  `parameter`, `station_count`, `flagged_readings`, `total_readings`,
  `fraction`) and a `network_wide_findings` field on `AuditResult`, included in
  `to_dict()`.
- `audit/orchestrator.py::_network_wide_findings`: for every (code, parameter)
  in the audit's counting defects, checks (a) the set of stations it touches
  equals the coverage model's own carrier set for that parameter
  (`model.series_grids` keys - not every station, a local fault, not systemic),
  and (b) the flagged cells are all *present* readings (checked by set
  membership against the frame's non-null cells) whose count clears a
  configured fraction gate.
- `config/thresholds.yaml`: new `network_wide_finding.min_fraction: 0.95`
  section, with a cited basis (tolerates the ordinary handful of absent cells
  a real drop always carries, without admitting a merely common code).
- `report/render.py`: a new "Network-wide findings" markdown section, between
  "Defects by reason code" and "Coverage" - golden `audit.md` regenerated
  (config hash changes with any `thresholds.yaml` edit, so this test always
  needs a regen after touching that file - see [[golden-fixture-config-hash-gotcha]]).
- `tests/unit/test_network_wide_findings.py` (new, 5 tests): a real finding
  when every carrying station is fully affected; no finding when only one
  station is affected even at 100% locally; no finding when the fraction is
  below the gate; **absence-pattern codes are never reported, regardless of
  how many stations or cells they touch** (see the bug below); the field
  survives the `to_dict()` round-trip.

**Frontend** (`features/audit/AuditReportView.tsx`): `networkWideFindingsFromSummary`
parses `summary.network_wide_findings` the same defensive way
`tallyFromSummary` already parses `defects_by_code`; a new panel between the
defect-rate definition and the by-code breakdown lists each finding
("R10 affects CO2 at all 16 stations that carry it — 10,627 of 10,627
readings (100.0%)"), links to its evidence, and says plainly "None in this
run" when the field is present but empty - distinct from omitting the panel
entirely when the field is absent altogether (an older run, recorded before
this feature existed). Three new tests in `AuditReportView.test.tsx`.

#### A real bug this update's own verification caught

Running `run_audit()` directly against the real `data/raw` frame (see
"Verification" below) - not just the synthetic test fixture - surfaced a
genuine defect in the first implementation: dividing by *expected* cells
(present + absent, from the coverage model) rather than *present* readings
made R01 (`ROW_ABSENT`) produce fractions **over 1.0** for NO and NOx
(`fraction=1.77`, `1.75`) - nonsensical, since R01's own flagged count *is*
the absent-cell count, disjoint from whatever's present. Switching the
denominator to present-reading counts fixed R10/CO2 correctly but would have
let R01 or R02 slip through as a "network-wide finding" whenever a parameter's
completeness happened to be low enough - a category error, since an absence
is a completeness fact (already reported separately by the coverage summary),
not a "these readings are wrong" fact. Fixed generically: a code's flagged
cells must be a subset of the frame's own present-value cells (checked by set
membership, not a hardcoded code list) before it's eligible at all. Guarded by
`test_absence_pattern_codes_are_never_reported_as_network_wide`, which
reproduces the shape of the bug (both stations fully affected, values varied
so R12 zero-variance doesn't also fire) rather than merely re-asserting the
fixed behaviour.

### 2. Attention parameter-mismatch cue

`GraphAttention` (`EvidencePanel.tsx`) already printed `target {parameter}` in
its header caption, but nothing distinguished "this matches what you're
looking at" from "this is a completely different pollutant's network
structure" beyond that one small line. Since the network only ever trains one
HST-GAT at a time, viewing a CO2 defect's evidence while the trained target is
PM10 (the real drop's actual configuration) is not a hypothetical - it is the
default case for every non-PM10 defect.

- `parameterMismatch = data.target_parameter !== defect.parameter`; when true,
  the caption switches from `text-text-tertiary` to `prov-state-degraded`
  (amber, the brand's own "ambiguity" colour) and a explicit note renders below
  the header: "This overlay is trained to reconstruct {target}, not
  {parameter} - read it as {target} network structure, not evidence about this
  {parameter} reading." Applied to both the populated-edges branch and the
  empty-edges branch (a mismatch and "no edges" are orthogonal facts, worth
  showing together when both are true).
- Two new tests: the mismatch note renders with the right wording when
  defect 3 (NO) is viewed against a PM10-targeted overlay, and does *not*
  render when the default defect (PM10) matches the overlay's own target.

## The Network Map question

Investigated rather than blindly re-fixed. The map itself renders correctly in
every test performed this session (stations, markers, basemap, legend all
present in fresh headless-browser loads). The most likely explanation for
what was seen: `NetworkMap.tsx` calls the *same* `useAttentionOverlay()` hook
the Evidence tab's attention card does (it drives the map's own "Learned
attention (HST-GAT)" toggle) - so the SIGSEGV update-17 found and fixed
(`OMP_NUM_THREADS=1` in `make api`/`api-bg`) was reachable from the Network Map
independently of the Evidence tab, and was reachable *before* that fix existed
or before a locally-running API process had been restarted to pick it up. A
crashed API mid-session, followed by a page reload, would show exactly
"the map no longer shows" (station/quality queries failing against a dead
process) - not a rendering bug in the map component itself.

Reproduced the underlying mechanics directly this session: confirmed the API
process is currently stable through repeated direct and browser-driven calls
to `/v1/graph/attention` (the endpoint takes a genuinely slow ~5.7-5.8s per
call, every call, with no caching - flagged below, not fixed here, since it is
a separate performance question from the crash). No code change was made for
this item; if the map still doesn't render after restarting the local API via
`make api-bg` (which picks up update-17's fix), that would point at something
this session did not reproduce and is worth a fresh, separate report.

## Test gate

**Backend** (`make check`): 691 passed, 2 deselected (+5 for
`test_network_wide_findings.py`). Coverage 90.58% (gate 88%). Contract check
clean (`network_wide_findings` lives in the untyped `summary` JSON blob, not a
typed response field, so no schema/contract regeneration was needed).
`test_audit_md_matches_golden`, `test_audit_recovers_every_injected_code_exactly`,
`test_markdown_is_deterministic_for_fixed_now` all re-verified green after the
`thresholds.yaml` edit and the golden regen.

**Frontend** (`pnpm test:coverage`): 295 passed (25 files, +5 over update-17's
290). Coverage 94.78% lines / 85.02% branches / 84.81% functions (gate 80%).
`pnpm lint` / `pnpm typecheck` clean.

**Verification against the real drop**: `run_audit()` called directly against
`loaders.load_data('data/raw')` (no API/DB round-trip) confirms exactly the
expected single finding - `NetworkWideFinding(reason_code='R10',
parameter='CO2', station_count=16, flagged_readings=10627,
total_readings=10627, fraction=1.0)` - both before the fix was needed (where
it wrongly also produced impossible R01 entries) and after (clean). A full
browser-driven check of the Audit report against the real, *stored* DB run was
deliberately not performed - the currently-loaded run predates this feature
and picking it up requires `db reset --yes` + `db load` (destructive to the
local dev database's residuals/adjudication state, recoverable but not
free), which felt disproportionate given the strength of the direct
computation + comprehensive unit/component-test evidence already in hand.
Flagged for the record rather than silently skipped.

## Deviations from the prompt

- The R01 denominator bug (above) was not part of the ask - it surfaced during
  this update's own verification step and was fixed in the same pass rather
  than shipped and reported separately, since leaving a demonstrably-wrong
  fraction (`>1.0`) in a feature whose entire point is honest reporting would
  have been a standing-rule violation on day one.
- No live browser verification against the real, DB-stored audit run (see
  above) - a deliberate, disclosed scope cut, not an oversight.

## Flag for review

- **`/v1/graph/attention` takes ~5.7-5.8 seconds per call, every call, with no
  server-side caching** - confirmed by direct repeated `curl` timing this
  session. Not a stability bug (the process survives it now), but a real
  latency a user will feel every time they open a defect's evidence view or
  toggle the map's learned-attention layer, since nothing memoises the HST-GAT
  forward pass between requests for the same underlying model + data. Worth a
  decision on whether to cache the overlay (it only changes when new data is
  loaded or the model is retrained) rather than recomputing it per request.
- The currently-loaded real-drop audit run in the local dev database predates
  this update's `network_wide_findings` field (see "Test gate" above) - whoever
  next reloads the real drop (`db reset --yes` + `db load --source data/raw`)
  will see it appear for the first time in the live Audit report, not before.
