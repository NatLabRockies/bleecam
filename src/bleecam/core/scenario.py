# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run a BLEECAM scenario from a YAML file — no Python required.

A scenario file declares the case, data, objective, and a list of criticality
constraints (by id, with parameters) to compose onto the model::

    case: gallium
    data_dir: src/bleecam/cases/gallium/data/gallium
    objective: cost            # cost | gwp | child_labor | any EF/SLCA column
    constraints:
      - id: capacity_ramp
        params: {process: "Wafer manufacturing", location: CN, factors: [1,0.8,0.5,0.2,0.05,0.05]}

Run with ``bleecam-run scenario.yaml``. View available constraints with
``bleecam-lib list`` / ``bleecam-lib describe <id>``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bleecam.core.criticality.registry import get


def _resolve_case_config(case: str, config: dict) -> Path:
    """Locate a case YAML: explicit `case_config:` in the scenario, or the package default."""
    if config.get("case_config"):
        return Path(config["case_config"])
    import bleecam
    default = Path(bleecam.__file__).parent / "cases" / case / f"{case}.case.yaml"
    if default.exists():
        return default
    raise ValueError(
        f"unknown case {case!r}: add a 'case_config:' path in the scenario, or place "
        f"cases/{case}/{case}.case.yaml in the package."
    )


def run_scenario(config: dict | str | Path, *, solver: str = "auto", out_dir: str | Path | None = None) -> dict[str, Any]:
    """Load a scenario, compose its criticality constraints, solve, and summarize."""
    if not isinstance(config, dict):
        config = yaml.safe_load(Path(config).read_text())
    case = str(config.get("case", "")).lower()
    out = Path(out_dir or config.get("out", "outputs/scenario"))
    objective = config.get("objective", "cost")

    if case == "gallium":
        from bleecam.cases.gallium.config_ga import CASE_CONFIG as _cc
        from bleecam.cases.gallium.gallium_pyomo import build_model as _bm, load_inputs, solve_model as _sm

        flow_scale = float(_cc.flow_scale)
        data = load_inputs(Path(config["data_dir"]), out, strict=True)
        _build = lambda: _bm(data, objective=objective)  # noqa: E731
        _solve = lambda m: _sm(m, solver)                # noqa: E731
    elif case in ("rare_earth", "ree"):
        from bleecam.cases.rare_earth.config import CASE_CONFIG as _cc
        from bleecam.cases.rare_earth.REE import build_model as _bm, load_inputs, solve_model as _sm

        flow_scale = float(_cc.flow_scale)
        data = load_inputs(Path(config["data_dir"]))
        _build = lambda: _bm(data, objective=objective)  # noqa: E731
        _solve = lambda m: _sm(m, solver)                # noqa: E731
    else:
        # Generic config-driven case: any material described purely by a case YAML
        # + data (no per-case Python), built by the generic core model builder.
        from bleecam.core import network
        from bleecam.core.case_config import load_case_config
        from bleecam.core.data_loader import load_case_data

        case_cfg_path = _resolve_case_config(case, config)
        case_cfg = load_case_config(case_cfg_path)
        # Data dir: the scenario's `data_dir` if given, else the case file's own
        # `data.dir` resolved relative to the case file (self-contained case folder).
        data_dir = config.get("data_dir")
        if data_dir is None:
            data_dir = Path(case_cfg_path).parent / case_cfg.data_dir
        flow_scale = float(case_cfg.flow_scale)
        data = load_case_data(case_cfg, data_dir)
        _build = lambda: network.build_model(case_cfg, data, objective=objective)  # noqa: E731
        _solve = lambda m: network.solve_model(m, case_cfg, solver)                # noqa: E731

    # Shared, case-agnostic path: build the model, compose the criticality
    # constraints from the library by id, solve, and summarize.
    model = _build()
    applied: list[str] = []
    for entry in config.get("constraints", []) or []:
        constraint = get(entry["id"])
        params = constraint.validate(entry.get("params", {}) or {})
        constraint.apply(model, data, **params)
        applied.append(entry["id"])
    result = _solve(model)
    # Models optimize in scaled-flow units (flows divided by the case's flow_scale),
    # so the raw objective is scaled. Report the real (un-scaled) objective too, so
    # the number is directly readable — real USD under the cost objective, real
    # physical units (kg CO2e, SLCA units) otherwise. Gallium uses flow_scale = 1
    # (already real); rare-earth uses 1000.
    ov = result["objective_value"]
    real = None if ov is None else float(ov) * flow_scale
    summary = {
        "case": case,
        "objective": objective,
        "constraints_applied": applied,
        "termination": result["termination_condition"],
        "objective_value": ov,
        "flow_scale": flow_scale,
        ("objective_real_usd" if objective == "cost" else "objective_real"): real,
        "demand_met": len(result["demand_slack"] or []) == 0,
        "model": model,
    }
    # Economic levers (e.g. price_support) discount the minimized objective by a
    # subsidy; surface the subsidy outlay and the true (unsubsidized) cost so the
    # buyer cost is never conflated with the resource cost.
    subsidy_expr = getattr(model, "_bleecam_subsidy_expr", None)
    if subsidy_expr is not None:
        from pyomo.environ import value

        sub = float(value(subsidy_expr))
        ov = summary["objective_value"]
        summary["subsidy_usd"] = sub
        summary["resource_cost_usd"] = None if ov is None else float(ov) + sub
    return summary


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="bleecam-run", description="Run a BLEECAM scenario from a YAML file (no code)."
    )
    parser.add_argument("scenario", help="path to a scenario YAML file")
    parser.add_argument("--solver", default="auto")
    args = parser.parse_args()
    summary = run_scenario(args.scenario, solver=args.solver)
    summary.pop("model", None)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
