from __future__ import annotations

from abc import ABC, abstractmethod

from lastmile_kaizen.optimization.tour import Tour, path_cost


class TourHeuristic(ABC):
    """Takes a tour and returns another tour over the same stops, same start."""

    name = "abstract"

    @abstractmethod
    def solve(self, tour: Tour) -> Tour:
        ...


class NearestNeighbor(TourHeuristic):
    """Greedy constructive heuristic: always drive to the closest unvisited stop.

    Myopic: it ends up making long jumps to collect the stops it skipped. On the
    largest DLA8 route it was WORSE than the human driver (3.42 h vs 3.06 h).
    """

    name = "nearest-neighbour"

    def solve(self, tour: Tour) -> Tour:
        costs = tour.matrix.raw
        current = tour.start
        order = [current]
        remaining = set(tour.stops[1:])
        while remaining:
            # sorted() makes tie-breaking deterministic (set order is hash-randomised)
            nxt = min(sorted(remaining), key=lambda candidate: costs[(current, candidate)])
            order.append(nxt)
            remaining.remove(nxt)
            current = nxt
        return tour.with_stops(order)


class TwoOpt(TourHeuristic):
    """First-improvement 2-opt local search, start stop (the station) kept fixed.

    A move reverses the segment stops[i..j]. In a symmetric matrix only the two border
    arcs change; here the matrix is asymmetric, so every arc inside the reversed segment
    is traversed the other way and changes cost too. Each candidate is therefore
    re-evaluated in full: O(n) per move, correct, and fast enough (~0.9 s for 194 stops).
    The search stops at a local optimum: no single reversal improves the tour.
    """

    name = "2-opt"

    def __init__(self, max_passes: int | None = None, tolerance: float = 1e-9) -> None:
        self.max_passes = max_passes
        self.tolerance = tolerance
        self.passes_ = 0

    def solve(self, tour: Tour) -> Tour:
        costs = tour.matrix.raw
        best = list(tour.stops)
        best_cost = path_cost(best, costs)
        n = len(best)
        improved, passes = True, 0
        while improved and (self.max_passes is None or passes < self.max_passes):
            improved = False
            passes += 1
            for i in range(1, n - 1):          # i >= 1: the station never moves
                for j in range(i + 1, n):
                    candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                    candidate_cost = path_cost(candidate, costs)
                    if candidate_cost < best_cost - self.tolerance:
                        best, best_cost, improved = candidate, candidate_cost, True
        self.passes_ = passes
        return tour.with_stops(best)
