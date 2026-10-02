from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from lastmile_kaizen.analysis import (
    BacktrackingAnalyzer,
    FeatureBuilder,
    ServiceTimeProfiler,
    TourDurationAnalyzer,
)
from lastmile_kaizen.config import Config
from lastmile_kaizen.ingestion import ETLPipeline
from lastmile_kaizen.modeling import ServiceTimeModel
from lastmile_kaizen.optimization import NearestNeighbor, OptimalityGapAnalyzer, Tour, TwoOpt
from lastmile_kaizen.storage import Warehouse

MIN_ROWS_FOR_MODEL = 50


def _print_dict(title: str, values: dict) -> None:
    print(f"\n=== {title} ===")
    for key, value in values.items():
        print(f"  {key:<24} {value:.2f}" if isinstance(value, float) else f"  {key:<24} {value}")


def _print_frame(title: str, frame: pd.DataFrame) -> None:
    print(f"\n=== {title} ===")
    print(frame.to_string(index=False))


def cmd_stations(config: Config, args: argparse.Namespace) -> None:
    counts = ETLPipeline(config).station_counts()
    print(counts.to_string())
    print(f"\n{counts.sum()} routes in {len(counts)} stations")


def cmd_build(config: Config, args: argparse.Namespace) -> None:
    counts = ETLPipeline(config).run()
    _print_dict(f"Tables written to {config.db_path}", counts)


def cmd_measure(config: Config, args: argparse.Namespace) -> None:
    with Warehouse(config.db_path, read_only=True) as wh:
        analyzer = TourDurationAnalyzer(wh)
        _print_dict("Tour duration baseline (Measure)", analyzer.summary())
        _print_frame("Longest tours", analyzer.per_route().head(5))


def cmd_service(config: Config, args: argparse.Namespace) -> None:
    with Warehouse(config.db_path) as wh:  # writable: materialises the features table
        profiler = ServiceTimeProfiler(wh, config)
        _print_frame("Service time per package", profiler.distribution())
        _print_frame("Slowest packages", profiler.slowest_packages())
        _print_dict("Cleaning rule impact", profiler.cleaning_impact())

        builder = FeatureBuilder(wh, config)
        n_rows = builder.build()
        print(f"\nfeatures table: {n_rows} stops (row count verified, no fan-out)")
        _print_frame("Cardinality per zone level", builder.cardinality())
        _print_frame("Sub-zone coverage", builder.sub_zone_coverage())
        _print_frame("Service per package by zone letter",
                     builder.service_per_package_by("zone_prefix"))
        features = builder.load()

    if len(features) < MIN_ROWS_FOR_MODEL:
        print(f"\nOnly {len(features)} stops: model comparison skipped.")
        return
    _print_frame("Model comparison (same test split)", ServiceTimeModel(features).compare())


def cmd_backtracking(config: Config, args: argparse.Namespace) -> None:
    with Warehouse(config.db_path, read_only=True) as wh:
        analyzer = BacktrackingAnalyzer(
            wh, granularity=args.granularity,
            ignore_missing_zones=not args.keep_missing_zones,
        )
        _print_dict("Backtracking index", analyzer.summary())
        print("\n=== Distribution ===")
        print(analyzer.distribution().to_string())


def cmd_gap(config: Config, args: argparse.Namespace) -> None:
    with Warehouse(config.db_path, read_only=True) as wh:
        analyzer = OptimalityGapAnalyzer(wh, TwoOpt())
        if args.route:
            actual = Tour.from_warehouse(wh, args.route)
            nearest = NearestNeighbor().solve(actual)
            result = analyzer.evaluate_route(args.route)
            print(f"\nRoute {args.route} ({len(actual)} stops)")
            print(f"  actual (driver)   : {actual.cost():9.0f} s")
            print(f"  nearest neighbour : {nearest.cost():9.0f} s")
            print(f"  2-opt             : {result['optimised_s']:9.0f} s "
                  f"(gap {result['gap_pct']:.1f} %, solved in {result['solve_time_s']:.2f} s)")
            return
        ids = analyzer.route_ids()[: args.limit] if args.limit else None
        results = analyzer.run(ids)
        _print_dict("Optimality gap (2-opt)", analyzer.summary(results))
        print(f"  worst 20% of routes hold {analyzer.pareto_share(results):.0f}% of the total gap")
        top = results.sort_values("gap_s", ascending=False).head(10)
        _print_frame("Routes to target first", top[["route_id", "n_stops", "gap_pct", "gap_s"]])
        if args.output:
            results.to_csv(args.output, index=False)
            print(f"\nPer-route results written to {args.output}")


COMMANDS = {
    "stations": cmd_stations,
    "build": cmd_build,
    "measure": cmd_measure,
    "service": cmd_service,
    "backtracking": cmd_backtracking,
    "gap": cmd_gap,
}


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, default=Path("data"),
                        help="folder holding the challenge JSON files (default: data)")
    common.add_argument("--db", type=Path, default=Path("lastmile.duckdb"),
                        help="DuckDB file (default: lastmile.duckdb)")
    common.add_argument("--stations", nargs="+", default=["DLA8"],
                        help="station codes to keep (default: DLA8)")

    parser = argparse.ArgumentParser(prog="lastmile", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stations", parents=[common], help="routes per station (discovery)")
    sub.add_parser("build", parents=[common], help="stream the JSON files into DuckDB")
    sub.add_parser("measure", parents=[common], help="tour duration baseline")
    sub.add_parser("service", parents=[common], help="service-time profiling + model")

    bt = sub.add_parser("backtracking", parents=[common], help="zone re-entry index")
    bt.add_argument("--granularity", choices=sorted(BacktrackingAnalyzer.GRANULARITIES),
                    default="sub_zone")
    bt.add_argument("--keep-missing-zones", action="store_true",
                    help="count stops without zone_id (reproduces the prototype artefact)")

    gap = sub.add_parser("gap", parents=[common], help="optimality gap with 2-opt")
    gap.add_argument("--route", help="analyse one route in detail")
    gap.add_argument("--limit", type=int, help="only the first N routes")
    gap.add_argument("--output", type=Path, help="write per-route results to CSV")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = Config(data_dir=args.data_dir, db_path=args.db, stations=frozenset(args.stations))
    COMMANDS[args.command](config, args)
