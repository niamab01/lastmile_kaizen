from __future__ import annotations

import pandas as pd

from lastmile_kaizen.config import Config
from lastmile_kaizen.storage.warehouse import Warehouse


class FeatureBuilder:
    """One row per stop: target = total planned service time of its delivered packages."""

    TABLE = "features"
    GROUPABLE = ("zone_prefix", "sub_zone", "sub_zone_grouped")

    def __init__(self, warehouse: Warehouse, config: Config) -> None:
        self.wh = warehouse
        self.config = config

    def _per_stop_sql(self) -> str:
        cfg = self.config
        return f"""
            SELECT route_id, stop_id,
                   SUM(service_time_s)                          AS service_total_s,
                   COUNT(*)                                     AS n_packages,
                   SUM(depth_cm * height_cm * width_cm) / 1000  AS volume_total_l
            FROM packages
            WHERE scan_status = 'DELIVERED'
              AND service_time_s BETWEEN {float(cfg.min_service_s)} AND {float(cfg.max_service_s)}
            GROUP BY route_id, stop_id
        """

    def build(self) -> int:
        threshold = int(self.config.min_subzone_count)
        self.wh.execute(f"""
            CREATE OR REPLACE TABLE {self.TABLE} AS
            WITH per_stop AS ({self._per_stop_sql()}),
            base AS (
                SELECT a.*,
                       seq.visit_order,
                       -- 'C-4.2D' -> 'C'   (10 values: too coarse, hides signal)
                       COALESCE(NULLIF(split_part(s.zone_id, '-', 1), ''), 'UNKNOWN') AS zone_prefix,
                       -- 'C-4.2D' -> 'C-4' (217 values: the useful granularity)
                       COALESCE(NULLIF(split_part(s.zone_id, '.', 1), ''), 'UNKNOWN') AS sub_zone
                FROM per_stop a
                JOIN stops s       ON a.route_id = s.route_id   AND a.stop_id = s.stop_id
                JOIN sequences seq ON seq.route_id = a.route_id AND seq.stop_id = a.stop_id
            ),
            freq AS (SELECT sub_zone, COUNT(*) AS n FROM base GROUP BY sub_zone)
            SELECT b.*,
                   CASE WHEN f.n >= {threshold} THEN b.sub_zone ELSE 'OTHER' END AS sub_zone_grouped
            FROM base b
            JOIN freq f ON b.sub_zone = f.sub_zone
        """)
        expected = int(self.wh.scalar(f"SELECT COUNT(*) FROM ({self._per_stop_sql()})"))
        actual = self.wh.count(self.TABLE)
        if actual != expected:
            raise RuntimeError(
                f"Joins changed the row count ({expected} stops -> {actual} rows): "
                "check the (route_id, stop_id) join keys for fan-out or missing stops."
            )
        return actual

    def cardinality(self) -> pd.DataFrame:
        return self.wh.query(f"""
            SELECT COUNT(DISTINCT zone_prefix)      AS zone_prefix,
                   COUNT(DISTINCT sub_zone)         AS sub_zone,
                   COUNT(DISTINCT sub_zone_grouped) AS sub_zone_grouped
            FROM {self.TABLE}
        """)

    def sub_zone_coverage(self) -> pd.DataFrame:
        threshold = int(self.config.min_subzone_count)
        return self.wh.query(f"""
            WITH counts AS (SELECT sub_zone, COUNT(*) AS n FROM {self.TABLE} GROUP BY sub_zone)
            SELECT COUNT(*)                                    AS total_sub_zones,
                   COUNT(*) FILTER (WHERE n >= {threshold})    AS frequent_sub_zones,
                   ROUND(100.0 * SUM(n) FILTER (WHERE n >= {threshold}) / SUM(n), 1)
                                                               AS stops_covered_pct
            FROM counts
        """)

    def service_per_package_by(self, column: str, min_stops: int = 1) -> pd.DataFrame:
        """Mean service time PER PACKAGE by zone level (removes the quantity confounder)."""
        if column not in self.GROUPABLE:
            raise ValueError(f"column must be one of {self.GROUPABLE}")
        return self.wh.query(f"""
            SELECT {column},
                   COUNT(*)                                   AS n_stops,
                   ROUND(AVG(service_total_s / n_packages), 1) AS service_per_package_s
            FROM {self.TABLE}
            GROUP BY {column}
            HAVING COUNT(*) >= ?
            ORDER BY service_per_package_s DESC
        """, [min_stops])

    def load(self) -> pd.DataFrame:
        return self.wh.query(f"SELECT * FROM {self.TABLE}")
