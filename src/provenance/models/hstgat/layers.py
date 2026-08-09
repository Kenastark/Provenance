"""The heterogeneous graph-attention primitives the HST-GAT is built from.

The attention layer is hand-rolled rather than PyG's ``GATConv`` for one reason that
matters to the phase brief: the wind-conditioned edge weight must enter as an
**additive pre-softmax bias**, not a hard mask and not a learned edge-feature
transform, so that (a) zeroing the bias recovers a plain heterogeneous GAT exactly,
and (b) increasing the bias monotonically shifts attention toward downwind
neighbours. Both are testable properties of *this* arithmetic, and ``GATConv``'s
``edge_attr`` path gives neither cleanly. Everything here is pure torch plus
``torch_geometric.utils.softmax`` (segment softmax) — no compiled companion wheels
(ADR 0009), deterministic on CPU (standing rule 8), and permutation-equivariant by
construction (every op is indexed by node, never by row order).
"""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torch_geometric.utils import softmax as segment_softmax


class GATMessage(nn.Module):
    """Single-relation graph attention with an additive pre-softmax bias.

    For a directed edge ``s -> d`` the attention logit is the standard decomposed GAT
    form ``LeakyReLU(a_src·Wh_s + a_dst·Wh_d)`` plus ``beta * bias[e]``. The bias is
    the wind-conditioned edge weight for the wind relation and 0 (i.e. no bias) for
    every other relation; ``beta`` is a scalar (a learnable parameter in the full
    model). With ``beta == 0`` or an all-zero bias, the logit is exactly a plain GAT's
    — this is the property the "zeroing recovers HetGAT" test pins.

    Attention is a segment softmax over the incoming edges of each destination node,
    per head; the message is the attention-weighted sum of projected source features.
    """

    def __init__(self, in_dim: int, out_dim: int, heads: int, *, negative_slope: float = 0.2):
        super().__init__()
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.heads = heads
        self.lin = nn.Linear(in_dim, heads * out_dim, bias=False)
        self.att_src = nn.Parameter(torch.empty(heads, out_dim))
        self.att_dst = nn.Parameter(torch.empty(heads, out_dim))
        self.leaky = nn.LeakyReLU(negative_slope)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.xavier_uniform_(self.lin.weight)
        nn.init.xavier_uniform_(self.att_src)
        nn.init.xavier_uniform_(self.att_dst)

    def forward(
        self,
        x_src: Tensor,
        x_dst: Tensor,
        edge_index: Tensor,
        *,
        bias: Tensor | None = None,
        beta: Tensor | float = 0.0,
        return_attention: bool = False,
    ) -> tuple[Tensor, Tensor | None]:
        """Aggregate messages into destination nodes.

        Args:
            x_src: ``[Ns, in_dim]`` source node features.
            x_dst: ``[Nd, in_dim]`` destination node features (defines the output rows).
            edge_index: ``[2, E]`` with row 0 = source index, row 1 = destination index.
            bias: ``[E]`` additive pre-softmax bias per edge (e.g. the wind weight), or None.
            beta: scalar scaling the bias; ``0`` recovers a plain GAT.
            return_attention: also return per-edge attention ``alpha`` of shape ``[E, heads]``.

        Returns:
            ``(out [Nd, heads*out_dim], alpha [E, heads] | None)``.
        """
        n_dst = x_dst.size(0)
        proj_src = self.lin(x_src).view(-1, self.heads, self.out_dim)  # [Ns, H, out]
        proj_dst = self.lin(x_dst).view(-1, self.heads, self.out_dim)  # [Nd, H, out]

        if edge_index.numel() == 0:
            out = x_dst.new_zeros((n_dst, self.heads * self.out_dim))
            alpha = x_dst.new_zeros((0, self.heads)) if return_attention else None
            return out, alpha

        src_idx = edge_index[0]
        dst_idx = edge_index[1]
        # Decomposed attention logits, per head: a_src·Wh_s + a_dst·Wh_d.
        e_src = (proj_src * self.att_src).sum(dim=-1)  # [Ns, H]
        e_dst = (proj_dst * self.att_dst).sum(dim=-1)  # [Nd, H]
        logits = self.leaky(e_src[src_idx] + e_dst[dst_idx])  # [E, H]

        if bias is not None:
            beta_t = beta if isinstance(beta, Tensor) else logits.new_tensor(beta)
            logits = logits + beta_t * bias.view(-1, 1)  # additive, pre-softmax

        alpha = segment_softmax(logits, dst_idx, num_nodes=n_dst)  # [E, H]
        messages = proj_src[src_idx] * alpha.unsqueeze(-1)  # [E, H, out]
        out = proj_src.new_zeros((n_dst, self.heads, self.out_dim))
        out.index_add_(0, dst_idx, messages)
        out = out.reshape(n_dst, self.heads * self.out_dim)
        return out, (alpha if return_attention else None)


class GCNMessage(nn.Module):
    """A plain (non-attentional) mean-aggregation message layer for the GCN baseline.

    Symmetric-normalised neighbour mean of a linear projection — the homogeneous GCN
    the blueprint asks for as a comparison point. No attention, no wind bias, no
    per-relation heads: exactly the ablation the model card contrasts against.
    """

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin = nn.Linear(in_dim, out_dim, bias=False)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.xavier_uniform_(self.lin.weight)

    def forward(self, x_src: Tensor, x_dst: Tensor, edge_index: Tensor) -> Tensor:
        n_dst = x_dst.size(0)
        proj = self.lin(x_src)
        if edge_index.numel() == 0:
            return x_dst.new_zeros((n_dst, proj.size(-1)))
        src_idx = edge_index[0]
        dst_idx = edge_index[1]
        out = proj.new_zeros((n_dst, proj.size(-1)))
        out.index_add_(0, dst_idx, proj[src_idx])
        # Degree-normalise so a well-connected node is not simply louder.
        deg = proj.new_zeros((n_dst,))
        deg.index_add_(0, dst_idx, torch.ones_like(dst_idx, dtype=proj.dtype))
        deg = deg.clamp(min=1.0)
        normalised: Tensor = out / deg.unsqueeze(-1)
        return normalised
