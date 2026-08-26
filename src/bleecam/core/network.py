# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generic, config-driven model builder for standard flow-network cases.

This is the no-code capstone: given a :class:`~bleecam.core.case_config.CaseConfig`
and the standard ``loaded_data`` (from :func:`bleecam.core.data_loader.load_case_data`),
:func:`build_model` assembles the same Pyomo model a hand-written case would — sets,
the ``flowQ`` flow variables keyed ``(t, process_from, loc_from, process_to,
loc_to, material)``, capacity / yield mass-balance / demand constraints, the cost
(or impact) objective, and the generic contracts (``_arc_unit_cost``,
``_bleecam_objective``). A standard material therefore needs no per-case Python.

The construction mirrors the Gallium case exactly (it reproduces Gallium's optimum
to the cent); the Gallium and REE modules keep their own builders, and this one
serves any case described purely by a case YAML + data.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

import pandas as pd
from pyomo.environ import (
    ConcreteModel, ConstraintList, NonNegativeReals, Objective, Set, SolverFactory, Var, minimize, value,
)

from .lca_import import WEIGHTED_GWP_COL
from .objectives import demand_slack_penalty_expression, linear_flow_expression

if TYPE_CHECKING:
    from .case_config import CaseConfig

FLOW_BOUND_DEMAND_MULTIPLE = 1.0e6

OBJECTIVE_ALIASES = {
    "gwp": WEIGHTED_GWP_COL,
    "child_labor": "SLCA_EF - Child labor impact (worker hour/kg)",
    "forced_labor": "SLCA_EF - Forced labor impact (worker hour/kg)",
    "fatal_injury": "SLCA_EF - Fatal injury impact (worker hour/kg)",
    "nonfatal_injury": "SLCA_EF - Non-fatal injury impact (worker hour/kg)",
}


class GenericModelError(RuntimeError):
    """Raised when a config-driven case cannot be built or solved."""


def _clean(v: Any) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


# ── cost maps (lifted, generic) ───────────────────────────────────────────────
@dataclass(frozen=True)
class CostMaps:
    process_processing_cost: dict[tuple[int, str, str, str], float]
    process_domestic_transport_cost: dict[tuple[int, str, str, str], float]
    arc_transportation_cost: dict[tuple[int, str, str, str, str, str], float]
    tariff_cost: dict[tuple[int, str, str, str, str, str], float]
    shipping_cost: dict[tuple[int, str, str], float]


def build_cost_maps(loaded_data: dict[str, Any]) -> CostMaps:
    cost_df = loaded_data["cost_df"]
    processing, dom_transport, arc_transport, tariff = {}, {}, {}, {}
    for _, row in cost_df.iterrows():
        t = int(row["time_period"])
        source, location, material = _clean(row["source"]), _clean(row["location"]), _clean(row["material"])
        dest, dest_loc = _clean(row["destination"]), _clean(row["destination_location"])
        if dest and dest_loc:
            arc_key = (t, source, location, dest, dest_loc, material)
            arc_transport[arc_key] = float(row["transportation cost"])
            if float(row["tariff_cost"]) != 0.0:
                tariff[arc_key] = float(row["tariff_cost"])
        else:
            pkey = (t, source, location, material)
            processing[pkey] = float(row["processing cost"])
            dom_transport[pkey] = float(row["transportation cost"])
    return CostMaps(processing, dom_transport, arc_transport, tariff, loaded_data["shipping_cost"])


def unit_cost_for_arc(cm: CostMaps, t: int, pf: str, lf: str, pt: str, lt: str, m: str) -> tuple[float, float, float, float]:
    pkey = (int(t), pf, lf, m)
    akey = (int(t), pf, lf, pt, lt, m)
    processing = cm.process_processing_cost.get(pkey, 0.0)
    domestic = cm.process_domestic_transport_cost.get(pkey, 0.0) + cm.arc_transportation_cost.get(akey, 0.0)
    shipping = cm.shipping_cost.get((int(t), lf, lt), 0.0) if lf != lt else 0.0
    return processing, domestic, shipping, cm.tariff_cost.get(akey, 0.0)


