# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generic, factor-map-driven objectives shared across BLEECAM cases.

Any objective — cost, GWP, human toxicity, a social indicator — is the same
shape: ``sum(factor[node] * flow[arc])`` over the network, plus a large penalty
on unmet demand so the optimizer meets demand rather than dropping it. The only
thing that changes between objectives is *which per-unit factor map* is used.

This lets a case optimize on any impact category the EF table provides (GWP is
the default for cross-case comparability, but all ~25 ReCiPe/TRACI categories
are selectable) using one code path, and gives the multi-objective (Pareto)
work a single primitive to build on.
"""
from __future__ import annotations

from typing import Any

# Per-unit factors are keyed by the *source node* that produces the material:
# (time_period, process, location, material).
NodeKey = tuple[int, str, str, str]


def linear_flow_expression(model: Any, factor_map: dict[NodeKey, float]):
    """Return ``sum(factor[source_node] * flowQ[arc])`` over all flow arcs.

    Assumes ``model.flowQ`` is indexed by 6-tuple arcs
    ``(t, process_from, loc_from, process_to, loc_to, material)`` and that the
    factor is attributed to the arc's *source* node (process_from, loc_from) —
    identical to how per-unit processing cost is applied, so environmental and
    social burdens accrue where a material is produced.
    """
    total = 0.0
    for key in model.flowQ:
        t, process_from, loc_from, _process_to, _loc_to, material = key
        factor = factor_map.get((int(t), str(process_from), str(loc_from), str(material)), 0.0)
        if factor:
            total += factor * model.flowQ[key]
    return total


def demand_slack_penalty_expression(model: Any, penalty: float):
    """Return ``penalty * sum(demand_slack)`` — keeps demand met under any objective."""
    return penalty * sum(model.demand_slack[key] for key in model.DemandKeys)


def impact_objective_rule(factor_map: dict[NodeKey, float], slack_penalty: float):
    """Build a Pyomo objective rule minimizing a factor-weighted flow total.

    :param factor_map: per-unit factors keyed by source node.
    :param slack_penalty: penalty per kg of unmet demand, in this objective's
        own units (large enough to force demand satisfaction).
    """

    def _rule(m):
        return linear_flow_expression(m, factor_map) + demand_slack_penalty_expression(m, slack_penalty)

    return _rule
