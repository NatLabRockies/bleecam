# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Golden-output regression test for the REE multi-location baseline.

REE solves with ipopt (hard-coded in the case). Where ipopt is unavailable
(e.g. the CI sandbox) the test skips. On a machine with ipopt it runs the case
end-to-end into a temp dir and reads run_summary.json, anchoring the golden on
the REAL cost objective ($) within OBJ_RTOL, with n_flow_rows / n_periods as
exact structural invariants.

(Earlier revisions stored total flow VOLUME under the "objective" key — a
mislabel: the REE cost objective is ~$397M, not the ~$96M flow volume. The cost
objective is both the meaningful figure and unique at optimality.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pyomo")
pd = pytest.importorskip("pandas")

SRC = Path(__file__).resolve().parents[1] / "src"


def _ipopt_available() -> bool:
    from pyomo.environ import SolverFactory
    try:
        return bool(SolverFactory("ipopt").available(False))
    except Exception:
        return False


def _ree_summary(ree_data_dir: Path, tmp_path: Path) -> dict:
    """Run REE end-to-end into tmp_path and summarize the written flow table."""
    out_dir = tmp_path / "ree_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(SRC) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    # Run as a module so relative imports resolve; isolate stray outputs in tmp.
    proc = subprocess.run(
        [sys.executable, "-m", "bleecam.cases.rare_earth.REE",
         "--data", str(ree_data_dir), "--out", str(out_dir)],
        cwd=str(out_dir), env=env, capture_output=True, text=True, timeout=1800,
    )
    results_csv = out_dir / "model_results_multilocation.csv"
    summary_json = out_dir / "run_summary.json"
    assert results_csv.exists() and summary_json.exists(), (
        "REE run did not write model_results_multilocation.csv / run_summary.json.\n"
        f"stdout tail:\n{proc.stdout[-2000:]}\nstderr tail:\n{proc.stderr[-2000:]}"
    )
    s = json.loads(summary_json.read_text())
    return {
        "objective": round(float(s["objective_real_usd"]), 2),   # the REAL cost objective ($)
        "n_flow_rows": int(s["n_flow_rows"]),
        "n_periods": int(s["n_periods"]),
    }


@pytest.mark.skipif(not _ipopt_available(), reason="ipopt not available in this environment")
def test_ree_regression_baseline(ree_data_dir, tmp_path, regression_check):
    summary = _ree_summary(ree_data_dir, tmp_path)
    # objective = the real cost objective ($) within OBJ_RTOL; n_flow_rows / n_periods exact.
    regression_check("ree", summary)
