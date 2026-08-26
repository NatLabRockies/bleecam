# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generate the separate Gallium dual-cost dashboard outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from gallium_border_cost_metrics import DualCostPaths, write_outputs
from gallium_dual_cost_dashboard import render_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Gallium dual-cost landed-cost dashboard outputs.")
    parser.add_argument("--results-dir", type=Path, default=Path("output/gallium"), help="Existing successful Gallium output directory to post-process.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/gallium_dual_cost_dashboard"), help="New output directory for dual-cost dashboard files.")
    parser.add_argument("--repo-demand", type=Path, default=Path("data/gallium/demand_ga.csv"), help="Current repo demand file used only for validation comparison; never modified.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = DualCostPaths(results_dir=args.results_dir, output_dir=args.output_dir, repo_demand_path=args.repo_demand)
    result = write_outputs(paths)
    dashboard_path = render_dashboard(args.output_dir)
    print("Wrote Gallium dual-cost dashboard outputs:")
    for filename in result["files"]:
        print(f"  {args.output_dir / filename}")
    print(f"  {dashboard_path}")
    print("Summary:")
    for key, value in result["summary"].items():
        print(f"  {key}: {value}")
    failed = result["checks"][~result["checks"]["passed"].astype(bool)]
    if not failed.empty:
        print("Validation checks needing review:")
        for _, row in failed.iterrows():
            print(f"  {row['check']}: {row['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
