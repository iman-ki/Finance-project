"""Command line: `python -m qrp run [--config path] [--refresh]`."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qrp.core.config import DEFAULT_CONFIG, load_config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="qrp", description="Quantitative Research Platform")
    commands = parser.add_subparsers(dest="command", required=True)

    run_cmd = commands.add_parser("run", help="backtest the strategy in a config file")
    run_cmd.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="YAML config")
    run_cmd.add_argument(
        "--refresh", action="store_true", help="re-download data even if a fresh copy is saved"
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        from qrp import pipeline  # heavy imports only when actually running

        report = pipeline.run(
            load_config(args.config), config_path=args.config, refresh=args.refresh
        )
        metrics = pd.read_csv(report.parent / "metrics.csv", index_col=0)
        print(metrics.to_string(float_format=lambda v: f"{v:,.4f}"))
        print(f"\nReport: {report}")
