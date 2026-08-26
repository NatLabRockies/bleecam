# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Render a Gallium policy scenario comparison dashboard."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pandas as pd

MATERIAL_COLORS = {
    "bauxite": "rgba(117,117,117,0.45)",
    "Bayer_liquor": "rgba(44,160,44,0.42)",
    "4N_Ga": "rgba(31,119,180,0.45)",
    "6N_Ga": "rgba(255,127,14,0.45)",
    "GaAs_wafer": "rgba(214,39,40,0.48)",
    "GaN_wafer": "rgba(148,103,189,0.48)",
    "Zn_sphalerite_concentrate": "rgba(227,119,194,0.35)",
    "ZLR_Zn_residue": "rgba(140,86,75,0.35)",
}
NODE_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]
STAGE_HINTS = {
    "Bauxite mining": 0,
    "ZS mining": 0,
    "Bayer process / alumina refining": 1,
    "Zinc concentration": 1,
    "Bayer liquor refining": 2,
    "Zinc smelting/refining": 2,
    "ZLR refining": 3,
    "High-purity gallium refining": 3,
    "New manufacturing scrap recovery": 3,
    "TMG synthesis": 4,
    "Wafer manufacturing": 4,
    "wafer_market_mix": 5,
    "wafer_demand": 6,
}
LOCATION_ORDER = {"AU": 0, "CA": 1, "CN": 2, "GR": 3, "JP": 4, "KR": 5, "KZ": 6, "US": 7}
ACTIVE_GWP_COLUMN = "EF_weighted__Global Warming Potential (Gwp1000)"


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.where(pd.notna(df), None).to_dict(orient="records")


def _discover_runtime_demand_path(out_dir: Path) -> Path | None:
    report_path = out_dir / "loader_reports" / "gallium_loader_validation_report.md"
    if not report_path.exists():
        return None
    import re

    match = re.search(r"Input directory: `([^`]+)`", report_path.read_text(encoding="utf-8"))
    if not match:
        return None
    demand_path = Path(match.group(1)) / "demand_ga.csv"
    return demand_path if demand_path.exists() else None


def _load_us_wafer_demand(out_dir: Path) -> tuple[pd.DataFrame, str]:
    demand_path = _discover_runtime_demand_path(out_dir)
    source = "successful scenario demand diagnostics"
    if demand_path is not None:
        demand = pd.read_csv(demand_path)
        source = str(demand_path)
    else:
        demand = pd.read_csv(_scenario_dir(out_dir, "total_system_cost") / "gallium_demand_diagnostics.csv")

    demand = demand.copy()
    if "time_period" not in demand.columns and "year" in demand.columns:
        years = sorted(demand["year"].dropna().unique().tolist())
        year_to_period = {year: idx for idx, year in enumerate(years)}
        demand["time_period"] = demand["year"].map(year_to_period)
    if "year" not in demand.columns:
        demand["year"] = demand["time_period"].astype(int).map(lambda value: 2025 + int(value))
    if "demand_kg" not in demand.columns and "served_kg" in demand.columns:
        demand["demand_kg"] = demand["served_kg"]

    mask = (demand["location"].astype(str) == "US") & demand["material"].isin(["GaAs_wafer", "GaN_wafer"])
    if "flow" in demand.columns:
        mask &= demand["flow"].astype(str).eq("wafer_demand")
    demand = demand[mask].copy()
    return demand[["time_period", "year", "material", "demand_kg"]], source


def _demand_summary(demand: pd.DataFrame) -> dict[str, Any]:
    if demand.empty:
        return {"cagr": 0.0, "shares": {}, "total_start": 0.0, "total_end": 0.0}
    total_by_period = demand.groupby("time_period")["demand_kg"].sum().sort_index()
    first = float(total_by_period.iloc[0])
    last = float(total_by_period.iloc[-1])
    years = int(total_by_period.index[-1] - total_by_period.index[0])
    cagr = (last / first) ** (1 / years) - 1 if first > 0 and years > 0 else 0.0
    material_totals = demand.groupby("material")["demand_kg"].sum()
    total = float(material_totals.sum())
    shares = {material: float(value / total) for material, value in material_totals.items()} if total > 0 else {}
    return {"cagr": cagr, "shares": shares, "total_start": first, "total_end": last}


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _kg(value: float) -> str:
    return f"{value:,.2f} kg"


def _process_location_node(label: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in str(label).split(" | ")]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return str(label), "", ""


def _node_label(process: str, location: str) -> str:
    return f"{process} ({location})" if location else process


def _node_label_components(label: str) -> tuple[str, str]:
    text = str(label)
    if text.endswith(")") and " (" in text:
        process, location = text.rsplit(" (", 1)
        return process, location[:-1]
    process, location, _material = _process_location_node(text)
    return process, location


