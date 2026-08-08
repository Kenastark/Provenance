# Dashboard v1.0 — the operator screens

Phase 3. Supersedes nothing; this is the first version of this document.

## What it is

The operator-facing second screen for the Green Sentinel network. Not a replacement
for the public dashboard: this is the screen that scores every reading for
genuineness and shows the working.

Five routes:

| Route | Screen | Blueprint |
|---|---|---|
| `/` | Network map (primary) | §9.1 |
| `/quality` | Data quality monitor | §9.4 |
| `/timeline` | Event timeline | §9.2 |
| `/evidence` | Evidence panel | §9.3 (partial) |
| `/audit` | Audit report | phase-1 report, rendered natively |

## The rules this screen exists to keep

**A trust score never renders without its breakdown and at least one reason code.**
Enforced three times over: the API cannot serialise a bare score, `TrustChip`'s
`reasonCodes` prop is a non-empty tuple so omitting it does not compile, and the
component throws at runtime if data arrives without one. `src/__tests__/TrustChip.test.tsx`
asserts all three.

**Colour is never the only channel.** Every trust state carries a distinct shape
(`--prov-shape-*`), so the map reads correctly for a colourblind operator, in
greyscale, and on a projector that has eaten the saturation.

**No number is written down that the data should produce.** The defect rate, the
completeness figure, station counts, uptime, the last calibration epoch — every one
is computed, and the two the API does not serve are derived on screen from the audit
ledger with the derivation stated beside the number. The e2e asserts the marker count
against what the API returns, never against a literal.

**Nothing reaches the public.** [Acknowledge] and [Dispatch] write to a local queue
in the browser. `lib/queue.ts` deliberately exports no send function, and a test
asserts it — until phase 7 records a human sign-off there is no transport out.

**Later phases get empty slots, not fabrications.** Event verdicts read "pending
adjudication" until the phase-4 graph can decide one. SHAP (phase 5) and attention
(phase 6) render as explicit "not yet computed" panels.

## The contract with the backend

Nothing about the API is restated by hand. `scripts/gen_frontend_contract.py`
generates three artefacts into `apps/web/src/api/`:

- `openapi.json` → `schema.d.ts` (via `openapi-typescript`) — every request and
  response type.
- `reason-codes.generated.ts` — the registry, including the operator sentence for
  every code.
- `tokens.generated.ts` — the trust thresholds and shape tokens, parsed out of
  `design/tokens/tokens.css`, so the marker colour and the classification cannot
  disagree.

`make web-contract-check` re-derives and diffs. CI runs it: if a route, a schema, a
reason code, or a token changes without the client being regenerated, the build
fails rather than the dashboard quietly describing a system that no longer exists.

## Time windows

The corpus is a historical drop, not a live feed. "Last 24 hours" is therefore 24
hours back from **the newest reading in the network**, not from the wall clock and
not from the audit run's `generated_at`. A May corpus audited in August has a
perfectly healthy run whose trailing week contains no readings at all; anchoring on
either of the other two makes every screen come up empty while nothing is wrong.

## Theme

Dark is the default — this is a map-first screen people sit in front of for a shift.
Light is a full implementation, not an inversion: the token file redefines the state
colours for light because Sentinel Green and Alert Amber at their core values do not
pass contrast as text on white. "System" is a real third option.

The approved horizontal lockup inks its wordmark in the brand's near-black, which is
invisible on the dark theme. `design/logo/provenance-lockup-horizontal-reversed.svg`
is the same artwork with the wordmark in `--prov-white`, generated from the original
by `scripts/gen_reversed_lockup.py` and asserted geometry-identical by a brand test.

## Running it

    make demo          # stack up, 18-station demo corpus loaded and audited, dashboard opens
    make web           # dashboard dev server alone
    make web-test      # component tests with the coverage gate
    make web-e2e       # Playwright: demo path, a11y, visual, responsive
    make web-visual-linux   # regenerate the Linux visual baselines (Docker)

Visual baselines are committed per platform (`…-chromium-darwin.png`,
`…-chromium-linux.png`) because macOS and Linux rasterise text differently; one
platform's baseline can never match the other's run. Both sets are kept so the
visual gate is real on a laptop and in CI.

The dashboard talks to `VITE_API_BASE_URL` (default `http://localhost:8000`) with
`VITE_API_KEY` (default the documented local-dev operator key). A real deployment
sets both, plus `PROVENANCE_CORS_ORIGINS` on the API.

## Known gaps, carried into later phases

- **Trust reason codes have no machine-readable evidence.** The trust engine computes
  the numbers behind T02/T03/T05 but the API returns them as prose in `notes` and
  `components[].detail` rather than as an evidence dict. The UI fills what it can
  (T01's defect count) and renders an em dash plus the component detail for the rest.
  Adding an `evidence` field to the trust payload would close this properly.
- **The wind-conditioned edge layer** is built, disabled, and explained. Phase 4.
- **Traffic counter and bus stop layers** are ingested by the phase-1 abstraction but
  not placed on the map.
- **The basemap** ships no tile data by design — see ADR 0005.
