# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the criticality library + YAML scenario runner (no-code path)."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("pandas")
pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "bleecam" / "cases" / "gallium" / "data" / "gallium"
CATALOG = ROOT / "docs" / "criticality_library.md"
RTOL = 1e-3


def _solver_available():
    from bleecam.core.solve import SolverUnavailableError, choose_solver
    try:
        choose_solver("auto")
        return True
    except SolverUnavailableError:
        return False


def _run(tmp_path, constraints):
    from bleecam.core.scenario import run_scenario
    return run_scenario(
        {"case": "gallium", "data_dir": str(DATA), "objective": "cost", "constraints": constraints},
        out_dir=tmp_path / "o",
    )


# ── registry + documentation (no solver needed) ──────────────────────────────
def test_library_registered():
    from bleecam.core.criticality import all_constraints, describe
    ids = {c.id for c in all_constraints()}
    assert {"capacity_ramp", "min_domestic_production", "max_source_share", "byproduct_cap",
            "price_support", "strategic_reserve"} <= ids
    text = describe("capacity_ramp")
    assert "scope" in text and "meaning" in text and "factors" in text


def test_catalog_documents_all_constraints():
    """The committed catalog must document exactly the registered constraints (no drift)."""
    from bleecam.core.criticality import all_constraints
    doc = CATALOG.read_text()
    constraints = all_constraints()
    assert doc.count("### `") == len(constraints), "regenerate: bleecam-lib docs --write docs/criticality_library.md"
    for c in constraints:
        assert f"### `{c.id}`" in doc
        assert f"`{c.family}`" in doc


# ── solved scenarios ─────────────────────────────────────────────────────────
pytestmark_solver = pytest.mark.skipif(not _solver_available(), reason="no Pyomo solver available")


@pytestmark_solver
def test_scenario_baseline_reproduces_golden(tmp_path):
    r = _run(tmp_path, [])
    assert r["termination"] == "optimal" and r["demand_met"]
    assert r["objective_value"] == pytest.approx(816_577_036, rel=RTOL)


@pytestmark_solver
def test_scenario_reports_real_usd(tmp_path):
    """The runner reports a real (un-scaled) objective alongside the scaled one, so
    the number is directly readable. Gallium's flow_scale is 1, so real == scaled;
    rare-earth's is 1000 (validated by the arithmetic real = scaled x flow_scale)."""
    r = _run(tmp_path, [])
    assert r["flow_scale"] == 1.0
    assert r["objective_real_usd"] == pytest.approx(r["objective_value"] * r["flow_scale"], rel=1e-9)
    assert r["objective_real_usd"] == pytest.approx(816_577_036, rel=RTOL)


@pytestmark_solver
def test_onshoring_floor_raises_cost_and_meets_demand(tmp_path):
    r = _run(tmp_path, [
        {"id": "min_domestic_production", "params": {"material": "GaN_wafer", "process": "Wafer manufacturing", "location": "US", "min_share": 0.25}},
        {"id": "min_domestic_production", "params": {"material": "GaAs_wafer", "process": "Wafer manufacturing", "location": "US", "min_share": 0.25}},
    ])
    assert r["termination"] == "optimal" and r["demand_met"]
    assert r["objective_value"] > 816_577_036
    assert r["objective_value"] == pytest.approx(954_408_271, rel=5e-3)


@pytestmark_solver
def test_max_source_share_forces_diversification(tmp_path):
    r = _run(tmp_path, [
        {"id": "max_source_share", "params": {"material": "GaN_wafer", "location": "CN", "process": "Wafer manufacturing", "max_share": 0.5}},
        {"id": "max_source_share", "params": {"material": "GaAs_wafer", "location": "CN", "process": "Wafer manufacturing", "max_share": 0.5}},
    ])
    assert r["termination"] == "optimal" and r["demand_met"]
    assert r["objective_value"] > 816_577_036
    assert r["objective_value"] == pytest.approx(1_092_239_505, rel=5e-3)


@pytestmark_solver
def test_byproduct_cap_binds_and_stays_feasible(tmp_path):
    r = _run(tmp_path, [
        {"id": "byproduct_cap", "params": {
            "process": "Bayer liquor refining", "material": "4N_Ga",
            "host_process": "Bayer process / alumina refining", "host_material": "Bayer_liquor",
            "ratio": 0.0005}},
    ])
    assert r["termination"] == "optimal" and r["demand_met"]
    assert r["objective_value"] > 816_577_036  # binds -> forces gallium off the cheapest route


@pytestmark_solver
def test_price_support_subsidizes_and_pulls_domestic_in(tmp_path):
    """A low guaranteed price for US wafers makes domestic competitive: the buyer
    cost falls, a positive subsidy is reported, and resource cost = buyer + subsidy."""
    r = _run(tmp_path, [
        {"id": "price_support", "params": {"material": "GaN_wafer", "location": "US", "process": "Wafer manufacturing", "target_price": 1.0}},
        {"id": "price_support", "params": {"material": "GaAs_wafer", "location": "US", "process": "Wafer manufacturing", "target_price": 1.0}},
    ])
    assert r["termination"] == "optimal" and r["demand_met"]
    assert r["subsidy_usd"] > 0                              # support actually paid out
    assert r["objective_value"] < 816_577_036               # subsidized buyer cost is lower
    # resource cost = subsidized objective + subsidy outlay
    assert r["resource_cost_usd"] == pytest.approx(r["objective_value"] + r["subsidy_usd"], rel=1e-9)


