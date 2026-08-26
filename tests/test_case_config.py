# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The declarative case YAMLs are the single source of truth for case declarations.

Guards two things: (1) the case YAMLs hold the right literal values, and (2) the
case config modules now SOURCE their declarations from the YAML (Phase 2), so the
running models are driven by the declarative config. The golden regression tests
(gallium / REE) are the end-to-end proof that these values reproduce the models.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("yaml")

from bleecam.core.case_config import load_case_config

CASES = Path(__file__).resolve().parents[1] / "src" / "bleecam" / "cases"


def test_gallium_case_yaml_drives_config_ga():
    from bleecam.cases.gallium import config_ga as ga
    c = load_case_config(CASES / "gallium" / "gallium.case.yaml")
    # (1) literal guard on the YAML content
    assert c.time_periods == (0, 1, 2, 3, 4, 5)
    assert c.demand_location == "US"
    assert c.demand_materials == ("GaAs_wafer", "GaN_wafer")
    assert c.demand_source_process == "wafer_market_mix"
    assert c.demand_sink_process == "wafer_demand"
    assert c.demand_slack_penalty == 1.0e9
    assert c.flow_tolerance == 1e-7
    assert c.baseline_scenario == "baseline_Ga"
    assert c.results_csv == "gallium_model_results.csv"
    assert c.demand_arcs == (
        ("wafer_market_mix", "US", "wafer_demand", "US", "GaAs_wafer"),
        ("wafer_market_mix", "US", "wafer_demand", "US", "GaN_wafer"),
    )
    assert c.capacity_exempt_processes == frozenset({"wafer_market_mix", "wafer_demand"})
    assert c.processes is None and c.materials is None and c.locations is None  # derived from data
    # (2) config_ga now SOURCES its declarations from the YAML
    assert ga.CASE_CONFIG.case == "gallium"
    assert ga.TIME_PERIODS == c.time_periods
    assert ga.DEMAND_MATERIALS == c.demand_materials
    assert ga.DEMAND_ARCS == c.demand_arcs
    assert ga.CAPACITY_EXEMPT_PROCESSES == c.capacity_exempt_processes
    assert ga.DEMAND_SLACK_PENALTY_USD_PER_KG == c.demand_slack_penalty


def test_rare_earth_case_yaml_drives_config():
    from bleecam.cases.rare_earth import config as ree
    c = load_case_config(CASES / "rare_earth" / "rare_earth.case.yaml")
    # (1) literal guard on the YAML content
    assert c.time_periods == (0, 1, 2, 3, 4)
    assert c.flow_scale == 1000.0
    assert c.demand_location == "US"
    assert "magnet manufacturing" in c.processes and "hp_magnet" in c.materials
    assert c.params["alloy"] == "neodynium dysprosium iron alloy"
    # (2) config.py now SOURCES its declarations from the YAML
    assert ree.list_of_processes == list(c.processes)
    assert ree.materials == list(c.materials)
    assert ree.locations == list(c.locations)
    assert ree.ACTIVE_PROCESS_LOCATIONS == {k: list(v) for k, v in c.active_process_locations.items()}
    assert ree.num_time_periods == 5 and ree.time_stamp == [0, 1, 2, 3, 4]
    assert ree.FLOW_SCALE == 1000.0
    assert ree.PENALTY_UNUSED_OXIDE_COST == 80
    assert ree.PENALTY_UNUSED_OXIDE_GWP == 15
    assert ree.PENALTY_UNUSED_OXIDE_SLCA == 0.001
    assert ree.DEFAULT_MAX_STOCK_CAPACITY == 4000000.0 / 1000.0
    assert ree.DEFAULT_STOCK_HOLDING_COST == 0.1
    assert ree.ALLOY == "neodynium dysprosium iron alloy"


def test_template_loads_and_validates():
    # The template is generic (placeholders), so assert structure/validation, not text.
    c = load_case_config(Path(__file__).resolve().parents[1] / "templates" / "case_template.yaml")
    assert c.case and c.demand_location and c.demand_materials
    assert c.time_periods == (0, 1, 2, 3, 4, 5)
    assert set(c.data_files) >= {"cost", "shipping", "demand", "capacity", "yield",
                                 "trade_topology", "emission_factors", "social_lca"}
    assert len(c.capacity_exempt_processes) == 2
