# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Run separate Gallium policy scenarios without touching baseline outputs.

Scenarios:
1. total_system_cost: the normal Gallium total-system-cost objective.
2. china_capacity_shutdown: a policy proxy for China-origin gallium export controls
   where all CN process capacities are forced to zero at runtime.

This script writes only under outputs/gallium_policy_scenarios/ by default.
"""

from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from typing import Any

import pandas as pd

from gallium_border_cost_metrics import (
    calculate_landed_cost_metrics,
    build_sankey_total_system,
    build_sankey_us_border,
    load_existing_outputs,
)
from gallium_pyomo import (
    load_inputs,
    build_model,
    solve_model,
    write_results_csv,
    write_diagnostic_outputs,
)
from gallium_policy_scenario_dashboard import render_policy_dashboard

CN_LOCATION = "CN"
SCENARIOS = ("total_system_cost", "china_capacity_shutdown")


def discover_successful_input_dir(report_path: Path = Path("output/gallium/gallium_loader_validation_report.md")) -> Path:
    """Use the successful baseline loader report to locate the flat runtime input package."""

    if report_path.exists():
        match = re.search(r"Input directory: `([^`]+)`", report_path.read_text(encoding="utf-8"))
        if match:
            return Path(match.group(1))
    return Path("data/gallium")


def apply_china_capacity_shutdown(loaded_data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of loaded_data with all CN process output capacities set to zero."""

    scenario_data = loaded_data.copy()
    scenario_data["max_output_capacity"] = copy.deepcopy(loaded_data["max_output_capacity"])
    zeroed_keys = 0
    for (process, location, material), period_caps in scenario_data["max_output_capacity"].items():
        if location == CN_LOCATION:
            for t in list(period_caps):
                period_caps[t] = 0.0
            zeroed_keys += 1
    scenario_data["scenario_note"] = (
        "China capacity shutdown proxy: all max_output_capacity entries with location == CN "
        "were set to zero at runtime. Input CSVs were not modified."
    )
    scenario_data["china_capacity_keys_zeroed"] = zeroed_keys
    return scenario_data


def run_one_scenario(
    base_loaded_data: dict[str, Any],
    scenario: str,
    out_dir: Path,
    solver: str,
) -> dict[str, Any]:
    """Build, solve, and write one Gallium scenario."""

    scenario_dir = out_dir / scenario
    scenario_dir.mkdir(parents=True, exist_ok=True)
    if scenario == "china_capacity_shutdown":
        loaded_data = apply_china_capacity_shutdown(base_loaded_data)
    elif scenario == "total_system_cost":
        loaded_data = base_loaded_data.copy()
    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    model = build_model(loaded_data)
    solve_summary = solve_model(model, solver_name=solver, tee=False)
    results_path = scenario_dir / "gallium_model_results.csv"
    write_results_csv(model, results_path)
    diagnostic_paths = write_diagnostic_outputs(model, loaded_data, solve_summary, scenario_dir)

    data = load_existing_outputs(scenario_dir)
    landed = calculate_landed_cost_metrics(data["flows"], data["demand"])
    landed_files = {
        "us_border_landed_cost_by_period.csv": landed["by_period"],
        "us_border_landed_cost_by_origin_material.csv": landed["by_origin_material"],
        "tariffs_paid_by_us.csv": landed["tariffs"],
        "domestic_vs_imported_wafer_supply.csv": landed["domestic_vs_imported"],
        "sankey_flows_total_system_cost.csv": build_sankey_total_system(data["flows"]),
        "sankey_flows_us_border_landed_cost.csv": build_sankey_us_border(landed["detail"]),
    }
    for filename, df in landed_files.items():
        df.to_csv(scenario_dir / filename, index=False)

    flows = data["flows"]
    demand = data["demand"]
    by_period = landed["by_period"]
    summary = {
        "scenario": scenario,
        "solver": solve_summary.get("solver"),
        "solve_status": solve_summary.get("solve_status"),
        "termination_condition": solve_summary.get("termination_condition"),
        "objective_value": solve_summary.get("objective_value"),
        "total_system_cost_usd": float(flows["total_cost_usd"].sum()),
        "us_border_landed_cost_usd": float(by_period["total_us_landed_cost_usd"].sum()),
        "average_us_landed_cost_usd_per_kg": float(by_period["total_us_landed_cost_usd"].sum() / by_period["total_us_wafer_demand_kg"].sum()),
        "tariffs_paid_usd": float(by_period["tariff_usd"].sum()),
        "imported_wafer_kg": float(by_period["imported_wafer_kg"].sum()),
        "domestic_wafer_kg": float(by_period["domestic_wafer_kg"].sum()),
        "total_us_wafer_demand_kg": float(by_period["total_us_wafer_demand_kg"].sum()),
        "demand_slack_kg": float(demand["shortage_slack_kg"].sum()),
        "china_capacity_keys_zeroed": loaded_data.get("china_capacity_keys_zeroed", 0),
        "scenario_note": loaded_data.get("scenario_note", "Baseline total-system-cost run."),
        "results_dir": str(scenario_dir),
        "result_rows": int(len(flows)),
        "diagnostic_file_count": int(len(diagnostic_paths)),
    }
    return summary


