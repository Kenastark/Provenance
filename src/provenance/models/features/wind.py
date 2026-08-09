"""Wind-direction encoding — the reason 359° and 1° must look like neighbours.

A compass bearing is circular: 0° and 360° are the same direction, and 359° is one
degree from 1°. Fed to a model as a raw number, that adjacency is destroyed — the
two values sit 358 apart, and a tree that splits on the raw degree learns a cliff
at north that no wind ever crosses. Encoding the angle as ``(sin θ, cos θ)`` puts it
back on the circle, where the Euclidean distance between 359° and 1° is tiny.

The test gate pins this: a model trained on the sin/cos encoding predicts almost the
same value for 359° and 1°; a model trained on raw degrees does not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WIND_SIN = "wind_dir_sin"
WIND_COS = "wind_dir_cos"
WIND_DEGREES = "wind_dir_deg"


def encode_wind_direction(degrees: pd.Series | np.ndarray) -> pd.DataFrame:
    """Return a two-column frame ``[wind_dir_sin, wind_dir_cos]`` for a bearing series.

    NaN bearings map to NaN in both columns (the caller imputes downstream), so a
    missing wind reading never silently becomes "due north".
    """
    values = pd.Series(degrees).astype("float64")
    radians = np.radians(values)
    return pd.DataFrame(
        {
            WIND_SIN: np.sin(radians),
            WIND_COS: np.cos(radians),
        },
        index=values.index,
    )
