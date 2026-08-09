"""The hybrid fault classifier: deterministic rules first, LightGBM for the subtle rest.

``classify_faults`` is the serving path. For every pollutant reading it asks the
deterministic detectors first; if any fires, the reading's class is decided by rule
and the model is never consulted — that is the load-bearing ordering the test gate
pins (a physically-impossible reading stays PHYSICALLY_IMPOSSIBLE whatever the model
would have said). Only readings no rule touches are handed to LightGBM, which chooses
among the three subtle classes it was trained on.

``train_fault_classifier`` builds the model from synthetic signatures on the clean
weather corpus, scored forward-chaining. It reports a per-class confusion matrix and
per-signature recall, and it never produces a single headline accuracy figure
(standing rule 4): with this few real positives such a number would describe the
injection process, not the world.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import confusion_matrix

from provenance.config.loading import load_models_config, load_thresholds
from provenance.detectors import registry
from provenance.detectors.base import REASON_CODE, AuditContext
from provenance.grid.coverage import build_coverage
from provenance.models.cv import assert_no_leakage, time_blocked_splits
from provenance.models.deweather.model import ACTUAL, RESIDUAL, DeweatherModel
from provenance.models.fault.labels import (
    SUBTLE_CLASSES,
    FaultClass,
    rule_class_for,
)
from provenance.models.fault.signatures import Injection, build_labeled_corpus
from provenance.schema import canonical as C

FAULT_CLASS = "fault_class"
SOURCE = "source"
CONFIDENCE = "confidence"

# The residual-derived features the subtle-case model learns from. Names are stable so
# the SHAP explainer and the model card agree on them (§8).
FAULT_FEATURES: tuple[str, ...] = (
    "residual",
    "resid_z",
    "resid_abs_z",
    "resid_roll_mean_6",
    "resid_roll_mean_24",
    "resid_trend",
    "resid_roll_std_6",
    "raw_z",
    "explained_ratio",
)

_EPS = 1e-9
# A meteorological artefact is a *high* reading the weather *explains*: well above the
# series median (raw_z large) yet leaving only a small residual (weather accounts for
# it). These thresholds define the training positives; they are modelling choices.
_METEO_RAW_Z = 1.5
_METEO_RESID_ABS_Z = 0.6


# --------------------------------------------------------------------------- features
def fault_features(residuals: pd.DataFrame) -> pd.DataFrame:
    """Residual-derived features per (station, parameter, hour), indexed by that key.

    A calibration drift shows up as a sustained residual trend; a meteorological
    artefact as a large raw excursion with a small residual. The features are built to
    expose exactly those two shapes.
    """
    if residuals.empty:
        return pd.DataFrame(columns=list(FAULT_FEATURES))
    parts: list[pd.DataFrame] = []
    for _key, group in residuals.groupby([C.STATION_ID, C.PARAMETER], sort=True):
        g = group.sort_values(C.TIMESTAMP)
        resid = g[RESIDUAL].to_numpy(dtype="float64")
        actual = g[ACTUAL].to_numpy(dtype="float64")
        resid_s = pd.Series(resid)
        actual_s = pd.Series(actual)

        resid_std = float(resid_s.std(ddof=0)) or 1.0
        actual_med = float(np.median(actual))
        actual_std = float(actual_s.std(ddof=0)) or 1.0

        roll_mean_6 = resid_s.rolling(6, min_periods=1).mean()
        roll_mean_24 = resid_s.rolling(24, min_periods=1).mean()
        roll_std_6 = resid_s.rolling(6, min_periods=1).std(ddof=0).fillna(0.0)
        resid_z = resid_s / resid_std
        raw_z = (actual_s - actual_med) / actual_std
        explained = np.clip(1.0 - np.abs(resid) / (np.abs(actual - actual_med) + _EPS), 0.0, 1.0)
        block = pd.DataFrame(
            {
                "residual": resid,
                "resid_z": resid_z.to_numpy(),
                "resid_abs_z": resid_z.abs().to_numpy(),
                "resid_roll_mean_6": roll_mean_6.to_numpy(),
                "resid_roll_mean_24": roll_mean_24.to_numpy(),
                "resid_trend": (roll_mean_6 - roll_mean_24).to_numpy(),
                "resid_roll_std_6": roll_std_6.to_numpy(),
                "raw_z": raw_z.to_numpy(),
                "explained_ratio": explained,
            },
            index=pd.MultiIndex.from_arrays(
                [g[C.STATION_ID], g[C.PARAMETER], g[C.TIMESTAMP]],
                names=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP],
            ),
        )
        parts.append(block)
    return pd.concat(parts)


def _meteo_labels(features: pd.DataFrame) -> set[tuple[str, str, pd.Timestamp]]:
    """Cells that read as weather-explained peaks — the meteorological-artefact positives."""
    mask = (features["raw_z"] > _METEO_RAW_Z) & (features["resid_abs_z"] < _METEO_RESID_ABS_Z)
    return {(str(s), str(p), pd.Timestamp(t)) for s, p, t in features.index[mask.to_numpy()]}


# --------------------------------------------------------------------------- rule pass
@dataclass(frozen=True, slots=True)
class _RulePass:
    """The deterministic layer's verdict on a frame."""

    cell_classes: dict[tuple[str, str, pd.Timestamp], FaultClass]
    comm_gap_starts: set[tuple[str, str, pd.Timestamp]]
    """(station, parameter, gap-start) for every R02 comm gap. These land on *removed*
    timestamps, so they annotate no surviving cell and are surfaced as their own rows."""


