from __future__ import annotations

import pandas as pd

from lastmile_kaizen.config import Config
from lastmile_kaizen.storage.warehouse import Warehouse


class ServiceTimeProfiler:
    """Distribution, outliers and the impact of the cleaning rule ("measure before you clean")."""

    def __init__(self, warehouse: Warehouse, config: Config) -> None:
        self.wh = warehouse
        self.config = config

    def distribution(self) -> pd.DataFrame:
        return self.wh.query("""
            SELECT COUNT(*)                           AS n_packages,
                   COUNT(DISTINCT service_time_s)     AS n_distinct_values,
                   ROUND(MIN(service_time_s), 1)      AS min_s,
                   ROUND(MAX(service_time_s), 1)      AS max_s,
                   ROUND(AVG(service_time_s), 1)      AS mean_s,
                   ROUND(MEDIAN(service_time_s), 1)   AS median_s
            FROM packages
        """)

    def slowest_packages(self, n: int = 10) -> pd.DataFrame:
        # Few columns on purpose: wide tables get their middle columns hidden by DuckDB.
        return self.wh.query("""
            SELECT scan_status,
                   ROUND(service_time_s, 1)                          AS service_s,
                   ROUND(depth_cm * height_cm * width_cm / 1000, 1)  AS volume_l
            FROM packages
            ORDER BY service_time_s DESC
            LIMIT ?
        """, [n])

    def fast_packages_by_status(self, threshold_s: float | None = None) -> pd.DataFrame:
        threshold = self.config.min_service_s if threshold_s is None else threshold_s
        return self.wh.query("""
            SELECT scan_status, COUNT(*) AS n, ROUND(AVG(service_time_s), 1) AS mean_s
            FROM packages
            WHERE service_time_s < ?
            GROUP BY scan_status
        """, [threshold])

    def cleaning_impact(self) -> dict[str, float]:
        cfg = self.config
        row = self.wh.fetchall("""
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE scan_status = 'DELIVERED'),
                   COUNT(*) FILTER (WHERE scan_status = 'DELIVERED'
                                      AND service_time_s BETWEEN ? AND ?)
            FROM packages
        """, [cfg.min_service_s, cfg.max_service_s])[0]
        total, delivered, kept = row
        return {
            "total": total,
            "delivered": delivered,
            "delivered_plausible": kept,
            "kept_pct": 100 * kept / total if total else 0.0,
        }
