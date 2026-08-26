# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reproducibility test for the LiAISON -> BLEECAM EF importer (WS3).

Asserts that ``core.lca_import.build_ef_table`` regenerates the committed
Gallium EF template exactly from the LiAISON LCIA node summary. This is the
guarantee that BLEECAM's environmental factors are reproducible from a
documented LiAISON artifact rather than hand-assembled — the crux of the
LCA-tool claim.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

GA = Path(__file__).resolve().parents[1] / "src" / "bleecam" / "cases" / "gallium" / "data" / "gallium"
NODE_SUMMARY = GA / "lcia" / "gallium_lcia_node_summary.csv"
COMMITTED_EF = GA / "EF_Template_Ga_from_LiAISON.csv"

KEY = ["time_period", "source", "location", "material"]


def test_importer_reproduces_committed_ef_template():
    from bleecam.core.lca_import import build_ef_table, WEIGHTED_GWP_COL

    result = build_ef_table(NODE_SUMMARY, time_periods=[0, 1, 2, 3, 4])
    gen = result.ef_table
    com = pd.read_csv(COMMITTED_EF)

    # Same rows (node x period) and same key set.
    assert len(gen) == len(com) == 260
    g = gen.set_index(KEY).sort_index()
    c = com.set_index(KEY).sort_index()
    assert g.index.equals(c.index)

    # Every shared EF_* factor column must match to the last bit.
    shared = [col for col in gen.columns if col.startswith("EF_") and col in com.columns]
    assert WEIGHTED_GWP_COL in shared
    assert len(shared) >= 26
    max_abs = (g[shared].astype(float) - c[shared].astype(float)).abs().max().max()
    assert max_abs == 0.0, f"EF values drifted from committed template (max abs diff {max_abs:.3e})"


def test_importer_provenance_is_populated():
    from bleecam.core.lca_import import build_ef_table

    prov = build_ef_table(NODE_SUMMARY, time_periods=[0, 1, 2, 3, 4]).provenance
    assert prov["lci_source"] == "LiAISON"
    assert prov["lcia_scope"] == "total_life_cycle"
    assert prov["gwp_alias_source"].startswith("EF_RECIPE__Global Warming")
    assert prov["n_nodes"] == 52
