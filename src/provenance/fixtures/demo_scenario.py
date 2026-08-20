"""Opt-in wind and plume/fault layer for the demo corpus.

The default synthetic corpus (``generator.py``) carries no meteorology at all, so
the wind-conditioned graph adjudicator has nothing to condition on and every event
reads AMBIGUOUS, and the deweather regressor has only calendar features to explain
PM10 with. This module is what ``prov fixtures make --with-weather --with-plume``
layers on top - never the default path, which stays byte-identical (CLAUDE.md rule
8 and the golden recovery ledger both depend on that).

Two pieces, applied in order by :func:`add_wind` then :func:`add_plume`:

* **Wind.** Every station but one gets ``Wind_Speed``/``Wind_Direction`` (the one
  exception mirrors the real network's confirmed gap: DEB-KER15 carries no wind
  sensors at all, ``schema_assumptions.yaml``). PM10 is coupled to wind speed with
  the same dilution coefficient as ``fixtures/weather.py``'s ``PM10`` spec - reused,
  not reinvented - so the deweather regressor has a real signal to recover.
  Everything here is a **deterministic period-12h sinusoid, no random noise** -
  the same shape ``generator._baseline`` already uses and for the same reason
  (its docstring: a pure diurnal sinusoid is mean-reverting inside every 12h
  window, so the R14 step-change CUSUM stays quiet). A noisy or 24h-period
  alternative was tried first and empirically tripped R14 on nearly every
  station - white noise alone has roughly a 50% chance of crossing this CUSUM's
  decision interval within a 336-hour series (its in-control average run length
  is ~465 samples), and a 24h period leaves each excursion on-side for a full
  12h, long enough to accumulate past the h=5 sigma decision interval. A pure
  period-12 sinusoid's CUSUM peaks at ~2.7 sigma regardless of amplitude or
  phase (the standardised shape is scale-invariant), which is why every series
  built here uses that shape.
* **Plume and fault.** One NO excursion above its 1000 µg/m3 physical ceiling (R07)
  at a source station, corroborated at every station the *real* wind-edge weight
  (``graph.edges.wind_edge_weight``) would call downwind - each raised to the exact
  attenuated, delayed excess ``graph.propagation.expected_arrival`` predicts for
  it. A second, identical-magnitude excursion at an unrelated station touches
  nothing else. Nothing about the adjudicator's verdict is hardcoded here: the
  corroborated event only reads GENUINE_EVENT because the planted evidence
  satisfies the same match-score arithmetic the adjudicator runs on real data, and
  the isolated one only reads LIKELY_FAULT because nothing corroborates it.

  This deliberately targets NO, not PM10. PM10 is the pollutant ``add_wind``
  couples to weather, and a first attempt planted the plume there too - a single
  excursion big enough to trip R07 is 40-70x the parameter's own baseline, and the
  deweather regressor's forward-chaining CV puts that hour in some fold's *test*
  set, where no weather feature can predict it and that fold's R² collapses (one
  run measured -19.6 on the fold containing it, dragging the mean to -4.9 - worse
  than the flat baseline this whole feature exists to fix). ``fixtures/weather.py``
  never hits this because its corpus is never audited; this one is. NO is not a
  deweather target (``config/models.yaml``'s pollutant list is PM10/NO2/O3/CO), so
  the plume/fault demonstration and the deweathering demonstration no longer
  compete for the same series.
"""

from __future__ import annotations

import numpy as np

from provenance.fixtures.generator import Ledger

WIND_SPEED_PARAM = "Wind_Speed"
WIND_DIRECTION_PARAM = "Wind_Direction"
_WIND_SPEED_UNIT = "km/h"  # the confirmed real-schema unit (thresholds.yaml basis note)
_WIND_DIRECTION_UNIT = "degrees"

# The station that carries no wind sensor at all - the synthetic stand-in for the
# real network's confirmed DEB-KER15 gap. Index into `stations`, not a station id,
# so it scales with whatever station count the caller asks for.
_NO_WIND_STATION_INDEX = 4  # STA-05

# PM10<->wind coupling: the dilution coefficient from fixtures/weather.py's
# `_PollutantSpec("PM10", ...)`, reused rather than reinvented. weather.py's other
# terms (boundary-layer height, noise calibrated to a `noise_ratio`) are not reused
# here: over a 14-30 day window the boundary-layer proxy's seasonal component is a
# slow, non-periodic drift (it completes under 10% of its 365-day cycle), and
# random noise has an honest ~50% chance of tripping the R14 CUSUM on its own (see
# the module docstring) - both are safe for weather.py's model-only corpus, which
# the audit never sees, but not for this one, which it does.
_K_WIND = -1.1

