"""The artefact store: save models with cards, load only what has a valid card.

Two rules meet here:

* **A model without a card must not load** (§5). ``load_artefact`` refuses an artefact
  whose card sidecar is missing, and refuses one whose card checksum disagrees with the
  pickled model — a silent mismatch between a model and its provenance is exactly the
  failure a card is meant to prevent.
* **Graceful degradation** (standing rule 6). ``load_bundle`` returns ``None`` when the
  artefacts are absent rather than raising; the caller then serves the statistics layer
  and flags the response degraded. Missing models are a normal state, not an error.

Artefacts are gitignored and reproducible from ``prov models train``; nothing here is
ever committed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

from provenance.config.settings import get_settings
from provenance.models.cards import ModelCard, deweather_card, fault_card, write_doc_card
from provenance.models.deweather.model import DeweatherModel
from provenance.models.fault.classify import FaultClassifier

_MODEL_SUFFIX = ".joblib"
_CARD_SUFFIX = ".card.json"


class ModelCardMissingError(RuntimeError):
    """An artefact was found with no card, or a card that does not match it.

    Raised rather than loading the model anyway: a model whose provenance cannot be
    verified is worse than no model, because it looks trustworthy and is not.
    """


@dataclass(frozen=True, slots=True)
class ModelBundle:
    """The models the serving layer needs together: deweather + fault."""

    deweather: DeweatherModel
    fault: FaultClassifier

    @property
    def versions(self) -> dict[str, str]:
        return {"deweather": self.deweather.version, "fault": self.fault.version}


def _artefacts_dir(artefacts_dir: Path | None) -> Path:
    return Path(artefacts_dir) if artefacts_dir is not None else get_settings().artefacts_dir


def save_model(
    model: DeweatherModel | FaultClassifier,
    *,
    artefacts_dir: Path | None = None,
    docs_dir: Path | None = None,
) -> dict[str, Path]:
    """Persist a model plus its card sidecar, and write the human-readable doc card.

    Returns the three written paths. The card is generated from the model's own record
    (:mod:`provenance.models.cards`), so it always matches what was saved.
    """
    directory = _artefacts_dir(artefacts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    card = _card_for(model)

    model_path = directory / f"{card.stem}{_MODEL_SUFFIX}"
    card_path = directory / f"{card.stem}{_CARD_SUFFIX}"
    joblib.dump(model, model_path)
    card_path.write_text(card.sidecar_json(), encoding="utf-8")
    resolved_docs = Path(docs_dir) if docs_dir is not None else get_settings().model_docs_dir
    doc_path = write_doc_card(card, resolved_docs)
    return {"model": model_path, "card": card_path, "doc": doc_path}


def _card_for(model: DeweatherModel | FaultClassifier) -> ModelCard:
    if isinstance(model, DeweatherModel):
        return deweather_card(model)
    return fault_card(model)


def load_artefact(
    stem: str, *, artefacts_dir: Path | None = None
) -> DeweatherModel | FaultClassifier:
    """Load one artefact by its versioned stem, enforcing that it carries a valid card.

    Raises :class:`ModelCardMissingError` when the card sidecar is absent, when the model
    artefact is absent, or when the card's training-data checksum disagrees with the
    loaded model. Never returns an unverified model.
    """
    directory = _artefacts_dir(artefacts_dir)
    model_path = directory / f"{stem}{_MODEL_SUFFIX}"
    card_path = directory / f"{stem}{_CARD_SUFFIX}"
    if not model_path.exists():
        raise ModelCardMissingError(f"No model artefact at {model_path}.")
    if not card_path.exists():
        raise ModelCardMissingError(
            f"Model {stem!r} has no card sidecar ({card_path.name}); refusing to load a "
            "model whose provenance is unknown (§5). Retrain with `prov models train`."
        )
    card_data: dict[str, Any] = json.loads(card_path.read_text(encoding="utf-8"))
    model = joblib.load(model_path)
    model_checksum = getattr(model, "data_checksum", None)
    if card_data.get("training_data_checksum") != model_checksum:
        raise ModelCardMissingError(
            f"Card for {stem!r} does not match the artefact: card checksum "
            f"{card_data.get('training_data_checksum')!r} != model checksum {model_checksum!r}."
        )
    return model  # type: ignore[no-any-return]


def latest_stem(name: str, *, artefacts_dir: Path | None = None) -> str | None:
    """The most recent versioned stem for ``name`` (deweather/fault), or None if absent."""
    directory = _artefacts_dir(artefacts_dir)
    if not directory.exists():
        return None
    candidates = sorted(directory.glob(f"{name}-*{_MODEL_SUFFIX}"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return None
    return candidates[-1].name[: -len(_MODEL_SUFFIX)]


def bundle_available(artefacts_dir: Path | None = None) -> bool:
    """True when both a deweather and a fault artefact (each with a card) are loadable."""
    directory = _artefacts_dir(artefacts_dir)
    for name in ("deweather", "fault"):
        stem = latest_stem(name, artefacts_dir=directory)
        if stem is None:
            return False
        if not (directory / f"{stem}{_CARD_SUFFIX}").exists():
            return False
    return True


def load_bundle(artefacts_dir: Path | None = None) -> ModelBundle | None:
    """Load the latest deweather + fault models, or ``None`` if either is unavailable.

    Never raises on a *missing* bundle (that is graceful degradation); it does raise
    :class:`ModelCardMissingError` if an artefact is present but its card is not, because
    that is a corrupt store, not an absent one.
    """
    directory = _artefacts_dir(artefacts_dir)
    dw_stem = latest_stem("deweather", artefacts_dir=directory)
    fault_stem = latest_stem("fault", artefacts_dir=directory)
    if dw_stem is None or fault_stem is None:
        return None
    deweather = load_artefact(dw_stem, artefacts_dir=directory)
    fault = load_artefact(fault_stem, artefacts_dir=directory)
    assert isinstance(deweather, DeweatherModel)
    assert isinstance(fault, FaultClassifier)
    return ModelBundle(deweather=deweather, fault=fault)


_BUNDLE_CACHE: dict[Path, ModelBundle] = {}
"""Process-local cache of loaded bundles, keyed by resolved artefacts directory.

Deliberately not :func:`functools.lru_cache`: a *miss* here is a normal state, not an
error (see the module docstring), and ``lru_cache`` cannot express "remember the model,
forget the absence". Caching a ``None`` would pin a freshly-trained artefact out of the
running process for its whole lifetime — the API would keep reporting "no model" long
after one existed. Only a successful load is remembered.
"""


def load_bundle_cached(artefacts_dir: Path | None = None) -> ModelBundle | None:
    """:func:`load_bundle`, reading each artefacts directory from disk at most once.

    Same contract as the uncached call: returns ``None`` when the bundle is absent and
    raises :class:`ModelCardMissingError` on a corrupt store. Absence is never cached, so
    a later call still picks up an artefact that has since been trained.

    The API warms this at startup (``api/app.py``), so request paths do not pay the load.
    """
    directory = _artefacts_dir(artefacts_dir)
    cached = _BUNDLE_CACHE.get(directory)
    if cached is not None:
        return cached
    bundle = load_bundle(directory)
    if bundle is not None:
        _BUNDLE_CACHE[directory] = bundle
    return bundle
