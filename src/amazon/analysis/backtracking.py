"""Descriptive backtracking index: how often a driver re-enters a zone already left."""

from __future__ import annotations

import pandas as pd

from lastmile_kaizen.storage.warehouse import Warehouse


class BacktrackingAnalyzer:
    """backtracking(route) = number of zone blocks - number of distinct zones."""

    GRANULARITIES = {
        "letter": "split_part(s.zone_id, '-', 1)",            
        "sub_zone": "split_part(s.zone_id, '.', 1)",          
        "cell": "left(s.zone_id, length(s.zone_id) - 1)",    
    }

    def __init__(self, warehouse: Warehouse, granularity: str = "sub_zone",
                 ignore_missing_zones: bool = True) -> None:
        if granularity not in self.GRANULARITIES:
            raise ValueError(f"granularity must be one of {sorted(self.GRANULARITIES)}")
        self.wh = warehouse
        self.granularity = granularity
        self.ignore_missing_zones = ignore_missing_zones

    def per_route(self) -> pd.DataFrame:
        expr = self.GRANULARITIES[self.granularity]
        missing_filter = "WHERE s.zone_id IS NOT NULL" if self.ignore_missing_zones else ""
        return self.wh.query(f"""
            WITH seq_zones AS (
                SELECT seq.route_id, seq.visit_order, s.zone_id,
                       COALESCE(NULLIF({expr}, ''), 'UNKNOWN') AS zone
                FROM sequences seq
                JOIN stops s ON s.route_id = seq.route_id AND s.stop_id = seq.stop_id
                {missing_filter}
            ),
            lagged AS (
                SELECT *, LAG(zone) OVER (PARTITION BY route_id ORDER BY visit_order) AS prev_zone
                FROM seq_zones
            )
            SELECT route_id,
                   COUNT(*)                                               AS n_stops,
                   COUNT(*) FILTER (WHERE zone_id IS NULL)                AS n_missing_zone,
                   COUNT(DISTINCT zone)                                   AS n_zones,
                   COUNT(*) FILTER (WHERE zone IS DISTINCT FROM prev_zone) AS n_blocks,
                   COUNT(*) FILTER (WHERE zone IS DISTINCT FROM prev_zone)
                     - COUNT(DISTINCT zone)                               AS backtracking
            FROM lagged
            GROUP BY route_id
            ORDER BY backtracking DESC
        """)

    def summary(self) -> dict[str, float]:
        df = self.per_route()
        return {
            "granularity": self.granularity,
            "n_routes": len(df),
            "zones_per_route_mean": df["n_zones"].mean(),
            "backtracking_mean": df["backtracking"].mean(),
            "backtracking_max": df["backtracking"].max(),
        }

    def distribution(self) -> pd.DataFrame:
        df = self.per_route()
        bins = [-1, 1, 4, 9, float("inf")]
        labels = ["a) 0-1 clean", "b) 2-4 moderate", "c) 5-9 high", "d) 10+ pathological"]
        bucket = pd.cut(df["backtracking"], bins=bins, labels=labels)
        out = bucket.value_counts().sort_index().rename("n_routes").to_frame()
        out["pct"] = (100 * out["n_routes"] / len(df)).round(1)
        return out
