"""Observed-schema discovery.

Standing rule 2: never invent field names or units - read them from the file at
runtime and fail loudly on mismatch. This module records what was actually seen
(columns, dtypes, unit strings, station ids, parameter names, value ranges) so a
human can diff the observed schema against ``schema_assumptions.yaml``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from provenance.schema import canonical as C


@dataclass(frozen=True, slots=True)
class ParameterProfile:
    parameter: str
    units: list[str]
    n_readings: int
    n_distinct_values: int
    value_min: float | None
    value_max: float | None


@dataclass(frozen=True, slots=True)
class ObservedSchema:
    """What the loader actually saw. Serialised into a manifest per data drop."""

    checksum: str
    n_rows: int
    columns: list[str]
    dtypes: dict[str, str]
    stations: list[str]
    parameters: list[str]
    units: list[str]
    timestamp_min: str | None
    timestamp_max: str | None
    parameter_profiles: list[ParameterProfile] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _checksum(frame: pd.DataFrame) -> str:
    """Content checksum stable across runs: order-independent over row hashes."""
    if C.ROW_HASH in frame.columns:
        joined = "".join(sorted(frame[C.ROW_HASH].astype(str)))
    else:  # pragma: no cover - callers pass canonical frames
        joined = pd.util.hash_pandas_object(frame, index=False).astype(str).str.cat()
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def observe(frame: pd.DataFrame) -> ObservedSchema:
    """Profile a canonical long frame into an :class:`ObservedSchema`."""
    profiles: list[ParameterProfile] = []
    for parameter, g in frame.groupby(C.PARAMETER, sort=True):
        values = pd.to_numeric(g[C.VALUE], errors="coerce")
        profiles.append(
            ParameterProfile(
                parameter=str(parameter),
                units=sorted(g[C.UNIT].dropna().unique().tolist()),
                n_readings=len(g),
                n_distinct_values=int(g[C.VALUE].nunique(dropna=True)),
                value_min=None if values.dropna().empty else float(values.min()),
                value_max=None if values.dropna().empty else float(values.max()),
            )
        )
    ts = pd.to_datetime(frame[C.TIMESTAMP], errors="coerce")
    return ObservedSchema(
        checksum=_checksum(frame),
        n_rows=len(frame),
        columns=list(frame.columns),
        dtypes={c: str(frame[c].dtype) for c in frame.columns},
        stations=sorted(frame[C.STATION_ID].dropna().unique().tolist()),
        parameters=sorted(frame[C.PARAMETER].dropna().unique().tolist()),
        units=sorted(frame[C.UNIT].dropna().unique().tolist()),
        timestamp_min=None if ts.dropna().empty else ts.min().isoformat(),
        timestamp_max=None if ts.dropna().empty else ts.max().isoformat(),
        parameter_profiles=profiles,
    )


def write_manifest(observed: ObservedSchema, manifests_dir: Path) -> Path:
    """Write the observed schema to ``observed-schema-<checksum>.json``.

    Deterministic: sorted keys, trailing newline, stable float formatting.
    """
    manifests_dir.mkdir(parents=True, exist_ok=True)
    out = manifests_dir / f"observed-schema-{observed.checksum}.json"
    payload = json.dumps(observed.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
    out.write_text(payload + "\n", encoding="utf-8")
    return out