def _stage_for_label(label: str) -> int:
    process, _location = _node_label_components(label)
    return STAGE_HINTS.get(process, 3)


def _ordered_nodes(nodes: set[str]) -> list[str]:
    def sort_key(label: str) -> tuple[int, int, str]:
        process, location = _node_label_components(label)
        return (STAGE_HINTS.get(process, 3), LOCATION_ORDER.get(location, 99), label)

    return sorted(nodes, key=sort_key)


def _stage_based_sankey_by_period(
    df: pd.DataFrame,
    *,
    min_value_kg: float = 1e-3,
    max_links_per_period: int = 80,
) -> dict[str, Any]:
    if df.empty:
        return {"periods": [], "byPeriod": {}}

    out: dict[str, Any] = {}
    periods = sorted(df["time_period"].dropna().astype(int).unique().tolist())
    for period in periods:
        period_df = df[(df["time_period"] == period) & (df["value_kg"] > min_value_kg)].copy()
        if period_df.empty:
            out[str(period)] = {"labels": [], "sources": [], "targets": [], "values": [], "materials": [], "colors": [], "x": [], "y": [], "nodeColors": []}
            continue
        period_df["source_node"] = period_df["source"].map(lambda v: _node_label(*_process_location_node(v)[:2]))
        period_df["target_node"] = period_df["target"].map(lambda v: _node_label(*_process_location_node(v)[:2]))
        grouped = (
            period_df.groupby(["source_node", "target_node", "material"], as_index=False)
            .agg(value_kg=("value_kg", "sum"), cost_usd=("cost_usd", "sum"))
            .sort_values("value_kg", ascending=False)
            .head(max_links_per_period)
        )
        nodes = _ordered_nodes(set(grouped["source_node"]).union(set(grouped["target_node"])))
        node_index = {label: idx for idx, label in enumerate(nodes)}
        max_stage = max([_stage_for_label(label) for label in nodes] or [1])
        stage_counts: dict[int, int] = {}
        stage_seen: dict[int, int] = {}
        for label in nodes:
            stage = _stage_for_label(label)
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        x_vals = []
        y_vals = []
        node_colors = []
        for idx, label in enumerate(nodes):
            stage = _stage_for_label(label)
            stage_seen[stage] = stage_seen.get(stage, 0) + 1
            count = stage_counts.get(stage, 1)
            x_vals.append(0.04 + 0.84 * (stage / max(max_stage, 1)))
            y_vals.append(stage_seen[stage] / (count + 1))
            node_colors.append(NODE_COLORS[idx % len(NODE_COLORS)])
        out[str(period)] = {
            "labels": nodes,
            "sources": [int(node_index[v]) for v in grouped["source_node"]],
            "targets": [int(node_index[v]) for v in grouped["target_node"]],
            "values": grouped["value_kg"].astype(float).tolist(),
            "materials": grouped["material"].astype(str).tolist(),
            "colors": [MATERIAL_COLORS.get(str(mat), "rgba(120,120,120,0.35)") for mat in grouped["material"]],
            "x": x_vals,
            "y": y_vals,
            "nodeColors": node_colors,
        }
    return {"periods": periods, "byPeriod": out}


def _us_sankey_by_period(df: pd.DataFrame, min_value_kg: float = 1e-6) -> dict[str, Any]:
    if df.empty:
        return {"periods": [], "byPeriod": {}}
    out: dict[str, Any] = {}
    periods = sorted(df["time_period"].dropna().astype(int).unique().tolist())
    for period in periods:
        period_df = df[(df["time_period"] == period) & (df["value_kg"] > min_value_kg)].copy()
        if period_df.empty:
            out[str(period)] = {"labels": [], "sources": [], "targets": [], "values": [], "materials": [], "colors": [], "x": [], "y": [], "nodeColors": []}
            continue
        labels = []
        idx = {}

        def add(label: str) -> int:
            if label not in idx:
                idx[label] = len(labels)
                labels.append(label)
            return idx[label]

        sources = [add(str(v)) for v in period_df["source"]]
        targets = [add(str(v)) for v in period_df["target"]]
        out[str(period)] = {
            "labels": labels,
            "sources": sources,
            "targets": targets,
            "values": period_df["value_kg"].astype(float).tolist(),
            "materials": period_df["material"].astype(str).tolist(),
            "colors": [MATERIAL_COLORS.get(str(mat), "rgba(120,120,120,0.35)") for mat in period_df["material"]],
            "x": [0.02 if i < len(set(sources)) else 0.96 for i in range(len(labels))],
            "y": [(i + 1) / (len(labels) + 1) for i in range(len(labels))],
            "nodeColors": [NODE_COLORS[i % len(NODE_COLORS)] for i in range(len(labels))],
        }
    return {"periods": periods, "byPeriod": out}