# Deterministic period-12h sinusoid parameters for the ambient wind series. Wind
# is a REGIONAL signal here, deliberately: every station shares the same phase and
# amplitude, with only a small per-station additive offset (mirroring
# fixtures/weather.py's `+ s_ix * 0.3` / `+ s_ix * 5`), not a per-station phase
# shift. A first attempt gave each station its own phase (like PM10's own
# `station_ix * 0.7`), which made wind_speed a de facto station fingerprint - the
# deweather model has no station-identity feature (deweathering assumes weather is
# a *shared* covariate), so at a wind_speed value characteristic of one station's
# phase but coincidentally visited by another, the model extrapolated wildly
# (predictions above 1000 against a true range under 50, one fold scoring
# R²=-22). A shared regional signal removes that confound and is also the more
# physically honest choice: stations 1-2 km apart do not run on independent wind
# clocks.
_WIND_SPEED_MEAN = 10.0
_WIND_SPEED_AMP = 6.0
_WIND_SPEED_PHASE = 2.4
_WIND_SPEED_STATION_STEP = 0.1  # km/h per station index - small, not a fingerprint
# A second, smaller period-5h term. Period 12 alone makes wind_speed a period-12
# function of t, exactly like PM10's own baseline - for a wind-coupled station the
# two compose into a THIRD period-12 sinusoid, so wind_speed ends up in a strict
# 1:1 relationship with PM10 that is *different* per station (each carries its own
# baseline phase) but identical in wind_speed itself. The deweather model has no
# station-identity feature, so it cannot tell whose relationship it is looking at,
# and a leaf built mostly from one station's data extrapolates wildly onto another
# (one run measured a fold predicting PM10=1046 against a true range under 50).
# Periods 12 and 5 share no common factor, so their sum does not resettle into a
# single short period - it breaks the aliasing while empirically staying just as
# CUSUM-quiet (peak ~3.0, still comfortably under h=5).
_WIND_SPEED_AMP2 = 4.0
_WIND_SPEED_PERIOD2 = 5
_WIND_SPEED_PHASE2 = 0.9
_WIND_DIR_MEAN = 225.0
_WIND_DIR_STATION_STEP = 2.0  # deg per station index, keeps the range off the 0/360 seam
_WIND_DIR_AMP = 20.0
_WIND_DIR_PHASE = 4.0

# The two planted events. Both source stations are clean ones outside the
# golden-4 injection layout (STA-01..04), so `--with-weather --with-plume` never
# touches a station the golden ledger already accounts for.
_PLUME_STATION_INDEX = 5  # STA-06: the corroborated plume's source
_FAULT_STATION_INDEX = 10  # STA-11: the isolated, uncorroborated spike
# Hours BEFORE THE END of the corpus, not after its start: the dashboard's event
# timeline defaults to the trailing week of whatever is loaded, and the demo
# corpus is 60 days long (see Makefile's DEMO_DAYS) so the deweather CV has
# enough rows to converge - fixed offsets from hour 0 would land both events
# nearly two months before that default window and the timeline would open on
# "no events in this window". Both stay well inside the last 7 days (168h) and
# well apart from each other.
_PLUME_HOUR_FROM_END = 140
_FAULT_HOUR_FROM_END = 90
_TARGET_PARAM = "NO"  # not a deweather target - see the module docstring
_EVENT_VALUE = 1100.0  # µg/m3: above the 1000 NO ceiling (R07), so both are notable
_EVENT_WIND_FROM_DEG = 270.0  # a westerly: the plume travels due east
_EVENT_WIND_SPEED = 18.0  # km/h: comfortably saturates the wind-edge speed response
_BASELINE_WINDOW = 48  # hours; mirrors AdjudicatorParams.baseline_window_hours


