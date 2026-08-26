# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Cost-only Gallium Pyomo baseline.

This model consumes ``gallium_data_loader.py`` output and solves a least-cost
supply-chain flow problem for GaAs and GaN wafer demand. It intentionally
keeps the formulation smooth and continuous for IPOPT, and does not load
emissions factors or Social LCA factors.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import html
import json
from pathlib import Path
from typing import Any

import pandas as pd
from pyomo.environ import (
    ConcreteModel,
    ConstraintList,
    NonNegativeReals,
    Objective,
    Set,
    Var,
    minimize,
    value,
)
from pyomo.opt import SolverFactory, TerminationCondition

from .config_ga import (
    DEFAULT_INPUT_DIR,
    DEFAULT_RESULTS_CSV,
    DEMAND_SLACK_PENALTY_USD_PER_KG,
    DEMAND_SOURCE_PROCESS,
    FLOW_TOLERANCE,
    SOLVER_CANDIDATES,
    TIME_PERIODS,
    build_cost_maps,
    unit_cost_for_arc,
)
from .constraints_ga import (
    add_capacity_constraints_ga,
    add_demand_constraints_ga,
    add_yield_mass_balance_constraints_ga,
    summarize_demand_slack,
)
from .gallium_data_loader import GalliumValidationError, load_gallium_data

from bleecam.core.lca_import import WEIGHTED_GWP_COL, load_impact_factor_maps
from bleecam.core.objectives import (
    demand_slack_penalty_expression,
    impact_objective_rule,
    linear_flow_expression,
)

# Every flow variable gets a finite upper bound so no objective (single-impact or
# AUGMECON) can produce an unbounded ray. The bound is DERIVED FROM THE DATA — a
# large multiple of total horizon demand — rather than a hard-coded magic number,
# so it is provably far above any feasible flow yet finite. See
# docs/methods_multiobjective.md: the *proper* fix for unboundedness is realistic
# finite process capacities (several upstream capacities are effectively-unlimited
# placeholders); this bound is a safety cap until those are tightened.
FLOW_BOUND_DEMAND_MULTIPLE = 1.0e6

# Per-kg, per-period holding cost for the finished-good inventory buffer. Positive so
# banking is never beneficial at baseline (the golden stays unchanged); only a
# strategic-reserve constraint or a supply-shock scenario induces a stockpile.
STOCK_HOLDING_COST_USD_PER_KG = 50.0


def flow_upper_bound(loaded_data: dict[str, Any]) -> float:
    """Return the per-flow upper bound: total horizon demand x a large safety multiple."""
    total_demand = float(loaded_data["demand_df"]["demand_kg"].sum())
    return max(total_demand, 1.0) * FLOW_BOUND_DEMAND_MULTIPLE

# Friendly objective aliases -> impact-table column names (env + social).
OBJECTIVE_ALIASES = {
    "gwp": WEIGHTED_GWP_COL,
    "child_labor": "SLCA_EF - Child labor impact (worker hour/kg)",
    "forced_labor": "SLCA_EF - Forced labor impact (worker hour/kg)",
    "fatal_injury": "SLCA_EF - Fatal injury impact (worker hour/kg)",
    "nonfatal_injury": "SLCA_EF - Non-fatal injury impact (worker hour/kg)",
}


class GalliumModelError(RuntimeError):
    """Raised when the Gallium Pyomo baseline cannot be built or solved."""


class SolverUnavailableError(GalliumModelError):
    """Raised when no configured Pyomo solver is available."""


def _loader_report_paths(out_dir: Path) -> tuple[Path, Path]:
    return out_dir / "gallium_loader_validation_report.md", out_dir / "gallium_loader_validation_report.csv"


def load_inputs(data_dir: Path, out_dir: Path, strict: bool = True) -> dict[str, Any]:
    """Load Gallium CSVs through the validated Gallium loader."""

    out_dir.mkdir(parents=True, exist_ok=True)
    report_md, report_csv = _loader_report_paths(out_dir)
    data = load_gallium_data(
        data_dir,
        report_md_path=report_md,
        report_csv_path=report_csv,
        strict=strict,
    )
    # Attach environmental/social impact factor maps from the EF table (the
    # engine-agnostic contract). Optional: cost-only runs work without it.
    impact_factors: dict[str, dict] = {}
    provenance: dict[str, Any] = {}
    ef_path = Path(data_dir) / "EF_Template.csv"
    if ef_path.exists():
        impact_factors.update(load_impact_factor_maps(ef_path, prefixes=("EF_",)))
        provenance["ef_file"] = str(ef_path)
    # Social (S-LCA) factors: same contract, SLCA_ columns, separate file.
    social_path = Path(data_dir) / "social_lca_template_ga.csv"
    if social_path.exists():
        impact_factors.update(load_impact_factor_maps(social_path, prefixes=("SLCA",)))
        provenance["social_file"] = str(social_path)
    data["impact_factors"] = impact_factors
    provenance["n_impact_categories"] = len(impact_factors)
    data["ef_provenance"] = provenance
    return data