def write_policy_methodology(out_dir: Path, input_dir: Path) -> None:
    text = f"""# Gallium Policy Scenario Methodology

## Trade Policy Interpretation

China's December 3, 2024 measure was an export-control action, not a tariff. Public reports and Chinese state-media summaries describe the rule as: in principle, exports to the United States of dual-use items related to gallium, germanium, antimony, and superhard materials were not permitted. As of late 2025, public reporting says that China suspended the U.S.-specific ban until November 27, 2026, but licensing controls remain. This means a tariff-only representation is not the cleanest model for the Gallium case.

## Scenario Design

This package therefore compares two optimization runs:

1. `total_system_cost`: unchanged Gallium total-system-cost optimization using the successful flat runtime input package.
2. `china_capacity_shutdown`: a conservative export-ban proxy where all `max_output_capacity` entries with `location == CN` are set to zero at runtime. No input CSVs are modified.

This is stricter than a CN-to-US export-arc ban because the current model does not carry country-of-origin tags through transshipment. A pure CN-to-US arc ban could allow China-origin material to route through a third country and lose origin identity. Shutting CN capacity removes Chinese supply from the optimized network.

## Input Directory

`{input_dir}`

## Objective

Both runs still optimize the existing Gallium total-system-cost objective. U.S. landed/border cost is calculated afterward for each solved route using the dual-cost post-processing logic.

## Tariff Convention

The current Gallium cost table sets the positive U.S. tariff rows on gallium intermediate flows into U.S. processing, not on the positive finished-wafer import route from CN to U.S. market mix. Finished CN wafer import arcs have `tariff_cost = 0` in the current data. Therefore baseline U.S. tariffs paid are zero.
"""
    (out_dir / "policy_scenario_methodology.md").write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gallium baseline and China-shutdown policy scenarios.")
    parser.add_argument("--input-dir", type=Path, default=None, help="Flat Gallium runtime input directory. Defaults to the input dir recorded in output/gallium/gallium_loader_validation_report.md.")
    parser.add_argument("--out", type=Path, default=Path("outputs/gallium_policy_scenarios"), help="New scenario output folder.")
    parser.add_argument("--solver", default="auto")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir or discover_successful_input_dir()
    args.out.mkdir(parents=True, exist_ok=True)
    loaded_data = load_inputs(input_dir, args.out / "loader_reports", strict=True)

    summaries = []
    for scenario in SCENARIOS:
        print(f"Running {scenario}...")
        summaries.append(run_one_scenario(loaded_data, scenario, args.out, args.solver))

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(args.out / "scenario_summary.csv", index=False)
    write_policy_methodology(args.out, input_dir)
    dashboard_path = render_policy_dashboard(args.out)

    print("Wrote policy scenario comparison outputs:")
    print(f"  {args.out / 'scenario_summary.csv'}")
    print(f"  {args.out / 'policy_scenario_methodology.md'}")
    print(f"  {dashboard_path}")
    print(summary_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