def add_wind(
    by_key: dict[tuple[str, str], np.ndarray],
    units: dict[tuple[str, str], str],
    present: dict[tuple[str, str], np.ndarray],
    ledger: Ledger,
    *,
    hours: int,
    t: np.ndarray,
    stations: tuple[str, ...],
) -> None:
    """Layer Wind_Speed/Wind_Direction onto the corpus and couple PM10 to it.

    Mutates ``by_key``/``units``/``present`` in place, exactly like ``_inject``
    does for the defect layer. One station is left without either wind parameter
    (see ``_NO_WIND_STATION_INDEX``); the coverage model reports that as a
    structural absence (R18) the same way it already does for STA-03's missing NO
    sensor - not a defect (standing rule 3). Fully deterministic: no RNG is used.

    PM10 is coupled at every station, including the golden-4 (STA-01..04):
    ``_inject`` still runs after this and overwrites STA-03's/STA-04's PM10 at
    their own fixed hours exactly as before, so the ledger-pinned injection layout
    is unaffected either way. Coupling all 18 gives the deweather regressor a
    single, consistent relationship to learn instead of a patchwork that differs
    by station - carving out even a few stations turned out to make the model
    *less* stable, not more (see the caller in generator.py for the n_days this
    needs to converge).
    """
    if len(stations) <= _NO_WIND_STATION_INDEX:
        raise ValueError(
            f"--with-weather needs at least {_NO_WIND_STATION_INDEX + 1} stations so one "
            f"can plausibly lack a wind sensor; got {len(stations)}."
        )
    no_wind_station = stations[_NO_WIND_STATION_INDEX]

    for i, station in enumerate(stations):
        speed = (
            _WIND_SPEED_MEAN
            + i * _WIND_SPEED_STATION_STEP
            + _WIND_SPEED_AMP * np.sin(2 * np.pi * t / 12 + _WIND_SPEED_PHASE)
            + _WIND_SPEED_AMP2 * np.sin(2 * np.pi * t / _WIND_SPEED_PERIOD2 + _WIND_SPEED_PHASE2)
        )
        direction = (
            _WIND_DIR_MEAN
            + i * _WIND_DIR_STATION_STEP
            + _WIND_DIR_AMP * np.sin(2 * np.pi * t / 12 + _WIND_DIR_PHASE)
        )

        if station != no_wind_station:
            by_key[(station, WIND_SPEED_PARAM)] = speed.copy()
            units[(station, WIND_SPEED_PARAM)] = _WIND_SPEED_UNIT
            present[(station, WIND_SPEED_PARAM)] = np.ones(hours, dtype=bool)
            by_key[(station, WIND_DIRECTION_PARAM)] = direction.copy()
            units[(station, WIND_DIRECTION_PARAM)] = _WIND_DIRECTION_UNIT
            present[(station, WIND_DIRECTION_PARAM)] = np.ones(hours, dtype=bool)

        if (station, "PM10") not in by_key:
            continue
        wind_term = _K_WIND * (speed - speed.mean())
        by_key[(station, "PM10")] = np.clip(by_key[(station, "PM10")] + wind_term, 0.0, None)
        # PM2.5 is a subset of PM10 by construction (generator.py's own comment on
        # `pm10_index`) and R09 flags any hour where that inverts. Re-deriving it
        # from the now wind-coupled PM10, rather than leaving it pinned to the
        # pre-coupling baseline, keeps PM2.5 <= PM10 an identity instead of
        # something the coupling amplitude has to stay under a margin for -
        # STA-01's 4 ledger-pinned R09 hours (injected afterwards) still invert it
        # deliberately; nothing else does.
        if (station, "PM2.5") in by_key:
            by_key[(station, "PM2.5")] = 0.45 * by_key[(station, "PM10")]

    ledger.bump(
        "R18",
        2,
        f"Wind_Speed and Wind_Direction absent entirely from {no_wind_station} "
        "(mirrors the real network's confirmed DEB-KER15 gap)",
    )


def _trailing_median(values: np.ndarray, event_hour: int) -> float:
    start = max(0, event_hour - _BASELINE_WINDOW)
    return float(np.median(values[start:event_hour]))


