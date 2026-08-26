# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Configuration helpers for the Gallium cost-only Pyomo baseline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bleecam.core.case_config import load_case_config

# Declarations now come from the declarative case file (single source of truth):
# edit gallium.case.yaml, not these constants. The generic cost logic below stays
# here for now (it moves to a shared core module in a later phase).
CASE_CONFIG = load_case_config(Path(__file__).parent / "gallium.case.yaml")

TIME_PERIODS = CASE_CONFIG.time_periods
BASELINE_SCENARIO = CASE_CONFIG.baseline_scenario
DEMAND_LOCATION = CASE_CONFIG.demand_location
DEMAND_FLOW = CASE_CONFIG.demand_flow
DEMAND_SOURCE_PROCESS = CASE_CONFIG.demand_source_process
DEMAND_SINK_PROCESS = CASE_CONFIG.demand_sink_process
DEMAND_MATERIALS = CASE_CONFIG.demand_materials
DEMAND_ARCS = CASE_CONFIG.demand_arcs

DEFAULT_INPUT_DIR = Path(".")
DEFAULT_RESULTS_CSV = CASE_CONFIG.results_csv

DEMAND_SLACK_PENALTY_USD_PER_KG = CASE_CONFIG.demand_slack_penalty
FLOW_TOLERANCE = CASE_CONFIG.flow_tolerance

CAPACITY_EXEMPT_PROCESSES = CASE_CONFIG.capacity_exempt_processes
SOLVER_CANDIDATES = CASE_CONFIG.solver_candidates


@dataclass(frozen=True)
class GalliumCostMaps:
    """Per-unit cost maps used by the Gallium objective."""

    process_processing_cost: dict[tuple[int, str, str, str], float]
    process_domestic_transport_cost: dict[tuple[int, str, str, str], float]
    arc_transportation_cost: dict[tuple[int, str, str, str, str, str], float]
    tariff_cost: dict[tuple[int, str, str, str, str, str], float]
    shipping_cost: dict[tuple[int, str, str], float]


def clean_text(value: Any) -> str:
    """Return loader-compatible stripped text for CSV key fields."""

    if value is None:
        return ""
    return str(value).strip()


def build_cost_maps(loaded_data: dict[str, Any]) -> GalliumCostMaps:
    """Build process-level and arc-level cost maps from loader output.

    Rows with blank destination fields are process-level processing/domestic
    transport costs. Rows with destination fields are topology-arc costs.
    """

    cost_df = loaded_data["cost_df"]
    process_processing_cost: dict[tuple[int, str, str, str], float] = {}
    process_domestic_transport_cost: dict[tuple[int, str, str, str], float] = {}
    arc_transportation_cost: dict[tuple[int, str, str, str, str, str], float] = {}
    tariff_cost: dict[tuple[int, str, str, str, str, str], float] = {}

    for _, row in cost_df.iterrows():
        t = int(row["time_period"])
        source = clean_text(row["source"])
        location = clean_text(row["location"])
        material = clean_text(row["material"])
        destination = clean_text(row["destination"])
        destination_location = clean_text(row["destination_location"])
        processing_cost = float(row["processing cost"])
        transport_cost = float(row["transportation cost"])
        tariff = float(row["tariff_cost"])

        if destination and destination_location:
            arc_key = (t, source, location, destination, destination_location, material)
            arc_transportation_cost[arc_key] = transport_cost
            if tariff != 0.0:
                tariff_cost[arc_key] = tariff
        else:
            process_key = (t, source, location, material)
            process_processing_cost[process_key] = processing_cost
            process_domestic_transport_cost[process_key] = transport_cost

    return GalliumCostMaps(
        process_processing_cost=process_processing_cost,
        process_domestic_transport_cost=process_domestic_transport_cost,
        arc_transportation_cost=arc_transportation_cost,
        tariff_cost=tariff_cost,
        shipping_cost=loaded_data["shipping_cost"],
    )


def unit_cost_for_arc(
    cost_maps: GalliumCostMaps,
    t: int,
    process_from: str,
    loc_from: str,
    process_to: str,
    loc_to: str,
    material: str,
) -> tuple[float, float, float, float]:
    """Return processing, domestic transport, shipping, and tariff costs."""

    process_key = (int(t), process_from, loc_from, material)
    arc_key = (int(t), process_from, loc_from, process_to, loc_to, material)
    processing = cost_maps.process_processing_cost.get(process_key, 0.0)
    domestic_transport = cost_maps.process_domestic_transport_cost.get(process_key, 0.0)
    domestic_transport += cost_maps.arc_transportation_cost.get(arc_key, 0.0)
    shipping = 0.0
    if loc_from != loc_to:
        shipping = cost_maps.shipping_cost.get((int(t), loc_from, loc_to), 0.0)
    tariff = cost_maps.tariff_cost.get(arc_key, 0.0)
    return processing, domestic_transport, shipping, tariff
