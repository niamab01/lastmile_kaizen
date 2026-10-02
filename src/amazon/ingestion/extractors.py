from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import ijson

from lastmile_kaizen.ingestion.sanitizer import JsonSanitizer


def to_float(value: Any) -> float | None:
    """ijson returns ``Decimal`` for numbers; analytics need plain floats (None-safe)."""
    return None if value is None else float(value)


def to_int(value: Any) -> int | None:
    return None if value is None else int(value)


class BaseExtractor(ABC):
    """Streams a ``{route_id: payload}`` JSON file one route at a time (flat memory)."""

    table_name: str = ""

    def __init__(self, path: str | Path, keep_routes: set[str] | None = None) -> None:
        self.path = Path(path)
        self.keep_routes = keep_routes

    def iter_routes(self) -> Iterator[tuple[str, Any]]:
        with self.path.open("rb") as handle:
            for route_id, payload in ijson.kvitems(JsonSanitizer(handle), ""):
                if self.keep_routes is not None and route_id not in self.keep_routes:
                    continue
                yield route_id, payload

    def extract(self) -> list[dict]:
        rows: list[dict] = []
        for route_id, payload in self.iter_routes():
            rows.extend(self.flatten(route_id, payload))
        return rows

    @abstractmethod
    def flatten(self, route_id: str, payload: Any) -> Iterable[dict]:
        """Turn the nested payload of one route into flat rows."""


class RoutesExtractor(BaseExtractor):
    """route_data.json -> one row per route. Also decides which routes are kept."""

    table_name = "routes"

    def __init__(self, path: str | Path, stations: Iterable[str] | None = None) -> None:
        super().__init__(path)
        self.stations = set(stations) if stations else None
        self.kept_route_ids: set[str] = set()

    def flatten(self, route_id: str, route: Any) -> list[dict]:
        if self.stations is not None and route["station_code"] not in self.stations:
            return []
        self.kept_route_ids.add(route_id)
        return [{
            "route_id": route_id,
            "station_code": route["station_code"],
            "route_date": route["date_YYYY_MM_DD"],
            "departure_time_utc": route["departure_time_utc"],
            "capacity_cm3": to_int(route["executor_capacity_cm3"]),
            "route_score": route["route_score"],
        }]


class StopsExtractor(BaseExtractor):
    """route_data.json -> one row per stop (second level of nesting)."""

    table_name = "stops"

    def flatten(self, route_id: str, route: Any) -> list[dict]:
        return [
            {
                "route_id": route_id,
                "stop_id": stop_id,
                "lat": to_float(stop["lat"]),
                "lng": to_float(stop["lng"]),
                "stop_type": stop["type"],
                "zone_id": stop["zone_id"],
            }
            for stop_id, stop in route["stops"].items()
        ]


class PackagesExtractor(BaseExtractor):
    """package_data.json -> one row per package; sub-dictionaries become columns."""

    table_name = "packages"

    def flatten(self, route_id: str, stops: Any) -> list[dict]:
        rows = []
        for stop_id, packages in stops.items():
            for package_id, pkg in packages.items():
                window = pkg.get("time_window") or {}
                dims = pkg.get("dimensions") or {}
                rows.append({
                    "route_id": route_id,
                    "stop_id": stop_id,
                    "package_id": package_id,
                    "scan_status": pkg["scan_status"],
                    "service_time_s": to_float(pkg["planned_service_time_seconds"]),
                    "tw_start_utc": window.get("start_time_utc"),
                    "tw_end_utc": window.get("end_time_utc"),
                    "depth_cm": to_float(dims.get("depth_cm")),
                    "height_cm": to_float(dims.get("height_cm")),
                    "width_cm": to_float(dims.get("width_cm")),
                })
        return rows


class TravelTimesExtractor(BaseExtractor):
    """travel_times.json -> one row per (from_stop, to_stop) arc of each route matrix."""

    table_name = "travel_times"

    def flatten(self, route_id: str, matrix: Any) -> list[dict]:
        return [
            {"route_id": route_id, "from_stop": origin, "to_stop": destination,
             "seconds": to_float(seconds)}
            for origin, destinations in matrix.items()
            for destination, seconds in destinations.items()
        ]


class SequencesExtractor(BaseExtractor):
    """actual_sequences.json -> one row per stop with its real visit order."""

    table_name = "sequences"

    def flatten(self, route_id: str, payload: Any) -> list[dict]:
        return [
            {"route_id": route_id, "stop_id": stop_id, "visit_order": to_int(order)}
            for stop_id, order in payload["actual"].items()
        ]
