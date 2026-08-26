# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""OAT elasticity screen sanity checks (gallium; solves with HiGHS)."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("pandas")
yaml = pytest.importorskip("yaml")

from bleecam.core.sensitivity import oat_elasticities

ROOT = Path(__file__).resolve().parents[1]
GA = ROOT / "src" / "bleecam" / "cases" / "gallium"
DATA = GA / "data" / "gallium"


def _solver_available():
    import pyomo.environ  # noqa: F401
    from pyomo.environ import SolverFactory
    for n in ("appsi_highs", "highs", "ipopt", "glpk", "cbc"):
        try:
            if SolverFactory(n).available(exception_flag=False):
                return True
        except Exception:
            continue
    return False


@pytest.mark.skipif(not _solver_available(), reason="no LP solver available")
def test_oat_gallium_cost_screen():
    cfg = {"case": "gallium", "data_dir": str(DATA), "objective": "cost", "constraints": []}
    factors = yaml.safe_load((GA / "sensitivity_factors.yaml").read_text())["factors"]
    res = oat_elasticities(cfg, factors, delta=0.1)
    e = {r["factor"]: r["elasticity"] for r in res["factors"]}
    # demand scales cost ~1:1; processing is the dominant cost driver; yield is inverse
    assert abs(e["Demand"] - 1.0) < 0.05
    assert e["Processing cost"] > 0.5
    assert e["Yield"] < -0.5
    # environmental / social factors do NOT move the cost objective
    assert abs(e["GWP factors"] or 0.0) < 1e-6
    assert abs(e["Child-labor factors"] or 0.0) < 1e-6
    # ranking puts a cost driver first
    assert res["factors"][0]["factor"] in {"Demand", "Processing cost", "Yield"}
