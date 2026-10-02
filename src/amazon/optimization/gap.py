from __future__ import annotations

import time
from collections.abc import Callable, Iterable

import pandas as pd

from lastmile_kaizen.optimization.heuristics import TourHeuristic, TwoOpt
from lastmile_kaizen.optimization.tour import Tour
from lastmile_kaizen.storage.warehouse import Warehouse


class OptimalityGapAnalyzer:
    """gap(route) = f(actual) - f(heuristic), in seconds and in % of f(actual)."""

    def __init__(self, warehouse: Warehouse, heuristic: TourHeuristic | None = None) -> None:
        self.wh = warehouse
        self.heuristic = heuristic or TwoOpt()

    def route_ids(self) -> list[str]:
        return [r for (r,) in self.wh.fetchall(
            "SELECT DISTINCT route_id FROM sequences ORDER BY route_id")]

    def evaluate_route(self, route_id: str) -> dict:
        actual = Tour.from_warehouse(self.wh, route_id)
        started = time.perf_counter()
        optimised = self.heuristic.solve(actual)
        elapsed = time.perf_counter() - started
        actual_s, optimised_s = actual.cost(), optimised.cost()
        return {
            "route_id": route_id,
            "n_stops": len(actual),
            "actual_s": actual_s,
            "optimised_s": optimised_s,
            "gap_s": actual_s - optimised_s,
            "gap_pct": 100 * (actual_s - optimised_s) / actual_s if actual_s else 0.0,
            "solve_time_s": elapsed,
        }

    def run(self, route_ids: Iterable[str] | None = None, progress_every: int = 50,
            log: Callable[[str], None] = print) -> pd.DataFrame:
        ids = list(route_ids) if route_ids is not None else self.route_ids()
        rows = []
        for k, route_id in enumerate(ids, start=1):
            rows.append(self.evaluate_route(route_id))
            if progress_every and k % progress_every == 0:
                log(f"  {k}/{len(ids)} routes done")
        return pd.DataFrame(rows)

    @staticmethod
    def summary(results: pd.DataFrame) -> dict[str, float]:
        return {
            "n_routes": len(results),
            "gap_pct_mean": results["gap_pct"].mean(),
            "gap_pct_median": results["gap_pct"].median(),
            "actual_travel_h_total": results["actual_s"].sum() / 3600,
            "recoverable_h_total": results["gap_s"].sum() / 3600,
            "solve_time_s_total": results["solve_time_s"].sum(),
        }

    @staticmethod
    def pareto_share(results: pd.DataFrame, top_fraction: float = 0.2) -> float:
        """Share (%) of the total gap concentrated in the worst ``top_fraction`` of routes."""
        ordered = results.sort_values("gap_s", ascending=False)
        top = max(1, int(round(len(ordered) * top_fraction)))
        total = ordered["gap_s"].sum()
        return 100 * ordered.head(top)["gap_s"].sum() / total if total else 0.0