def _flow_arc_records(loaded_data: dict[str, Any]) -> list[tuple[int, str, str, str, str, str]]:
    arcs = sorted(loaded_data["allowed_trade_arcs"])
    return [(t, *arc) for t in TIME_PERIODS for arc in arcs]


def _demand_keys(demand_df: pd.DataFrame) -> list[tuple[int, str, str]]:
    keys = []
    for _, row in demand_df.iterrows():
        key = (int(row["time_period"]), str(row["location"]).strip(), str(row["material"]).strip())
        if key not in keys:
            keys.append(key)
    return keys


def _safe_value(expr, default: float = 0.0) -> float:
    raw = value(expr, exception=False)
    if raw is None:
        return default
    return float(raw)


def _resolve_impact_column(objective: str, impact_factors: dict) -> str:
    """Map a friendly objective name (or raw EF column) to an EF column present in the table."""
    col = OBJECTIVE_ALIASES.get(objective, objective)
    if col not in impact_factors:
        available = sorted(impact_factors)
        raise GalliumModelError(
            f"Impact objective {objective!r} (column {col!r}) is not in the EF table. "
            f"{len(available)} categories available, e.g. {available[:3]}. "
            "Ensure EF_Template.csv is present in the data dir."
        )
    return col


def gallium_flow_cost_expression(model: ConcreteModel, cost_maps) -> Any:
    """Total per-unit-cost-weighted flow (processing + transport + shipping + tariff)."""
    total = 0.0
    for key in model.FlowArcs:
        t, process_from, loc_from, process_to, loc_to, material = key
        unit_cost = sum(
            unit_cost_for_arc(
                cost_maps, int(t), str(process_from), str(loc_from),
                str(process_to), str(loc_to), str(material),
            )
        )
        total += unit_cost * model.flowQ[key]
    return total


def assemble_gallium_network(loaded_data: dict[str, Any]):
    """Build the Gallium network model (sets, bounded flow vars, constraints) with
    no objective. Shared by the single-objective builder and the AUGMECON runner.

    :returns: ``(model, cost_maps)``.
    """
    cost_maps = build_cost_maps(loaded_data)
    model = ConcreteModel(name="Gallium supply-chain network")
    model.TimePeriods = Set(initialize=loaded_data["time_periods"], ordered=True)
    model.Processes = Set(initialize=loaded_data["processes"], ordered=True)
    model.Processes2 = Set(initialize=loaded_data["processes"], ordered=True)
    model.Locations = Set(initialize=loaded_data["locations"], ordered=True)
    model.materials = Set(initialize=loaded_data["materials"], ordered=True)
    model.FlowArcs = Set(dimen=6, initialize=_flow_arc_records(loaded_data), ordered=True)
    model.DemandKeys = Set(dimen=3, initialize=_demand_keys(loaded_data["demand_df"]), ordered=True)

    ub = flow_upper_bound(loaded_data)
    model.flowQ = Var(model.FlowArcs, domain=NonNegativeReals, bounds=(0, ub), initialize=0.0)
    model.demand_slack = Var(model.DemandKeys, domain=NonNegativeReals, initialize=0.0)
    # Finished-good inventory buffer (enables strategic-reserve / stockpile analysis).
    stock_materials = sorted({m for (_, _, m) in model.DemandKeys})
    model.StockMaterials = Set(initialize=stock_materials, ordered=True)
    model.stock_level = Var(model.TimePeriods, model.StockMaterials, domain=NonNegativeReals, bounds=(0, ub), initialize=0.0)
    model.flow_to_stock = Var(model.TimePeriods, model.StockMaterials, domain=NonNegativeReals, bounds=(0, ub), initialize=0.0)
    model.flow_from_stock = Var(model.TimePeriods, model.StockMaterials, domain=NonNegativeReals, bounds=(0, ub), initialize=0.0)
    model.constraints = ConstraintList()
    model._flow_upper_bound = ub
    model._stock_holding_cost = STOCK_HOLDING_COST_USD_PER_KG

    _periods = list(model.TimePeriods)
    for _m in stock_materials:
        for _i, _t in enumerate(_periods):
            _prev = model.stock_level[_periods[_i - 1], _m] if _i > 0 else 0.0
            model.constraints.add(model.stock_level[_t, _m] == _prev + model.flow_to_stock[_t, _m] - model.flow_from_stock[_t, _m])

    add_capacity_constraints_ga(model, loaded_data["max_output_capacity"])
    add_yield_mass_balance_constraints_ga(model, loaded_data["yield_factor"])
    add_demand_constraints_ga(model, loaded_data["demand_df"])

    model._gallium_cost_maps = cost_maps
    # Generic economic contract: a plain {arc_key -> unit cost ($/kg)} map so
    # case-agnostic economic levers (e.g. price_support) can read per-arc costs
    # without importing any gallium-specific cost logic.
    model._arc_unit_cost = {
        key: float(sum(unit_cost_for_arc(
            cost_maps, int(key[0]), str(key[1]), str(key[2]),
            str(key[3]), str(key[4]), str(key[5]),
        )))
        for key in model.FlowArcs
    }
    return model, cost_maps


