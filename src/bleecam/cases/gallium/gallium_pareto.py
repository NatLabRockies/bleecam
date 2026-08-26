# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Gallium 3-objective Pareto front via AUGMECON2 (cost x GWP x child labor).

This mirrors the REE case's ``pareto.py`` method exactly: an ``ObjectiveList`` of
three minimized expressions (cost, GWP, child-labor SLCA), each carrying a
demand-slack penalty, handed to :class:`pyaugmecon.PyAugmecon` with the same
options. The model's flow variables are bounded (see
``gallium_pyomo.FLOW_UPPER_BOUND_KG``), which — together with the augmented
epsilon-constraint method — keeps every solve bounded despite impact-free
recycling loops. This is the *reproducible baseline* method for BLEECAM
multi-objective results, consistent with how the Phase 1 report was produced.

Run (needs ipopt + pyaugmecon, as in the report):

    python -m bleecam.cases.gallium.gallium_pareto \
        --data src/bleecam/cases/gallium/data/gallium --out outputs/gallium_pareto --grid 50
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pyomo.environ import ObjectiveList, minimize

from bleecam.core.objectives import linear_flow_expression
from .config_ga import DEFAULT_INPUT_DIR, DEMAND_SLACK_PENALTY_USD_PER_KG
from .gallium_pyomo import (
    OBJECTIVE_ALIASES,
    assemble_gallium_network,
    gallium_flow_cost_expression,
    load_inputs,
)

# AUGMECON2 options — identical set to the REE pareto.py run.
AUGMECON_OPTS = {
    "name": "BLEECAM_Gallium_Pareto",
    "nadir_ratio": 1.0,
    "early_exit": True,
    "bypass_coefficient": True,
    "flag_array": True,
    "penalty_weight": 0.001,
    "solver_io": "nl",
    "output_excel": False,
    "process_logging": False,
}


def _slack_penalty(model, penalty: float):
    return penalty * sum(model.demand_slack[key] for key in model.DemandKeys)


def _max_factor(factor_map: dict) -> float:
    return max((abs(v) for v in factor_map.values()), default=1.0)


def build_pareto_model(loaded_data: dict):
    """Assemble the bounded Gallium network with a 3-objective ObjectiveList
    (cost, GWP, child labor), all deactivated for PyAugmecon to drive."""
    model, cost_maps = assemble_gallium_network(loaded_data)
    impact = loaded_data["impact_factors"]
    gwp_map = impact[OBJECTIVE_ALIASES["gwp"]]
    slca_map = impact[OBJECTIVE_ALIASES["child_labor"]]

    cost_expr = gallium_flow_cost_expression(model, cost_maps) + _slack_penalty(
        model, DEMAND_SLACK_PENALTY_USD_PER_KG
    )
    # Per-objective slack penalty scaled to the objective's own magnitude so each
    # payoff-table solve meets demand without wrecking LP conditioning.
    gwp_expr = linear_flow_expression(model, gwp_map) + _slack_penalty(model, _max_factor(gwp_map) * 1e3)
    slca_expr = linear_flow_expression(model, slca_map) + _slack_penalty(model, _max_factor(slca_map) * 1e3)

    model.obj_list = ObjectiveList()
    model.obj_list.add(expr=cost_expr, sense=minimize)     # 1: cost (USD)
    model.obj_list.add(expr=gwp_expr, sense=minimize)      # 2: GWP (kg CO2-eq)
    model.obj_list.add(expr=slca_expr, sense=minimize)     # 3: child labor (worker-hr)
    for i in range(len(model.obj_list)):
        model.obj_list[i + 1].deactivate()
    return model


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gallium AUGMECON2 3-objective Pareto (cost x GWP x child labor).")
    p.add_argument("--data", type=Path, default=DEFAULT_INPUT_DIR)
    p.add_argument("--out", type=Path, default=Path("outputs/gallium_pareto"))
    p.add_argument("--grid", type=int, default=50, help="Grid points per constrained objective (default 50).")
    p.add_argument("--cpus", type=int, default=1, help="CPU cores for parallel solves.")
    p.add_argument("--solver", default="ipopt", help="Solver name for PyAugmecon (default ipopt, as in the report).")
    return p.parse_args()


def run(args: argparse.Namespace) -> int:
    from pyaugmecon import PyAugmecon  # lazy: only needed for the actual run

    print("=" * 60)
    print("BLEECAM Gallium — AUGMECON2 3-objective Pareto (cost x GWP x child labor)")
    print(f"  grid points : {args.grid}   solver: {args.solver}")
    print("=" * 60)
    data = load_inputs(args.data, args.out, strict=True)
    model = build_pareto_model(data)

    opts = dict(AUGMECON_OPTS, grid_points=args.grid, cpu_count=args.cpus, solver_name=args.solver)
    pa = PyAugmecon(model, opts, solver_opts={})
    pa.solve()

    pareto_keys = pa.get_pareto_solutions()
    print(f"\nPareto solutions : {len(pareto_keys)}")
    print(f"Models solved    : {pa.model.models_solved.value()}")
    print(f"Runtime          : {pa.runtime}s")

    # Gallium objectives are already in real units (no FLOW_SCALE).
    df = pd.DataFrame(
        [{"cost_usd": k[0], "gwp_kg_co2eq": k[1], "child_labor_hrs": k[2]} for k in pareto_keys]
    ).sort_values("cost_usd").reset_index(drop=True)
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "gallium_pareto_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nPareto CSV -> {csv_path}")
    return 0


def main() -> int:
    return run(_parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
