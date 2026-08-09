"""The per-pollutant deweathering regressor and what it records about itself.

One gradient-boosted regressor per pollutant maps meteorology + time features to the
reading. Training is forward-chaining (time-blocked CV, no leakage) and every fold's
held-out R² is recorded, because the R² band is a first-class honesty gate, not an
afterthought — a model that scores 0.98 has left no room for a real event to surface,
and one that scores 0.05 has learned nothing about the weather.

The model carries its own provenance: the training window, the data checksum, the
feature list with per-column provenance, the CV scheme and the per-pollutant metrics.
That record is exactly what the model card is generated from, so the card cannot drift
from the model it describes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from provenance.config.loading import load_models_config
from provenance.models.cv import assert_no_leakage, time_blocked_splits
from provenance.models.features import FeatureSet, build_features
from provenance.schema import canonical as C
from provenance.schema.observe import observe

PREDICTED = "predicted"
RESIDUAL = "residual"
ACTUAL = "actual"


@dataclass(frozen=True, slots=True)
class PollutantMetrics:
    """Held-out CV metrics for one pollutant's deweather model."""

    parameter: str
    cv_r2_mean: float
    cv_r2_folds: tuple[float, ...]
    cv_mae_mean: float
    n_train: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter,
            "cv_r2_mean": round(self.cv_r2_mean, 4),
            "cv_r2_folds": [round(v, 4) for v in self.cv_r2_folds],
            "cv_mae_mean": round(self.cv_mae_mean, 4),
            "n_train": self.n_train,
        }


@dataclass(frozen=True, slots=True)
class DeweatherModel:
    """Fitted per-pollutant regressors plus their training record.

    Constructed by :func:`train_deweather`; persisted and reloaded by
    :mod:`provenance.models.registry`. ``predict`` and ``residual_frame`` are pure
    functions of a readings frame and this model.
    """

    version: str
    regressors: dict[str, LGBMRegressor]
    feature_set: FeatureSet
    feature_names: tuple[str, ...]
    metrics: dict[str, PollutantMetrics]
    data_checksum: str
    window_start: str
    window_end: str
    n_splits: int
    weather_available: bool

    @property
    def pollutants(self) -> list[str]:
        return sorted(self.regressors)

    def predict_series(
        self, frame: pd.DataFrame, *, weather: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """Weather-predicted value for every (station, pollutant, hour) this model covers."""
        matrix, _ = build_features(frame, weather=weather)
        features = matrix[list(self.feature_names)]
        out: list[pd.DataFrame] = []
        for parameter, model in self.regressors.items():
            present = _target_series(frame, parameter).reindex(matrix.index)
            mask = present.notna()
            if not mask.any():
                continue
            predicted = pd.Series(
                model.predict(features[mask.to_numpy()]), index=matrix.index[mask.to_numpy()]
            )
            block = pd.DataFrame(
                {
                    C.STATION_ID: matrix.index.get_level_values(C.STATION_ID)[mask.to_numpy()],
                    C.TIMESTAMP: matrix.index.get_level_values(C.TIMESTAMP)[mask.to_numpy()],
                    C.PARAMETER: parameter,
                    ACTUAL: present[mask].to_numpy(),
                    PREDICTED: predicted.to_numpy(),
                }
            )
            block[RESIDUAL] = block[ACTUAL] - block[PREDICTED]
            out.append(block)
        if not out:
            return pd.DataFrame(
                columns=[C.STATION_ID, C.TIMESTAMP, C.PARAMETER, ACTUAL, PREDICTED, RESIDUAL]
            )
        combined = pd.concat(out, ignore_index=True)
        return combined.sort_values(
            [C.STATION_ID, C.PARAMETER, C.TIMESTAMP], kind="stable"
        ).reset_index(drop=True)

    def to_card_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "data_checksum": self.data_checksum,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "n_splits": self.n_splits,
            "weather_available": self.weather_available,
            "pollutants": self.pollutants,
            "features": self.feature_set.to_dict()["features"],
            "metrics": {p: self.metrics[p].to_dict() for p in sorted(self.metrics)},
        }


