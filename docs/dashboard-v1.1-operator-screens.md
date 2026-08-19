# Dashboard v1.1 — the operator screens

Phase 3, after the flag review. **Supersedes
`dashboard-v1.0-operator-screens.md`.**

What changed in v1.1: trust reason codes now carry machine-readable evidence, so
they render as sentences rather than as sentences with an em dash where a figure
belongs; the audit report's per-code breakdown reads the engine's own tally instead
of counting a truncated page; and the contract drift check moved to a workflow that
cannot be skipped. The gaps list at the end is corrected accordingly.

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

`make web-contract-check` re-derives and diffs. The check runs in `ci.yml`, which
has **no `paths:` filter**, so it cannot be skipped: a path filter only protects
against the changes someone thought to list, and editing `trust/score.py`'s
`to_dict` alters the served contract without touching a single frontend path. An
architecture test asserts the job stays in an unfiltered workflow.

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

## Where the numbers on each screen come from

Every figure is either served by the engine or derived on screen from the engine's
own ledger with the derivation stated beside it. The two categories:

**Served, authoritative.** The defect rate and its numerator and denominator, the
conventional completeness figure, the per-code defect breakdown
(`summary.defects_by_code`, computed over every row when the audit ran), trust and
its components, and every reason code's evidence.

**Derived on screen, and labelled.** Uptime, as `1 - (R01 absent cells / expected
cells)` over the selected window; and the last calibration epoch, as the newest R15
discontinuity the audit detected. The API serves neither. Both derivations rest on
two properties of the data that are asserted on the *backend* by
`tests/unit/test_uptime_assumptions.py` — that every station series is hourly, and
that R01 is one flag per absent cell — so if either stops holding, a test fails and
names this file rather than the dashboard quietly reporting a wrong percentage.

List queries follow the cursor to exhaustion (capped at 100 pages), so a count is a
count. Counting one 500-row page is what made the audit report show 6 of 13 reason
codes on the demo corpus, with R10 at 145 instead of 336.

## Known gaps, carried into later phases

- **The wind-conditioned edge layer** is built, disabled, and explained. Phase 4.
- **Traffic counter and bus stop layers** are ingested by the phase-1 abstraction but
  not placed on the map.
- **The basemap** ships no tile data by design — see ADR 0005. Whether the demo
  should point at a real tile source is an open decision, escalated at the phase-3
  flag review; note that `VITE_MAP_STYLE_URL` is inlined at build time, so switching
  it needs a rebuild and cannot be flipped at the venue.
- **Uptime and last-calibration should eventually be served**, not derived. They are
  correct and tethered today, but a windowed aggregate belongs in the audit engine.
- **A recorded, driven demo capture** is outstanding — see
  `docs/demo/checkpoint-3-capture-checklist-v1.0.md`.
