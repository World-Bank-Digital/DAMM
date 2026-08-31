#!/usr/bin/env python3
"""Thin command-line entry point for the cost-free DAMM simulation harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from simulation import REPORT_NAME, SimulationError, simulate_workflow


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_id", nargs="?", help="built-in scenario identifier")
    parser.add_argument("output_dir", nargs="?", help="new or empty output directory")
    parser.add_argument("--scenario", dest="scenario_option")
    parser.add_argument("--output", dest="output_option")
    parser.add_argument("--country")
    parser.add_argument("--iso", dest="iso3")
    parser.add_argument("--profile", choices=("minimal", "typical", "dense"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    scenario_id = args.scenario_option or args.scenario_id
    output_dir = args.output_option or args.output_dir
    if not scenario_id or not output_dir:
        parser.error("provide SCENARIO OUTPUT_DIR or --scenario and --output")
    if args.scenario_option and args.scenario_id:
        parser.error("scenario was supplied both positionally and with --scenario")
    if args.output_option and args.output_dir:
        parser.error("output was supplied both positionally and with --output")
    try:
        report = simulate_workflow(
            scenario_id,
            output_dir,
            country=args.country,
            iso3=args.iso3,
            profile=args.profile,
        )
    except (OSError, SimulationError, ValueError) as error:
        parser.exit(2, f"simulation error: {error}\n")
    report_path = Path(output_dir).expanduser().resolve() / REPORT_NAME
    print(report_path)
    print(json.dumps({
        "schema_version": report["schema_version"],
        "scenario_id": report["scenario_id"],
        "run_id": report["run_id"],
        "harness_verdict": report["harness_verdict"],
        "workflow_status": report["observed"]["workflow_status"],
        "external_spend_usd": report["external_spend_usd"],
        "label": report["label"],
    }, sort_keys=True, separators=(",", ":")))
    return 0 if report["harness_verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