def _html_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    return df.head(max_rows).to_html(index=False, classes="data-table", border=0)


def _scenario_dir(base: Path, scenario: str) -> Path:
    return base / scenario


def _load_scope_a_ef(repo_root: Path) -> pd.DataFrame:
    ef_path = repo_root / "data" / "gallium" / "EF_Template.csv"
    ef = pd.read_csv(ef_path)
    if ACTIVE_GWP_COLUMN not in ef.columns:
        raise KeyError(f"{ACTIVE_GWP_COLUMN} not found in {ef_path}")
    ef[ACTIVE_GWP_COLUMN] = pd.to_numeric(ef[ACTIVE_GWP_COLUMN], errors="coerce").fillna(0.0)
    return ef[["time_period", "source", "location", "material", ACTIVE_GWP_COLUMN, "lcia_scope_name", "comments"]]


def _load_lci_inventory(repo_root: Path) -> pd.DataFrame:
    lci_path = repo_root / "data" / "gallium" / "lci" / "gallium_master_lci_liaison_ready.csv"
    if not lci_path.exists():
        return pd.DataFrame()
    lci = pd.read_csv(lci_path)
    lci["value"] = pd.to_numeric(lci["value"], errors="coerce").fillna(0.0)
    lci["input_bool"] = lci["input"].astype(str).str.lower().isin(["true", "1", "yes"])
    return lci


def _scenario_flow_impacts(out_dir: Path, scenario: str, label: str, ef: pd.DataFrame) -> pd.DataFrame:
    flows = pd.read_csv(_scenario_dir(out_dir, scenario) / "gallium_model_results.csv")
    merged = flows.merge(
        ef,
        left_on=["time_period", "process_from", "loc_from", "material"],
        right_on=["time_period", "source", "location", "material"],
        how="left",
    )
    merged[ACTIVE_GWP_COLUMN] = pd.to_numeric(merged[ACTIVE_GWP_COLUMN], errors="coerce").fillna(0.0)
    merged["scope_A_gwp_kg_co2e"] = merged["quantity_kg"] * merged[ACTIVE_GWP_COLUMN]
    merged["scenario"] = label
    return merged


def _hotspot_records(impact_frames: list[pd.DataFrame]) -> pd.DataFrame:
    impacts = pd.concat(impact_frames, ignore_index=True)
    grouped = (
        impacts.groupby(["scenario", "time_period", "process_from", "loc_from", "material"], as_index=False)
        .agg(
            flow_kg=("quantity_kg", "sum"),
            scope_A_gwp_factor=("EF_weighted__Global Warming Potential (Gwp1000)", "first"),
            scope_A_gwp_kg_co2e=("scope_A_gwp_kg_co2e", "sum"),
        )
    )
    grouped["node_key"] = grouped["process_from"] + " (" + grouped["loc_from"] + ") -> " + grouped["material"]
    grouped = grouped.sort_values(["scenario", "time_period", "scope_A_gwp_kg_co2e"], ascending=[True, True, False])
    return grouped