def _rule_pass(frame: pd.DataFrame) -> _RulePass:
    """Run the deterministic detectors and reduce them to per-cell fault classes."""
    ctx = AuditContext(thresholds=load_thresholds(), coverage=build_coverage(frame))
    defects = registry.run_detectors(frame, ctx)
    by_cell: dict[tuple[str, str, pd.Timestamp], set[str]] = {}
    comm_gap_starts: set[tuple[str, str, pd.Timestamp]] = set()
    for rec in defects.to_dict(orient="records"):
        code = str(rec[REASON_CODE])
        key = (str(rec[C.STATION_ID]), str(rec[C.PARAMETER]), pd.Timestamp(rec[C.TIMESTAMP]))
        if code == "R02":
            comm_gap_starts.add(key)
            continue
        by_cell.setdefault(key, set()).add(code)
    cell_classes: dict[tuple[str, str, pd.Timestamp], FaultClass] = {}
    for key, codes in by_cell.items():
        cls = rule_class_for(codes)
        if cls is not None:
            cell_classes[key] = cls
    return _RulePass(cell_classes=cell_classes, comm_gap_starts=comm_gap_starts)


# --------------------------------------------------------------------------- classifier
@dataclass(frozen=True, slots=True)
class FaultClassifier:
    """A trained hybrid fault classifier and its self-reported evaluation.

    ``ml_model`` may be ``None`` — the classifier still runs, deciding every rule cell
    deterministically and defaulting everything else to ``none``. That is graceful
    degradation (standing rule 6): the rule layer never needs a model artefact.
    """

    version: str
    ml_model: LGBMClassifier | None
    feature_names: tuple[str, ...]
    ml_classes: tuple[str, ...]
    confusion: dict[str, dict[str, int]]
    per_class: dict[str, dict[str, float]]
    signature_recall: dict[str, float]
    meteo_precision: float
    recall_floors: dict[str, float]
    meteo_precision_floor: float
    data_checksum: str
    window_start: str
    window_end: str
    n_splits: int
    n_train: int
    notes: list[str] = field(default_factory=list)

    def to_card_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "data_checksum": self.data_checksum,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "n_splits": self.n_splits,
            "n_train": self.n_train,
            "classes": [c.value for c in FaultClass],
            "ml_classes": list(self.ml_classes),
            "features": list(self.feature_names),
            "confusion_matrix": self.confusion,
            "per_class": self.per_class,
            "signature_recall": self.signature_recall,
            "recall_floors": self.recall_floors,
            "meteorological_artefact_precision": round(self.meteo_precision, 4),
            "meteorological_artefact_precision_floor": self.meteo_precision_floor,
            "notes": self.notes,
        }


