# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Multi-objective methods for BLEECAM (cost vs. an impact category).

Why this module exists — the degeneracy argument
-------------------------------------------------
Minimizing a single *impact* (e.g., GWP) directly is ill-posed for network
optimization: every arc whose source node has a zero or missing impact factor
is "free" under that objective, so the optimizer lands on a degenerate vertex
with enormous circulating flows. The minimum *impact value* is correct, but the
*flow network* achieving it is meaningless.

Cost does not have this problem — every arc costs something — so cost acts as a
natural regularizer. This module provides the two standard, defensible ways to
use cost to get sensible impact-optimal networks and trade-off frontiers:

* :func:`lexicographic_impact_optimal` — minimize the impact, then, among all
  min-impact solutions, minimize cost. Yields the true impact floor *and* a
  clean, least-cost network that achieves it.
* :func:`epsilon_constraint_frontier` — keep cost as the objective and sweep an
  upper bound (epsilon) on the impact, tracing the cost-vs-impact Pareto front.
  This is the method used for the published Gallium/REE Pareto results.

Both take the case's ``build_model`` and ``solve_model`` callables, so they are
case-agnostic.
"""
from __future__ import annotations

from typing import Any, Callable

from pyomo.environ import value

from .objectives import linear_flow_expression

NodeKey = tuple[int, str, str, str]


def _add_impact_cap(model: Any, factor_map: dict[NodeKey, float], cap: float) -> None:
    """Add the constraint ``sum(factor * flow) <= cap`` to a cost-objective model."""
    model.constraints.add(linear_flow_expression(model, factor_map) <= cap)


def _impact_of(model: Any, factor_map: dict[NodeKey, float]) -> float:
    """Evaluate the realized impact of a solved model's flows."""
    return float(value(linear_flow_expression(model, factor_map)))


def lexicographic_impact_optimal(
    build_model: Callable[..., Any],
    solve_model: Callable[..., dict],
    loaded_data: dict[str, Any],
    impact_col: str,
    *,
    solver: str = "auto",
    rel_tol: float = 1e-6,
) -> dict[str, Any]:
    """Minimize ``impact_col``, then minimize cost among min-impact solutions.

    :returns: dict with ``impact`` (true floor), ``cost`` (least cost achieving
        it), ``termination``, and the solved ``model`` (a clean, bounded network).
    """
    factor_map = loaded_data["impact_factors"][impact_col]

    # Stage 1: impact floor. build_model regularizes impact objectives (a pure
    # single-impact objective can be unbounded), so this is well-posed; the true
    # floor is read from the flows, not the (normalized) objective value.
    m1 = build_model(loaded_data, objective=impact_col)
    r1 = solve_model(m1, solver)
    impact_star = _impact_of(m1, factor_map)

    # Stage 2: least cost subject to impact <= floor (+ tiny tolerance).
    m2 = build_model(loaded_data, objective="cost")
    cap = impact_star * (1.0 + rel_tol) + rel_tol
    _add_impact_cap(m2, factor_map, cap)
    r2 = solve_model(m2, solver)

    return {
        "impact_col": impact_col,
        "impact": impact_star,
        "cost": r2["objective_value"],
        "termination": r2["termination_condition"],
        "stage1_termination": r1["termination_condition"],
        "model": m2,
    }


def epsilon_constraint_frontier(
    build_model: Callable[..., Any],
    solve_model: Callable[..., dict],
    loaded_data: dict[str, Any],
    impact_col: str,
    *,
    solver: str = "auto",
    n_points: int = 6,
) -> list[dict[str, Any]]:
    """Trace the cost-vs-impact Pareto frontier by sweeping an impact cap.

    Anchors the sweep between the impact of the cost-optimal network (upper) and
    the impact floor from :func:`lexicographic_impact_optimal` (lower), then
    minimizes cost at ``n_points`` caps in between. Each returned point is
    cost-regularized (sensible network) by construction.
    """
    factor_map = loaded_data["impact_factors"][impact_col]

    # Upper anchor: cost-optimal network and its (incidental) impact.
    mc = build_model(loaded_data, objective="cost")
    rc = solve_model(mc, solver)
    impact_hi = _impact_of(mc, factor_map)
    cost_lo = rc["objective_value"]

    # Lower anchor: impact floor and its least cost.
    lex = lexicographic_impact_optimal(build_model, solve_model, loaded_data, impact_col, solver=solver)
    impact_lo, cost_hi = lex["impact"], lex["cost"]

    points: list[dict[str, Any]] = [
        {"label": "cost_optimal", "cost": cost_lo, "impact": impact_hi, "cap": None},
    ]
    if n_points >= 2 and impact_hi > impact_lo:
        span = impact_hi - impact_lo
        for i in range(n_points):
            cap = impact_lo + span * i / (n_points - 1)
            m = build_model(loaded_data, objective="cost")
            _add_impact_cap(m, factor_map, cap)
            r = solve_model(m, solver)
            if r["termination_condition"] == "optimal":
                points.append({
                    "label": f"cap_{i}",
                    "cost": r["objective_value"],
                    "impact": _impact_of(m, factor_map),
                    "cap": cap,
                })
    # Sort by impact ascending (impact floor -> cost-optimal).
    points.sort(key=lambda p: p["impact"])
    return points