def _network_io_records(impact_frames: list[pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for frame in impact_frames:
        scenario = frame["scenario"].iloc[0]
        for _, row in frame.iterrows():
            rows.append(
                {
                    "scenario": scenario,
                    "time_period": int(row["time_period"]),
                    "process": row["process_from"],
                    "location": row["loc_from"],
                    "direction": "output",
                    "counterparty": f"{row['process_to']} ({row['loc_to']})",
                    "material": row["material"],
                    "quantity_kg": float(row["quantity_kg"]),
                    "gwp_kg_co2e": float(row["scope_A_gwp_kg_co2e"]),
                }
            )
            rows.append(
                {
                    "scenario": scenario,
                    "time_period": int(row["time_period"]),
                    "process": row["process_to"],
                    "location": row["loc_to"],
                    "direction": "input",
                    "counterparty": f"{row['process_from']} ({row['loc_from']})",
                    "material": row["material"],
                    "quantity_kg": float(row["quantity_kg"]),
                    "gwp_kg_co2e": float(row["scope_A_gwp_kg_co2e"]),
                }
            )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return (
        out.groupby(["scenario", "time_period", "process", "location", "direction", "counterparty", "material"], as_index=False)
        .agg(quantity_kg=("quantity_kg", "sum"), gwp_kg_co2e=("gwp_kg_co2e", "sum"))
        .sort_values(["scenario", "time_period", "process", "location", "direction", "quantity_kg"], ascending=[True, True, True, True, True, False])
    )


def _lci_io_records(lci: pd.DataFrame, max_rows_per_process_location: int = 12) -> pd.DataFrame:
    if lci.empty:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for (process, location, direction), group in lci.groupby(
        ["process", "process_location", lci["input_bool"].map({True: "input", False: "output"})]
    ):
        subset = group.copy()
        subset["abs_value"] = subset["value"].abs()
        subset = subset.sort_values("abs_value", ascending=False).head(max_rows_per_process_location)
        subset["process"] = process
        subset["location"] = location
        subset["direction"] = direction
        rows.append(subset[["process", "location", "direction", "flow", "value", "unit", "type", "supplying_location", "Ecoinvent selection"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def render_policy_dashboard(out_dir: Path) -> Path:
    repo_root = Path.cwd()
    summary = pd.read_csv(out_dir / "scenario_summary.csv")
    baseline = summary[summary["scenario"] == "total_system_cost"].iloc[0]
    shutdown = summary[summary["scenario"] == "china_capacity_shutdown"].iloc[0]
    baseline_period = pd.read_csv(_scenario_dir(out_dir, "total_system_cost") / "us_border_landed_cost_by_period.csv")
    shutdown_period = pd.read_csv(_scenario_dir(out_dir, "china_capacity_shutdown") / "us_border_landed_cost_by_period.csv")
    baseline_origin = pd.read_csv(_scenario_dir(out_dir, "total_system_cost") / "us_border_landed_cost_by_origin_material.csv")
    shutdown_origin = pd.read_csv(_scenario_dir(out_dir, "china_capacity_shutdown") / "us_border_landed_cost_by_origin_material.csv")
    demand_df, demand_source = _load_us_wafer_demand(out_dir)
    demand_info = _demand_summary(demand_df)
    baseline_sankey = pd.read_csv(_scenario_dir(out_dir, "total_system_cost") / "sankey_flows_total_system_cost.csv")
    shutdown_sankey = pd.read_csv(_scenario_dir(out_dir, "china_capacity_shutdown") / "sankey_flows_total_system_cost.csv")
    baseline_us_sankey = pd.read_csv(_scenario_dir(out_dir, "total_system_cost") / "sankey_flows_us_border_landed_cost.csv")
    shutdown_us_sankey = pd.read_csv(_scenario_dir(out_dir, "china_capacity_shutdown") / "sankey_flows_us_border_landed_cost.csv")
    ef = _load_scope_a_ef(repo_root)
    lci = _load_lci_inventory(repo_root)
    baseline_impacts = _scenario_flow_impacts(out_dir, "total_system_cost", "Baseline total-system cost", ef)
    shutdown_impacts = _scenario_flow_impacts(out_dir, "china_capacity_shutdown", "China capacity shutdown", ef)
    hotspot_df = _hotspot_records([baseline_impacts, shutdown_impacts])
    network_io_df = _network_io_records([baseline_impacts, shutdown_impacts])
    lci_io_df = _lci_io_records(lci)

    hotspot_dir = out_dir / "dashboard_hotspot_inputs_outputs"
    hotspot_dir.mkdir(parents=True, exist_ok=True)
    hotspot_df.to_csv(hotspot_dir / "scope_A_gwp_hotspots_by_process_period.csv", index=False)
    network_io_df.to_csv(hotspot_dir / "optimized_network_inputs_outputs_by_process_period.csv", index=False)
    lci_io_df.to_csv(hotspot_dir / "lci_recipe_top_inputs_outputs_by_process.csv", index=False)

    delta_system = float(shutdown["total_system_cost_usd"] - baseline["total_system_cost_usd"])
    delta_landed = float(shutdown["us_border_landed_cost_usd"] - baseline["us_border_landed_cost_usd"])
    delta_avg = float(shutdown["average_us_landed_cost_usd_per_kg"] - baseline["average_us_landed_cost_usd_per_kg"])

    payload = {
        "summary": _records(summary),
        "baselinePeriod": _records(baseline_period),
        "shutdownPeriod": _records(shutdown_period),
        "demand": _records(demand_df),
        "demandSource": demand_source,
        "demandInfo": demand_info,
        "baselineSankey": _stage_based_sankey_by_period(baseline_sankey),
        "shutdownSankey": _stage_based_sankey_by_period(shutdown_sankey),
        "baselineUSSankey": _us_sankey_by_period(baseline_us_sankey),
        "shutdownUSSankey": _us_sankey_by_period(shutdown_us_sankey),
        "hotspots": _records(hotspot_df),
        "networkIO": _records(network_io_df),
        "lciIO": _records(lci_io_df),
        "hotspotNote": "Scope A material-supply baseline GWP uses data/gallium/EF_Template.csv. Full wafer-processing LCIA is excluded from Scope A; wafer demand and process flow remain in the optimizer.",
    }

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gallium Policy Scenario Comparison</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{ margin:0; font-family:Arial, sans-serif; background:#f6f7f9; color:#20242a; }}
header {{ background:#223b55; color:white; padding:22px 32px; }}
main {{ max-width:1540px; margin:0 auto; padding:24px 30px 48px; }}
.card-row {{ display:grid; grid-template-columns:repeat(4,minmax(190px,1fr)); gap:14px; }}
.card {{ background:white; border-radius:6px; padding:16px; border-top:4px solid #2878d7; box-shadow:0 1px 5px rgba(0,0,0,.08); }}
.card h3 {{ margin:0 0 8px; color:#5d6b82; font-size:12px; text-transform:uppercase; }}
.card .value {{ font-size:22px; font-weight:700; }}
section {{ background:white; margin-top:18px; padding:20px; border-radius:6px; box-shadow:0 1px 5px rgba(0,0,0,.08); }}
h2 {{ margin:0 0 12px; color:#223b55; font-size:20px; }}
p {{ line-height:1.45; }}
.note {{ background:#eef4fb; border-left:4px solid #2878d7; padding:12px 14px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.stack {{ display:grid; grid-template-columns:1fr; gap:22px; }}
.chart {{ height:430px; }}
.chart.tall {{ height:700px; }}
.chart.medium {{ height:430px; }}
.control-row {{ display:flex; align-items:center; gap:10px; margin:8px 0 12px; }}
.control-row select {{ padding:6px 8px; border:1px solid #cbd5e1; border-radius:4px; background:white; }}
.mini-grid {{ display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)); gap:12px; margin:10px 0 14px; }}
.mini-card {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:5px; padding:11px; }}
.mini-card h4 {{ margin:0 0 6px; font-size:11px; color:#64748b; text-transform:uppercase; }}
.mini-card .metric {{ font-size:18px; font-weight:700; color:#1e293b; }}
.legend {{ display:flex; flex-wrap:wrap; gap:10px; font-size:12px; margin-bottom:8px; }}
.legend span {{ display:inline-flex; align-items:center; gap:5px; }}
.legend i {{ width:14px; height:8px; display:inline-block; border-radius:2px; }}
.data-table {{ border-collapse:collapse; width:100%; font-size:12px; }}
.data-table th {{ background:#223b55; color:white; padding:7px; text-align:left; }}
.data-table td {{ border-bottom:1px solid #e5e7eb; padding:6px 7px; }}
.scroll-table {{ max-height:360px; overflow:auto; border:1px solid #e5e7eb; border-radius:5px; }}
@media(max-width:1000px) {{ .card-row,.grid2 {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>Gallium Policy Scenario Comparison</h1>
  <div>Generated {dt.datetime.now().isoformat(timespec='seconds')} | Baseline total-system optimization vs China capacity-shutdown proxy</div>
</header>
<main>
  <div class="card-row">
    <div class="card"><h3>Baseline System Cost</h3><div class="value">{_money(float(baseline['total_system_cost_usd']))}</div></div>
    <div class="card"><h3>Shutdown System Cost</h3><div class="value">{_money(float(shutdown['total_system_cost_usd']))}</div></div>
    <div class="card"><h3>System Cost Delta</h3><div class="value">{_money(delta_system)}</div></div>
    <div class="card"><h3>Shutdown Slack</h3><div class="value">{_kg(float(shutdown['demand_slack_kg']))}</div></div>
  </div>
  <div class="card-row" style="margin-top:14px;">
    <div class="card"><h3>Baseline Landed Cost</h3><div class="value">{_money(float(baseline['us_border_landed_cost_usd']))}</div></div>
    <div class="card"><h3>Shutdown Landed Cost</h3><div class="value">{_money(float(shutdown['us_border_landed_cost_usd']))}</div></div>
    <div class="card"><h3>Landed Cost Delta</h3><div class="value">{_money(delta_landed)}</div></div>
    <div class="card"><h3>Avg Landed Delta</h3><div class="value">{_money(delta_avg)}/kg</div></div>
  </div>

  <section>
    <h2>Interpretation</h2>
    <p class="note">This is not a tariff scenario. China's measure is better represented as export availability / export-control risk. The shutdown scenario forces all CN process capacities to zero at runtime, without changing input CSVs, then reruns the same total-system-cost objective.</p>
  </section>

  <section>
    <h2>U.S. Wafer Demand Assumptions</h2>
    <p class="note">Demand is read from the runtime Gallium demand file used by the successful scenario runs. The modeled wafer demand grows at approximately 6.5% CAGR across periods 0-5 and uses USGS-derived wafer shares of about 80% GaAs and 20% GaN by mass.</p>
    <div id="demandChart" class="chart"></div>
    <p id="demandCaption" style="font-size:13px; color:#475569;"></p>
  </section>

  <section>
    <h2>Cost Comparison By Period</h2>
    <div class="grid2">
      <div id="systemCost" class="chart"></div>
      <div id="landedCost" class="chart"></div>
    </div>
  </section>

  <section>
    <h2>Scope A GWP Hotspots and Process Inputs/Outputs</h2>
    <p class="note">Scope A keeps the optimized wafer demand and supply-chain flows, but excludes the high-uncertainty full wafer-processing LCIA factors from baseline GWP. Use this section to see which process-location-material rows drive material-supply GWP, then inspect both the optimized network inputs/outputs and the per-kg LiAISON LCI recipe behind the selected process.</p>
    <div class="control-row">
      <label for="hotScenario"><strong>Scenario:</strong></label><select id="hotScenario"></select>
      <label for="hotPeriod"><strong>Period:</strong></label><select id="hotPeriod"></select>
      <label for="hotNode"><strong>Process hotspot:</strong></label><select id="hotNode" style="min-width:360px;"></select>
    </div>
    <div class="mini-grid">
      <div class="mini-card"><h4>Selected Flow</h4><div id="hotFlow" class="metric">—</div></div>
      <div class="mini-card"><h4>Scope A GWP</h4><div id="hotGwp" class="metric">—</div></div>
      <div class="mini-card"><h4>GWP Factor</h4><div id="hotFactor" class="metric">—</div></div>
    </div>
    <div id="hotspotChart" class="chart"></div>
    <div class="grid2">
      <div>
        <h3>Optimized Network Inputs/Outputs</h3>
        <div id="networkIoTable" class="scroll-table"></div>
      </div>
      <div>
        <h3>LiAISON LCI Recipe Inputs/Outputs</h3>
        <div id="lciIoTable" class="scroll-table"></div>
      </div>
    </div>
  </section>

  <section>
    <h2>Total-System Routing Sankeys</h2>
    <p class="note">Stage-based Sankeys use process/location nodes and material-colored links. The baseline total-system-cost run keeps using CN in every period. The China-shutdown run shown below is a separate scenario with CN capacity disabled for the full horizon, so it is already rerouted in period 0 rather than switching at period 2 or 3.</p>
    <div class="control-row"><label for="periodSelect"><strong>Period:</strong></label><select id="periodSelect"></select></div>
    <div class="legend">
      <span><i style="background:#777"></i>bauxite</span>
      <span><i style="background:#2ca02c"></i>Bayer liquor</span>
      <span><i style="background:#1f77b4"></i>4N Ga</span>
      <span><i style="background:#ff7f0e"></i>6N Ga</span>
      <span><i style="background:#d62728"></i>GaAs wafer</span>
      <span><i style="background:#9467bd"></i>GaN wafer</span>
    </div>
    <div class="stack">
      <div><h3>Baseline Total-System Route</h3><div id="baselineSankey" class="chart tall"></div></div>
      <div><h3>China-Capacity-Shutdown Route</h3><div id="shutdownSankey" class="chart tall"></div></div>
    </div>
  </section>

  <section>
    <h2>U.S. Wafer Landed-Cost Sankeys</h2>
    <div class="stack">
      <div><h3>Baseline U.S. Wafer Supply</h3><div id="baselineUSSankey" class="chart medium"></div></div>
      <div><h3>Shutdown U.S. Wafer Supply</h3><div id="shutdownUSSankey" class="chart medium"></div></div>
    </div>
  </section>

  <section>
    <h2>Scenario Summary</h2>
    {_html_table(summary)}
  </section>

  <section>
    <h2>U.S. Landed-Cost Origin Detail</h2>
    <div class="grid2">
      <div><h3>Baseline</h3>{_html_table(baseline_origin)}</div>
      <div><h3>China Shutdown</h3>{_html_table(shutdown_origin)}</div>
    </div>
  </section>
</main>
<script>
const payload = {json.dumps(payload)};
const s = payload.summary;
const demandPeriods = [...new Set(payload.demand.map(r => r.time_period))].sort((a,b)=>a-b);
const demandLabels = demandPeriods.map(t => {{
  const row = payload.demand.find(r => r.time_period === t);
  return row ? String(row.year) + ' (P' + t + ')' : 'P' + t;
}});
const demandMaterials = ['GaAs_wafer', 'GaN_wafer'];
const demandColors = {{'GaAs_wafer':'#d62728', 'GaN_wafer':'#9467bd'}};
Plotly.react('demandChart', demandMaterials.map(mat => ({{
  type:'bar',
  name: mat.replace('_', ' '),
  x: demandLabels,
  y: demandPeriods.map(t => payload.demand.filter(r => r.time_period === t && r.material === mat).reduce((sum, row) => sum + row.demand_kg, 0)),
  marker:{{color:demandColors[mat]}}
}})), {{barmode:'stack', title:'U.S. GaAs/GaN wafer demand used in scenario runs', xaxis:{{title:'Year / model period'}}, yaxis:{{title:'Demand (kg)'}}, margin:{{t:45}}}}, {{responsive:true}});
const shares = payload.demandInfo.shares || {{}};
document.getElementById('demandCaption').textContent = 'Source: ' + payload.demandSource + '. Implied total-demand CAGR: ' + (100 * payload.demandInfo.cagr).toFixed(2) + '%. Material shares over the horizon: GaAs ' + (100 * (shares.GaAs_wafer || 0)).toFixed(1) + '%, GaN ' + (100 * (shares.GaN_wafer || 0)).toFixed(1) + '%.';
Plotly.react('systemCost', s.map(row => ({{ type:'bar', name:row.scenario, x:[row.scenario], y:[row.total_system_cost_usd] }})), {{title:'Total system cost by scenario', yaxis:{{title:'USD'}}, margin:{{t:40}}}}, {{responsive:true}});
const landedRows = s.map(row => ({{scenario:row.scenario, value:row.us_border_landed_cost_usd}}));
Plotly.react('landedCost', [{{type:'bar', x:landedRows.map(r=>r.scenario), y:landedRows.map(r=>r.value), marker:{{color:['#2878d7','#e88425']}}}}], {{title:'U.S. landed cost by scenario', yaxis:{{title:'USD'}}, margin:{{t:40}}}}, {{responsive:true}});
function fmtKg(v) {{ return Number(v || 0).toLocaleString(undefined, {{maximumFractionDigits:2}}) + ' kg'; }}
function fmtGwp(v) {{ return Number(v || 0).toLocaleString(undefined, {{maximumFractionDigits:2}}) + ' kg CO₂-eq'; }}
function fmtFactor(v) {{ return Number(v || 0).toLocaleString(undefined, {{maximumFractionDigits:4}}) + ' kg CO₂-eq/kg'; }}
function tableHtml(rows, columns) {{
  if (!rows || rows.length === 0) return '<p style="padding:14px;color:#64748b;">No rows for this selection.</p>';
  let html = '<table class="data-table"><thead><tr>' + columns.map(c => '<th>' + c.label + '</th>').join('') + '</tr></thead><tbody>';
  rows.forEach(r => {{
    html += '<tr>' + columns.map(c => {{
      let value = r[c.key];
      if (c.fmt === 'kg') value = fmtKg(value);
      if (c.fmt === 'gwp') value = fmtGwp(value);
      if (c.fmt === 'num') value = Number(value || 0).toLocaleString(undefined, {{maximumFractionDigits:4}});
      return '<td>' + (value === null || value === undefined ? '' : value) + '</td>';
    }}).join('') + '</tr>';
  }});
  return html + '</tbody></table>';
}}
function initHotspotControls() {{
  const scenarios = [...new Set(payload.hotspots.map(r => r.scenario))];
  const periods = [...new Set(payload.hotspots.map(r => r.time_period))].sort((a,b)=>a-b);
  const scenSel = document.getElementById('hotScenario');
  const periodSel = document.getElementById('hotPeriod');
  scenarios.forEach(s => {{ const o=document.createElement('option'); o.value=s; o.textContent=s; scenSel.appendChild(o); }});
  periods.forEach(p => {{ const o=document.createElement('option'); o.value=p; o.textContent='Period ' + p; periodSel.appendChild(o); }});
  scenSel.addEventListener('change', updateHotspotNodes);
  periodSel.addEventListener('change', updateHotspotNodes);
  document.getElementById('hotNode').addEventListener('change', renderHotspots);
  if (scenarios.includes('China capacity shutdown')) scenSel.value = 'China capacity shutdown';
  if (periods.includes(3)) periodSel.value = 3;
  updateHotspotNodes();
}}
function updateHotspotNodes() {{
  const scen = document.getElementById('hotScenario').value;
  const period = parseInt(document.getElementById('hotPeriod').value);
  const rows = payload.hotspots.filter(r => r.scenario === scen && r.time_period === period && Math.abs(r.scope_A_gwp_kg_co2e || 0) > 0)
    .sort((a,b)=>(b.scope_A_gwp_kg_co2e||0)-(a.scope_A_gwp_kg_co2e||0));
  const nodeSel = document.getElementById('hotNode');
  nodeSel.innerHTML = '';
  rows.forEach(r => {{ const o=document.createElement('option'); o.value=r.node_key; o.textContent=r.node_key; nodeSel.appendChild(o); }});
  renderHotspots();
}}
function renderHotspots() {{
  const scen = document.getElementById('hotScenario').value;
  const period = parseInt(document.getElementById('hotPeriod').value);
  const nodeKey = document.getElementById('hotNode').value;
  const rows = payload.hotspots.filter(r => r.scenario === scen && r.time_period === period)
    .sort((a,b)=>(b.scope_A_gwp_kg_co2e||0)-(a.scope_A_gwp_kg_co2e||0));
  const top = rows.slice(0, 12);
  Plotly.react('hotspotChart', [{{type:'bar', orientation:'h', y:top.map(r=>r.node_key).reverse(), x:top.map(r=>r.scope_A_gwp_kg_co2e||0).reverse(), marker:{{color:'#2878d7'}}, hovertemplate:'%{{y}}<br>%{{x:,.2f}} kg CO₂-eq<extra></extra>'}}], {{title:'Top Scope A GWP hotspots for selected scenario/period', xaxis:{{title:'kg CO₂-eq'}}, margin:{{t:42,l:260,r:30,b:45}}}}, {{responsive:true}});
  const selected = rows.find(r => r.node_key === nodeKey) || rows[0];
  if (!selected) return;
  document.getElementById('hotFlow').textContent = fmtKg(selected.flow_kg);
  document.getElementById('hotGwp').textContent = fmtGwp(selected.scope_A_gwp_kg_co2e);
  document.getElementById('hotFactor').textContent = fmtFactor(selected.scope_A_gwp_factor);
  const networkRows = payload.networkIO.filter(r => r.scenario === scen && r.time_period === period && r.process === selected.process_from && r.location === selected.loc_from)
    .sort((a,b)=>(b.quantity_kg||0)-(a.quantity_kg||0)).slice(0, 30);
  document.getElementById('networkIoTable').innerHTML = tableHtml(networkRows, [
    {{key:'direction', label:'Direction'}},
    {{key:'counterparty', label:'Counterparty'}},
    {{key:'material', label:'Material'}},
    {{key:'quantity_kg', label:'Quantity', fmt:'kg'}},
    {{key:'gwp_kg_co2e', label:'Scope A GWP', fmt:'gwp'}},
  ]);
  const lciRows = payload.lciIO.filter(r => r.process === selected.process_from && r.location === selected.loc_from)
    .sort((a,b)=>Math.abs(b.value||0)-Math.abs(a.value||0)).slice(0, 30);
  document.getElementById('lciIoTable').innerHTML = tableHtml(lciRows, [
    {{key:'direction', label:'Direction'}},
    {{key:'flow', label:'LCI flow'}},
    {{key:'value', label:'Per-kg value', fmt:'num'}},
    {{key:'unit', label:'Unit'}},
    {{key:'supplying_location', label:'Supplier'}},
    {{key:'type', label:'Type'}},
  ]);
}}
function sankeyTrace(data) {{ return {{ type:'sankey', arrangement:'fixed', node:{{label:data.labels, x:data.x, y:data.y, color:data.nodeColors, pad:18, thickness:16, line:{{color:'#ffffff', width:0.5}}}}, link:{{source:data.sources, target:data.targets, value:data.values, customdata:data.materials, color:data.colors, hovertemplate:'%{{source.label}} → %{{target.label}}<br>%{{value:,.2f}} kg<br>%{{customdata}}<extra></extra>'}} }}; }}
function layoutFor(title, size=12) {{ return {{title:title, font:{{size:size}}, margin:{{t:35,l:10,r:10,b:10}}}}; }}
function drawPeriod(period) {{
  const key = String(period);
  Plotly.react('baselineSankey', [sankeyTrace(payload.baselineSankey.byPeriod[key])], layoutFor('Baseline period ' + key), {{responsive:true}});
  Plotly.react('shutdownSankey', [sankeyTrace(payload.shutdownSankey.byPeriod[key])], layoutFor('China shutdown period ' + key), {{responsive:true}});
  Plotly.react('baselineUSSankey', [sankeyTrace(payload.baselineUSSankey.byPeriod[key])], layoutFor('Baseline U.S. wafer supply period ' + key, 13), {{responsive:true}});
  Plotly.react('shutdownUSSankey', [sankeyTrace(payload.shutdownUSSankey.byPeriod[key])], layoutFor('Shutdown U.S. wafer supply period ' + key, 13), {{responsive:true}});
}}
const select = document.getElementById('periodSelect');
const periods = payload.baselineSankey.periods.length ? payload.baselineSankey.periods : [0];
periods.forEach(p => {{ const option = document.createElement('option'); option.value = p; option.textContent = 'Period ' + p; select.appendChild(option); }});
select.value = periods[periods.length - 1];
select.addEventListener('change', () => drawPeriod(select.value));
drawPeriod(select.value);
initHotspotControls();
</script>
</body>
</html>
"""
    path = out_dir / "dashboard_policy_comparison.html"
    path.write_text(html, encoding="utf-8")
    return path
