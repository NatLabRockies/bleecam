# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""LiAISON -> BLEECAM life-cycle impact importer (WS3).

Formalizes the previously hand-run EF-template generation into versioned,
testable code. It reads a LiAISON LCIA *node summary* (long/tidy output of the
LiAISON Brightway2 model) and produces BLEECAM's wide EF table keyed by
``(time_period, source, location, material)`` — the schema both the REE and
Gallium cases already share.

This makes the environmental side of BLEECAM *reproducible from a documented
LiAISON artifact*, which is the basis for treating BLEECAM as an LCA tool rather
than a model fed by hand-assembled CSVs.

Input (LiAISON LCIA node summary) columns
-----------------------------------------
``scope, process, process_location, flow, lcia_method, lcia_category, value,
unit, database, raw_file`` — one row per (scope, node, method, category).

Output (BLEECAM EF table) columns
---------------------------------
``time_period, source, location, material``  (key; source=process, material=flow)
+ ``EF_weighted__Global Warming Potential (Gwp1000)``  (active optimizer alias)
+ one ``EF_{RECIPE|TRACI}__{category}`` column per LCIA indicator.

Provenance is returned alongside the table (LCIA scope, methods, databases,
source files) so every EF value is traceable to its LiAISON origin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

# LiAISON lcia_method label -> BLEECAM EF column-prefix token.
METHOD_PREFIX: dict[str, str] = {
    "RECIPE": "RECIPE",
    "TRACI2.1": "TRACI",
}

# Active GWP alias wiring: the optimizer reads EF_weighted__GWP1000, populated
# from ReCiPe GWP1000 when available (documented fallback: TRACI GWP100).
RECIPE_GWP_CATEGORY = "Global Warming Potential (Gwp1000)"
TRACI_GWP_CATEGORY = "Global Warming Potential (Gwp100)"
WEIGHTED_GWP_COL = "EF_weighted__Global Warming Potential (Gwp1000)"

KEY_COLS = ["time_period", "source", "location", "material"]

DEFAULT_SCOPE = "total_life_cycle"


@dataclass
class EFImportResult:
    """EF table plus provenance for traceability back to the LiAISON run."""

    ef_table: pd.DataFrame
    provenance: dict[str, Any] = field(default_factory=dict)


def load_impact_factor_maps(
    ef_table: pd.DataFrame | str | Path,
    prefixes: tuple[str, ...] = ("EF_",),
) -> dict[str, dict[tuple[int, str, str, str], float]]:
    """Read a conforming impact table and return one factor map per impact column.

    This is the *consumer* side of the impact-factor contract: it does not care
    whether the table came from the LiAISON adapter, an openLCA export, or a
    hand-built file — only that it has the key columns (``time_period, source,
    location, material``) and one or more impact columns. ``prefixes`` selects
    which columns are impacts (``EF_`` for environmental, ``SLCA`` for social).
    Each returned map is keyed by the source node
    ``(time_period, process, location, material)`` for use by
    :mod:`bleecam.core.objectives`.
    """
    if not isinstance(ef_table, pd.DataFrame):
        ef_table = pd.read_csv(ef_table)

    missing = [c for c in KEY_COLS if c not in ef_table.columns]
    if missing:
        raise ValueError(f"Impact table is missing required key columns: {missing}")

    impact_cols = [c for c in ef_table.columns if c.startswith(prefixes)]
    maps: dict[str, dict[tuple[int, str, str, str], float]] = {}
    for col in impact_cols:
        sub = ef_table[KEY_COLS + [col]].dropna(subset=[col])
        maps[col] = {
            (int(t), str(s), str(loc), str(mat)): float(v)
            for t, s, loc, mat, v in sub.itertuples(index=False, name=None)
        }
    return maps


def _ef_column(method: str, category: str) -> str:
    prefix = METHOD_PREFIX.get(method, method)
    return f"EF_{prefix}__{category}"


def build_ef_table(
    node_summary: pd.DataFrame | str | Path,
    time_periods: list[int],
    *,
    scope: str = DEFAULT_SCOPE,
) -> EFImportResult:
    """Build the wide BLEECAM EF table from a LiAISON LCIA node summary.

    :param node_summary: LiAISON node-summary DataFrame or path to its CSV.
    :param time_periods: periods to replicate the static node factors across.
    :param scope: LCIA scope to use (default ``total_life_cycle``).
    :returns: :class:`EFImportResult` with the EF table and provenance.
    """
    if not isinstance(node_summary, pd.DataFrame):
        node_summary = pd.read_csv(node_summary)

    df = node_summary[node_summary["scope"] == scope].copy()
    if df.empty:
        raise ValueError(f"No rows for scope={scope!r} in the LiAISON node summary.")

    df["_col"] = [
        _ef_column(m, c) for m, c in zip(df["lcia_method"], df["lcia_category"])
    ]

    # The LiAISON output can repeat a (node, method, category) triple with
    # identical values (e.g. ReCiPe Agricultural Land Occupation). Collapse
    # duplicates, asserting the collapsed values agree so we never silently
    # average conflicting factors.
    node_cols = ["process", "process_location", "flow"]
    dup = df.groupby(node_cols + ["_col"])["value"].nunique()
    conflicts = dup[dup > 1]
    if len(conflicts):
        raise ValueError(
            f"Conflicting LCIA values for {len(conflicts)} (node, indicator) pairs; "
            "cannot collapse safely. First few:\n" + str(conflicts.head())
        )
    df = df.drop_duplicates(node_cols + ["_col"], keep="first")

    wide = (
        df.pivot(index=node_cols, columns="_col", values="value")
        .reset_index()
        .rename(columns={"process": "source", "process_location": "location", "flow": "material"})
    )
    wide.columns.name = None

    # Active GWP alias.
    recipe_gwp = _ef_column("RECIPE", RECIPE_GWP_CATEGORY)
    traci_gwp = _ef_column("TRACI2.1", TRACI_GWP_CATEGORY)
    if recipe_gwp in wide.columns:
        wide[WEIGHTED_GWP_COL] = wide[recipe_gwp]
        gwp_alias_source = recipe_gwp
    elif traci_gwp in wide.columns:
        wide[WEIGHTED_GWP_COL] = wide[traci_gwp]
        gwp_alias_source = traci_gwp
    else:
        raise ValueError("Neither ReCiPe GWP1000 nor TRACI GWP100 present for the GWP alias.")

    # Replicate static node factors across the requested time periods.
    frames = []
    for t in time_periods:
        f = wide.copy()
        f.insert(0, "time_period", t)
        frames.append(f)
    ef = pd.concat(frames, ignore_index=True)

    # Deterministic column order: key, active alias, then indicators sorted.
    indicator_cols = sorted(c for c in wide.columns
                            if c.startswith("EF_") and c != WEIGHTED_GWP_COL)
    ordered = ["time_period", "source", "location", "material", WEIGHTED_GWP_COL] + indicator_cols
    ef = ef[ordered].sort_values(KEY_COLS).reset_index(drop=True)

    provenance = {
        "lcia_scope": scope,
        "lcia_methods": sorted(node_summary["lcia_method"].unique().tolist()),
        "databases": sorted(node_summary["database"].dropna().unique().tolist())
        if "database" in node_summary else [],
        "gwp_alias_source": gwp_alias_source,
        "n_nodes": int(len(wide)),
        "n_indicator_columns": len(indicator_cols),
        "time_periods": list(time_periods),
        "lci_source": "LiAISON",
    }
    return EFImportResult(ef_table=ef, provenance=provenance)
