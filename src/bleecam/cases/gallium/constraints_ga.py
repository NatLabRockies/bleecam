# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Gallium-specific constraints for the cost-only Pyomo baseline."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from pyomo.environ import value

from .config_ga import CAPACITY_EXEMPT_PROCESSES, DEMAND_FLOW, DEMAND_LOCATION, DEMAND_SOURCE_PROCESS


FlowKey = tuple[int, str, str, str, str, str]
ArcKey = tuple[str, str, str, str, str]


def _flow_terms(model, keys: Iterable[FlowKey]):
    return [model.flowQ[key] for key in keys if key in model.flowQ]


def _outgoing_keys(
    model,
    t: int,
    process: str,
    location: str,
    material: str | None = None,
) -> list[FlowKey]:
    return [
        key
        for key in model.FlowArcs
        if int(key[0]) == int(t)
        and str(key[1]) == process
        and str(key[2]) == location
        and (material is None or str(key[5]) == material)
    ]


def _incoming_keys(
    model,
    t: int,
    process: str,
    location: str,
    material: str | None = None,
) -> list[FlowKey]:
    return [
        key
        for key in model.FlowArcs
        if int(key[0]) == int(t)
        and str(key[3]) == process
        and str(key[4]) == location
        and (material is None or str(key[5]) == material)
    ]


def add_capacity_constraints_ga(
    model,
    max_output_capacity: dict[tuple[str, str, str], dict[int, float]],
    *,
    exempt_processes: set[str] | frozenset[str] = CAPACITY_EXEMPT_PROCESSES,
) -> None:
    """Limit total outgoing flow by process, location, material, and period."""

    for (process, location, material), period_caps in max_output_capacity.items():
        if process in exempt_processes:
            continue
        for t, capacity in period_caps.items():
            if t not in model.TimePeriods:
                continue
            terms = _flow_terms(model, _outgoing_keys(model, t, process, location, material))
            if terms:
                model.constraints.add(sum(terms) <= float(capacity))


def add_yield_mass_balance_constraints_ga(
    model,
    yield_factor: dict[tuple[int, str, str, str], float],
) -> None:
    """Add generic Gallium yield constraints from ``yield_ga.csv``.

    Source processes with no inbound topology arcs are governed by capacity only.
    For transformation/pass-through nodes, outgoing material requires sufficient
    inbound material. Same-material pass-throughs are constrained material-wise;
    remaining outputs share the process input pool by yield-adjusted equivalents.
    """

    by_process_location: dict[tuple[int, str, str], list[tuple[str, float]]] = defaultdict(list)
    for (t, process, location, material), factor in yield_factor.items():
        if t in model.TimePeriods and factor >= 0:
            by_process_location[(int(t), process, location)].append((material, float(factor)))

    for (t, process, location), material_factors in by_process_location.items():
        all_incoming = _flow_terms(model, _incoming_keys(model, t, process, location))
        if not all_incoming:
            continue

        pooled_output_terms = []
        for material, factor in material_factors:
            outgoing = _flow_terms(model, _outgoing_keys(model, t, process, location, material))
            if not outgoing:
                continue
            if factor <= 0.0:
                model.constraints.add(sum(outgoing) == 0.0)
                continue

            same_material_incoming = _flow_terms(
                model, _incoming_keys(model, t, process, location, material)
            )
            if same_material_incoming:
                model.constraints.add(sum(outgoing) <= factor * sum(same_material_incoming))
            else:
                pooled_output_terms.append(sum(outgoing) / factor)

        if pooled_output_terms:
            model.constraints.add(sum(pooled_output_terms) <= sum(all_incoming))


def add_demand_constraints_ga(model, demand_df) -> None:
    """Require terminal wafer demand, allowing shortage slack for diagnostics."""

    for _, row in demand_df.iterrows():
        t = int(row["time_period"])
        location = str(row["location"]).strip()
        material = str(row["material"]).strip()
        flow = str(row["flow"]).strip()
        demand = float(row["demand_kg"])
        if flow != DEMAND_FLOW or location != DEMAND_LOCATION:
            continue

        terminal_key = (t, DEMAND_SOURCE_PROCESS, location, flow, location, material)
        terminal_flow = model.flowQ[terminal_key] if terminal_key in model.flowQ else 0.0
        slack_key = (t, location, material)
        expr = terminal_flow + model.demand_slack[slack_key]
        # If the model has a finished-good buffer, demand can be met from production
        # plus a stock draw, and surplus production can be banked (golden-neutral: at
        # baseline, holding cost makes both zero).
        if hasattr(model, "stock_level") and (t, material) in model.stock_level:
            expr = expr + model.flow_from_stock[t, material] - model.flow_to_stock[t, material]
        model.constraints.add(expr == demand)


def summarize_demand_slack(model, tolerance: float = 1e-7) -> list[dict[str, float | int | str]]:
    """Return nonzero demand slack records from a solved model."""

    rows = []
    for key in model.DemandKeys:
        raw = value(model.demand_slack[key], exception=False)
        slack = 0.0 if raw is None else float(raw)
        if slack > tolerance:
            t, location, material = key
            rows.append(
                {
                    "time_period": int(t),
                    "location": str(location),
                    "material": str(material),
                    "demand_slack_kg": slack,
                }
            )
    return rows
