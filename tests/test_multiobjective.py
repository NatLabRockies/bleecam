# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Multi-objective regression tests (Gallium cost vs. GWP).

Guards the degeneracy fix: the lexicographic min-GWP-then-cost solve must yield
a *bounded* network (not the degenerate free-flow vertex a pure impact objective
produces), and the epsilon-constraint frontier must be a proper trade-off
(cost non-increasing as the GWP cap loosens). Solver-tolerant on values.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("pandas")

DATA = Path(__file__).resolve().parents[1] / "src" / "bleecam" / "cases" / "gallium" / "data" / "gallium"
GWP = "EF_weighted__Global Warming Potential (Gwp1000)"
RTOL = 1e-3


def _solver_available():
    from bleecam.core.solve import choose_solver, SolverUnavailableError
    try:
        choose_solver("auto")
        return True
    except SolverUnavailableError:
        return False


pytestmark = pytest.mark.skipif(not _solver_available(), reason="no Pyomo solver available")


def _data(tmp_path):
    from bleecam.cases.gallium.gallium_pyomo import load_inputs
    return load_inputs(DATA, tmp_path / "out", strict=True)


def test_lexicographic_gwp_bounded_and_meaningful(tmp_path):
    from bleecam.cases.gallium.gallium_pyomo import build_model, solve_model
    from bleecam.core.multiobjective import lexicographic_impact_optimal

    data = _data(tmp_path)
    lex = lexicographic_impact_optimal(build_model, solve_model, data, GWP)

    # Total demand across the horizon is ~106,027 kg. A cost-regularized network
    # must be within a small multiple of that, NOT billions (the degenerate case).
    total_flow = sum((lex["model"].flowQ[k].value or 0) for k in lex["model"].flowQ)
    assert total_flow < 50 * 106_027, f"network looks degenerate: total flow {total_flow:,.0f}"

    # GWP floor and its least cost (solver-tolerant regression anchors).
    assert lex["impact"] == pytest.approx(26_151_284, rel=RTOL)
    assert lex["cost"] == pytest.approx(851_806_147, rel=5e-3)


def test_epsilon_frontier_is_a_tradeoff(tmp_path):
    from bleecam.cases.gallium.gallium_pyomo import build_model, solve_model
    from bleecam.core.multiobjective import epsilon_constraint_frontier

    data = _data(tmp_path)
    pts = epsilon_constraint_frontier(build_model, solve_model, data, GWP, n_points=4)
    assert len(pts) >= 3

    # Sorted by impact ascending; cost must be non-increasing (a real frontier).
    costs = [p["cost"] for p in pts]
    for a, b in zip(costs, costs[1:]):
        assert b <= a * (1 + 1e-6), f"frontier not monotone: {costs}"

    # Cost-optimal end must reproduce the golden objective.
    assert min(costs) == pytest.approx(816_577_036, rel=RTOL)
