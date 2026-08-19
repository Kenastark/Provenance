"""Turn SHAP attributions into the operator sentence a human acts on.

"driven primarily by a sustained 6-day trend deviation, not short-term noise" says
more to a city official than a table of feature weights ever will. The renderer maps
each stable feature name to a plain-language phrase, ranks the attributions by
magnitude, and names the top few with their direction (raised / lowered).

The phrase map is keyed on the same stable feature names the feature layer and the
SHAP explainer use, so a rename in one place is a rename everywhere — the sentence can
never quietly describe a feature the model isn't using.
"""

from __future__ import annotations

from provenance.explain.shap_explain import ShapExplanation

# Stable feature name → the phrase an operator reads. Covers both the deweather
# feature set and the fault classifier's residual-derived features.
_PHRASES: dict[str, str] = {
    # weather / deweather features
    "temperature": "air temperature",
    "precipitation": "precipitation",
    "wind_speed": "wind speed",
    "wind_dir_sin": "wind direction",
    "wind_dir_cos": "wind direction",
    "wind_dir_deg": "wind direction",
    "humidity": "humidity",
    "pressure": "barometric pressure",
    "boundary_layer_proxy": "the shallow overnight mixing layer",
    "hour_sin": "time of day",
    "hour_cos": "time of day",
    "dow_sin": "day of week",
    "dow_cos": "day of week",
    "season_sin": "the seasonal cycle",
    "season_cos": "the seasonal cycle",
    "traffic_flow": "road traffic",
    # fault / residual-derived features
    "residual": "the weather-adjusted residual",
    "resid_z": "how far the residual sits from normal",
    "resid_abs_z": "the size of the residual anomaly",
    "resid_roll_mean_6": "a 6-hour residual shift",
    "resid_roll_mean_24": "a day-long residual shift",
    "resid_trend": "a sustained multi-day trend deviation",
    "resid_roll_std_6": "short-term residual noise",
    "raw_z": "how high the raw reading sits above its own normal",
    "explained_ratio": "how well weather explains the rise",
}


def feature_phrase(name: str) -> str:
    """The operator-facing phrase for a feature name (falls back to the name itself)."""
    return _PHRASES.get(name, name.replace("_", " "))


def operator_sentence(explanation: ShapExplanation, *, top_k: int = 3) -> str:
    """A one-line, plain-language account of what drove this prediction.

    Names the top-``k`` features by attribution magnitude and their direction, and
    contrasts them with the smallest contributor as the "not …" clause, which is what
    turns a ranking into a claim ("driven by X, not short-term noise").
    """
    top = explanation.top(top_k)
    if not top or all(a.value == 0.0 for a in top):
        return "No single feature stands out; the prediction sits near its baseline."

    # Deduplicate phrases (wind sin/cos both say "wind direction") while keeping order,
    # annotating each with the direction it pushed the prediction.
    seen: set[str] = set()
    ranked: list[str] = []
    for a in top:
        phrase = feature_phrase(a.feature)
        if phrase in seen or a.value == 0.0:
            continue
        seen.add(phrase)
        direction = "raised" if a.value > 0 else "lowered"
        ranked.append(f"{phrase} ({direction})")

    head = f"Driven primarily by {ranked[0]}"
    if len(ranked) > 2:
        head += ", then " + ", ".join(ranked[1:-1]) + f" and {ranked[-1]}"
    elif len(ranked) == 2:
        head += f", then {ranked[1]}"

    # The smallest-magnitude attribution becomes the "not …" contrast.
    least = min(explanation.attributions, key=lambda a: abs(a.value))
    least_phrase = feature_phrase(least.feature)
    if least_phrase not in seen:
        head += f"; not {least_phrase}"
    return head + "."