def build_model(loaded_data: dict[str, Any], objective: str = "cost") -> ConcreteModel:
    """Build the Gallium supply-chain model.

    :param objective: ``"cost"`` (default), ``"gwp"``, a social alias
        (``"child_labor"`` ...), or any ``EF_*``/``SLCA`` impact column present in
        the impact table. Non-cost objectives minimize the factor-weighted
        network flow via :mod:`bleecam.core.objectives`.

    Impact objectives are built on *normalized* factors (scaled to O(1)) with a
    fixed demand-slack penalty and a tiny total-flow regularizer. Normalization
    keeps the LP well-conditioned across categories whose raw factors span many
    orders of magnitude; the flow regularizer bounds the problem, since a pure
    single-impact objective can be unbounded (impact-free, and even cost-free,
    recycling loops admit infinite flow). The regularizer is negligible against
    the O(1) impact, so the impact floor is read back from the flows exactly.
    """

    model, cost_maps = assemble_gallium_network(loaded_data)

    if objective == "cost":
        cost_expr = gallium_flow_cost_expression(model, cost_maps) + \
            DEMAND_SLACK_PENALTY_USD_PER_KG * sum(model.demand_slack[key] for key in model.DemandKeys) + \
            model._stock_holding_cost * sum(model.stock_level[t, m] for t in model.TimePeriods for m in model.StockMaterials)
        model.obj = Objective(expr=cost_expr, sense=minimize)
        model._bleecam_objective = "cost"
    else:
        impact_factors = loaded_data.get("impact_factors", {})
        col = _resolve_impact_column(objective, impact_factors)
        factor_map = impact_factors[col]
        max_factor = max((abs(v) for v in factor_map.values()), default=0.0)
        if max_factor <= 0:
            raise GalliumModelError(
                f"Impact category {col!r} has all-zero/empty factors; cannot optimize it."
            )
        # Normalize factors to O(1) so the LP is well-conditioned regardless of
        # the category's raw magnitude (social factors span ~1e-8..1e-1).
        norm_map = {k: v / max_factor for k, v in factor_map.items()}
        # Normalized impact per kg is <= 1, so this penalty strongly forces demand.
        slack_penalty = 1.0e3
        # Tiny total-flow regularizer: bounds impact-free (and cost-free) rays and
        # drives incidental flows to zero; negligible vs the O(1) impact so the
        # true floor is recovered from the flows.
        flow_reg = 1.0e-6
        impact_expr = (
            linear_flow_expression(model, norm_map)
            + demand_slack_penalty_expression(model, slack_penalty)
            + flow_reg * sum(model.flowQ[key] for key in model.FlowArcs)
        )
        model.obj = Objective(expr=impact_expr, sense=minimize)
        model._bleecam_objective = col
        model._bleecam_impact_scale = max_factor
    model._gallium_cost_maps = cost_maps
    return model


# Solver selection is shared in bleecam.core.solve. The Gallium case keeps its
# own SolverUnavailableError (a GalliumModelError) for its existing except
# clauses, so we delegate to core and translate the exception type.
from bleecam.core.solve import available_solver as _core_available_solver
from bleecam.core.solve import choose_solver as _core_choose_solver
from bleecam.core.solve import SolverUnavailableError as _CoreSolverUnavailableError


