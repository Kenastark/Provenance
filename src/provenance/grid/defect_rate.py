"""The one and only definition of the defect rate.

Standing rule 1: never hardcode a number the data should produce. The single most
scrutinised number in the pitch is the defect rate, so there is exactly one place
in the codebase that defines it, and every report renders that definition next to
the number.

    defect rate = defective covered cells / covered cells

A *cell* is one (station, parameter, timestamp) position in the expected grid.
The timestamp step is each series' own inferred cadence, not a fixed hour: air and
groundwater tick hourly, noise ticks daily, and the coverage model reindexes each
series against its own cadence (see ``grid.coverage``). Calling the step an "hour"
would be wrong for the daily series and is deliberately avoided here and in
``DEFINITION`` - the arithmetic was always per-cadence, only the wording was loose.
A cell is *covered* when the station actually carries that parameter (so a sensor
the station never had is neither numerator nor denominator - standing rule 3).
A cell is *defective* when at least one reason code that counts toward the rate
fired on it. Cells are counted once, however many codes fired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DEFINITION: Final[str] = (
    "defect rate = defective covered cells / covered cells, where a covered cell "
    "is one (station, parameter, tick) the station actually measures - the tick being "
    "that series' own measured cadence, hourly or daily, never assumed - and a "
    "defective cell is one on which at least one defect-counting reason code fired. "
    "Structural absences (sensors a station never carried) are excluded from both "
    "the numerator and the denominator."
)


@dataclass(frozen=True, slots=True)
class DefectRate:
    """The headline number, with the arithmetic that made it attached."""

    n_defective_cells: int
    n_covered_cells: int

    definition: str = DEFINITION

    def __post_init__(self) -> None:
        if self.n_covered_cells < 0 or self.n_defective_cells < 0:
            raise ValueError("cell counts cannot be negative")
        if self.n_defective_cells > self.n_covered_cells:
            raise ValueError(
                f"defective cells ({self.n_defective_cells}) exceed covered cells "
                f"({self.n_covered_cells}); the numerator must be a subset of the denominator"
            )

    @property
    def rate(self) -> float:
        """Fraction in [0, 1]. Zero covered cells is defined as a zero rate."""
        if self.n_covered_cells == 0:
            return 0.0
        return self.n_defective_cells / self.n_covered_cells

    @property
    def percent(self) -> float:
        return round(self.rate * 100.0, 4)
