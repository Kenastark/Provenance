"""The expectation seam: what a downwind neighbour *should* show, and who computed it.

The phase-4 adjudicator asks one question of every downwind neighbour — *given the
event, how big a rise should reach here, when, and is it inside the horizon?* — and
compares that expectation to what the neighbour actually did. Phase 4 answered it with
the analytic plume approximation (:mod:`provenance.graph.propagation`). Phase 6 can
answer it with the learned HST-GAT forecast instead.

The catch is the layering (``tests/architecture/test_layering.py``): ``graph`` must
never import ``models``. So the swap is done by **dependency injection**, not import.
This module defines the interface (:class:`ExpectationProvider`) and the analytic
implementation (:class:`AnalyticExpectation`) here in ``graph``; the learned
implementation lives in ``models`` and satisfies the same Protocol structurally; and
whoever calls the adjudicator (the CLI, behind the feature flag) chooses which to
inject. The adjudicator itself imports neither the model nor torch.

Provenance is first-class: every expectation carries a ``provenance`` string
("analytic" | "hst-gat"), which the adjudicator records in the evidence bundle so a
human can always see which path produced a verdict (standing rule 6 — the fallback is
visible, never silent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from provenance.graph.edges import WindEdgeParams
from provenance.graph.propagation import PropagationParams, expected_arrival
from provenance.graph.topology import StationPoint
from provenance.graph.wind import WindVector

if TYPE_CHECKING:  # pragma: no cover - avoids a circular import at runtime
    from provenance.graph.adjudicate import CandidateEvent

ANALYTIC = "analytic"
LEARNED = "hst-gat"


@dataclass(frozen=True, slots=True)
class NeighbourExpectation:
    """What a plume from the event should do to one downwind neighbour.

    ``sigma`` is a predictive standard deviation and is ``None`` for the analytic
    provider (which is a point expectation, not a distribution); the learned provider
    fills it in and it feeds the calibrated interval. ``distance_km`` and
    ``bearing_deg`` are geometry — facts, identical whichever provider runs.
    """

    station_id: str
    distance_km: float
    bearing_deg: float
    arrival_delay_min: float
    expected_excess: float
    within_horizon: bool
    sigma: float | None = None
    interval: tuple[float, float] | None = None
    """A calibrated (split-conformal) interval on ``expected_excess`` — present only on
    the learned path, and only when a conformal calibrator was persisted with the model.
    ``None`` for the analytic prior (a point expectation with no distribution)."""


@runtime_checkable
class ExpectationProvider(Protocol):
    """Computes a :class:`NeighbourExpectation` for one (event, neighbour) pair.

    Structural: the analytic provider here and the learned provider in ``models`` both
    satisfy it, so the adjudicator depends on the interface, never on either module.
    ``provenance`` is a read-only property so a frozen-dataclass field satisfies it.
    """

    @property
    def provenance(self) -> str: ...

    def expect(
        self,
        source: StationPoint,
        neighbour: StationPoint,
        wind: WindVector,
        event: CandidateEvent,
        wind_params: WindEdgeParams,
        prop_params: PropagationParams,
    ) -> NeighbourExpectation: ...


@dataclass(frozen=True, slots=True)
class AnalyticExpectation:
    """The phase-4 analytic plume expectation, wrapped as an :class:`ExpectationProvider`.

    This is the adjudicator's default, and it delegates straight to
    :func:`provenance.graph.propagation.expected_arrival`, so injecting it reproduces
    the phase-4 behaviour byte-for-byte (the KER11 characterization test pins this).
    """

    provenance: str = ANALYTIC

    def expect(
        self,
        source: StationPoint,
        neighbour: StationPoint,
        wind: WindVector,
        event: CandidateEvent,
        wind_params: WindEdgeParams,
        prop_params: PropagationParams,
    ) -> NeighbourExpectation:
        arrival = expected_arrival(source, neighbour, wind, event.excess, wind_params, prop_params)
        return NeighbourExpectation(
            station_id=arrival.station_id,
            distance_km=arrival.distance_km,
            bearing_deg=arrival.bearing_deg,
            arrival_delay_min=arrival.arrival_delay_min,
            expected_excess=arrival.expected_excess,
            within_horizon=arrival.within_horizon,
            sigma=None,
        )