def add_plume(
    by_key: dict[tuple[str, str], np.ndarray],
    ledger: Ledger,
    *,
    hours: int,
    stations: tuple[str, ...],
) -> None:
    """Plant one wind-corroborated plume and one isolated, uncorroborated spike.

    Both are ``_TARGET_PARAM`` excursions above the physical ceiling, so the
    audit's ``_notable_events`` (R07, physical_exceedance) surfaces each as a
    candidate for the graph adjudicator. The plume's downwind neighbours are not
    hand-picked:
    every station the real wind-edge weight would call downwind of the source is
    raised to the exact attenuated, delayed excess a genuine plume would deliver
    there, computed with the adjudicator's own physics
    (``graph.edges.wind_edge_weight``, ``graph.propagation.expected_arrival``). The
    isolated spike touches no other station, so nothing corroborates it.
    """
    from provenance.config.loading import load_graph_config
    from provenance.fixtures.generator import _INJECTED_STATIONS, station_locations
    from provenance.graph.adjudicate import AdjudicatorParams
    from provenance.graph.edges import WindEdgeParams, wind_edge_weight
    from provenance.graph.propagation import PropagationParams, expected_arrival
    from provenance.graph.topology import StationPoint
    from provenance.graph.wind import WindProvenance, WindVector

    if len(stations) <= _FAULT_STATION_INDEX:
        raise ValueError(
            f"--with-plume needs at least {_FAULT_STATION_INDEX + 1} stations for its "
            f"source geometry; got {len(stations)}."
        )
    if hours <= _PLUME_HOUR_FROM_END + _BASELINE_WINDOW:
        raise ValueError(
            f"--with-plume needs at least {_PLUME_HOUR_FROM_END + _BASELINE_WINDOW + 1} hours "
            f"(--days >= {(_PLUME_HOUR_FROM_END + _BASELINE_WINDOW) // 24 + 1}) for its events' "
            f"trailing baseline windows; got {hours}."
        )
    plume_hour = hours - _PLUME_HOUR_FROM_END
    fault_hour = hours - _FAULT_HOUR_FROM_END
    for key in ((_PLUME_STATION_INDEX, "plume"), (_FAULT_STATION_INDEX, "fault")):
        index, name = key
        if (stations[index], WIND_SPEED_PARAM) not in by_key:
            raise ValueError(
                f"--with-plume needs its {name} source ({stations[index]}) to carry a wind "
                "sensor; call add_wind() first."
            )

    cfg = load_graph_config()
    wind_params = WindEdgeParams.from_config(cfg)
    prop_params = PropagationParams.from_config(cfg)
    adj_params = AdjudicatorParams.from_config(cfg)

    # The golden-4 (STA-01..04) carry the ledger-pinned injection layout - R13's
    # STA-04, in particular, is only "abnormally flat" as long as nothing else
    # touches its PM10. A physically real plume WOULD light these stations up too
    # (several sit close enough to the source to clear the wind-edge floor), but
    # sweeping them in here would silently rewrite golden-corpus behaviour for a
    # scenario that is supposed to live entirely on the clean stations, so they are
    # excluded from the auto-discovered downwind set.
    golden = set(stations[:_INJECTED_STATIONS])
    locations = station_locations(len(stations))
    points = {s: StationPoint(s, loc["lat"], loc["lon"]) for s, loc in locations.items()}
    event_wind = WindVector(
        from_deg=_EVENT_WIND_FROM_DEG,
        speed=_EVENT_WIND_SPEED,
        speed_unit=_WIND_SPEED_UNIT,
        provenance=WindProvenance.STATION_LOCAL,
        station_count=1,
    )

    def plant(source: str, event_hour: int, *, corroborate: bool) -> int:
        src_values = by_key[(source, _TARGET_PARAM)]
        baseline = _trailing_median(src_values, event_hour)
        event_excess = _EVENT_VALUE - baseline
        src_values[event_hour] = _EVENT_VALUE
        by_key[(source, WIND_DIRECTION_PARAM)][event_hour] = _EVENT_WIND_FROM_DEG
        by_key[(source, WIND_SPEED_PARAM)][event_hour] = _EVENT_WIND_SPEED
        if not corroborate:
            return 0

        src_point = points[source]
        n_touched = 0
        for neighbour, p in points.items():
            if (
                neighbour == source
                or neighbour in golden
                or (neighbour, _TARGET_PARAM) not in by_key
            ):
                continue
            weight = wind_edge_weight(
                src_point.lat,
                src_point.lon,
                p.lat,
                p.lon,
                event_wind.from_deg,
                event_wind.speed,
                wind_params,
            )
            if weight < adj_params.downwind_weight_floor:
                continue
            arrival = expected_arrival(
                src_point, p, event_wind, event_excess, wind_params, prop_params
            )
            if not arrival.within_horizon or arrival.expected_excess <= 0:
                continue
            nb_values = by_key[(neighbour, _TARGET_PARAM)]
            nb_baseline = _trailing_median(nb_values, event_hour)
            nb_values[event_hour + 1] = nb_baseline + arrival.expected_excess
            n_touched += 1
        return n_touched

    plume_source = stations[_PLUME_STATION_INDEX]
    fault_source = stations[_FAULT_STATION_INDEX]
    n_touched = plant(plume_source, plume_hour, corroborate=True)
    plant(fault_source, fault_hour, corroborate=False)

    ledger.bump(
        "R07",
        2,
        f"--with-plume: a wind-corroborated {_TARGET_PARAM} plume at {plume_source} "
        f"({n_touched} downwind neighbour(s) raised to their expected attenuated excess) "
        f"and an isolated, uncorroborated {_TARGET_PARAM} spike of the same magnitude at "
        f"{fault_source}",
    )
