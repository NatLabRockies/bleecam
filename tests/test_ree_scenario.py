# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cross-case tests: the criticality library composes onto the REE magnet case.

The build/compose/guard tests need no solver and run anywhere. The solve test
needs ipopt (REE's solver — appsi/HiGHS rejects the model's degree-None terms),
so it skips where ipopt is unavailable.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("pandas")

ROOT = Path(__file__).resolve().parents[1]
REE_DATA = ROOT / "src" / "bleecam" / "cases" / "rare_earth" / "data"


def _ipopt_available():
    import pyomo.environ  # noqa: F401  (register solver plugins)
    from pyomo.environ import SolverFactory
    try:
        return bool(SolverFactory("ipopt").available(exception_flag=False))
    except Exception:
        return False


def test_ree_builds_with_generic_contracts():
    from bleecam.cases.rare_earth.REE import build_model, load_inputs
    data = load_inputs(REE_DATA)
    m = build_model(data, "cost")
    assert m._bleecam_objective == "cost"
    assert len(m._arc_unit_cost) == len(m.flowQ)
    assert set(data["demand_df"].columns) >= {"time_period", "material", "demand_kg"}


def test_ree_price_support_composes_and_guards():
    from bleecam.cases.rare_earth.REE import build_model, load_inputs
    from bleecam.core.criticality.registry import get
    data = load_inputs(REE_DATA)
    m = build_model(data, "cost")
    c = get("price_support")
    before = str(m.obj.expr)
    c.apply(m, data, **c.validate({"material": "hp_magnet", "location": "US",
                                   "process": "magnet manufacturing", "target_price": 5.0}))
    assert getattr(m, "_bleecam_subsidy_expr", None) is not None   # subsidy recorded
    assert str(m.obj.expr) != before                              # objective discounted
    # exactly one of target_price / subsidy
    with pytest.raises(ValueError):
        c.apply(m, data, **c.validate({"material": "hp_magnet", "location": "US",
                                       "target_price": 5, "subsidy": 1}))
    # economic lever only under the cost objective
    mg = build_model(data, "gwp")
    with pytest.raises(ValueError):
        get("price_support").apply(mg, data, material="hp_magnet", location="US", target_price=5)


@pytest.mark.skipif(not _ipopt_available(), reason="REE solves with ipopt")
def test_ree_price_support_solves_and_reports_subsidy(tmp_path):
    from bleecam.core.scenario import run_scenario
    r = run_scenario(
        {"case": "rare_earth", "data_dir": str(REE_DATA), "objective": "cost",
         "constraints": [{"id": "price_support", "params": {
             "material": "hp_magnet", "location": "US",
             "process": "magnet manufacturing", "target_price": 5.0}}]},
        out_dir=tmp_path / "o",
    )
    assert r["termination"] in ("optimal", "feasible", "locallyOptimal")
    assert r["subsidy_usd"] >= 0
    assert "resource_cost_usd" in r
