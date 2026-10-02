from __future__ import annotations

from collections import Counter

import pandas as pd

from lastmile_kaizen.config import Config
from lastmile_kaizen.ingestion.extractors import (
    BaseExtractor,
    PackagesExtractor,
    RoutesExtractor,
    SequencesExtractor,
    StopsExtractor,
    TravelTimesExtractor,
)
from lastmile_kaizen.storage.warehouse import Warehouse


class ETLPipeline:
    """Extract (stream) -> Transform (flatten) -> Load (DuckDB file)."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def station_counts(self) -> pd.Series:
        """Discovery step: number of routes per station, without loading anything else."""
        counts: Counter[str] = Counter()
        explorer = RoutesExtractor(self.config.path(self.config.route_file))
        for _, route in explorer.iter_routes():
            counts[route["station_code"]] += 1
        return pd.Series(counts, name="n_routes").sort_values(ascending=False)

    def run(self) -> dict[str, int]:
        cfg = self.config
        routes = RoutesExtractor(cfg.path(cfg.route_file), cfg.stations)
        counts: dict[str, int] = {}
        with Warehouse(cfg.db_path) as warehouse:
            # Routes first: they decide which route_ids every other table keeps.
            counts[routes.table_name] = self._load(warehouse, routes)
            kept = routes.kept_route_ids
            if not kept:
                raise ValueError(f"No route found for stations {sorted(cfg.stations)}")
            for extractor in (
                StopsExtractor(cfg.path(cfg.route_file), kept),
                PackagesExtractor(cfg.path(cfg.package_file), kept),
                TravelTimesExtractor(cfg.path(cfg.travel_file), kept),
                SequencesExtractor(cfg.path(cfg.sequence_file), kept),
            ):
                counts[extractor.table_name] = self._load(warehouse, extractor)
        return counts

    @staticmethod
    def _load(warehouse: Warehouse, extractor: BaseExtractor) -> int:
        rows = extractor.extract()
        warehouse.write_table(extractor.table_name, rows)
        return len(rows)
