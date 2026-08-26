# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rare-earth case declarations — now sourced from rare_earth.case.yaml.

Edit the case YAML, not these names. This module re-exports the same symbols the
REE code has always imported, so nothing downstream changes; the values now flow
from the declarative config (single source of truth).
"""
from pathlib import Path

from bleecam.core.case_config import load_case_config

CASE_CONFIG = load_case_config(Path(__file__).parent / "rare_earth.case.yaml")

list_of_processes = list(CASE_CONFIG.processes)
locations = list(CASE_CONFIG.locations)
materials = list(CASE_CONFIG.materials)
ACTIVE_PROCESS_LOCATIONS = {k: list(v) for k, v in CASE_CONFIG.active_process_locations.items()}
DEMAND_LOCATION = CASE_CONFIG.demand_location
ALLOY = CASE_CONFIG.params["alloy"]
num_time_periods = len(CASE_CONFIG.time_periods)
time_stamp = list(CASE_CONFIG.time_periods)
PENALTY_UNUSED_OXIDE_COST = CASE_CONFIG.params["penalty_unused_oxide_cost"]
PENALTY_UNUSED_OXIDE_GWP = CASE_CONFIG.params["penalty_unused_oxide_gwp"]
PENALTY_UNUSED_OXIDE_SLCA = CASE_CONFIG.params["penalty_unused_oxide_slca"]
FLOW_SCALE = CASE_CONFIG.flow_scale
DEFAULT_MAX_STOCK_CAPACITY = CASE_CONFIG.params["default_max_stock_capacity_kg"] / FLOW_SCALE
DEFAULT_STOCK_HOLDING_COST = CASE_CONFIG.params["default_stock_holding_cost"]
