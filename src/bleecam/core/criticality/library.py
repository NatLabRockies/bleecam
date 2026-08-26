# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Criticality constraint library — the registered, user-selectable constraints.

Each function is registered with :mod:`bleecam.core.criticality.registry` and
applied by name (with parameters) from a YAML scenario file. Constraints are
**material-agnostic**: they operate on the generic model structure every case
shares — flow arcs indexed by ``(time_period, process_from, loc_from,
process_to, loc_to, material)``, the capacity map, and demand — not on any
material's chemistry.
"""
from __future__ import annotations

from typing import Any

from .registry import Param, register


# ── flow helpers (source node = process_from @ loc_from producing `material`) ──
def _node_outflow(model: Any, t: int, process: str, location: str, material: str):
    return sum(
        model.flowQ[key]
        for key in model.flowQ
        if int(key[0]) == t and key[1] == process and key[2] == location and key[5] == material
    )


def _material_production_at(model: Any, t: int, location: str, material: str, process: str | None):
    return sum(
        model.flowQ[key]
        for key in model.flowQ
        if int(key[0]) == t and key[2] == location and key[5] == material
        and (process is None or key[1] == process)
    )


def _demand(loaded_data: Any, t: int, material: str) -> float:
    d = loaded_data["demand_df"]
    return float(d[(d["time_period"].astype(int) == t) & (d["material"] == material)]["demand_kg"].sum())


def _is_number(x) -> bool:
    return isinstance(x, (int, float))


def _add_le(model: Any, lhs, rhs, ctx: str = "") -> None:
    """Add ``lhs <= rhs``, skipping trivially-true numeric cases and reporting infeasible ones."""
    if _is_number(lhs) and _is_number(rhs):
        if lhs > rhs + 1e-6:
            raise ValueError(f"criticality constraint infeasible ({ctx}): {lhs} <= {rhs}")
        return
    model.constraints.add(lhs <= rhs)


def _add_ge(model: Any, lhs, rhs, ctx: str = "") -> None:
    """Add ``lhs >= rhs``; a numeric lhs below rhs means the requirement is impossible for this node."""
    if _is_number(lhs) and _is_number(rhs):
        if lhs < rhs - 1e-6:
            raise ValueError(
                f"criticality constraint requires >= {rhs} but no production is possible here ({ctx})"
            )
        return
    model.constraints.add(lhs >= rhs)


def _pinned_stock_value(model: Any, t: int, material: str):
    """If ``stock_level[t, material]`` is fixed to a constant by an existing equality
    (e.g. an initial-stock boundary condition ``stock_level[0, m] == 0``), return that
    constant; otherwise ``None``.

    Inventory cases pin the opening inventory of the first period as a boundary
    condition. A reserve lower bound above that pinned value would be flatly
    infeasible, so the reserve lever uses this to skip such periods gracefully.
    """
    from pyomo.core.base.constraint import Constraint
    from pyomo.core.expr.visitor import identify_variables
    from pyomo.environ import value

    target_var = model.stock_level[t, material]
    for con in model.component_objects(Constraint, active=True):
        for idx in con:
            c = con[idx]
            if not c.equality:
                continue
            vs = list(identify_variables(c.body))
            # a pure pin is "the variable == constant": exactly one variable, and it is ours
            if len(vs) == 1 and vs[0] is target_var:
                try:
                    return float(value(c.upper))
                except Exception:
                    return None
    return None


# ══════════════════════════════════ capacity_policy ══════════════════════════
@register(
    id="capacity_ramp",
    family="capacity_policy",
    summary="Scale a process-location's per-period output capacity by given multipliers.",
    scope="A change in a process's available production capacity at a location over time — a "
          "country capacity ramp-down, expansion, or shutdown (supply-shock and policy scenarios).",
    meaning="For the named (process, location[, material]), caps total output in each period at "
            "baseline_capacity x factor[period]. Tightens the existing capacity limit only.",
    params=[
        Param("process", "str", True, None, "producing process name"),
        Param("location", "str", True, None, "process location / country code"),
        Param("factors", "list[float]", True, None,
              "per-period multiplier on baseline capacity; last value reused if shorter than the horizon"),
        Param("material", "str", False, None, "restrict to one output material; default = all from this node"),
    ],
    example='{process: "Wafer manufacturing", location: CN, factors: [1.0, 0.8, 0.5, 0.2, 0.05, 0.05]}',
    notes="A capacity cap only binds if it falls below actual utilization; where capacity is heavily "
          "over-provisioned (e.g. Chinese gallium ~1.6% utilization) capacity haircuts bind weakly.",
)
def capacity_ramp(model, loaded_data, process, location, factors, material=None):
    cap = loaded_data["max_output_capacity"]
    periods = sorted(int(t) for t in model.TimePeriods)
    for (p, l, m), percap in cap.items():
        if p != process or l != location:
            continue
        if material is not None and m != material:
            continue
        for i, t in enumerate(periods):
            factor = factors[i] if i < len(factors) else factors[-1]
            base = percap.get(t, percap.get(str(t)))
            if base is None:
                continue
            _add_le(model, _node_outflow(model, t, p, l, m), base * factor, ctx=f"capacity_ramp {p}@{l} t{t}")


@register(
    id="min_domestic_production",
    family="capacity_policy",
    summary="Onshoring floor: require minimum domestic production of a material each period.",
    scope="An onshoring / domestic-content policy floor — require a minimum amount of a material "
          "to be produced domestically each period.",
    meaning="For the named material at location (default US), requires production >= min_share x demand "
            "(or >= min_kg) each period, forcing domestic activity the cost-optimum would avoid.",
    params=[
        Param("material", "str", True, None, "material to require domestic production of"),
        Param("min_share", "float", False, None, "minimum fraction of that period's demand (0-1)"),
        Param("min_kg", "float", False, None, "minimum absolute kg per period"),
        Param("location", "str", False, "US", "domestic location / country code"),
        Param("process", "str", False, None, "producing process to count (recommended); default = any"),
    ],
    example='{material: GaN_wafer, process: "Wafer manufacturing", location: US, min_share: 0.25}',
    notes="Provide either min_share or min_kg.",
)
def min_domestic_production(model, loaded_data, material, min_share=None, min_kg=None,
                            location="US", process=None):
    if min_share is None and min_kg is None:
        raise ValueError("min_domestic_production: provide either min_share or min_kg")
    for t in sorted(int(x) for x in model.TimePeriods):
        prod = _material_production_at(model, t, location, material, process)
        floor = float(min_kg) if min_kg is not None else float(min_share) * _demand(loaded_data, t, material)
        if floor > 0:
            _add_ge(model, prod, floor, ctx=f"min_domestic_production {material}@{location} t{t}")


# ═══════════════════════════════════ diversification ═════════════════════════
@register(
    id="max_source_share",
    family="diversification",
    summary="Cap the share of a material's demand produced at a single source location.",
    scope="A supply-diversification / de-risking limit — cap how much of a material may come from "
          "any single country, to reduce concentration and single-source dependence.",
    meaning="For the named material at location, requires production <= max_share x demand each period, "
            "forcing the balance to other locations.",
    params=[
        Param("material", "str", True, None, "material to limit"),
        Param("location", "str", True, None, "source location / country code to cap"),
        Param("max_share", "float", True, None, "maximum fraction of that period's demand from this source (0-1)"),
        Param("process", "str", False, None, "producing process to count (recommended); default = any"),
    ],
    example='{material: GaN_wafer, location: CN, process: "Wafer manufacturing", max_share: 0.6}',
)
def max_source_share(model, loaded_data, material, location, max_share, process=None):
    for t in sorted(int(x) for x in model.TimePeriods):
        prod = _material_production_at(model, t, location, material, process)
        _add_le(model, prod, float(max_share) * _demand(loaded_data, t, material),
                ctx=f"max_source_share {material}@{location} t{t}")


# ══════════════════════════════════════ byproduct ═══════════════════════════
@register(
    id="byproduct_cap",
    family="byproduct",
    summary="Bound a by-product's output by a fraction of its host-material throughput.",
    scope="A by-product production limit — a critical mineral recovered as a by-product (e.g. gallium "
          "from bauxite/alumina or zinc) can only be produced in proportion to the host metal's output.",
    meaning="For each location and period, caps output of (process, material) at ratio x output of "
            "(host_process, host_material) at the same location and period.",
    params=[
        Param("process", "str", True, None, "by-product producing process"),
        Param("material", "str", True, None, "by-product material"),
        Param("host_process", "str", True, None, "host-material producing process"),
        Param("host_material", "str", True, None, "host material (its throughput bounds the by-product)"),
        Param("ratio", "float", True, None, "max by-product per unit host material (e.g. recovery yield / grade)"),
        Param("location", "str", False, None, "restrict to one location; default = all locations"),
    ],
    example='{process: "Bayer liquor refining", material: 4N_Ga, host_process: "Bayer process / alumina refining", '
            'host_material: Bayer_liquor, ratio: 0.0007}',
    notes="Applied per location where both the by-product and host node exist.",
)
def byproduct_cap(model, loaded_data, process, material, host_process, host_material, ratio, location=None):
    locations = [location] if location is not None else list(model.Locations)
    for L in locations:
        for t in sorted(int(x) for x in model.TimePeriods):
            byproduct = _node_outflow(model, t, process, L, material)
            if _is_number(byproduct):  # no by-product arcs here; nothing to cap
                continue
            host = _node_outflow(model, t, host_process, L, host_material)
            _add_le(model, byproduct, float(ratio) * host, ctx=f"byproduct_cap {process}@{L} t{t}")


# ═══════════════════════════════════ economic_policy ═════════════════════════
@register(
    id="price_support",
    family="economic_policy",
    summary="Producer price support: guarantee a target producer a competitive price (subsidy) so it can enter "
            "the least-cost solution; the subsidy outlay is reported, not hidden in the objective.",
    scope="A domestic / allied producer price-support policy — pay producers enough to stay competitive against a "
          "dominant supplier's low export price (e.g. the US guaranteeing gallium producers a competitive price). "
          "BLEECAM is a buyer-side least-cost model, so a floor is expressed as support to the producer, not a "
          "penalty on imports.",
    meaning="For the target material at location, lowers the effective per-kg cost the sourcing model sees down to "
            "target_price where its true cost is higher (equivalently a per-kg production subsidy), so the producer "
            "can be selected. Effective cost never goes below target_price (or below zero for a fixed subsidy), so "
            "the problem stays bounded. The subsidy outlay (true cost - target_price, x volume) is accumulated and "
            "reported separately as subsidy_usd; resource_cost_usd = subsidized objective + subsidy.",
    params=[
        Param("material", "str", True, None, "material whose production is supported"),
        Param("location", "str", True, None, "producer location / country code to support (e.g. US)"),
        Param("target_price", "float", False, None,
              "guaranteed competitive effective price ($/kg); per-kg subsidy = max(0, true_cost - target_price)"),
        Param("subsidy", "float", False, None,
              "alternative to target_price: a fixed per-kg production subsidy ($/kg) on the target routes"),
        Param("process", "str", False, None, "producing process to support (recommended); default = any"),
    ],
    example='{material: GaN_wafer, location: US, process: "Wafer manufacturing", target_price: 1200}',
    notes="Provide exactly one of target_price or subsidy. Only valid under the cost objective (an economic "
          "lever). China runs separate domestic and export price schemas; peg target_price to the export price "
          "the US would otherwise pay to reflect the true competitiveness gap.",
)
def price_support(model, loaded_data, material, location, target_price=None, subsidy=None, process=None):
    if (target_price is None) == (subsidy is None):
        raise ValueError("price_support: provide exactly one of target_price or subsidy")
    if getattr(model, "_bleecam_objective", None) != "cost":
        raise ValueError("price_support only applies under the cost objective (it is an economic lever)")
    arc_cost = getattr(model, "_arc_unit_cost", None)
    if arc_cost is None:
        raise ValueError("price_support: this case does not expose per-arc unit costs (_arc_unit_cost)")
    if target_price is not None and float(target_price) <= 0:
        raise ValueError("price_support: target_price must be > 0")
    if subsidy is not None and float(subsidy) <= 0:
        raise ValueError("price_support: subsidy must be > 0")

    subsidy_expr = 0.0
    for key in model.flowQ:
        _, process_from, loc_from, _, _, m = key
        if m != material or loc_from != location:
            continue
        if process is not None and process_from != process:
            continue
        c = float(arc_cost.get(key, 0.0))
        s = min(float(subsidy), c) if subsidy is not None else max(0.0, c - float(target_price))
        if s > 0:
            subsidy_expr = subsidy_expr + s * model.flowQ[key]

    if _is_number(subsidy_expr):  # nothing matched / already competitive — a no-op support
        return
    # Discount the cost the optimizer minimizes by the subsidy, and record the
    # outlay so the run can report it (the objective becomes the *buyer* cost).
    model.obj.set_value(model.obj.expr - subsidy_expr)
    prev = getattr(model, "_bleecam_subsidy_expr", None)
    model._bleecam_subsidy_expr = subsidy_expr if prev is None else prev + subsidy_expr


# ══════════════════════════════════════ resilience ═══════════════════════════
@register(
    id="strategic_reserve",
    family="resilience",
    summary="Hold a finished-good strategic reserve — a minimum inventory carried each period.",
    scope="A strategic stockpile / reserve policy — carry a minimum inventory of a finished "
          "material (NdFeB magnets, gallium wafers) as a buffer against supply disruption.",
    meaning="For the named material, requires the inventory buffer (model.stock_level) to hold at "
            "least the target each period: coverage_fraction x demand, coverage_periods x demand, or "
            "an absolute min_kg. The model pays to build and carry the reserve; under a supply-shock "
            "scenario it is drawn down to keep demand met.",
    params=[
        Param("material", "str", True, None, "finished material to stockpile"),
        Param("coverage_fraction", "float", False, None, "reserve as a fraction of each period's demand (0.5 = half a period)"),
        Param("coverage_periods", "float", False, None, "reserve as a multiple of a period's demand (2 = two periods of cover)"),
        Param("min_kg", "float", False, None, "reserve as an absolute quantity (kg) per period"),
        Param("from_period", "int", False, None, "first period the reserve must be held (default: all periods)"),
    ],
    example="{material: hp_magnet, coverage_periods: 1}",
    notes="Requires an inventory-capable case (a finished-good buffer, model.stock_level) — the gallium "
          "and rare-earth cases both provide one. Provide exactly one of coverage_fraction, "
          "coverage_periods, min_kg. If the case pins a period's opening inventory as a boundary "
          "condition (e.g. rare-earth fixes stock_level at t=0 to its initial stock), the reserve is "
          "skipped for that period instead of forcing an infeasible model; use from_period to control "
          "the first enforced period explicitly. To let the model size the reserve OPTIMALLY instead of "
          "imposing it, omit this lever and run a supply-shock scenario: the buffer is banked whenever "
          "its holding cost is less than the unmet demand it averts.",
)
def strategic_reserve(model, loaded_data, material, coverage_fraction=None, coverage_periods=None,
                      min_kg=None, from_period=None):
    if not hasattr(model, "stock_level"):
        raise ValueError("strategic_reserve requires an inventory-capable model (model.stock_level); "
                         "this case has no finished-good buffer")
    if sum(x is not None for x in (coverage_fraction, coverage_periods, min_kg)) != 1:
        raise ValueError("strategic_reserve: provide exactly one of coverage_fraction, coverage_periods, min_kg")
    skipped: list[dict[str, Any]] = []
    applied = 0
    for t in sorted(int(x) for x in model.TimePeriods):
        if from_period is not None and t < int(from_period):
            continue
        if (t, material) not in model.stock_level:
            continue
        if min_kg is not None:
            target = float(min_kg)
        else:
            factor = float(coverage_fraction if coverage_fraction is not None else coverage_periods)
            target = factor * _demand(loaded_data, t, material)
        if target <= 0:
            continue
        # Respect any pre-existing boundary condition: if the case pins this period's
        # inventory to a fixed value below the target (e.g. opening stock == 0), a
        # reserve floor here is infeasible by construction. Skip it and record why,
        # rather than handing the solver an infeasible model.
        pinned = _pinned_stock_value(model, t, material)
        if pinned is not None and pinned < target - 1e-6:
            skipped.append({"period": t, "material": material, "pinned_to": pinned, "reserve_target": target})
            continue
        _add_ge(model, model.stock_level[t, material], target, ctx=f"strategic_reserve {material} t{t}")
        applied += 1
    if applied == 0 and skipped:
        raise ValueError(
            "strategic_reserve was skipped in every period because inventory is pinned by the case "
            f"(e.g. opening stock is fixed): {skipped}. Set from_period to the first period whose "
            "inventory is a free decision, or lower the reserve target."
        )
    if skipped:
        notes = getattr(model, "_strategic_reserve_notes", [])
        notes.extend(skipped)
        model._strategic_reserve_notes = notes
