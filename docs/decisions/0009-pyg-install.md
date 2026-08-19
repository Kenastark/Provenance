# 0009 - PyTorch Geometric install: pure-Python, CPU-first, MPS-optional

**Status:** Accepted (2026-08-09)

> Note on numbering: the phase-6 brief asked for this ADR as `0006-pyg-install.md`,
> but `0006` was already taken by `0006-fetched-local-basemap.md` (phase 3). ADRs
> are numbered sequentially and never renumbered (see `docs/decisions/README.md`),
> so this is `0009`, the next free number. The content is exactly the PyG-install
> decision the brief specified.

## Context

Phase 6 adds the neural stack (HST-GAT, §6.4) on top of the phase-4 graph. That
means a hard dependency on PyTorch and PyTorch Geometric. Two facts make this a
decision worth recording rather than a `uv add` nobody remembers:

1. **PyG on Apple Silicon is fragile.** The classic pain is the compiled companion
   wheels — `torch-scatter`, `torch-sparse`, `torch-cluster` — which historically
   had to match the exact torch build and CUDA/CPU variant, and which frequently had
   no arm64 macOS wheel at all, forcing a from-source build against the right
   `torch` headers. Getting that wrong is hours lost to linker errors.
2. **CI is CPU-only and time-budgeted** (Ubuntu runner, no GPU), while local
   development is on an Apple Silicon Mac where MPS is available. The install has to
   be identical and reproducible in both, or a model that trains locally fails to
   even import in CI.

## Decision

**Install `torch` and `torch-geometric` only — no `torch-scatter`/`torch-sparse`/
`torch-cluster` — and rely on PyG's pure-Python scatter fallback.** Modern PyG
(>= 2.3) does not require the compiled extensions for the operators this phase uses:
it dispatches to `torch.scatter_reduce`/`torch.index_select`, which ship with core
torch on every platform. The hand-rolled heterogeneous attention layer
(`models/hstgat/layers.py`) uses `torch_geometric.utils.softmax` (segment softmax)
and `torch.zeros(...).index_add_`, both pure-torch, so nothing in the model path
touches a compiled companion wheel.

**The exact working install, recorded so it can be reproduced byte-for-byte:**

| Package | Version | Notes |
| --- | --- | --- |
| Python | 3.12 | `.python-version`, pinned repo-wide |
| `torch` | 2.8.0 | PyPI wheel; arm64-macOS build carries MPS, Linux build is CPU |
| `torch-geometric` | 2.6.1 | pure-Python; no companion wheels installed |

Pinned in `pyproject.toml` as `torch>=2.2,<2.9` and `torch-geometric>=2.5,<2.7`,
and frozen precisely in `uv.lock` (the file CI installs from). The `<2.9` / `<2.7`
ceilings keep a future resolver from silently pulling a major that changes the
attention or scatter semantics the tests pin.

**Device policy.** Everything trains and runs on CPU by default, which is what CI
uses and what makes two runs byte-identical (standing rule 8). MPS is *opt-in*
locally via `PROVENANCE_TORCH_DEVICE=mps`, and the training loop falls back to CPU
with a logged warning if the requested device is unavailable, so a config copied
from a Mac to the runner degrades gracefully rather than crashing. Determinism is
only guaranteed on CPU; the model card says so.

## Consequences

- A fresh `uv pip install -e ".[dev]"` brings up the full neural stack on both
  arm64 macOS and x86-64 Linux with no extra index URL, no `--find-links`, and no
  build step. Verified: `HeteroData`, `GATConv`, and `torch_geometric.utils.softmax`
  all import and run a forward+attention-export pass on CPU.
- We give up the marginal speed of the compiled scatter kernels. On this problem
  (16 stations, 720 timesteps, a deliberately small model — §5.1) that is
  irrelevant: a full training run is seconds on CPU, and the CI overfit-a-tiny-batch
  gate is sub-second.
- If a future phase needs the compiled kernels (much larger graphs, GPU training),
  they are additive: install the matching `torch-scatter`/`torch-sparse` for the
  pinned torch version from the PyG wheel index. Nothing in the model code has to
  change — PyG picks the compiled path up automatically when it is present.
- The neural stack is a real dependency of the `models` layer, but the rest of the
  pipeline never imports torch: `graph/snapshot.py` stays torch-free and materialises
  a `HeteroData` only through a lazy import in `to_hetero_data()`, so the audit,
  trust and statistics layers still import and run on a machine without torch.