def _target_series(frame: pd.DataFrame, parameter: str) -> pd.Series:
    """Mean pollutant value per (station, hour) — the regression target, deduplicated."""
    rows = frame[frame[C.PARAMETER] == parameter]
    if rows.empty:
        return pd.Series(dtype="float64")
    return rows.groupby([C.STATION_ID, C.TIMESTAMP])[C.VALUE].mean().astype("float64")


def _lgbm(cfg: dict[str, Any]) -> LGBMRegressor:
    p = cfg["deweather"]["lightgbm"]
    return LGBMRegressor(
        n_estimators=int(p["n_estimators"]),
        learning_rate=float(p["learning_rate"]),
        num_leaves=int(p["num_leaves"]),
        min_child_samples=int(p["min_child_samples"]),
        subsample=float(p["subsample"]),
        colsample_bytree=float(p["colsample_bytree"]),
        random_state=int(p["random_state"]),
        # Determinism: a single thread with force_row_wise makes two trainings on the
        # same data byte-identical, which the reproducibility tests depend on.
        n_jobs=1,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
    )


def train_deweather(
    frame: pd.DataFrame,
    *,
    weather: pd.DataFrame | None = None,
    per_interval_traffic: pd.Series | None = None,
    cfg: dict[str, Any] | None = None,
    pollutants: list[str] | None = None,
) -> DeweatherModel:
    """Train one deweather regressor per weather-responsive pollutant present.

    The pollutant list is the config's intersected with what the frame actually
    carries — a pollutant the network does not measure is skipped, never invented
    (standing rule 2). Every fold is checked for leakage before its score is trusted.
    """
    cfg = cfg or load_models_config()
    dw = cfg["deweather"]
    n_splits = int(dw["n_splits"])
    requested = pollutants if pollutants is not None else list(dw["pollutants"])

    matrix, feature_set = build_features(
        frame, weather=weather, per_interval_traffic=per_interval_traffic
    )
    feature_names = tuple(feature_set.available_names)
    features_all = matrix[list(feature_names)]

    present_params = set(frame[C.PARAMETER].astype(str).unique())
    to_train = [p for p in requested if p in present_params]

    regressors: dict[str, LGBMRegressor] = {}
    metrics: dict[str, PollutantMetrics] = {}
    for parameter in to_train:
        target = _target_series(frame, parameter).reindex(matrix.index)
        mask = target.notna().to_numpy()
        Xp = features_all[mask]
        yp = target[mask]
        ts = Xp.index.get_level_values(C.TIMESTAMP)

        splits = time_blocked_splits(ts, n_splits=n_splits)
        assert_no_leakage(ts, splits)  # forward-chaining only — never trust a leaky fold

        fold_r2: list[float] = []
        fold_mae: list[float] = []
        for train_idx, test_idx in splits:
            model = _lgbm(cfg)
            model.fit(Xp.iloc[train_idx], yp.iloc[train_idx])
            pred = model.predict(Xp.iloc[test_idx])
            fold_r2.append(float(r2_score(yp.iloc[test_idx], pred)))
            fold_mae.append(float(mean_absolute_error(yp.iloc[test_idx], pred)))

        final = _lgbm(cfg)
        final.fit(Xp, yp)
        regressors[parameter] = final
        metrics[parameter] = PollutantMetrics(
            parameter=parameter,
            cv_r2_mean=float(np.mean(fold_r2)) if fold_r2 else float("nan"),
            cv_r2_folds=tuple(fold_r2),
            cv_mae_mean=float(np.mean(fold_mae)) if fold_mae else float("nan"),
            n_train=len(yp),
        )

    if not regressors:
        raise ValueError(
            "No weather-responsive pollutants to deweather were found in the frame. "
            f"Requested {requested}, present {sorted(present_params)}."
        )

    obs = observe(frame)
    checksum = obs.checksum
    return DeweatherModel(
        version=f"v1-{checksum[:8]}",
        regressors=regressors,
        feature_set=feature_set,
        feature_names=feature_names,
        metrics=metrics,
        data_checksum=checksum,
        window_start=str(obs.timestamp_min),
        window_end=str(obs.timestamp_max),
        n_splits=n_splits,
        weather_available=weather is not None and not weather.empty,
    )