# ── constraints (lifted from constraints_ga, parameterized by config) ──────────
def _flow_terms(model, keys: Iterable):
    return [model.flowQ[k] for k in keys if k in model.flowQ]


def _outgoing_keys(model, t, process, location, material=None):
    return [k for k in model.FlowArcs if int(k[0]) == int(t) and str(k[1]) == process
            and str(k[2]) == location and (material is None or str(k[5]) == material)]


def _incoming_keys(model, t, process, location, material=None):
    return [k for k in model.FlowArcs if int(k[0]) == int(t) and str(k[3]) == process
            and str(k[4]) == location and (material is None or str(k[5]) == material)]


def add_capacity_constraints(model, max_output_capacity, exempt_processes) -> None:
    for (process, location, material), period_caps in max_output_capacity.items():
        if process in exempt_processes:
            continue
        for t, capacity in period_caps.items():
            if t not in model.TimePeriods:
                continue
            terms = _flow_terms(model, _outgoing_keys(model, t, process, location, material))
            if terms:
                model.constraints.add(sum(terms) <= float(capacity))


def add_yield_mass_balance_constraints(model, yield_factor) -> None:
    by_pl: dict[tuple[int, str, str], list[tuple[str, float]]] = defaultdict(list)
    for (t, process, location, material), factor in yield_factor.items():
        if t in model.TimePeriods and factor >= 0:
            by_pl[(int(t), process, location)].append((material, float(factor)))
    for (t, process, location), mfs in by_pl.items():
        all_incoming = _flow_terms(model, _incoming_keys(model, t, process, location))
        if not all_incoming:
            continue
        pooled = []
        for material, factor in mfs:
            outgoing = _flow_terms(model, _outgoing_keys(model, t, process, location, material))
            if not outgoing:
                continue
            if factor <= 0.0:
                model.constraints.add(sum(outgoing) == 0.0)
                continue
            same = _flow_terms(model, _incoming_keys(model, t, process, location, material))
            if same:
                model.constraints.add(sum(outgoing) <= factor * sum(same))
            else:
                pooled.append(sum(outgoing) / factor)
        if pooled:
            model.constraints.add(sum(pooled) <= sum(all_incoming))


def add_demand_constraints(model, demand_df, *, flow, location, source_process) -> None:
    has_flow = "flow" in demand_df.columns
    for _, row in demand_df.iterrows():
        t = int(row["time_period"])
        loc, mat = str(row["location"]).strip(), str(row["material"]).strip()
        rflow = str(row["flow"]).strip() if has_flow else flow
        if rflow != flow or loc != location:
            continue
        terminal_key = (t, source_process, loc, flow, loc, mat)
        terminal_flow = model.flowQ[terminal_key] if terminal_key in model.flowQ else 0.0
        model.constraints.add(terminal_flow + model.demand_slack[(t, loc, mat)] == float(row["demand_kg"]))


def summarize_demand_slack(model, tolerance: float = 1e-7) -> list[dict[str, Any]]:
    rows = []
    for key in model.DemandKeys:
        raw = value(model.demand_slack[key], exception=False)
        slack = 0.0 if raw is None else float(raw)
        if slack > tolerance:
            t, loc, mat = key
            rows.append({"time_period": int(t), "location": str(loc), "material": str(mat), "demand_slack_kg": slack})
    return rows


# ── assembly / objective ──────────────────────────────────────────────────────
def _flow_arc_records(loaded_data):
    arcs = sorted(loaded_data["allowed_trade_arcs"])
    return [(t, *arc) for t in loaded_data["time_periods"] for arc in arcs]


def _demand_keys(demand_df):
    keys = []
    for _, row in demand_df.iterrows():
        key = (int(row["time_period"]), str(row["location"]).strip(), str(row["material"]).strip())
        if key not in keys:
            keys.append(key)
    return keys


