# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Canonical loaded-data contract shared across BLEECAM cases.

This module documents — as code — the structure that a case data loader is
expected to produce and that the shared optimization/objective/report layers
consume. It is the target schema for the LiAISON -> BLEECAM importer (WS3) and
for the eventual generic core model.

The two existing loaders emit conceptually the same objects with different key
names (REE ``load_all_data`` and Gallium ``load_gallium_data``); this contract
is the convergence point. It is intentionally dependency-light (TypedDicts, no
runtime enforcement) so it can be adopted incrementally without behavior change.

Key conventions
---------------
* ``time_periods``  : ordered integer periods, ``0..N`` (relative, not calendar).
* Index tuples use ``(period, process, location, material)`` for node-level
  parameters and a 6-tuple ``(process_from, loc_from, process_to, loc_to,
  material, period)`` style for arc-level parameters (see ``FlowArc``).
* All per-unit factor maps (cost, emission, social) share the node-level key so
  a single objective builder can sum ``factor[key] * flow`` across categories.
"""
from __future__ import annotations

from typing import TypedDict

# ── Index alias documentation ────────────────────────────────────────────────
# Node-level key: (time_period, process, location, material)
NodeKey = tuple[int, str, str, str]
# Arc/topology key: (process_from, loc_from, process_to, loc_to, material)
ArcKey = tuple[str, str, str, str, str]
# Demand terminal key: (time_period, location, material)
DemandKey = tuple[int, str, str]


class FactorMaps(TypedDict, total=False):
    """Per-unit impact factors keyed by :data:`NodeKey`.

    Each entry maps a node key to a per-kg factor. An objective for any category
    is ``sum(factor[key] * flow[key])``. Categories are optional so a case can
    supply only what it has (Gallium ships environmental EF + social SLCA;
    a cost-only baseline supplies only ``cost``).
    """

    cost: dict[NodeKey, float]              # $/kg (processing/transport composite)
    gwp: dict[NodeKey, float]               # kg CO2-eq/kg (from LiAISON LCIA)
    slca: dict[str, dict[NodeKey, float]]   # social category -> factor map


class LoadedData(TypedDict, total=False):
    """The canonical bundle a case loader returns.

    Optional keys let a case populate incrementally; the shared layers should
    treat missing categories as "not available" rather than error.
    """

    # Index sets
    time_periods: list[int]
    processes: list[str]
    locations: list[str]
    materials: list[str]
    flow_arcs: list[ArcKey]

    # Demand (terminal requirement to satisfy)
    demand: dict[DemandKey, float]

    # Per-unit factor maps (see FactorMaps)
    factors: FactorMaps

    # Capacity / yield / trade structure
    max_output_capacity: dict[NodeKey, float]
    yield_factor: dict[NodeKey, float]
    allowed_arcs: set[ArcKey]

    # Provenance / validation
    validation_summary: dict
    lci_source: str  # e.g. "LiAISON" — set by the LCA importer (WS3)


__all__ = ["LoadedData", "FactorMaps", "NodeKey", "ArcKey", "DemandKey"]