def available_solver(name: str):
    return _core_available_solver(name)


def choose_solver(requested: str = "auto"):
    """Return the requested available solver, or the first configured solver."""
    try:
        return _core_choose_solver(requested, candidates=SOLVER_CANDIDATES)
    except _CoreSolverUnavailableError as exc:
        raise SolverUnavailableError(str(exc)) from exc


def solve_model(model: ConcreteModel, solver_name: str = "auto", tee: bool = False) -> dict[str, Any]:
    """Solve the model and return a compact status dictionary."""

    selected_name, solver = choose_solver(solver_name)
    result = solver.solve(model, tee=tee)
    termination = result.solver.termination_condition
    status = str(result.solver.status)
    objective_value = value(model.obj, exception=False)
    slack_rows = summarize_demand_slack(model, FLOW_TOLERANCE)
    if termination == TerminationCondition.optimal:
        solve_status = "optimal_with_slack" if slack_rows else "optimal"
    elif termination in {TerminationCondition.feasible, TerminationCondition.locallyOptimal}:
        solve_status = "feasible_with_slack" if slack_rows else "feasible"
    elif termination == TerminationCondition.infeasible:
        solve_status = "infeasible"
    else:
        solve_status = str(termination)
    return {
        "solver": selected_name,
        "solver_status": status,
        "termination_condition": str(termination),
        "solve_status": solve_status,
        "objective_value": None if objective_value is None else float(objective_value),
        "demand_slack": slack_rows,
    }


def diagnose_input_package(loaded_data: dict[str, Any]) -> dict[str, Any]:
    """Identify likely data issues before or after solve."""

    issues = []
    blocking = [
        issue for issue in loaded_data.get("validation_issues", []) if issue.get("severity") == "blocking"
    ]
    for issue in blocking:
        issues.append(
            {
                "category": _issue_category(issue.get("issue_type", "")),
                "issue_type": issue.get("issue_type", ""),
                "file": issue.get("file", ""),
                "row_or_key": issue.get("row_or_key", ""),
                "recommendation": issue.get("recommendation", ""),
            }
        )
    return {"blocking_issue_count": len(blocking), "issues": issues}


def _issue_category(issue_type: str) -> str:
    if "demand" in issue_type or "terminal" in issue_type:
        return "demand/topology"
    if "capacity" in issue_type:
        return "capacity"
    if "yield" in issue_type:
        return "yield"
    if "topology" in issue_type or "arc" in issue_type:
        return "topology"
    if "cost" in issue_type or "shipping" in issue_type or "tariff" in issue_type:
        return "cost/shipping"
    if "missing_required_file" in issue_type:
        return "missing input"
    return "input data"


def nonzero_flow_rows(model: ConcreteModel, tolerance: float = FLOW_TOLERANCE) -> list[dict[str, Any]]:
    """Return clean result rows for nonzero flow variables."""

    rows = []
    cost_maps = model._gallium_cost_maps
    for key in model.FlowArcs:
        quantity = _safe_value(model.flowQ[key])
        if quantity <= tolerance:
            continue
        t, process_from, loc_from, process_to, loc_to, material = key
        cost_parts = unit_cost_for_arc(
            cost_maps,
            int(t),
            str(process_from),
            str(loc_from),
            str(process_to),
            str(loc_to),
            str(material),
        )
        unit_cost = sum(cost_parts)
        rows.append(
            {
                "time_period": int(t),
                "process_from": str(process_from),
                "loc_from": str(loc_from),
                "process_to": str(process_to),
                "loc_to": str(loc_to),
                "material": str(material),
                "quantity_kg": quantity,
                "processing_cost_usd_per_kg": cost_parts[0],
                "domestic_transport_cost_usd_per_kg": cost_parts[1],
                "shipping_cost_usd_per_kg": cost_parts[2],
                "tariff_cost_usd_per_kg": cost_parts[3],
                "total_unit_cost_usd_per_kg": unit_cost,
                "total_cost_usd": unit_cost * quantity,
            }
        )
    return rows


