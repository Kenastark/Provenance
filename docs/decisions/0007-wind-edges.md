# 0007 - Wind-conditioned edges are a plume approximation, not a dispersion model

**Status:** Accepted (2026-08-09)

> Note on numbering: the phase-4 brief asked for this ADR as `0004-wind-edges.md`,
> but `0004` was already taken by `0004-api-auth-phase2.md` (phase 2). ADRs are
> numbered sequentially and never renumbered, so this is `0007`, the next free
> number. The content is exactly the wind-edge decision the brief specified.

## Context

Phase 4 makes the graph *wind-aware*: the weight of the edge from station *i* to
station *j* depends on the wind at time *t*, so that "downwind neighbour" becomes a
computable, time-varying notion the adjudicator can lean on. The obvious question a
reviewer (or a judge, §16 critique 3) will ask is: **is this an atmospheric
dispersion model?** If we let anyone believe it is, we have oversold the system and
invited a comparison to Gaussian-plume or CFD tools we would lose.

We need a weight that:

- rises when *j* is downwind of *i* and falls off as it moves off-axis or upwind;
- falls off with distance;
- is cheap enough to recompute for the whole graph every timestep (< 100 ms);
- is deterministic and dependency-free now, and differentiable later (phase 6 puts
  a GAT on top of the same graph);
- is honest about what it is.

## Decision

**The wind-conditioned edge weight is a lightweight, differentiable approximation
of a Gaussian plume's footprint — explicitly NOT an atmospheric dispersion model.**
It is:

    w(i, j, t) = exp(-Δθ / sigma_angle) · f(|wind_speed(t)|) · g(distance(i, j))

- `exp(-Δθ / sigma_angle)` — a dispersion-cone term. `Δθ` is the wrapped angular gap
  between the i→j bearing and the direction the air is *travelling* (the reported
  meteorological "from" bearing + 180°). `sigma_angle` (default 25°) is the cone
  half-width. Maximum at dead-downwind alignment, ~0 off-axis or upwind.
- `f(s) = s / (s + s_half)` — a saturating response to wind speed. `f(0) = 0`, so a
  calm timestep collapses every wind edge to 0 *without evaluating the undefined
  calm-wind direction* — the graph stays finite (no NaN, no division by zero).
- `g(d) = exp(-d / d_decay)`, hard-cut to 0 beyond `max_neighbour_distance_km`, so
  the edge set is local and bounded.

Geometry is computed on a **sphere** (great-circle bearing and haversine distance),
not the WGS84 ellipsoid: over the network's ~15 km extent the azimuth error is
< 0.1° and the distance error < ~0.3%, far below what a cone weight needs, and the
sphere is deterministic and dependency-free (`graph/geometry.py`). The parameters
live in `config/graph.yaml`, marked `status: provisional` — they are
physically-reasoned defaults, **not** calibrated values, because there are far too
few real corroborated events to fit them (§16 critique 2).

Wind provenance is tracked per edge. Not every station measures wind (DEB-KER15
carries no wind sensors, confirmed in `schema_assumptions.yaml`), so a station with
no local reading falls back to the **city-level HungaroMet vector** — the circular
mean over the stations that did report — and the edge records whether its wind was
`station-local`, `city-fallback`, or `unavailable`. A bearing average is circular
(unit-vector mean), never arithmetic, so 350° and 10° average to 0°, not 180°.

## Consequences

- The pitch can say plainly what this is: a fast, transparent, physically-motivated
  proxy that ranks which neighbours a plume should reach and by how much. That
  honesty is a feature — it is the opposite of the black box the product exists to
  audit.
- No headline accuracy figure is reported for the adjudicator built on top of this
  (standing rule 4); see the model card.
- The same `GraphSnapshot` interface (node/edge tables over numpy) is what phase 6
  will back with a PyG `HeteroData`, so the neural stack inherits this edge without
  a caller changing.
- If real sub-metre geodesy or a genuine dispersion model is ever wanted, both are
  drop-in: swap `geometry.py` for pyproj, or add a second edge type alongside this
  one. Neither is needed to ship a defensible B3 demo.
