# Model card — HST-GAT v1

**Type:** Heterogeneous spatio-temporal graph-attention network (§6.4), trained as a
masked autoencoder with a Gaussian NLL. **Neural.** The analytic B3 adjudicator has its
own card (`propagation-adjudicator-v1.md`); this one is the learned model that can stand
in for its expectation behind a feature flag.

**Version:** v1 · **Date:** 2026-08-09 · **Config:** `config/models.yaml` (`hstgat`,
`conformal` blocks; `status: provisional`) · **Install:** ADR 0009.

> The per-training auto-generated card (`hst-gat-v1-<checksum>.md`, gitignored) carries
> the exact metrics of a specific run against a specific corpus. This hand-written card
> describes the model *design* and reports representative numbers from a controlled
> 18-station × 480-hour synthetic corpus; the parameter count is fixed by the
> architecture and does not depend on the corpus.

## What it does

For every `EnvStation` and every hour it predicts a **mean and a variance** for the
target pollutant (PM10 by default), conditioned on the wind-weighted graph:

    h_i(t) = GRU( h_i(t-1), HetGAT_aggregate({h_j(t) : j ∈ N(i)}, edge_weights(t)) )

Trained by masking a fraction of known values and reconstructing them from neighbours
and history (masked autoencoder), scored with a **masked Gaussian NLL** so the predicted
σ is meaningful, not decorative. That graph-conditioned expectation is what the
propagation adjudicator can use in place of the analytic plume prior (`--learned`), and
what split conformal turns into a calibrated interval.

## Architecture and parameter count

| | |
|---|---|
| Hidden width | 16 |
| Attention heads (per edge type) | 2 |
| Edge types with type-specific attention | 5 (spatial, wind, weather, road, transit) |
| Temporal memory | one shared-weight `GRUCell`, per-station hidden state |
| Head | linear → (mean, softplus(var) + floor) |
| **Total trainable parameters** | **3,299** |
| GCN baseline parameters | 2,018 |

**Small-data justification (§5.1).** The binding constraint is ~720 timesteps per
station: with 16–18 stations that is a small dataset by neural standards. 3,299
parameters is deliberate — capacity is spent on *structure* (heterogeneous attention, a
per-station GRU, wind as a prior) rather than *width*, so the model generalises rather
than memorises. Training is forward-chaining only (time-blocked CV, standing rule 7),
fully seeded and byte-identical on CPU (standing rule 8, ADR 0009).

## The wind bias

The wind-conditioned edge weight enters the wind relation's attention as an **additive
pre-softmax bias**, scaled by a learnable `β` — a *prior*, not a hard mask, so the model
can override the physics when the data warrants it. Two properties are pinned by tests:

- `β = 0` (or a zero bias) recovers a **plain HetGAT** exactly.
- Increasing `β` **monotonically increases** the attention paid to the wind-connected
  (downwind-aligned) neighbour.

## Conformal coverage (§7.7)

Split conformal with the normalised score `|y − ŷ| / σ`, calibrated on a **held-out
time block** (never a random slice), α = 0.1:

| Nominal coverage | Achieved (empirical) | n (calibration / test) | interval |
|---|---|---|---|
| 90% | **89.7%** | 2,160 / 2,160 | `ŷ ± 2.55·σ` |

Inside the phase gate's [85%, 95%] band. The guarantee is distribution-free given
exchangeability; for a short time series the achieved number moves with the corpus, so
it is reported as **measured**, not promised, and regenerated into the auto-card on every
`prov models train-hstgat`.

## GCN baseline comparison

The blueprint asks for a plain GCN (no attention, no wind, no heterogeneity) as a
control. On the controlled synthetic corpus (uniform westerly wind, diurnal background,
**no genuine wind-carried plume events**):

| Model | Held-out reconstruction RMSE (physical) | Params |
|---|---|---|
| HST-GAT | 7.52 | 3,299 |
| GCN baseline | 7.35 | 2,018 |

**Read this honestly:** on a corpus with no real propagation to exploit, the attention
and wind machinery buy nothing over a plain graph convolution — the two are within noise,
and the baseline is even marginally ahead. The HST-GAT's advantage is *designed to appear
on real, wind-carried events*, exactly the regime we cannot quantify with this few real
positives (standing rule 4). The value it adds today is architectural and inspectable:
attention that a human can read, and a calibrated σ — not a reconstruction-error win on a
corpus without plumes.

## Honest limitations

- **No headline accuracy or F1 for the propagation validator** (standing rule 4). With
  this few real corroborated events such a number would describe the synthetic injection
  process, not the world. Reported instead: reconstruction NLL/RMSE, per-case evidence in
  the adjudication bundle, and calibrated intervals. A test enforces this.
- **The auxiliary node types carry no confirmed time-varying features yet** (Enclod/GTFS
  unconfirmed, ADR 0003). Their attention heads are architecturally present but
  data-limited, represented by learned placeholder embeddings — never invented signal
  (standing rule 2).
- **Determinism is guaranteed on CPU only** (ADR 0009); an MPS/GPU run may differ in the
  last bits and is opt-in.
- **The learned path is opt-in and falls back to the analytic prior** when no artefact is
  loaded, with the fallback recorded in the evidence bundle (standing rule 6). The demo's
  default KER11 verdict still comes from the analytic adjudicator.
