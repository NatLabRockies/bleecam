# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Golden-output regression test for the Gallium cost-only baseline.

Runs the full pipeline (load -> validate -> build -> solve) and asserts the
result matches the captured baseline within a solver-tolerant tolerance, plus
the hard invariants: loader is clean (0 blocking issues) and demand is fully
met (no slack).
"""
from __future__ import annotations

import pytest

pytest.importorskip("pyomo")
pd = pytest.importorskip("pandas")


def _gallium_summary(data_dir, report_dir) -> dict:
    from bleecam.cases.gallium.gallium_data_loader import load_gallium_data
    from bleecam.cases.gallium.gallium_pyomo import build_model, solve_model

    # Route validation reports into the test's temp dir so the suite never
    # writes artifacts into the repo working tree.
    data = load_gallium_data(
        str(data_dir),
        strict=True,
        report_md_path=str(report_dir / "gallium_loader_validation_report.md"),
        report_csv_path=str(report_dir / "gallium_loader_validation_report.csv"),
    )
    summary = data["validation_summary"]
    blocking = int(summary.get("issue_counts_by_severity", {}).get("blocking", 0))

    model = build_model(data)
    result = solve_model(model, solver_name="auto")

    # Demand fully met == no positive demand slack.
    slack = result.get("demand_slack", []) or []
    demand_fully_met = len(slack) == 0

    return {
        "objective": float(result["objective_value"]),
        "termination": result["termination_condition"],
        "demand_fully_met": demand_fully_met,
        "blocking_issues": blocking,
        "n_periods": len(data.get("time_periods", [])),
    }


def test_gallium_solves_optimal(gallium_data_dir, tmp_path):
    summary = _gallium_summary(gallium_data_dir, tmp_path)
    assert summary["termination"] == "optimal"
    assert summary["blocking_issues"] == 0
    assert summary["demand_fully_met"] is True


def test_gallium_regression_baseline(gallium_data_dir, tmp_path, regression_check):
    summary = _gallium_summary(gallium_data_dir, tmp_path)
    regression_check("gallium", summary)