def flow_upper_bound(loaded_data) -> float:
    total = float(pd.to_numeric(loaded_data["demand_df"]["demand_kg"], errors="coerce").fillna(0).sum())
    return max(total, 1.0) * FLOW_BOUND_DEMAND_MULTIPLE


def assemble_network(config: "CaseConfig", loaded_data: dict[str, Any]):
    cost_maps = build_cost_maps(loaded_data)
    model = ConcreteModel(name=f"{config.case} supply-chain network")
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
    model.constraints = ConstraintList()
    model._flow_upper_bound = ub

    add_capacity_constraints(model, loaded_data["max_output_capacity"], config.capacity_exempt_processes)
    add_yield_mass_balance_constraints(model, loaded_data["yield_factor"])
    add_demand_constraints(model, loaded_data["demand_df"], flow=config.demand_flow,
                           location=config.demand_location, source_process=config.demand_source_process)

    model._cost_maps = cost_maps
    model._arc_unit_cost = {
        key: float(sum(unit_cost_for_arc(cost_maps, int(key[0]), str(key[1]), str(key[2]),
                                         str(key[3]), str(key[4]), str(key[5]))))
        for key in model.FlowArcs
    }
    return model, cost_maps


def flow_cost_expression(model, cost_maps) -> Any:
    total = 0.0
    for key in model.FlowArcs:
        t, pf, lf, pt, lt, m = key
        total += float(sum(unit_cost_for_arc(cost_maps, int(t), str(pf), str(lf), str(pt), str(lt), str(m)))) * model.flowQ[key]
    return total


def _resolve_impact_column(objective: str, impact_factors: dict) -> str:
    col = OBJECTIVE_ALIASES.get(objective, objective)
    if col not in impact_factors:
        raise GenericModelError(
            f"impact objective {objective!r} (column {col!r}) is not in the EF table; "
            f"{len(impact_factors)} categories available."
        )
    return col


def build_model(config: "CaseConfig", loaded_data: dict[str, Any], objective: str = "cost") -> ConcreteModel:
    """Assemble the config-driven model with the standard generic contracts."""
    model, cost_maps = assemble_network(config, loaded_data)
    if objective == "cost":
        cost_expr = flow_cost_expression(model, cost_maps) + \
            config.demand_slack_penalty * sum(model.demand_slack[k] for k in model.DemandKeys)
        model.obj = Objective(expr=cost_expr, sense=minimize)
        model._bleecam_objective = "cost"
    else:
        impact_factors = loaded_data.get("impact_factors", {})
        col = _resolve_impact_column(objective, impact_factors)
        factor_map = impact_factors[col]
        max_factor = max((abs(v) for v in factor_map.values()), default=0.0)
        if max_factor <= 0:
            raise GenericModelError(f"impact category {col!r} has all-zero/empty factors.")
        norm_map = {k: v / max_factor for k, v in factor_map.items()}
        impact_expr = (
            linear_flow_expression(model, norm_map)
            + demand_slack_penalty_expression(model, 1.0e3)
            + 1.0e-6 * sum(model.flowQ[k] for k in model.FlowArcs)
        )
        model.obj = Objective(expr=impact_expr, sense=minimize)
        model._bleecam_objective = col
        model._bleecam_impact_scale = max_factor
    model._cost_maps = cost_maps
    return model


def solve_model(model, config: "CaseConfig", solver: str = "auto") -> dict[str, Any]:
    candidates = list(config.solver_candidates) if solver == "auto" else [solver]
    opt = None
    for name in candidates:
        try:
            s = SolverFactory(name)
            if s is not None and s.available(exception_flag=False):
                opt = s
                break
        except Exception:
            continue
    if opt is None:
        raise GenericModelError(f"no solver available (tried {candidates})")
    results = opt.solve(model)
    obj = value(model.obj, exception=False)
    return {
        "termination_condition": str(results.solver.termination_condition),
        "objective_value": None if obj is None else float(obj),
        "demand_slack": summarize_demand_slack(model, config.flow_tolerance),
    }