@pytestmark_solver
def test_price_support_requires_exactly_one_lever(tmp_path):
    with pytest.raises(ValueError):
        _run(tmp_path, [{"id": "price_support", "params": {"material": "GaN_wafer", "location": "US"}}])
    with pytest.raises(ValueError):
        _run(tmp_path, [{"id": "price_support", "params": {
            "material": "GaN_wafer", "location": "US", "target_price": 1200, "subsidy": 500}}])


def test_price_support_rejects_non_cost_objective(tmp_path):
    """The economic lever is only meaningful under the cost objective."""
    from bleecam.core.scenario import run_scenario
    with pytest.raises(ValueError):
        run_scenario(
            {"case": "gallium", "data_dir": str(DATA), "objective": "gwp",
             "constraints": [{"id": "price_support", "params": {"material": "GaN_wafer", "location": "US", "target_price": 1200}}]},
            out_dir=tmp_path / "o",
        )


@pytestmark_solver
def test_strategic_reserve_binds_and_holds_stock(tmp_path):
    """A one-period reserve forces the model to build & carry inventory, raising cost."""
    from pyomo.environ import value
    r = _run(tmp_path, [
        {"id": "strategic_reserve", "params": {"material": "GaN_wafer", "coverage_periods": 1}},
        {"id": "strategic_reserve", "params": {"material": "GaAs_wafer", "coverage_periods": 1}},
    ])
    assert r["termination"] == "optimal" and r["demand_met"]
    assert r["objective_value"] > 816_577_036          # carrying a reserve costs more than baseline
    m = r["model"]
    held = sum(value(m.stock_level[t, mm]) for t in m.TimePeriods for mm in m.StockMaterials)
    assert held > 0                                     # a reserve is actually held


@pytestmark_solver
def test_strategic_reserve_requires_exactly_one_measure(tmp_path):
    with pytest.raises(ValueError):
        _run(tmp_path, [{"id": "strategic_reserve", "params": {"material": "GaN_wafer"}}])


def test_strategic_reserve_skips_pinned_initial_stock():
    """If a case pins opening inventory (stock_level[0] == 0) as a boundary condition,
    the reserve must skip that period gracefully — not hand the solver an infeasible
    model (the rare-earth case pins stock_level at t=0). No solver required."""
    import pandas as pd
    from pyomo.environ import ConcreteModel, Set, Var, NonNegativeReals, ConstraintList
    from bleecam.core.criticality import get

    m = ConcreteModel()
    m.TimePeriods = Set(initialize=[0, 1, 2])
    m.StockMaterials = Set(initialize=["mag"])
    m.stock_level = Var(m.TimePeriods, m.StockMaterials, domain=NonNegativeReals, bounds=(0, 1e6), initialize=0)
    m.constraints = ConstraintList()
    m.constraints.add(m.stock_level[0, "mag"] == 0.0)   # opening-inventory boundary condition
    data = {"demand_df": pd.DataFrame(
        {"time_period": [0, 1, 2], "material": ["mag"] * 3, "demand_kg": [100.0, 100.0, 100.0]})}

    n_before = len(m.constraints)
    get("strategic_reserve").apply(m, data, material="mag", coverage_periods=1)
    added = len(m.constraints) - n_before

    assert added == 2                                   # periods 1 and 2 constrained; period 0 skipped
    notes = getattr(m, "_strategic_reserve_notes", [])
    assert notes and notes[0]["period"] == 0 and notes[0]["pinned_to"] == 0.0


def test_strategic_reserve_all_pinned_raises_actionable_error():
    """If every requested period is pinned below target, raise a clear error (not silent infeasibility)."""
    import pandas as pd
    from pyomo.environ import ConcreteModel, Set, Var, NonNegativeReals, ConstraintList
    from bleecam.core.criticality import get

    m = ConcreteModel()
    m.TimePeriods = Set(initialize=[0])
    m.StockMaterials = Set(initialize=["mag"])
    m.stock_level = Var(m.TimePeriods, m.StockMaterials, domain=NonNegativeReals, bounds=(0, 1e6), initialize=0)
    m.constraints = ConstraintList()
    m.constraints.add(m.stock_level[0, "mag"] == 0.0)
    data = {"demand_df": pd.DataFrame({"time_period": [0], "material": ["mag"], "demand_kg": [100.0]})}

    with pytest.raises(ValueError, match="pinned"):
        get("strategic_reserve").apply(m, data, material="mag", coverage_periods=1)


# ── validation ───────────────────────────────────────────────────────────────
@pytestmark_solver
def test_unknown_constraint_is_rejected(tmp_path):
    with pytest.raises(KeyError):
        _run(tmp_path, [{"id": "does_not_exist"}])


@pytestmark_solver
def test_bad_param_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        _run(tmp_path, [{"id": "capacity_ramp", "params": {"process": "Wafer manufacturing"}}])
