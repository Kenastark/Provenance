"""Whether the model layer is available to the API right now.

The serving layer must answer one question cheaply and often: are the trained model
artefacts present? When they are not, every model-backed response degrades to the
statistics layer and says so (standing rule 6). The check is a file-existence test, so
it is safe to run per request; the expensive load happens only when a model is actually
needed.

Imports are deferred into the functions so bringing up the API does not drag in
LightGBM/SHAP unless a model is genuinely being consulted.
"""

from __future__ import annotations


def models_available() -> bool:
    """True when a deweather and a fault artefact (each with a valid card) are loadable."""
    from provenance.config.settings import get_settings
    from provenance.models import registry

    return registry.bundle_available(get_settings().artefacts_dir)


def model_versions() -> dict[str, str]:
    """The versions of the currently-available models, or ``{}`` when none are present."""
    from provenance.config.settings import get_settings
    from provenance.models import registry

    directory = get_settings().artefacts_dir
    out: dict[str, str] = {}
    for name in ("deweather", "fault"):
        stem = registry.latest_stem(name, artefacts_dir=directory)
        if stem is not None:
            # Stem is "<name>-<version>"; recover the version portion.
            out[name] = stem[len(name) + 1 :]
    return out
