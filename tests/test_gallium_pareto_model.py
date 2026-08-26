# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Structural test for the Gallium AUGMECON 3-objective model.

Verifies the model handed to PyAugmecon matches the REE method: three
deactivated minimized objectives (cost, GWP, child labor) on a bounded network.
Does not run AUGMECON itself (that needs ipopt + pyaugmecon, as in the report).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pytest.importorskip("pandas")

DATA = Path(__file__).resolve().parents[1] / "src" / "bleecam" / "cases" / "gallium" / "data" / "gallium"


def test_pareto_model_has_three_bounded_deactivated_objectives(tmp_path):
    from bleecam.cases.gallium.gallium_pareto import build_pareto_model
    from bleecam.cases.gallium.gallium_pyomo import flow_upper_bound, load_inputs

    data = load_inputs(DATA, tmp_path / "out", strict=True)
    model = build_pareto_model(data)

    objs = list(model.obj_list.values())
    assert len(objs) == 3, "expect cost, GWP, child-labor objectives"
    assert all(not o.active for o in objs), "PyAugmecon requires all objectives deactivated"

    # Every flow variable must be finitely bounded (keeps AUGMECON well-posed),
    # and the bound is derived from demand — far above any feasible flow.
    ub = flow_upper_bound(data)
    total_demand = float(data["demand_df"]["demand_kg"].sum())
    assert ub > total_demand
    any_arc = next(iter(model.flowQ))
    assert model.flowQ[any_arc].ub == ub
    assert model.flowQ[any_arc].lb == 0
