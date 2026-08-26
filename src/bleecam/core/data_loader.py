# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generic, config-driven data loader for standard flow-network cases.

Reads the CSVs named in a case's :class:`~bleecam.core.case_config.CaseConfig`
(``data.files``) into the standard ``loaded_data`` contract that the model
builder consumes — the same maps a case's bespoke loader produces, minus any
material-specific business rules. This is what lets a NEW material (e.g. copper)
be loaded with no per-case loader: fill the case YAML + drop in the CSVs.

Standard CSV schema (same columns the Gallium package uses):
  trade_topology : process_from, loc_from, process_to, loc_to, material
  demand         : time_period, location, material, demand_kg   (+ optional scenario, flow)
  capacity       : time_period, process, location, material, capacity
  cost           : time_period, source, location, material, destination,
                   destination_location, processing cost, transportation cost, tariff_cost
  yield          : time_period, process, location, material, yield
  shipping       : time_period, loc_from, loc_to, shipping_cost_usd_per_kg
Environmental (EF_*) and social (SLCA*) factor tables are attached via the
engine-agnostic contract in :mod:`bleecam.core.lca_import`.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from .lca_import import load_impact_factor_maps

if TYPE_CHECKING:
    from .case_config import CaseConfig

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "trade_topology": ["process_from", "loc_from", "process_to", "loc_to", "material"],
    "demand": ["time_period", "location", "material", "demand_kg"],
    "capacity": ["time_period", "process", "location", "material", "capacity"],
    "cost": ["time_period", "source", "location", "material", "destination",
             "destination_location", "processing cost", "transportation cost", "tariff_cost"],
    "yield": ["time_period", "process", "location", "material", "yield"],
    "shipping": ["time_period", "loc_from", "loc_to", "shipping_cost_usd_per_kg"],
}
_CORE_FILES = ("trade_topology", "demand", "capacity", "cost", "yield", "shipping")


def _clean(value: Any) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _read(path: Path, cols: list[str], key: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"case data: '{key}' file not found: {path}")
    df = pd.read_csv(path, keep_default_na=False)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(_clean)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"case data '{key}' ({path.name}) is missing required column(s): {missing}")
    return df


def _tuple_set(df: pd.DataFrame, cols: list[str]) -> set[tuple[Any, ...]]:
    return set(map(tuple, df[cols].drop_duplicates().values.tolist()))


def _extend_to_horizon(df: pd.DataFrame, horizon: list[int]) -> pd.DataFrame:
    """Carry the last provided period forward to cover the declared horizon.

    If a file supplies periods 0..k but the case declares 0..N, the period-k rows
    are copied to k+1..N (parameters held constant). Files already covering the
    horizon are returned unchanged.
    """
    if "time_period" not in df.columns:  # e.g. trade_topology is period-independent
        return df
    periods = pd.to_numeric(df["time_period"], errors="coerce").dropna().astype(int)
    if periods.empty:
        return df
    last = int(periods.max())
    missing = [p for p in horizon if p > last]
    if not missing:
        return df
    tail = df[pd.to_numeric(df["time_period"], errors="coerce").astype("Int64") == last]
    extra = []
    for p in missing:
        rows = tail.copy()
        rows["time_period"] = p
        extra.append(rows)
    return pd.concat([df, *extra], ignore_index=True)


def load_case_data(config: "CaseConfig", data_dir: str | Path) -> dict[str, Any]:
    """Load a case's CSVs into the standard ``loaded_data`` contract (no bespoke rules)."""
    base = Path(data_dir)
    horizon = list(config.time_periods)
    frames: dict[str, pd.DataFrame] = {}
    for key in _CORE_FILES:
        fname = config.data_files.get(key)
        if not fname:
            raise KeyError(f"case config {config.case!r}: data.files must name '{key}'")
        frames[key] = _extend_to_horizon(_read(base / fname, REQUIRED_COLUMNS[key], key), horizon)

    topo = frames["trade_topology"]
    allowed_trade_arcs = _tuple_set(topo, REQUIRED_COLUMNS["trade_topology"])
    processes = sorted(set(topo["process_from"]) | set(topo["process_to"]))
    locations = sorted(set(topo["loc_from"]) | set(topo["loc_to"]))
    materials = sorted(set(topo["material"]))

    max_output_capacity: dict[tuple[str, str, str], dict[int, float]] = {}
    for r in frames["capacity"].itertuples(index=False):
        key = (_clean(r.process), _clean(r.location), _clean(r.material))
        max_output_capacity.setdefault(key, {})[int(r.time_period)] = float(r.capacity)

    yield_factor: dict[tuple[int, str, str, str], float] = {}
    for _, r in frames["yield"].iterrows():
        yield_factor[(int(r["time_period"]), _clean(r["process"]), _clean(r["location"]),
                      _clean(r["material"]))] = float(r["yield"])

    arc_processing_cost, arc_transportation_cost, tariff_cost = {}, {}, {}
    for _, r in frames["cost"].iterrows():
        key = (int(r["time_period"]), _clean(r["source"]), _clean(r["location"]),
               _clean(r["destination"]), _clean(r["destination_location"]), _clean(r["material"]))
        arc_processing_cost[key] = float(r["processing cost"])
        arc_transportation_cost[key] = float(r["transportation cost"])
        tar = float(r["tariff_cost"])
        if tar != 0.0:
            tariff_cost[key] = tar

    shipping_cost = {
        (int(r.time_period), _clean(r.loc_from), _clean(r.loc_to)): float(r.shipping_cost_usd_per_kg)
        for r in frames["shipping"].itertuples(index=False)
    }

    time_periods = list(horizon)

    loaded: dict[str, Any] = {
        "topology_df": topo,
        "demand_df": frames["demand"],
        "capacity_df": frames["capacity"],
        "cost_df": frames["cost"],
        "yield_df": frames["yield"],
        "shipping_df": frames["shipping"],
        "processes": processes,
        "locations": locations,
        "materials": materials,
        "time_periods": time_periods,
        "allowed_trade_arcs": allowed_trade_arcs,
        "max_output_capacity": max_output_capacity,
        "yield_factor": yield_factor,
        "arc_processing_cost": arc_processing_cost,
        "arc_transportation_cost": arc_transportation_cost,
        "tariff_cost": tariff_cost,
        "shipping_cost": shipping_cost,
    }

    # Environmental + social factors via the engine-agnostic LCIA contract.
    impact_factors: dict[str, dict] = {}
    provenance: dict[str, Any] = {}
    ef_name = config.data_files.get("emission_factors")
    if ef_name and (base / ef_name).exists():
        impact_factors.update(load_impact_factor_maps(base / ef_name, prefixes=("EF_",)))
        provenance["ef_file"] = str(base / ef_name)
    social_name = config.data_files.get("social_lca")
    if social_name and (base / social_name).exists():
        impact_factors.update(load_impact_factor_maps(base / social_name, prefixes=("SLCA",)))
        provenance["social_file"] = str(base / social_name)
    loaded["impact_factors"] = impact_factors
    provenance["n_impact_categories"] = len(impact_factors)
    loaded["ef_provenance"] = provenance
    return loaded
