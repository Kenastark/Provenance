"""Feature-layer tests, including the wind-encoding gate.

The load-bearing one is ``test_wind_sincos_beats_raw_degrees``: a model trained on the
sin/cos encoding treats 359° and 1° as neighbours, and a model trained on raw degrees
does not. If that ever stops holding, the wind feature has silently become a cliff at
north.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from lightgbm import LGBMRegressor

from provenance.models.features import build_features, encode_wind_direction
from provenance.models.features.provenance import FeatureProvenance
from provenance.schema import canonical as C

pytestmark = pytest.mark.unit


def test_encode_wind_direction_is_circular() -> None:
    enc = encode_wind_direction(pd.Series([0.0, 90.0, 180.0, 270.0, 359.0, 1.0]))
    assert list(enc.columns) == ["wind_dir_sin", "wind_dir_cos"]
    # 359° and 1° are 2° apart on the circle → tiny Euclidean distance in (sin, cos).
    p359 = enc.iloc[4].to_numpy()
    p1 = enc.iloc[5].to_numpy()
    assert np.linalg.norm(p359 - p1) < 0.05
    # 0° and 180° are opposite → far apart.
    assert np.linalg.norm(enc.iloc[0].to_numpy() - enc.iloc[2].to_numpy()) > 1.5


def test_wind_encoding_keeps_359_and_1_adjacent() -> None:
    """The core property: 359° and 1° are neighbours under sin/cos, a chasm under degrees."""
    enc = encode_wind_direction(pd.Series([359.0, 1.0]))
    dist_sincos = float(np.linalg.norm(enc.iloc[0].to_numpy() - enc.iloc[1].to_numpy()))
    dist_raw = abs(359.0 - 1.0)
    assert dist_sincos < 0.05  # two degrees apart on the circle → tiny distance
    assert dist_raw > 300.0  # 358 apart as a raw number → the encoding to reject


def test_wind_sincos_beats_raw_degrees() -> None:
    """A model must predict near-identically for 359° and 1° under sin/cos, not degrees.

    The wrap region is withheld from training, so 359° and 1° are both novel and each
    model must generalise across the boundary. Under sin/cos they are neighbours and the
    model gives them close values; under raw degrees they sit at opposite ends of the
    feature range and the tree assigns them far-apart leaves — the larger, spurious gap.
    """
    rng = np.random.RandomState(0)
    deg = rng.uniform(5, 355, 4000)  # withhold only the narrow wrap band [355°, 5°]
    rad = np.radians(deg)
    y = np.sin(rad) + rng.normal(0, 0.02, deg.size)  # asymmetric across the wrap

    def _fit(X: np.ndarray) -> LGBMRegressor:
        return LGBMRegressor(
            n_estimators=300,
            num_leaves=31,
            min_child_samples=20,
            random_state=0,
            n_jobs=1,
            verbose=-1,
        ).fit(X, y)

    m_sincos = _fit(np.column_stack([np.sin(rad), np.cos(rad)]))
    m_raw = _fit(deg.reshape(-1, 1))

    q359 = np.array([[np.sin(np.radians(359)), np.cos(np.radians(359))]])
    q1 = np.array([[np.sin(np.radians(1)), np.cos(np.radians(1))]])
    gap_sincos = abs(float(m_sincos.predict(q359)[0]) - float(m_sincos.predict(q1)[0]))
    gap_raw = abs(float(m_raw.predict([[359.0]])[0]) - float(m_raw.predict([[1.0]])[0]))

    # The circular encoding keeps 359° and 1° close; raw degrees opens a materially
    # larger gap where the wind was continuous.
    assert gap_sincos < 0.2
    assert gap_raw > 1.5 * gap_sincos


def test_build_features_shape_provenance_and_no_nan(
    weather_corpus: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    frame, weather = weather_corpus
    X, fs = build_features(frame, weather=weather)

    stations = frame[C.STATION_ID].nunique()
    hours = frame[C.TIMESTAMP].nunique()
    assert X.shape[0] == stations * hours
    assert not X.isna().any().any()  # every feature imputed; no NaN reaches a model

    # Provenance is honest: wind/humidity/pressure are measured; the BLH is a proxy;
    # temperature/precip are the weather feed; traffic is the unconfirmed one.
    prov = {s.name: s.provenance for s in fs.specs}
    assert prov["wind_speed"] is FeatureProvenance.MEASURED
    assert prov["boundary_layer_proxy"] is FeatureProvenance.PROXY
    assert prov["temperature"] is FeatureProvenance.WEATHER_FEED
    assert prov["traffic_flow"] is FeatureProvenance.TRAFFIC
    assert "traffic_flow" not in fs.available_names  # unconfirmed feed → not available


def test_weather_feed_flagged_unavailable_when_absent(
    weather_corpus: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    frame, _ = weather_corpus
    _, fs = build_features(frame, weather=None)
    temp = fs.spec_for("temperature")
    assert temp.provenance is FeatureProvenance.WEATHER_FEED
    assert temp.available is False  # imputed constant, honestly flagged (§5.3)
