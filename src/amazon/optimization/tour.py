from __future__ import annotations

from collections.abc import Iterator, Sequence

from lastmile_kaizen.storage.warehouse import Warehouse


def path_cost(stops: Sequence[str], costs: dict[tuple[str, str], float]) -> float:
    """Objective function f = sum of c(i, i+1) over consecutive stops (n - 1 arcs)."""
    return sum(costs[(a, b)] for a, b in zip(stops, stops[1:]))


class TravelMatrix:
    """Weighted complete digraph G = (V, A): c(i, j) = travel seconds from i to j.

    The matrix is ASYMMETRIC (c(i, j) != c(j, i)), so the problem is an ATSP.
    """

    def __init__(self, costs: dict[tuple[str, str], float]) -> None:
        self._costs = costs

    def __call__(self, origin: str, destination: str) -> float:
        return self._costs[(origin, destination)]

    def __len__(self) -> int:
        return len(self._costs)

    @property
    def raw(self) -> dict[tuple[str, str], float]:
        """Plain dict, for the hot loops of the heuristics."""
        return self._costs

    @classmethod
    def from_warehouse(cls, warehouse: Warehouse, route_id: str) -> "TravelMatrix":
        rows = warehouse.fetchall(
            "SELECT from_stop, to_stop, seconds FROM travel_times WHERE route_id = ?",
            [route_id],
        )
        return cls({(a, b): float(s) for a, b, s in rows})


class Tour:
    """An ordered visit of every stop of a route, starting at the station (stops[0])."""

    def __init__(self, stops: Sequence[str], matrix: TravelMatrix) -> None:
        self.stops = list(stops)
        self.matrix = matrix

    def __len__(self) -> int:
        return len(self.stops)

    def __iter__(self) -> Iterator[str]:
        return iter(self.stops)

    @property
    def start(self) -> str:
        return self.stops[0]

    def cost(self) -> float:
        return path_cost(self.stops, self.matrix.raw)

    def with_stops(self, stops: Sequence[str]) -> "Tour":
        return Tour(stops, self.matrix)

    def reverse_segment(self, i: int, j: int) -> "Tour":
        """2-opt move: [A,B,C,D,E,F] with (i=1, j=4) -> [A,E,D,C,B,F]."""
        s = self.stops
        return self.with_stops(s[:i] + s[i:j + 1][::-1] + s[j + 1:])

    @classmethod
    def from_warehouse(cls, warehouse: Warehouse, route_id: str) -> "Tour":
        """The ACTUAL tour driven, ordered by visit_order."""
        stops = [row[0] for row in warehouse.fetchall(
            "SELECT stop_id FROM sequences WHERE route_id = ? ORDER BY visit_order",
            [route_id],
        )]
        return cls(stops, TravelMatrix.from_warehouse(warehouse, route_id))