def classify_faults(
    frame: pd.DataFrame,
    classifier: FaultClassifier,
    deweather_model: DeweatherModel,
    *,
    weather: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Classify every pollutant reading: rules first, then the subtle-case model.

    Returns one row per assessed cell with ``fault_class``, ``source`` (``rule`` or
    ``ml``) and ``confidence``. Comm-gap rows are appended for the outage timestamps.
    """
    rule = _rule_pass(frame)
    residuals = deweather_model.predict_series(frame, weather=weather)
    features = fault_features(residuals)

    rows: list[dict[str, Any]] = []
    ml_index: list[tuple[str, str, pd.Timestamp]] = []
    for key in features.index:
        k = (str(key[0]), str(key[1]), pd.Timestamp(key[2]))
        if k in rule.cell_classes:
            rows.append(_row(k, rule.cell_classes[k], "rule", 1.0))
        else:
            ml_index.append(k)

    if ml_index and classifier.ml_model is not None:
        rows_index = pd.MultiIndex.from_tuples(
            ml_index, names=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP]
        )
        X = features.loc[rows_index, list(classifier.feature_names)]
        proba = np.asarray(classifier.ml_model.predict_proba(X))
        classes = classifier.ml_model.classes_
        best = proba.argmax(axis=1)
        for k, row_proba, bi in zip(ml_index, proba, best, strict=True):
            rows.append(_row(k, FaultClass(classes[bi]), "ml", float(row_proba[bi])))
    else:
        # Degraded: no subtle-case model, so every non-rule cell defaults to none.
        for k in ml_index:
            rows.append(_row(k, FaultClass.NONE, "rule", 1.0))

    for gap in sorted(rule.comm_gap_starts):
        rows.append(_row(gap, FaultClass.COMMUNICATION_FAILURE, "rule", 1.0))
    out = pd.DataFrame(
        rows, columns=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP, FAULT_CLASS, SOURCE, CONFIDENCE]
    )
    if out.empty:
        return out
    return out.sort_values([C.STATION_ID, C.PARAMETER, C.TIMESTAMP], kind="stable").reset_index(
        drop=True
    )


def _row(
    key: tuple[str, str, pd.Timestamp], cls: FaultClass, source: str, confidence: float
) -> dict[str, Any]:
    return {
        C.STATION_ID: key[0],
        C.PARAMETER: key[1],
        C.TIMESTAMP: key[2],
        FAULT_CLASS: cls.value,
        SOURCE: source,
        CONFIDENCE: round(confidence, 4),
    }


def _lgbm_classifier(cfg: dict[str, Any]) -> LGBMClassifier:
    p = cfg["fault"]["lightgbm"]
    return LGBMClassifier(
        n_estimators=int(p["n_estimators"]),
        learning_rate=float(p["learning_rate"]),
        num_leaves=int(p["num_leaves"]),
        min_child_samples=int(p["min_child_samples"]),
        random_state=int(p["random_state"]),
        # Class-weighted cross-entropy: the subtle classes are rare, so weighting keeps
        # the majority "none" from swamping them. The objective is left to the wrapper,
        # which picks softmax multiclass for 3+ classes and binary logloss for 2 — the
        # explicit "multiclass" setting fails on the 2-class case some corpora produce.
        class_weight="balanced",
        n_jobs=1,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
    )


def train_fault_classifier(
    clean_frame: pd.DataFrame,
    deweather_model: DeweatherModel,
    *,
    weather: pd.DataFrame | None = None,
    cfg: dict[str, Any] | None = None,
    seed: int = 20260907,
) -> FaultClassifier:
    """Train the subtle-case model on synthetic signatures and report its evaluation."""
    cfg = cfg or load_models_config()
    n_splits = int(cfg["fault"]["n_splits"])
    floors = {str(k): float(v) for k, v in cfg["fault"]["recall_floors"].items()}
    meteo_floor = float(cfg["fault"]["meteorological_artefact_precision_floor"])

    labeled = build_labeled_corpus(clean_frame, seed=seed)
    residuals = deweather_model.predict_series(labeled.frame, weather=weather)
    features = fault_features(residuals)

    # Ground-truth label per pollutant cell: injection labels, then weather-explained
    # peaks, then none.
    meteo = _meteo_labels(features)
    labels: list[str] = []
    keys: list[tuple[str, str, pd.Timestamp]] = []
    for idx in features.index:
        k = (str(idx[0]), str(idx[1]), pd.Timestamp(idx[2]))
        keys.append(k)
        if k in labeled.cell_labels:
            labels.append(labeled.cell_labels[k].value)
        elif k in meteo:
            labels.append(FaultClass.METEOROLOGICAL_ARTEFACT.value)
        else:
            labels.append(FaultClass.NONE.value)
    y_true = pd.Series(labels, index=features.index)
    ts = pd.DatetimeIndex([k[2] for k in keys])

    # ML trains only on subtle-class cells (rule cells are the rules' business).
    subtle_values = {c.value for c in SUBTLE_CLASSES}
    subtle_mask = y_true.isin(subtle_values).to_numpy()
    X_ml = features.loc[subtle_mask, list(FAULT_FEATURES)]
    y_ml = y_true[subtle_mask]
    ts_ml = ts[subtle_mask]

    from provenance.schema.observe import observe

    obs = observe(labeled.frame)
    base_notes = [
        "No headline accuracy figure is reported for this classifier (standing rule 4).",
        "Deterministic rules (R07/R08/R09 physical, R12 frozen, R02 comms, R10 unit) "
        "short-circuit the model and are excluded from the learned confusion matrix.",
    ]

    # Too little subtle-class variety to fit a classifier (a very clean or very small
    # corpus): fall back to a rules-only classifier. It still runs — the rules decide
    # every hard class and everything else is "none" — which is graceful degradation,
    # not a failure (standing rule 6).
    if y_ml.nunique() < 2:
        return _rules_only_classifier(obs, floors, meteo_floor, n_splits, len(y_ml), base_notes)

    splits = time_blocked_splits(ts_ml, n_splits=n_splits)
    assert_no_leakage(ts_ml, splits)  # forward-chaining only

    # Held-out evaluation on the last time block, via the full hybrid. Skip it (rather
    # than fit on one class) when the pre-boundary window lacks subtle variety.
    boundary = _last_block_start(ts, n_splits)
    train_ml_mask = np.asarray(ts_ml < boundary)
    notes = list(base_notes)
    if train_ml_mask.sum() > 0 and y_ml[train_ml_mask].nunique() >= 2:
        eval_model = _lgbm_classifier(cfg)
        eval_model.fit(X_ml[train_ml_mask], y_ml[train_ml_mask])
        confusion, per_class, meteo_precision, signature_recall = _evaluate_hybrid(
            labeled=labeled,
            features=features,
            y_true=y_true,
            keys=keys,
            boundary=boundary,
            eval_model=eval_model,
        )
    else:
        confusion, per_class, meteo_precision, signature_recall = {}, {}, 0.0, {}
        notes.append(
            "Held-out evaluation skipped: fewer than two subtle classes fell before the "
            "split boundary on this corpus."
        )

    # Final model: fit on every subtle-class cell.
    final = _lgbm_classifier(cfg)
    final.fit(X_ml, y_ml)

    return FaultClassifier(
        version=f"v1-{obs.checksum[:8]}",
        ml_model=final,
        feature_names=FAULT_FEATURES,
        ml_classes=tuple(str(c) for c in final.classes_),
        confusion=confusion,
        per_class=per_class,
        signature_recall=signature_recall,
        meteo_precision=meteo_precision,
        recall_floors=floors,
        meteo_precision_floor=meteo_floor,
        data_checksum=obs.checksum,
        window_start=str(obs.timestamp_min),
        window_end=str(obs.timestamp_max),
        n_splits=n_splits,
        n_train=len(y_ml),
        notes=notes,
    )


def _rules_only_classifier(
    obs: Any,
    floors: dict[str, float],
    meteo_floor: float,
    n_splits: int,
    n_train: int,
    base_notes: list[str],
) -> FaultClassifier:
    """A classifier with no ML component — the rules still decide the hard classes."""
    return FaultClassifier(
        version=f"v1-{obs.checksum[:8]}",
        ml_model=None,
        feature_names=FAULT_FEATURES,
        ml_classes=(),
        confusion={},
        per_class={},
        signature_recall={},
        meteo_precision=0.0,
        recall_floors=floors,
        meteo_precision_floor=meteo_floor,
        data_checksum=obs.checksum,
        window_start=str(obs.timestamp_min),
        window_end=str(obs.timestamp_max),
        n_splits=n_splits,
        n_train=n_train,
        notes=[*base_notes, "Rules-only: too little subtle-class variety to train the ML."],
    )


def _last_block_start(ts: pd.DatetimeIndex, n_splits: int) -> pd.Timestamp:
    unique = np.array(sorted(pd.DatetimeIndex(ts).unique()))
    blocks = np.array_split(unique, n_splits + 1)
    return pd.Timestamp(blocks[-1][0])


def _evaluate_hybrid(
    *,
    labeled: Any,
    features: pd.DataFrame,
    y_true: pd.Series,
    keys: list[tuple[str, str, pd.Timestamp]],
    boundary: pd.Timestamp,
    eval_model: LGBMClassifier,
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, float]], float, dict[str, float]]:
    """Confusion matrix + per-signature recall on the held-out block, via rules+ML."""
    rule = _rule_pass(labeled.frame)

    test_keys = [k for k in keys if k[2] >= boundary]
    y_pred_list: list[str] = []
    y_true_list: list[str] = []
    ml_classes = list(eval_model.classes_)
    for k in test_keys:
        true = y_true.loc[(k[0], k[1], k[2])]
        if k in rule.cell_classes:
            pred = rule.cell_classes[k].value
        else:
            one = pd.MultiIndex.from_tuples([k], names=[C.STATION_ID, C.PARAMETER, C.TIMESTAMP])
            X = features.loc[one, list(FAULT_FEATURES)]
            proba = np.asarray(eval_model.predict_proba(X))[0]
            pred = str(ml_classes[int(proba.argmax())])
        y_true_list.append(str(true))
        y_pred_list.append(str(pred))

    all_classes = [c.value for c in FaultClass]
    cm = confusion_matrix(y_true_list, y_pred_list, labels=all_classes)
    confusion = {
        all_classes[i]: {all_classes[j]: int(cm[i, j]) for j in range(len(all_classes))}
        for i in range(len(all_classes))
    }
    per_class = _per_class_metrics(cm, all_classes)
    meteo_precision = per_class[FaultClass.METEOROLOGICAL_ARTEFACT.value]["precision"]

    # Per-signature recall on the held-out block (cell-level for present-cell faults;
    # gap-level for dropouts, whose cells were removed and cannot appear as test cells).
    signature_recall = _signature_recall(
        labeled.injections, rule.comm_gap_starts, y_pred_list, test_keys, boundary
    )
    return confusion, per_class, meteo_precision, signature_recall


def _per_class_metrics(cm: np.ndarray, classes: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for i, cls in enumerate(classes):
        tp = int(cm[i, i])
        support = int(cm[i, :].sum())
        predicted = int(cm[:, i].sum())
        recall = tp / support if support else 0.0
        precision = tp / predicted if predicted else 0.0
        out[cls] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "support": support,
        }
    return out


def _signature_recall(
    injections: tuple[Injection, ...],
    comm_gap_starts: set[tuple[str, str, pd.Timestamp]],
    y_pred_list: list[str],
    test_keys: list[tuple[str, str, pd.Timestamp]],
    boundary: pd.Timestamp,
) -> dict[str, float]:
    """Recall per signature kind, evaluated on the held-out block only.

    Present-cell faults (flatline/gain/drift) are scored cell-by-cell against the
    hybrid's prediction. A dropout removes its cells, so it is scored gap-by-gap: it is
    recovered iff the comm-gap rule (R02) fired somewhere inside the injected window.
    """
    pred_by_key = dict(zip(test_keys, y_pred_list, strict=True))
    hits: dict[str, int] = {}
    total: dict[str, int] = {}
    for inj in injections:
        cells_in_block = [pd.Timestamp(t) for t in inj.timestamps if pd.Timestamp(t) >= boundary]
        if not cells_in_block:
            continue
        if inj.kind == "dropout":
            window = {(inj.station_id, inj.parameter, t) for t in cells_in_block}
            recovered = bool(window & comm_gap_starts)
            total[inj.kind] = total.get(inj.kind, 0) + 1
            hits[inj.kind] = hits.get(inj.kind, 0) + (1 if recovered else 0)
            continue
        for t in cells_in_block:
            pred = pred_by_key.get((inj.station_id, inj.parameter, t))
            if pred is None:
                continue
            total[inj.kind] = total.get(inj.kind, 0) + 1
            hits[inj.kind] = hits.get(inj.kind, 0) + (1 if pred == inj.fault_class.value else 0)
    return {kind: round(hits.get(kind, 0) / total[kind], 4) for kind in total if total[kind]}
