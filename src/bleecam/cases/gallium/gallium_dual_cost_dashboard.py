# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Render the separate Gallium dual-cost dashboard."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.where(pd.notna(df), None).to_dict(orient="records")


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _kg(value: float) -> str:
    return f"{value:,.2f} kg"


def _pct(value: float) -> str:
    return f"{100 * value:,.1f}%"


def _table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "<p>No rows.</p>"
    return df.head(max_rows).to_html(index=False, classes="data-table", border=0)


def _sankey_payload(df: pd.DataFrame, max_links: int = 80) -> dict[str, Any]:
    if df.empty:
        return {"labels": [], "sources": [], "targets": [], "values": [], "materials": [], "costs": []}
    plot_df = df.copy().sort_values("value_kg", ascending=False).head(max_links)
    labels: list[str] = []
    index: dict[str, int] = {}

    def label_id(label: str) -> int:
        if label not in index:
            index[label] = len(labels)
            labels.append(label)
        return index[label]

    sources = [label_id(str(x)) for x in plot_df["source"]]
    targets = [label_id(str(x)) for x in plot_df["target"]]
    return {
        "labels": labels,
        "sources": sources,
        "targets": targets,
        "values": plot_df["value_kg"].astype(float).tolist(),
        "materials": plot_df["material"].astype(str).tolist(),
        "costs": plot_df["cost_usd"].astype(float).tolist(),
    }


