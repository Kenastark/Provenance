"""A deterministic synthetic Enclod archive CSV for the traffic-counter map layer.

Mirrors :mod:`provenance.fixtures.gtfs`: the real archive is never shipped in the
repo (rule 10), so this writes one file in the observed wide shape — ``time, uuid,
nick, lat, lng`` plus the ten cumulative measure columns from
``schema_assumptions.yaml`` — around a set of counter coordinates. It is synthetic
and says so; the one thing it is faithful to is *shape*, so
:func:`provenance.io.ingest.enclod.counter_locations` reads this and a real archive
file unchanged.

Only ``counter_locations`` (coordinates) is exercised by this fixture today — the
measure columns are written as flat, monotonic counters purely so the file matches
the real CSV's column set, not because any test differences them yet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_MEASURE_COLUMNS = (
    "cars_60+",
    "vans_opposite_direction",
    "vans_0-30",
    "vans_30-60",
    "vans_60+",
    "trucks_opposite_direction",
    "trucks_0-30",
    "trucks_30-60",
    "trucks_60+",
    "uncategorized",
)


def write_enclod_bundle(
    out_dir: Path, counters: dict[str, tuple[float, float]], *, n_ticks: int = 4
) -> Path:
    """Write one synthetic monthly archive CSV under ``out_dir``, one row per
    (counter, 15-minute tick), in the real wide column order."""
    rows: list[dict[str, object]] = []
    start = pd.Timestamp("2026-02-01T00:00:00Z")
    for counter_id, (lat, lon) in sorted(counters.items()):
        for tick in range(n_ticks):
            row: dict[str, object] = {
                "time": (start + tick * pd.Timedelta(minutes=15))
                .isoformat()
                .replace("+00:00", "Z"),
                "uuid": counter_id,
                "nick": f"counter.{counter_id}",
                "lat": lat,
                "lng": lon,
            }
            row.update(dict.fromkeys(_MEASURE_COLUMNS, 100 * (tick + 1)))
            rows.append(row)

    out_dir = Path(out_dir) / "enclod_traffic"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Filename must start with "enclod" (lowercase) to satisfy
    # ``EnclodAdapter.discover``'s ``**/enclod*.csv`` glob.
    path = out_dir / "enclod-2026-02.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
