from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Paths, station filter and data-cleaning thresholds.

    Every analytical decision that is a *parameter* (not code) lives here, so a reader
    can see at a glance which choices drive the results.
    """

    data_dir: Path = Path("data")
    db_path: Path = Path("lastmile.duckdb")
    stations: frozenset[str] = field(default_factory=lambda: frozenset({"DLA8"}))

    route_file: str = "route_data.json"
    package_file: str = "package_data.json"
    travel_file: str = "travel_times.json"
    sequence_file: str = "actual_sequences.json"

    # Service-time cleaning rule (see README, "Cleaning rule")
    min_service_s: float = 5.0
    max_service_s: float = 900.0

    # Sub-zones seen fewer times than this are grouped into "OTHER"
    min_subzone_count: int = 100

    def path(self, filename: str) -> Path:
        return Path(self.data_dir) / filename