def flow_results_dataframe(model: ConcreteModel) -> pd.DataFrame:
    """Return nonzero flow results with both clean and REE-style column names."""

    df = pd.DataFrame(nonzero_flow_rows(model))
    if df.empty:
        return pd.DataFrame(
            columns=[
                "time_period",
                "process_from",
                "loc_from",
                "process_to",
                "loc_to",
                "material",
                "quantity_kg",
                "processing_cost_usd_per_kg",
                "domestic_transport_cost_usd_per_kg",
                "shipping_cost_usd_per_kg",
                "tariff_cost_usd_per_kg",
                "total_unit_cost_usd_per_kg",
                "total_cost_usd",
                "source",
                "source_location",
                "destination",
                "destination_location",
                "flow_value",
            ]
        )
    df["source"] = df["process_from"]
    df["source_location"] = df["loc_from"]
    df["destination"] = df["process_to"]
    df["destination_location"] = df["loc_to"]
    df["flow_value"] = df["quantity_kg"]
    return df


def write_results_csv(model: ConcreteModel, path: Path) -> None:
    """Write nonzero flow results to CSV."""

    rows = nonzero_flow_rows(model)
    fieldnames = [
        "time_period",
        "process_from",
        "loc_from",
        "process_to",
        "loc_to",
        "material",
        "quantity_kg",
        "processing_cost_usd_per_kg",
        "domestic_transport_cost_usd_per_kg",
        "shipping_cost_usd_per_kg",
        "tariff_cost_usd_per_kg",
        "total_unit_cost_usd_per_kg",
        "total_cost_usd",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def demand_diagnostics_dataframe(model: ConcreteModel, loaded_data: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for _, row in loaded_data["demand_df"].iterrows():
        t = int(row["time_period"])
        location = str(row["location"]).strip()
        material = str(row["material"]).strip()
        flow = str(row["flow"]).strip()
        demand = float(row["demand_kg"])
        terminal_key = (t, DEMAND_SOURCE_PROCESS, location, flow, location, material)
        served = _safe_value(model.flowQ[terminal_key]) if terminal_key in model.flowQ else 0.0
        slack_key = (t, location, material)
        raw_slack = _safe_value(model.demand_slack[slack_key]) if slack_key in model.demand_slack else 0.0
        slack = 0.0 if abs(raw_slack) <= FLOW_TOLERANCE else raw_slack
        rows.append(
            {
                "time_period": t,
                "location": location,
                "material": material,
                "demand_kg": demand,
                "served_kg": served,
                "shortage_slack_kg": slack,
                "served_fraction": served / demand if demand else 1.0,
                "status": "slack" if slack > FLOW_TOLERANCE else "met",
            }
        )
    return pd.DataFrame(rows)


def _outgoing_quantity(model: ConcreteModel, t: int, process: str, location: str, material: str) -> float:
    total = 0.0
    for key in model.FlowArcs:
        kt, process_from, loc_from, _process_to, _loc_to, mat = key
        if int(kt) == int(t) and str(process_from) == process and str(loc_from) == location and str(mat) == material:
            total += _safe_value(model.flowQ[key])
    return total


def capacity_diagnostics_dataframe(model: ConcreteModel, loaded_data: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for (process, location, material), period_caps in loaded_data["max_output_capacity"].items():
        for t, capacity in period_caps.items():
            used = _outgoing_quantity(model, int(t), process, location, material)
            rows.append(
                {
                    "time_period": int(t),
                    "process": process,
                    "location": location,
                    "material": material,
                    "capacity_kg": float(capacity),
                    "used_kg": used,
                    "remaining_capacity_kg": float(capacity) - used,
                    "utilization_fraction": used / float(capacity) if float(capacity) > 0 else None,
                    "binding": bool(float(capacity) > 0 and abs(float(capacity) - used) <= 1e-5),
                }
            )
    return pd.DataFrame(rows)


def cost_summary_dataframe(flow_df: pd.DataFrame) -> pd.DataFrame:
    if flow_df.empty:
        return pd.DataFrame(columns=["time_period", "material", "quantity_kg", "total_cost_usd"])
    return (
        flow_df.groupby(["time_period", "material"], as_index=False)
        .agg(quantity_kg=("quantity_kg", "sum"), total_cost_usd=("total_cost_usd", "sum"))
        .sort_values(["time_period", "material"])
    )


def write_markdown_diagnostic_report(
    path: Path,
    solve_summary: dict[str, Any],
    flow_df: pd.DataFrame,
    demand_df: pd.DataFrame,
    capacity_df: pd.DataFrame,
    cost_df: pd.DataFrame,
) -> None:
    total_flow = float(flow_df["quantity_kg"].sum()) if not flow_df.empty else 0.0
    total_cost = float(flow_df["total_cost_usd"].sum()) if not flow_df.empty else 0.0
    total_slack = float(demand_df["shortage_slack_kg"].sum()) if not demand_df.empty else 0.0
    top_capacity = capacity_df.dropna(subset=["utilization_fraction"]).sort_values(
        "utilization_fraction", ascending=False
    ).head(10)

    lines = [
        "# Gallium Cost-Only Diagnostic Report",
        "",
        f"Generated: {_dt.datetime.now().isoformat(timespec='seconds')}",
        f"Solve status: `{solve_summary.get('solve_status')}`",
        f"Solver: `{solve_summary.get('solver')}`",
        f"Termination: `{solve_summary.get('termination_condition')}`",
        f"Objective value: `{solve_summary.get('objective_value')}`",
        "",
        "## Summary",
        "",
        f"- Nonzero flow rows: {len(flow_df)}",
        f"- Total flow: {total_flow:,.6f} kg",
        f"- Total flow cost: ${total_cost:,.2f}",
        f"- Total demand slack: {total_slack:,.6f} kg",
        "",
        "## Demand And Slack",
        "",
        demand_df.to_markdown(index=False) if not demand_df.empty else "No demand rows found.",
        "",
        "## Cost By Period And Material",
        "",
        cost_df.to_markdown(index=False) if not cost_df.empty else "No nonzero flow costs found.",
        "",
        "## Highest Capacity Utilization",
        "",
        top_capacity.to_markdown(index=False) if not top_capacity.empty else "No positive capacity utilization found.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _records_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    clean = df.where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def write_html_diagnostic_report(
    path: Path,
    solve_summary: dict[str, Any],
    flow_df: pd.DataFrame,
    demand_df: pd.DataFrame,
    capacity_df: pd.DataFrame,
    cost_df: pd.DataFrame,
) -> None:
    """Write a Gallium-specific interactive HTML report."""

    flow_records = _records_for_json(flow_df)
    demand_records = _records_for_json(demand_df)
    capacity_top = capacity_df.dropna(subset=["utilization_fraction"]).sort_values(
        "utilization_fraction", ascending=False
    ).head(25)
    total_flow = float(flow_df["quantity_kg"].sum()) if not flow_df.empty else 0.0
    total_cost = float(flow_df["total_cost_usd"].sum()) if not flow_df.empty else 0.0
    total_slack = float(demand_df["shortage_slack_kg"].sum()) if not demand_df.empty else 0.0
    cross_border = int((flow_df["loc_from"] != flow_df["loc_to"]).sum()) if not flow_df.empty else 0

    demand_table = demand_df.to_html(index=False, classes="data-table", border=0) if not demand_df.empty else "<p>No demand rows.</p>"
    capacity_table = capacity_top.to_html(index=False, classes="data-table", border=0) if not capacity_top.empty else "<p>No capacity utilization.</p>"
    cost_table = cost_df.to_html(index=False, classes="data-table", border=0) if not cost_df.empty else "<p>No flow costs.</p>"

    payload = {
        "flows": flow_records,
        "demand": demand_records,
        "cost": _records_for_json(cost_df),
    }
    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gallium Cost-Only Diagnostic Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f6f8; color: #20242a; }}
header {{ background: #243b53; color: white; padding: 18px 28px; }}
main {{ padding: 22px 28px; max-width: 1400px; margin: auto; }}
.card-row {{ display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 14px; }}
.card {{ background: white; border-radius: 6px; padding: 16px; border-top: 4px solid #2f80ed; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.card h3 {{ margin: 0 0 8px; color: #667085; font-size: 12px; text-transform: uppercase; }}
.card .value {{ font-size: 24px; font-weight: 700; }}
section {{ background: white; margin-top: 18px; padding: 18px; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
h2 {{ margin-top: 0; font-size: 18px; color: #243b53; }}
.data-table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
.data-table th {{ background: #243b53; color: white; text-align: left; padding: 7px; }}
.data-table td {{ border-bottom: 1px solid #e5e7eb; padding: 6px 7px; }}
.chart {{ height: 420px; }}
@media (max-width: 900px) {{ .card-row {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>Gallium Cost-Only Diagnostic Report</h1>
  <div>Generated {_dt.datetime.now().isoformat(timespec='seconds')} | Status {html.escape(str(solve_summary.get('solve_status')))}</div>
</header>
<main>
  <div class="card-row">
    <div class="card"><h3>Objective</h3><div class="value">{solve_summary.get('objective_value')}</div></div>
    <div class="card"><h3>Total Flow</h3><div class="value">{total_flow:,.2f} kg</div></div>
    <div class="card"><h3>Total Cost</h3><div class="value">${total_cost:,.2f}</div></div>
    <div class="card"><h3>Demand Slack</h3><div class="value">{total_slack:,.2f} kg</div></div>
  </div>
  <section><h2>Flow By Material And Period</h2><div id="flowChart" class="chart"></div></section>
  <section><h2>Cost By Material And Period</h2><div id="costChart" class="chart"></div></section>
  <section><h2>Demand Fulfillment</h2>{demand_table}</section>
  <section><h2>Top Capacity Utilization</h2>{capacity_table}</section>
  <section><h2>Cost Summary</h2>{cost_table}</section>
  <section><h2>Nonzero Flow Table</h2><p>{len(flow_df)} nonzero flow rows; {cross_border} cross-location rows.</p>{flow_df.to_html(index=False, classes='data-table', border=0) if not flow_df.empty else '<p>No nonzero flows.</p>'}</section>
</main>
<script>
const payload = {json.dumps(payload)};
const periods = [...new Set(payload.flows.map(r => r.time_period))].sort((a,b) => a-b);
const materials = [...new Set(payload.flows.map(r => r.material))].sort();
const flowTraces = materials.map(mat => {{
  return {{
    type: 'bar', name: mat, x: periods,
    y: periods.map(t => payload.flows.filter(r => r.time_period === t && r.material === mat).reduce((s,r) => s + r.quantity_kg, 0))
  }};
}});
Plotly.react('flowChart', flowTraces, {{barmode:'stack', xaxis:{{title:'Time period'}}, yaxis:{{title:'kg'}}, margin:{{t:20}}}}, {{responsive:true}});
const costTraces = materials.map(mat => {{
  return {{
    type: 'bar', name: mat, x: periods,
    y: periods.map(t => payload.flows.filter(r => r.time_period === t && r.material === mat).reduce((s,r) => s + r.total_cost_usd, 0))
  }};
}});
Plotly.react('costChart', costTraces, {{barmode:'stack', xaxis:{{title:'Time period'}}, yaxis:{{title:'USD'}}, margin:{{t:20}}}}, {{responsive:true}});
</script>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def write_plot_outputs(out_dir: Path, flow_df: pd.DataFrame, demand_df: pd.DataFrame, capacity_df: pd.DataFrame) -> list[Path]:
    """Write static Gallium diagnostic plots as PNG files."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paths: list[Path] = []

    def save_placeholder(path: Path, title: str, message: str) -> None:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.axis("off")
        ax.set_title(title)
        ax.text(0.5, 0.5, message, ha="center", va="center")
        fig.tight_layout()
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(path)

    flow_path = out_dir / "gallium_flow_by_material.png"
    if flow_df.empty:
        save_placeholder(flow_path, "Gallium Flow By Material", "No nonzero flows")
    else:
        pivot = flow_df.pivot_table(index="time_period", columns="material", values="quantity_kg", aggfunc="sum", fill_value=0)
        ax = pivot.plot(kind="bar", stacked=True, figsize=(10, 5))
        ax.set_xlabel("Time period")
        ax.set_ylabel("Flow (kg)")
        ax.set_title("Gallium Flow By Material")
        ax.figure.tight_layout()
        ax.figure.savefig(flow_path, dpi=160)
        plt.close(ax.figure)
        paths.append(flow_path)

    demand_path = out_dir / "gallium_demand_fulfillment.png"
    if demand_df.empty:
        save_placeholder(demand_path, "Gallium Demand Fulfillment", "No demand rows")
    else:
        plot_df = demand_df.pivot_table(index="time_period", columns="material", values=["demand_kg", "served_kg", "shortage_slack_kg"], aggfunc="sum", fill_value=0)
        ax = plot_df.plot(kind="bar", figsize=(12, 5))
        ax.set_xlabel("Time period")
        ax.set_ylabel("kg")
        ax.set_title("Gallium Demand, Served Flow, And Slack")
        ax.figure.tight_layout()
        ax.figure.savefig(demand_path, dpi=160)
        plt.close(ax.figure)
        paths.append(demand_path)

    capacity_path = out_dir / "gallium_top_capacity_utilization.png"
    cap = capacity_df.dropna(subset=["utilization_fraction"]).copy()
    cap = cap[cap["utilization_fraction"] > 0].sort_values("utilization_fraction", ascending=False).head(20)
    if cap.empty:
        save_placeholder(capacity_path, "Gallium Capacity Utilization", "No positive capacity utilization")
    else:
        cap["label"] = cap["process"] + " | " + cap["location"] + " | " + cap["material"] + " | t=" + cap["time_period"].astype(str)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(cap["label"], cap["utilization_fraction"])
        ax.invert_yaxis()
        ax.set_xlabel("Utilization fraction")
        ax.set_title("Top Gallium Capacity Utilization")
        fig.tight_layout()
        fig.savefig(capacity_path, dpi=160)
        plt.close(fig)
        paths.append(capacity_path)
    return paths


def write_diagnostic_outputs(
    model: ConcreteModel,
    loaded_data: dict[str, Any],
    solve_summary: dict[str, Any],
    out_dir: Path,
    *,
    write_html: bool = True,
    write_plots: bool = True,
) -> list[Path]:
    """Write Gallium diagnostic report files, HTML, and plots."""

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    flow_df = flow_results_dataframe(model)
    demand_df = demand_diagnostics_dataframe(model, loaded_data)
    capacity_df = capacity_diagnostics_dataframe(model, loaded_data)
    cost_df = cost_summary_dataframe(flow_df)

    for filename, df in [
        ("gallium_nonzero_flows_diagnostic.csv", flow_df),
        ("gallium_demand_diagnostics.csv", demand_df),
        ("gallium_capacity_utilization.csv", capacity_df),
        ("gallium_cost_summary.csv", cost_df),
    ]:
        path = out_dir / filename
        df.to_csv(path, index=False)
        paths.append(path)

    report_path = out_dir / "gallium_diagnostic_report.md"
    write_markdown_diagnostic_report(report_path, solve_summary, flow_df, demand_df, capacity_df, cost_df)
    paths.append(report_path)

    if write_html:
        html_path = out_dir / "gallium_diagnostic_report.html"
        write_html_diagnostic_report(html_path, solve_summary, flow_df, demand_df, capacity_df, cost_df)
        paths.append(html_path)

    if write_plots:
        paths.extend(write_plot_outputs(out_dir, flow_df, demand_df, capacity_df))
    return paths


def _resolve_output_path(out_dir: Path, requested: Path) -> Path:
    return requested if requested.is_absolute() else out_dir / requested


def run(args: argparse.Namespace) -> int:
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        loaded_data = load_inputs(args.input_dir, out_dir, strict=True)
    except GalliumValidationError as exc:
        print(f"Input validation failed: {exc}")
        partial = load_inputs(args.input_dir, out_dir, strict=False)
        print(diagnose_input_package(partial))
        return 2

    model = build_model(loaded_data)
    try:
        solve_summary = solve_model(model, args.solver, tee=args.tee)
    except SolverUnavailableError as exc:
        print(f"Solver unavailable: {exc}")
        return 3

    print(solve_summary)
    solved = solve_summary["solve_status"] in {
        "optimal",
        "optimal_with_slack",
        "feasible",
        "feasible_with_slack",
    }
    if solved:
        if not args.no_write_results:
            results_path = _resolve_output_path(out_dir, args.results)
            write_results_csv(model, results_path)
            print(f"Wrote nonzero flows to {results_path}")
            if not args.no_diagnostics:
                paths = write_diagnostic_outputs(
                    model,
                    loaded_data,
                    solve_summary,
                    out_dir,
                    write_html=not args.no_html,
                    write_plots=not args.no_plots,
                )
                print("Wrote Gallium diagnostics:")
                for path in paths:
                    print(f"  {path}")
    elif solve_summary["solve_status"] == "infeasible":
        print(diagnose_input_package(loaded_data))
        return 4
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Gallium cost-only Pyomo baseline.")
    parser.add_argument(
        "--input-dir",
        "--data",
        dest="input_dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Flat directory containing Gallium CSV inputs, matching gallium_data_loader.py.",
    )
    parser.add_argument("--out", type=Path, default=Path("."))
    parser.add_argument("--results", type=Path, default=Path(DEFAULT_RESULTS_CSV))
    parser.add_argument("--solver", default="auto")
    parser.add_argument("--tee", action="store_true")
    parser.add_argument("--no-write-results", action="store_true")
    parser.add_argument("--no-diagnostics", action="store_true")
    parser.add_argument("--no-html", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Console-script entry point (see pyproject `bleecam-ga`)."""
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
