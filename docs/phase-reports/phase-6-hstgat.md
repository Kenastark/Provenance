## Phase 6 — HST-GAT, conformal prediction, learned propagation

Date: 2026-08-09. Branch: `phase-6-hstgat`. Tag: `v0.6.0`.

### What was built

The research contribution, sequenced last so a slip would have cost ambition, not
viability. A heterogeneous spatio-temporal graph-attention network (HST-GAT, §6.4) with
a per-`EnvStation` GRU memory learns a graph-conditioned expectation of each station's
reading from its wind-weighted neighbours, trained as a masked autoencoder with a
Gaussian NLL (mean **and** variance). Its outputs are wrapped with hand-rolled split
conformal intervals (§7.7), its attention is exported as weighted map edges (§8), and it
can stand in for the Phase-4 analytic expectation in the propagation adjudicator **behind
a feature flag, with an automatic analytic fallback**. `GraphSnapshot.to_hetero_data()`
now materialises a real PyG `HeteroData` behind the unchanged node/edge-table interface.

### Test gate

`make check` green: ruff, `mypy --strict`, and the full pytest suite — **449 passed,
92.04% coverage** (gate 88%), CPU-only, ~3 min. The phase's specific gate items each
have a test:

- **Overfit-a-tiny-batch** — drives standardised reconstruction MSE to ~1e-7 on 8 cells.
- **Shape/dtype for every layer and every edge type** — all five relations exercised.
- **Permutation invariance** — relabelling node indices permutes predictions identically.
- **Determinism** — two seeded builds and two seeded trainings are byte-identical (CPU).
- **No NaN/inf on the real corpus shape** — a full forward on 18 stations × 720 hours.
- **Attention bias** — zeroing the wind bias recovers a plain HetGAT; raising it
  monotonically increases the wind-connected neighbour's attention.
- **Conformal coverage** — 90% nominal → empirical inside [85%, 95%] on a held-out block.
- **Fallback** — with the artefact deleted, the adjudicator returns the Phase-4 analytic
  verdict and the evidence bundle records `expectation_provenance = "analytic"`.
- **KER11 regression** — the demo characterization test is unchanged (the analytic
  default reproduces Phase-4 verdicts byte-for-byte).
- **Standing rule 4** — a test scans the model's metrics and the evidence bundle to prove
  no propagation accuracy/F1 is reported anywhere.

### Deviations from the prompt

- **ADR numbered 0009, not 0006.** The brief asked for `0006-pyg-install.md`, but `0006`
  was already taken by `0006-fetched-local-basemap.md` (phase 3). ADRs are sequential and
  immutable (`docs/decisions/README.md`), so this is `0009` — the same convention phase 4
  used when its `0004` was taken (see the note in `0007-wind-edges.md`). Content is exactly
  the PyG-install decision requested.
- **Learned propagation is wired by dependency injection, not a direct import.** The
  layering test forbids `graph` from importing `models`, so the adjudicator could not
  simply call the HST-GAT. Instead `graph` defines an `ExpectationProvider` Protocol with
  an `AnalyticExpectation` default; `models` implements the learned one; the CLI injects it
  behind the flag. This is a stronger design than the literal "swap the call" and keeps the
  import graph acyclic. The analytic default reproduces Phase-4 byte-for-byte.
- **The attention map overlay ships as a backend export, not a new dashboard layer.** The
  attention weights are exported as structured, map-ready edges (`attention_overlay`) and
  written to the adjudication reports; the live map overlay is demoed from that export. I
  deliberately left `apps/web` and the API schema untouched this phase so the frontend
  contract, e2e and visual-regression CI jobs stay green on an `src/provenance/**` change.
  See "Flag for review".

### Flag for review

- **The demo's headline "attention edges lighting up toward downwind neighbours" is
  delivered as data, not yet as pixels on the MapLibre canvas.** The export
  (`models/hstgat/attention.py`) is complete and tested and the map can consume it, but
  wiring it into `apps/web` would drift the pinned Playwright visual baselines and pull the
  full e2e job onto the critical path for a merge. If the stage demo needs the overlay
  rendered live rather than shown from the exported JSON, that is a small, contained
  frontend task for a follow-up — and it should regenerate both the darwin and the pinned
  Linux baselines in the same change.
- **The learned propagation path is genuinely useful only on a wind-carrying corpus with
  real events.** On the seeded/synthetic fixtures the wind edges are calm or degenerate, so
  the learned verdict is exercised for its *mechanism and fallback*, never for accuracy
  (which we are forbidden to quote anyway). The number that matters on stage — the KER11
  verdict — still comes from the analytic path by default; `--learned` is the opt-in
  research demonstration. This is the honest posture, but worth a human eye before anyone
  reads the learned path as "better" rather than "different and calibrated".
- **Conformal coverage is validated tightly on a synthetic regression (0.907 at 90%
  nominal) and reported on the HST-GAT's own held-out reconstruction in the model card.**
  The guarantee is distribution-free given exchangeability; for a short time series the
  achieved number moves with the corpus, so the card reports it as measured, not promised.
