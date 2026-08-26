# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The generic config-driven builder reproduces a hand-written case exactly.

Driven only by gallium.case.yaml + the generic loader + core/network.build_model,
the model must reproduce the Gallium golden optimum to the cent — proving a
standard flow-network material needs no per-case Python.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("pandas")

from bleecam.core import network
from bleecam.core.case_config import load_case_config
from bleecam.core.data_loader import load_case_data

ROOT = Path(__file__).resolve().parents[1]
GA = ROOT / "src" / "bleecam" / "cases" / "gallium"
DATA = GA / "data" / "gallium"


def _solver_available():
    import pyomo.environ  # noqa: F401
    from pyomo.environ import SolverFactory
    for name in ("appsi_highs", "highs", "ipopt", "glpk", "cbc"):
        try:
            if SolverFactory(name).available(exception_flag=False):
                return True
        except Exception:
            continue
    return False


@pytest.mark.skipif(not _solver_available(), reason="no LP solver available")
def test_generic_builder_reproduces_gallium_optimum():
    cfg = load_case_config(GA / "gallium.case.yaml")
    data = load_case_data(cfg, DATA)
    model = network.build_model(cfg, data, objective="cost")
    r = network.solve_model(model, cfg, "auto")
    assert r["termination_condition"] == "optimal"
    assert len(r["demand_slack"]) == 0                       # demand fully met
    assert r["objective_value"] == pytest.approx(816_577_036, rel=1e-3)


@pytest.mark.skipif(not _solver_available(), reason="no LP solver available")
def test_generic_runner_end_to_end_and_library_composes(tmp_path):
    """A NEW case (unknown to the runner) routes through the generic path via a
    case_config, reproduces the optimum, and the criticality library composes on it."""
    from bleecam.core.scenario import run_scenario
    base = {"case": "demo_generic", "case_config": str(GA / "gallium.case.yaml"),
            "data_dir": str(DATA), "objective": "cost"}
    r0 = run_scenario({**base, "constraints": []}, out_dir=tmp_path / "a")
    assert r0["termination"] == "optimal" and r0["demand_met"]
    assert r0["objective_value"] == pytest.approx(816_577_036, rel=1e-3)
    # library lever composes on the generic model (diversification binds -> higher cost)
    r1 = run_scenario({**base, "constraints": [
        {"id": "max_source_share", "params": {"material": "GaN_wafer", "location": "CN",
                                              "process": "Wafer manufacturing", "max_share": 0.5}}]},
        out_dir=tmp_path / "b")
    assert r1["termination"] == "optimal" and r1["demand_met"]
    assert r1["objective_value"] > r0["objective_value"]