def render_dashboard(output_dir: Path) -> Path:
    by_period = pd.read_csv(output_dir / "us_border_landed_cost_by_period.csv")
    by_origin = pd.read_csv(output_dir / "us_border_landed_cost_by_origin_material.csv")
    tariffs = pd.read_csv(output_dir / "tariffs_paid_by_us.csv")
    shares = pd.read_csv(output_dir / "domestic_vs_imported_wafer_supply.csv")
    comparison = pd.read_csv(output_dir / "total_system_vs_us_border_cost_comparison.csv")
    sankey_total = pd.read_csv(output_dir / "sankey_flows_total_system_cost.csv")
    sankey_us = pd.read_csv(output_dir / "sankey_flows_us_border_landed_cost.csv")
    checks = pd.read_csv(output_dir / "validation_checks.csv")

    total_system = float(comparison["total_system_cost_usd"].sum())
    total_landed = float(by_period["total_us_landed_cost_usd"].sum())
    total_demand = float(by_period["total_us_wafer_demand_kg"].sum())
    avg_landed = total_landed / total_demand if total_demand else 0.0
    tariffs_paid = float(by_period["tariff_usd"].sum())
    imported = float(by_period["imported_wafer_kg"].sum())
    domestic = float(by_period["domestic_wafer_kg"].sum())
    import_share = imported / (imported + domestic) if imported + domestic else 0.0
    domestic_share = domestic / (imported + domestic) if imported + domestic else 0.0

    material_avg = by_origin.groupby("material", as_index=False).agg(
        quantity_kg=("quantity_kg", "sum"),
        total_us_landed_cost_usd=("total_us_landed_cost_usd", "sum"),
    )
    material_avg["average_us_landed_cost_usd_per_kg"] = material_avg["total_us_landed_cost_usd"] / material_avg["quantity_kg"]

    payload = {
        "comparison": _records(comparison),
        "byPeriod": _records(by_period),
        "materialAvg": _records(material_avg),
        "tariffs": _records(tariffs),
        "shares": _records(shares),
        "sankeyTotal": _sankey_payload(sankey_total, 60),
        "sankeyUS": _sankey_payload(sankey_us, 40),
    }

    failed_checks = checks[~checks["passed"].astype(bool)] if not checks.empty else checks
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gallium Dual-Cost Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{ margin:0; font-family: Arial, sans-serif; background:#f6f7f9; color:#20242a; }}
header {{ background:#20384f; color:white; padding:22px 32px; }}
main {{ max-width:1500px; margin:0 auto; padding:24px 30px 48px; }}
.card-row {{ display:grid; grid-template-columns:repeat(4,minmax(180px,1fr)); gap:14px; }}
.card {{ background:white; border-radius:6px; padding:16px; border-top:4px solid #2878d7; box-shadow:0 1px 5px rgba(0,0,0,.08); }}
.card h3 {{ margin:0 0 8px; color:#5d6b82; font-size:12px; text-transform:uppercase; }}
.card .value {{ font-size:24px; font-weight:700; }}
section {{ background:white; margin-top:18px; padding:20px; border-radius:6px; box-shadow:0 1px 5px rgba(0,0,0,.08); }}
h2 {{ margin:0 0 12px; color:#20384f; font-size:20px; }}
p {{ line-height:1.45; }}
.chart {{ height:430px; }}
.chart.tall {{ height:560px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.data-table {{ border-collapse:collapse; width:100%; font-size:12px; }}
.data-table th {{ background:#20384f; color:white; padding:7px; text-align:left; }}
.data-table td {{ border-bottom:1px solid #e5e7eb; padding:6px 7px; }}
.note {{ background:#eef4fb; border-left:4px solid #2878d7; padding:12px 14px; }}
.warn {{ background:#fff7ed; border-left:4px solid #e88425; padding:12px 14px; }}
@media(max-width:1000px) {{ .card-row,.grid2 {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>Gallium Dual-Cost Dashboard</h1>
  <div>Generated {dt.datetime.now().isoformat(timespec='seconds')} | Post-processed U.S. landed-cost metric under total-system-cost-optimized solution</div>
</header>
<main>
  <div class="card-row">
    <div class="card"><h3>Total System Cost</h3><div class="value">{_money(total_system)}</div></div>
    <div class="card"><h3>U.S. Landed Cost</h3><div class="value">{_money(total_landed)}</div></div>
    <div class="card"><h3>Avg U.S. Landed $/kg</h3><div class="value">{_money(avg_landed)}</div></div>
    <div class="card"><h3>Tariffs Paid</h3><div class="value">{_money(tariffs_paid)}</div></div>
  </div>
  <div class="card-row" style="margin-top:14px;">
    <div class="card"><h3>U.S. Wafer Demand Served</h3><div class="value">{_kg(total_demand)}</div></div>
    <div class="card"><h3>Import Share</h3><div class="value">{_pct(import_share)}</div></div>
    <div class="card"><h3>Domestic Share</h3><div class="value">{_pct(domestic_share)}</div></div>
    <div class="card"><h3>Imported Wafer Supply</h3><div class="value">{_kg(imported)}</div></div>
  </div>

  <section>
    <h2>Executive Summary</h2>
    <p>The total-system-cost result preserves the existing BLEECAM optimized supply-chain perspective. The U.S. landed-cost metric is a separate post-processing view of what the U.S. effectively pays for GaAs/GaN wafer demand delivered into the U.S. demand system, including a modeled FOB wafer value proxy, final U.S. shipping/transport, tariffs, and U.S. terminal delivery where present.</p>
    <p class="note">This dashboard does not implement a second optimization objective. It reports U.S. landed cost under the existing total-system-cost-optimized solution.</p>
  </section>

  <section>
    <h2>Cost Perspective Comparison</h2>
    <div class="grid2">
      <div id="periodCost" class="chart"></div>
      <div id="materialAvg" class="chart"></div>
    </div>
  </section>

  <section>
    <h2>Sankeys</h2>
    <div class="grid2">
      <div><h3>Total System Flow Sankey</h3><div id="sankeyTotal" class="chart tall"></div></div>
      <div><h3>U.S. Landed-Cost Wafer Sankey</h3><div id="sankeyUS" class="chart tall"></div></div>
    </div>
  </section>

  <section>
    <h2>Tariffs And Import Exposure</h2>
    <div class="grid2">
      <div id="importShare" class="chart"></div>
      <div id="tariffsChart" class="chart"></div>
    </div>
    <h3>Origin / Material Landed-Cost Detail</h3>
    {_table(by_origin.sort_values(['time_period','material','origin']), 30)}
  </section>

  <section>
    <h2>Validation</h2>
    {('<p class="warn">Some validation checks require review.</p>' if not failed_checks.empty else '<p class="note">All core generated metric checks passed.</p>')}
    {_table(checks, 20)}
  </section>

  <section>
    <h2>Methodology</h2>
    <p><strong>Formula:</strong> imported landed cost = Q_import × (FOB_unit_value + ship_unit_cost + tariff_rate × tariff_base_unit). Domestic cost = Q_domestic × domestic_delivered_unit_cost.</p>
    <p><strong>FOB proxy:</strong> path-attributed modeled cost propagated through positive optimized flows. This is not an observed market price.</p>
    <p><strong>Tariff base:</strong> default is FOB_unit_value. Existing model tariffs are absolute USD/kg values, so the dashboard infers a proxy ad valorem rate where needed. A FOB-plus-shipping sensitivity is reported in the tariff CSV.</p>
    <p><strong>Perspective:</strong> the U.S. landed-cost result is post-processed under the total-system-cost-optimized solution. A true landed-cost optimization would require embedding the landed-cost metric into the Pyomo objective and carrying origin attribution through the market-mix node.</p>
  </section>
</main>
<script>
const payload = {json.dumps(payload)};
Plotly.react('periodCost', [
  {{type:'bar', name:'Total system cost', x: payload.comparison.map(r=>r.time_period), y: payload.comparison.map(r=>r.total_system_cost_usd)}},
  {{type:'bar', name:'U.S. landed cost', x: payload.comparison.map(r=>r.time_period), y: payload.comparison.map(r=>r.total_us_landed_cost_usd)}}
], {{barmode:'group', title:'Cost by period', xaxis:{{title:'Time period'}}, yaxis:{{title:'USD'}}, margin:{{t:40}}}}, {{responsive:true}});
Plotly.react('materialAvg', [{{
  type:'bar', x: payload.materialAvg.map(r=>r.material), y: payload.materialAvg.map(r=>r.average_us_landed_cost_usd_per_kg), marker:{{color:['#d62728','#9467bd']}}
}}], {{title:'Average U.S. landed cost by wafer material', yaxis:{{title:'USD/kg'}}, margin:{{t:40}}}}, {{responsive:true}});
function sankeyTrace(data) {{
  return {{type:'sankey', arrangement:'snap', node:{{label:data.labels, pad:12, thickness:14}}, link:{{source:data.sources, target:data.targets, value:data.values, customdata:data.materials, hovertemplate:'%{{source.label}} → %{{target.label}}<br>%{{value:,.2f}} kg<br>%{{customdata}}<extra></extra>'}}}};
}}
Plotly.react('sankeyTotal', [sankeyTrace(payload.sankeyTotal)], {{margin:{{t:10,l:10,r:10,b:10}}}}, {{responsive:true}});
Plotly.react('sankeyUS', [sankeyTrace(payload.sankeyUS)], {{margin:{{t:10,l:10,r:10,b:10}}}}, {{responsive:true}});
const sharePeriods = [...new Set(payload.shares.map(r=>r.time_period))].sort((a,b)=>a-b);
const shareTypes = [...new Set(payload.shares.map(r=>r.supply_type))].sort();
Plotly.react('importShare', shareTypes.map(st => {{ return {{type:'bar', name:st, x:sharePeriods, y:sharePeriods.map(t => payload.shares.filter(r=>r.time_period===t && r.supply_type===st).reduce((s,r)=>s+r.quantity_kg,0))}}; }}), {{barmode:'stack', title:'Domestic vs imported wafer supply', xaxis:{{title:'Time period'}}, yaxis:{{title:'kg'}}, margin:{{t:40}}}}, {{responsive:true}});
const tariffPeriods = [...new Set(payload.tariffs.map(r=>r.time_period))].sort((a,b)=>a-b);
Plotly.react('tariffsChart', [{{type:'bar', x:tariffPeriods, y:tariffPeriods.map(t => payload.tariffs.filter(r=>r.time_period===t).reduce((s,r)=>s+r.tariff_usd,0)), name:'Tariffs'}}], {{title:'Tariffs paid by period', xaxis:{{title:'Time period'}}, yaxis:{{title:'USD'}}, margin:{{t:40}}}}, {{responsive:true}});
</script>
</body>
</html>
"""
    path = output_dir / "dashboard_dual_cost.html"
    path.write_text(html, encoding="utf-8")
    return path
