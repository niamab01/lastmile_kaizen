from __future__ import annotations

import pandas as pd

from lastmile_kaizen.storage.warehouse import Warehouse


TRAVEL_PER_ROUTE_SQL = """
    SELECT a.route_id, SUM(tt.seconds) AS travel_s
    FROM sequences a
    JOIN sequences b
      ON a.route_id = b.route_id AND b.visit_order = a.visit_order + 1
    JOIN travel_times tt
      ON tt.route_id = a.route_id AND tt.from_stop = a.stop_id AND tt.to_stop = b.stop_id
    GROUP BY a.route_id
"""

SERVICE_PER_ROUTE_SQL = """
    SELECT route_id, SUM(service_time_s) AS service_s
    FROM packages
    GROUP BY route_id
"""


class TourDurationAnalyzer:
    """Splits each tour into driving time and time spent serving stops."""

    def __init__(self, warehouse: Warehouse) -> None:
        self.wh = warehouse

    def per_route(self) -> pd.DataFrame:
        return self.wh.query(f"""
            WITH travel  AS ({TRAVEL_PER_ROUTE_SQL}),
                 service AS ({SERVICE_PER_ROUTE_SQL})
            SELECT t.route_id, t.travel_s, s.service_s, t.travel_s + s.service_s AS total_s
            FROM travel t
            JOIN service s ON t.route_id = s.route_id
            ORDER BY total_s DESC
        """)

    def summary(self) -> dict[str, float]:
        df = self.per_route()
        return {
            "n_routes": len(df),
            "travel_h_mean": df["travel_s"].mean() / 3600,
            "travel_h_min": df["travel_s"].min() / 3600,
            "travel_h_max": df["travel_s"].max() / 3600,
            "service_h_mean": df["service_s"].mean() / 3600,
            "total_h_mean": df["total_s"].mean() / 3600,
            "service_share_pct": 100 * df["service_s"].mean() / df["total_s"].mean(),
        }
