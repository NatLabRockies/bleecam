# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The generic config-driven loader reproduces the case's own loader contract.

Proves core/data_loader.load_case_data (driven by the case YAML) parses the
standard CSV schema into the same loaded_data maps the bespoke Gallium loader
produces — so a new material needs no per-case loader, just data + a case YAML.
Period-dependent maps differ only where Gallium's loader synthesises a period-5
row, so we compare the period-independent structure and shared-period values.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pandas")

from bleecam.core.case_config import load_case_config
from bleecam.core.data_loader import load_case_data

ROOT = Path(__file__).resolve().parents[1]
GA = ROOT / "src" / "bleecam" / "cases" / "gallium"
DATA = GA / "data" / "gallium"


def _gallium_reference(tmp_path):
    from bleecam.cases.gallium.gallium_data_loader import load_gallium_data
    return load_gallium_data(DATA, report_md_path=tmp_path / "r.md",
                             report_csv_path=tmp_path / "r.csv", strict=True)


def test_generic_loader_matches_gallium_contract(tmp_path):
    cfg = load_case_config(GA / "gallium.case.yaml")
    c = load_case_data(cfg, DATA)
    g = _gallium_reference(tmp_path)

    # topology-derived, period-independent — must match exactly
    assert c["allowed_trade_arcs"] == g["allowed_trade_arcs"]
    assert c["processes"] == g["processes"]
    assert c["locations"] == g["locations"]
    assert c["materials"] == g["materials"]

    # same capacity / yield nodes (ignore the period dimension where Gallium extends p5)
    assert set(c["max_output_capacity"]) == set(g["max_output_capacity"])
    assert {k[1:] for k in c["yield_factor"]} == {k[1:] for k in g["yield_factor"]}

    # shared-period values agree (spot-check period 0 across the maps)
    k_cap = next(iter(g["max_output_capacity"]))
    assert c["max_output_capacity"][k_cap][0] == g["max_output_capacity"][k_cap][0]
    p0_yield = [k for k in g["yield_factor"] if k[0] == 0][0]
    assert c["yield_factor"][p0_yield] == g["yield_factor"][p0_yield]
    p0_ship = [k for k in g["shipping_cost"] if k[0] == 0][0]
    assert c["shipping_cost"][p0_ship] == g["shipping_cost"][p0_ship]

    # environmental factors attached via the engine-agnostic contract
    assert len(c["impact_factors"]) > 0


def test_generic_loader_reports_missing_columns(tmp_path):
    cfg = load_case_config(GA / "gallium.case.yaml")
    bad = tmp_path / "data"
    bad.mkdir()
    (bad / cfg.data_files["trade_topology"]).write_text("process_from,loc_from\nx,US\n")
    for key in ("demand", "capacity", "cost", "yield", "shipping"):
        (bad / cfg.data_files[key]).write_text("time_period\n0\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_case_data(cfg, bad)
