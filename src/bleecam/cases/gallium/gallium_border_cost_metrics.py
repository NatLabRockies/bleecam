# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Post-process Gallium BLEECAM results into U.S. border landed-cost metrics.

This module is intentionally separate from the working Gallium Pyomo baseline.
It reads existing successful outputs and writes a separate dual-cost dashboard
package without changing model inputs, results, or dashboard files.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

US_LOCATION = "US"
WAFER_MARKET_MIX = "wafer_market_mix"
WAFER_DEMAND = "wafer_demand"
WAFER_MATERIALS = ("GaAs_wafer", "GaN_wafer")
FLOW_TOLERANCE = 1e-6


@dataclass(frozen=True)
class DualCostPaths:
    results_dir: Path = Path("output/gallium")
    output_dir: Path = Path("outputs/gallium_dual_cost_dashboard")
    repo_demand_path: Path = Path("data/gallium/demand_ga.csv")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path)


def load_existing_outputs(results_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the existing successful Gallium run outputs."""

    return {
        "flows": _read_csv(results_dir / "gallium_model_results.csv"),
        "cost_summary": _read_csv(results_dir / "gallium_cost_summary.csv"),
        "demand": _read_csv(results_dir / "gallium_demand_diagnostics.csv"),
        "capacity": _read_csv(results_dir / "gallium_capacity_utilization.csv"),
    }


def _node(process: str, location: str, material: str) -> tuple[str, str, str]:
    return (str(process), str(location), str(material))


def _unit_arc_cost(row: pd.Series) -> float:
    return float(row["total_unit_cost_usd_per_kg"])


def _positive_flows(flows: pd.DataFrame, tolerance: float = FLOW_TOLERANCE) -> pd.DataFrame:
    out = flows.copy()
    numeric_cols = [
        "quantity_kg",
        "processing_cost_usd_per_kg",
        "domestic_transport_cost_usd_per_kg",
        "shipping_cost_usd_per_kg",
        "tariff_cost_usd_per_kg",
        "total_unit_cost_usd_per_kg",
        "total_cost_usd",
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out[out["quantity_kg"] > tolerance].copy()


def compute_embodied_source_costs(
    flows: pd.DataFrame,
    *,
    tolerance: float = FLOW_TOLERANCE,
    max_iterations: int = 200,
    convergence_tol: float = 1e-9,
) -> dict[tuple[int, str, str, str], float]:
    """Approximate cumulative modeled cost available at each source node.

    The existing Gallium outputs do not contain a marginal/cumulative cost-to-node.
    This routine propagates path-attributed cost through the optimized positive-flow
    network. For material transformations, input value is allocated across outgoing
    positive flow at the same process/location, which accounts for yield losses in
    the observed optimized flow quantities.
    """

    positive = _positive_flows(flows, tolerance)
    result: dict[tuple[int, str, str, str], float] = {}

    for t, period_df in positive.groupby("time_period", sort=True):
        outgoing_qty_by_node: dict[tuple[str, str, str], float] = defaultdict(float)
        outgoing_qty_by_process: dict[tuple[str, str], float] = defaultdict(float)
        nodes: set[tuple[str, str, str]] = set()

        for _, row in period_df.iterrows():
            source = _node(row["process_from"], row["loc_from"], row["material"])
            dest = _node(row["process_to"], row["loc_to"], row["material"])
            q = float(row["quantity_kg"])
            outgoing_qty_by_node[source] += q
            outgoing_qty_by_process[(source[0], source[1])] += q
            nodes.add(source)
            nodes.add(dest)

        source_cost = {node: 0.0 for node in nodes}
        for _iteration in range(max_iterations):
            incoming_value_by_node: dict[tuple[str, str, str], float] = defaultdict(float)
            incoming_value_by_process: dict[tuple[str, str], float] = defaultdict(float)

            for _, row in period_df.iterrows():
                source = _node(row["process_from"], row["loc_from"], row["material"])
                dest = _node(row["process_to"], row["loc_to"], row["material"])
                q = float(row["quantity_kg"])
                delivered_unit = source_cost.get(source, 0.0) + _unit_arc_cost(row)
                delivered_value = q * delivered_unit
                incoming_value_by_node[dest] += delivered_value
                incoming_value_by_process[(dest[0], dest[1])] += delivered_value

            next_cost: dict[tuple[str, str, str], float] = {}
            max_delta = 0.0
            for node in nodes:
                out_qty = outgoing_qty_by_node.get(node, 0.0)
                process_key = (node[0], node[1])
                process_out_qty = outgoing_qty_by_process.get(process_key, 0.0)
                if out_qty <= tolerance:
                    new_value = source_cost.get(node, 0.0)
                elif incoming_value_by_node.get(node, 0.0) > tolerance:
                    new_value = incoming_value_by_node[node] / out_qty
                elif incoming_value_by_process.get(process_key, 0.0) > tolerance and process_out_qty > tolerance:
                    new_value = incoming_value_by_process[process_key] / process_out_qty
                else:
                    new_value = 0.0
                next_cost[node] = new_value
                max_delta = max(max_delta, abs(new_value - source_cost.get(node, 0.0)))
            source_cost = next_cost
            if max_delta <= convergence_tol:
                break

        for (process, location, material), unit_cost in source_cost.items():
            result[(int(t), process, location, material)] = float(unit_cost)
    return result


def _terminal_delivery_units(flows: pd.DataFrame) -> dict[tuple[int, str], float]:
    terminal = flows[
        (flows["process_from"] == WAFER_MARKET_MIX)
        & (flows["process_to"] == WAFER_DEMAND)
        & (flows["loc_from"] == US_LOCATION)
        & (flows["loc_to"] == US_LOCATION)
        & (flows["material"].isin(WAFER_MATERIALS))
        & (flows["quantity_kg"] > FLOW_TOLERANCE)
    ]
    units: dict[tuple[int, str], float] = {}
    for _, row in terminal.iterrows():
        units[(int(row["time_period"]), str(row["material"]))] = _unit_arc_cost(row)
    return units


def identify_final_us_wafer_supply(flows: pd.DataFrame) -> pd.DataFrame:
    """Return wafer supply arcs entering the U.S. demand system before origin is lost."""

    positive = _positive_flows(flows)
    supply = positive[
        positive["material"].isin(WAFER_MATERIALS)
        & (positive["loc_to"] == US_LOCATION)
        & positive["process_to"].isin([WAFER_MARKET_MIX, WAFER_DEMAND])
        & (positive["process_from"] != WAFER_MARKET_MIX)
    ].copy()
    supply["supply_type"] = supply["loc_from"].map(lambda loc: "domestic" if loc == US_LOCATION else "imported")
    supply["origin"] = supply["loc_from"]
    return supply


def calculate_landed_cost_metrics(
    flows: pd.DataFrame,
    demand: pd.DataFrame,
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    """Calculate U.S. landed-cost metrics from an optimized total-system solution."""

    embodied_cost = compute_embodied_source_costs(flows)
    terminal_units = _terminal_delivery_units(flows)
    supply = identify_final_us_wafer_supply(flows)
    rows: list[dict[str, Any]] = []

    for _, row in supply.iterrows():
        t = int(row["time_period"])
        material = str(row["material"])
        q = float(row["quantity_kg"])
        origin = str(row["origin"])
        source_key = (t, str(row["process_from"]), str(row["loc_from"]), material)
        source_embodied_unit = embodied_cost.get(source_key, 0.0)
        final_processing_unit = float(row["processing_cost_usd_per_kg"])
        final_shipping_transport_unit = float(row["domestic_transport_cost_usd_per_kg"]) + float(row["shipping_cost_usd_per_kg"])
        tariff_unit_existing = max(0.0, float(row["tariff_cost_usd_per_kg"]))
        terminal_delivery_unit = 0.0 if row["process_to"] == WAFER_DEMAND else terminal_units.get((t, material), 0.0)
        is_import = origin != US_LOCATION

        fob_unit = source_embodied_unit + final_processing_unit
        tariff_rate_proxy = tariff_unit_existing / fob_unit if is_import and fob_unit > 0 else 0.0
        tariff_base_fob_unit = fob_unit
        tariff_base_fob_plus_shipping_unit = fob_unit + final_shipping_transport_unit
        tariff_default_unit = tariff_rate_proxy * tariff_base_fob_unit if is_import else 0.0
        tariff_fob_plus_shipping_unit = tariff_rate_proxy * tariff_base_fob_plus_shipping_unit if is_import else 0.0

        customs_value_usd = q * fob_unit if is_import else 0.0
        import_shipping_usd = q * final_shipping_transport_unit if is_import else 0.0
        tariff_usd = q * tariff_default_unit if is_import else 0.0
        tariff_fob_plus_shipping_usd = q * tariff_fob_plus_shipping_unit if is_import else 0.0
        terminal_delivery_usd = q * terminal_delivery_unit

        if is_import:
            landed_import_cost_usd = customs_value_usd + import_shipping_usd + tariff_usd + terminal_delivery_usd
            domestic_delivered_unit = 0.0
            domestic_delivered_cost_usd = 0.0
        else:
            domestic_delivered_unit = source_embodied_unit + final_processing_unit + final_shipping_transport_unit + terminal_delivery_unit
            domestic_delivered_cost_usd = q * domestic_delivered_unit
            landed_import_cost_usd = 0.0

        rows.append(
            {
                "time_period": t,
                "material": material,
                "origin": origin,
                "supply_type": "imported" if is_import else "domestic",
                "process_from": str(row["process_from"]),
                "loc_from": str(row["loc_from"]),
                "process_to": str(row["process_to"]),
                "loc_to": str(row["loc_to"]),
                "quantity_kg": q,
                "source_embodied_unit_cost_usd_per_kg": source_embodied_unit,
                "final_wafer_processing_unit_cost_usd_per_kg": final_processing_unit,
                "FOB_unit_value_usd_per_kg": fob_unit if is_import else 0.0,
                "ship_unit_cost_usd_per_kg": final_shipping_transport_unit if is_import else 0.0,
                "tariff_rate_proxy": tariff_rate_proxy,
                "tariff_base_unit_usd_per_kg": tariff_base_fob_unit if is_import else 0.0,
                "tariff_base_convention": "FOB_unit_value; inferred rate from existing absolute tariff_cost_usd_per_kg",
                "tariff_unit_cost_default_usd_per_kg": tariff_default_unit,
                "tariff_unit_cost_fob_plus_shipping_sensitivity_usd_per_kg": tariff_fob_plus_shipping_unit,
                "customs_value_usd": customs_value_usd,
                "shipping_usd": import_shipping_usd,
                "tariff_usd": tariff_usd,
                "tariff_fob_plus_shipping_sensitivity_usd": tariff_fob_plus_shipping_usd,
                "terminal_delivery_unit_cost_usd_per_kg": terminal_delivery_unit,
                "terminal_delivery_usd": terminal_delivery_usd,
                "landed_import_cost_usd": landed_import_cost_usd,
                "domestic_delivered_unit_cost_usd_per_kg": domestic_delivered_unit,
                "domestic_delivered_cost_usd": domestic_delivered_cost_usd,
                "total_us_landed_cost_usd": landed_import_cost_usd + domestic_delivered_cost_usd,
                "average_landed_cost_component_usd_per_kg": (landed_import_cost_usd + domestic_delivered_cost_usd) / q if q else 0.0,
            }
        )

    detail = pd.DataFrame(rows)
    if detail.empty:
        detail = pd.DataFrame(
            columns=[
                "time_period",
                "material",
                "origin",
                "supply_type",
                "quantity_kg",
                "total_us_landed_cost_usd",
            ]
        )

    demand_wafer = demand[demand["material"].isin(WAFER_MATERIALS)].copy()
    demand_by_period = demand_wafer.groupby("time_period", as_index=False).agg(
        total_us_wafer_demand_kg=("demand_kg", "sum"),
        served_kg=("served_kg", "sum"),
        shortage_slack_kg=("shortage_slack_kg", "sum"),
    )

    by_period = detail.groupby("time_period", as_index=False).agg(
        imported_wafer_kg=("quantity_kg", lambda s: detail.loc[s.index][detail.loc[s.index, "supply_type"] == "imported"]["quantity_kg"].sum()),
        domestic_wafer_kg=("quantity_kg", lambda s: detail.loc[s.index][detail.loc[s.index, "supply_type"] == "domestic"]["quantity_kg"].sum()),
        customs_value_usd=("customs_value_usd", "sum"),
        shipping_usd=("shipping_usd", "sum"),
        tariff_usd=("tariff_usd", "sum"),
        tariff_fob_plus_shipping_sensitivity_usd=("tariff_fob_plus_shipping_sensitivity_usd", "sum"),
        terminal_delivery_usd=("terminal_delivery_usd", "sum"),
        landed_import_cost_usd=("landed_import_cost_usd", "sum"),
        domestic_delivered_cost_usd=("domestic_delivered_cost_usd", "sum"),
        total_us_landed_cost_usd=("total_us_landed_cost_usd", "sum"),
    )
    by_period = by_period.merge(demand_by_period, on="time_period", how="left")
    by_period["average_us_landed_cost_usd_per_kg"] = by_period["total_us_landed_cost_usd"] / by_period["total_us_wafer_demand_kg"]
    by_period["import_share"] = by_period["imported_wafer_kg"] / (by_period["imported_wafer_kg"] + by_period["domestic_wafer_kg"])
    by_period["domestic_share"] = by_period["domestic_wafer_kg"] / (by_period["imported_wafer_kg"] + by_period["domestic_wafer_kg"])

    by_origin_material = detail.groupby(["time_period", "origin", "material", "supply_type"], as_index=False).agg(
        quantity_kg=("quantity_kg", "sum"),
        customs_value_usd=("customs_value_usd", "sum"),
        shipping_usd=("shipping_usd", "sum"),
        tariff_usd=("tariff_usd", "sum"),
        tariff_fob_plus_shipping_sensitivity_usd=("tariff_fob_plus_shipping_sensitivity_usd", "sum"),
        terminal_delivery_usd=("terminal_delivery_usd", "sum"),
        landed_import_cost_usd=("landed_import_cost_usd", "sum"),
        domestic_delivered_cost_usd=("domestic_delivered_cost_usd", "sum"),
        total_us_landed_cost_usd=("total_us_landed_cost_usd", "sum"),
        FOB_unit_value_usd_per_kg=("FOB_unit_value_usd_per_kg", "mean"),
        ship_unit_cost_usd_per_kg=("ship_unit_cost_usd_per_kg", "mean"),
        tariff_rate_proxy=("tariff_rate_proxy", "mean"),
        domestic_delivered_unit_cost_usd_per_kg=("domestic_delivered_unit_cost_usd_per_kg", "mean"),
    )

    tariffs = detail[detail["supply_type"] == "imported"].copy()
    tariffs = tariffs[
        [
            "time_period",
            "origin",
            "material",
            "quantity_kg",
            "FOB_unit_value_usd_per_kg",
            "ship_unit_cost_usd_per_kg",
            "tariff_rate_proxy",
            "tariff_base_unit_usd_per_kg",
            "tariff_usd",
            "tariff_fob_plus_shipping_sensitivity_usd",
        ]
    ]

    domestic_vs_imported = detail.groupby(["time_period", "material", "supply_type"], as_index=False).agg(
        quantity_kg=("quantity_kg", "sum"),
        total_us_landed_cost_usd=("total_us_landed_cost_usd", "sum"),
    )
    totals = domestic_vs_imported.groupby(["time_period", "material"], as_index=False).agg(
        total_quantity_kg=("quantity_kg", "sum"),
        total_cost_usd=("total_us_landed_cost_usd", "sum"),
    )
    domestic_vs_imported = domestic_vs_imported.merge(totals, on=["time_period", "material"], how="left")
    domestic_vs_imported["supply_share"] = domestic_vs_imported["quantity_kg"] / domestic_vs_imported["total_quantity_kg"]

    return {
        "detail": detail,
        "by_period": by_period,
        "by_origin_material": by_origin_material,
        "tariffs": tariffs,
        "domestic_vs_imported": domestic_vs_imported,
        "embodied_costs": embodied_cost,
    }


def build_total_system_comparison(flows: pd.DataFrame, by_period: pd.DataFrame) -> pd.DataFrame:
    system = flows.groupby("time_period", as_index=False).agg(total_system_cost_usd=("total_cost_usd", "sum"))
    comparison = system.merge(
        by_period[
            [
                "time_period",
                "total_us_landed_cost_usd",
                "average_us_landed_cost_usd_per_kg",
                "total_us_wafer_demand_kg",
                "import_share",
                "domestic_share",
                "tariff_usd",
            ]
        ],
        on="time_period",
        how="left",
    )
    comparison["perspective_note"] = "U.S. landed cost is a post-processed metric under the total-system-cost-optimized solution."
    return comparison


def build_sankey_total_system(flows: pd.DataFrame) -> pd.DataFrame:
    positive = _positive_flows(flows, FLOW_TOLERANCE).copy()
    positive["source"] = positive["process_from"] + " | " + positive["loc_from"] + " | " + positive["material"]
    positive["target"] = positive["process_to"] + " | " + positive["loc_to"] + " | " + positive["material"]
    return positive[
        [
            "time_period",
            "source",
            "target",
            "material",
            "quantity_kg",
            "total_cost_usd",
            "total_unit_cost_usd_per_kg",
        ]
    ].rename(columns={"quantity_kg": "value_kg", "total_cost_usd": "cost_usd"})


def build_sankey_us_border(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=["time_period", "source", "target", "material", "value_kg", "cost_usd", "supply_type"])
    out = detail.copy()
    out["source"] = out["origin"] + " " + out["material"] + " wafer supply"
    out["target"] = "US wafer demand"
    return out[
        [
            "time_period",
            "source",
            "target",
            "material",
            "quantity_kg",
            "total_us_landed_cost_usd",
            "supply_type",
        ]
    ].rename(columns={"quantity_kg": "value_kg", "total_us_landed_cost_usd": "cost_usd"})


def _load_repo_demand_for_check(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "time_period" not in df.columns and "year" in df.columns:
        years = {year: idx for idx, year in enumerate(sorted(df["year"].unique()))}
        df = df.copy()
        df["time_period"] = df["year"].map(years)
    required = {"time_period", "location", "material", "flow", "demand_kg"}
    if not required.issubset(df.columns):
        return None
    return df


def validation_checks(
    flows: pd.DataFrame,
    demand: pd.DataFrame,
    by_period: pd.DataFrame,
    detail: pd.DataFrame,
    repo_demand_path: Path,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(check: str, passed: bool, detail_text: str) -> None:
        rows.append({"check": check, "passed": bool(passed), "detail": detail_text})

    add("no_negative_flow", bool((flows["quantity_kg"] >= -FLOW_TOLERANCE).all()), "All existing result flows are nonnegative within tolerance.")
    cost_cols = [c for c in flows.columns if "cost" in c]
    add("no_negative_cost", bool((flows[cost_cols] >= -FLOW_TOLERANCE).all().all()), "All reported unit and total costs are nonnegative within tolerance.")
    add("tariffs_nonnegative", bool((detail.get("tariff_usd", pd.Series(dtype=float)) >= -FLOW_TOLERANCE).all()), "All U.S. tariff calculations are nonnegative.")
    domestic_tariff = detail[(detail.get("supply_type", pd.Series(dtype=str)) == "domestic") & (detail.get("tariff_usd", pd.Series(dtype=float)).abs() > FLOW_TOLERANCE)]
    add("domestic_flows_not_charged_tariff", domestic_tariff.empty, f"Domestic tariff rows above tolerance: {len(domestic_tariff)}")
    add("wafer_materials_present", set(WAFER_MATERIALS).issubset(set(demand["material"])), "GaAs_wafer and GaN_wafer are present in successful-run demand diagnostics.")

    demand_sum = demand[demand["material"].isin(WAFER_MATERIALS)].groupby("time_period")["demand_kg"].sum().sort_index()
    supply_sum = detail.groupby("time_period")["quantity_kg"].sum().sort_index()
    aligned = pd.concat([demand_sum.rename("demand"), supply_sum.rename("supply")], axis=1).fillna(0.0)
    max_gap = float((aligned["demand"] - aligned["supply"]).abs().max()) if not aligned.empty else 0.0
    add("successful_output_demand_equals_identified_supply", max_gap <= 1e-4, f"Max period demand/supply gap kg: {max_gap:.8f}")

    avg_check = by_period.copy()
    avg_check["recomputed_avg"] = avg_check["total_us_landed_cost_usd"] / avg_check["total_us_wafer_demand_kg"]
    max_avg_gap = float((avg_check["recomputed_avg"] - avg_check["average_us_landed_cost_usd_per_kg"]).abs().max()) if not avg_check.empty else 0.0
    add("average_landed_cost_identity", max_avg_gap <= 1e-9, f"Max average-cost identity gap: {max_avg_gap:.12f}")

    repo_demand = _load_repo_demand_for_check(repo_demand_path)
    if repo_demand is None:
        add("repo_demand_file_comparable", False, f"Could not compare current repo demand file at {repo_demand_path} to successful output demand diagnostics.")
    else:
        repo_us = repo_demand[(repo_demand["location"] == US_LOCATION) & (repo_demand["flow"] == WAFER_DEMAND) & (repo_demand["material"].isin(WAFER_MATERIALS))]
        repo_group = repo_us.groupby(["time_period", "material"], as_index=False)["demand_kg"].sum()
        successful = demand[demand["material"].isin(WAFER_MATERIALS)][["time_period", "material", "demand_kg"]].copy()
        merged = successful.merge(repo_group, on=["time_period", "material"], how="outer", suffixes=("_successful_output", "_repo_demand")).fillna(0.0)
        max_repo_gap = float((merged["demand_kg_successful_output"] - merged["demand_kg_repo_demand"]).abs().max()) if not merged.empty else 0.0
        add("repo_demand_matches_successful_output", max_repo_gap <= 1e-4, f"Max demand gap kg between current data/gallium/demand_ga.csv and successful output diagnostics: {max_repo_gap:.8f}")

    imported = detail[detail.get("supply_type", pd.Series(dtype=str)) == "imported"]
    import_origin_ok = bool(((imported["origin"] != US_LOCATION) & (imported["loc_to"] == US_LOCATION)).all()) if not imported.empty else True
    add("imports_identified_as_non_us_into_us", import_origin_ok, "Imported wafer supply rows have non-U.S. origin and U.S. destination.")
    return pd.DataFrame(rows)


def write_methodology(
    path: Path,
    summary: dict[str, Any],
    checks: pd.DataFrame,
) -> None:
    lines = [
        "# Gallium Dual-Cost Dashboard Methodology",
        "",
        "## Scope",
        "",
        "This package is a post-processing layer over the existing successful Gallium total-system-cost baseline. It does not rerun or overwrite the working optimization, dashboard, input CSVs, or existing outputs.",
        "",
        "## U.S. Landed-Cost Formula",
        "",
        "For each period and wafer material, imported wafer landed cost is calculated as:",
        "",
        "`Q_import * (FOB_unit_value + ship_unit_cost + tariff_rate * tariff_base_unit)`",
        "",
        "Domestic U.S. wafer supply is calculated as:",
        "",
        "`Q_domestic * domestic_delivered_unit_cost`",
        "",
        "The dashboard also includes the U.S. wafer market-mix to demand terminal delivery cost when present, because the requested metric is delivered to the U.S. demand system.",
        "",
        "## FOB Unit Value Proxy",
        "",
        "The existing Gallium outputs do not contain a cumulative cost-to-node or marginal cost. FOB unit value is therefore approximated by propagating modeled embodied cost through the optimized positive-flow network. For material transformations, incoming embodied value is allocated across outgoing positive flow at the same process/location, so observed yield losses are reflected in the unit cost. This is a path-attributed modeled cost proxy, not an observed market price.",
        "",
        "## Tariff Convention",
        "",
        "The existing Gallium model reports `tariff_cost_usd_per_kg` as an additive absolute unit cost, not as an explicit ad valorem rate. For this dashboard, the default tariff base is FOB unit value. A proxy tariff rate is inferred as `tariff_cost_usd_per_kg / FOB_unit_value` when a positive tariff appears. The default tariff dollars therefore reproduce the existing model's absolute tariff convention. A sensitivity column also reports tariff dollars using `FOB_unit_value + shipping` as the tariff base.",
        "",
        "## Optimization Status",
        "",
        "No second optimization objective was implemented. U.S. landed cost is a post-processed metric under the existing total-system-cost-optimized solution.",
        "",
        "## Summary Metrics",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Validation Checks", ""])
    if checks.empty:
        lines.append("No validation checks were produced.")
    else:
        lines.append(checks.to_markdown(index=False))
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(paths: DualCostPaths) -> dict[str, Any]:
    data = load_existing_outputs(paths.results_dir)
    flows = data["flows"]
    demand = data["demand"]
    metrics = calculate_landed_cost_metrics(flows, demand)
    detail = metrics["detail"]
    by_period = metrics["by_period"]
    by_origin_material = metrics["by_origin_material"]
    tariffs = metrics["tariffs"]
    domestic_vs_imported = metrics["domestic_vs_imported"]
    comparison = build_total_system_comparison(flows, by_period)
    sankey_total = build_sankey_total_system(flows)
    sankey_us = build_sankey_us_border(detail)
    checks = validation_checks(flows, demand, by_period, detail, paths.repo_demand_path)

    paths.output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "us_border_landed_cost_by_period.csv": by_period,
        "us_border_landed_cost_by_origin_material.csv": by_origin_material,
        "tariffs_paid_by_us.csv": tariffs,
        "domestic_vs_imported_wafer_supply.csv": domestic_vs_imported,
        "total_system_vs_us_border_cost_comparison.csv": comparison,
        "sankey_flows_total_system_cost.csv": sankey_total,
        "sankey_flows_us_border_landed_cost.csv": sankey_us,
        "validation_checks.csv": checks,
    }
    for filename, df in files.items():
        df.to_csv(paths.output_dir / filename, index=False)

    total_system_cost = float(flows["total_cost_usd"].sum())
    total_landed = float(by_period["total_us_landed_cost_usd"].sum())
    total_demand = float(by_period["total_us_wafer_demand_kg"].sum())
    total_tariffs = float(by_period["tariff_usd"].sum())
    total_imports = float(by_period["imported_wafer_kg"].sum())
    total_domestic = float(by_period["domestic_wafer_kg"].sum())
    summary = {
        "total_system_cost_usd": f"{total_system_cost:,.2f}",
        "us_border_landed_cost_usd": f"{total_landed:,.2f}",
        "average_us_landed_cost_usd_per_kg": f"{(total_landed / total_demand if total_demand else 0.0):,.2f}",
        "tariffs_paid_usd": f"{total_tariffs:,.2f}",
        "total_us_wafer_demand_kg": f"{total_demand:,.6f}",
        "imported_wafer_kg": f"{total_imports:,.6f}",
        "domestic_wafer_kg": f"{total_domestic:,.6f}",
        "import_share": f"{(total_imports / (total_imports + total_domestic) if total_imports + total_domestic else 0.0):.2%}",
        "domestic_share": f"{(total_domestic / (total_imports + total_domestic) if total_imports + total_domestic else 0.0):.2%}",
    }
    write_methodology(paths.output_dir / "dual_cost_methodology.md", summary, checks)
    return {
        "paths": paths,
        "summary": summary,
        "checks": checks,
        "files": list(files.keys()) + ["dual_cost_methodology.md"],
    }
