# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Declarative, case-agnostic configuration for BLEECAM material cases.

A case's *declarations* — time horizon, the demand definition, penalties, the
solver list, and the names of the data files — live in a YAML case file instead
of a hand-written Python module. This is the first step toward a no-code path
for adding a new material: a researcher fills a ``<case>.case.yaml`` (and the
data CSVs) rather than editing Python.

Load one with :func:`load_case_config`; the generic cost logic that used to live
in each case's config module now lives in :mod:`bleecam.core.case_cost`.

The schema has a common core (all cases) plus an open ``params:`` map for
case-specific constants used by bespoke physics (e.g. the rare-earth unused-oxide
penalties and stock defaults). Explicit ``processes`` / ``materials`` /
``locations`` are optional — omit them to derive the sets from the data (as the
Gallium case does); list them when the case needs them fixed (as REE does).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SOLVER_CANDIDATES = ("ipopt", "appsi_ipopt", "appsi_highs", "highs", "glpk", "cbc")


@dataclass
class CaseConfig:
    """A material case's declarative configuration (parsed from a case YAML)."""

    case: str
    time_periods: tuple[int, ...]
    demand_location: str
    demand_materials: tuple[str, ...]
    demand_source_process: str
    demand_sink_process: str
    data_dir: str
    description: str = ""
    units: str = "kg"
    flow_scale: float = 1.0
    demand_flow: str = ""
    demand_slack_penalty: float = 1.0e9
    solver_candidates: tuple[str, ...] = DEFAULT_SOLVER_CANDIDATES
    flow_tolerance: float = 1e-7
    results_csv: str = "model_results.csv"
    baseline_scenario: str = ""
    processes: tuple[str, ...] | None = None
    materials: tuple[str, ...] | None = None
    locations: tuple[str, ...] | None = None
    active_process_locations: dict[str, tuple[str, ...]] | None = None
    data_files: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def demand_arcs(self) -> tuple[tuple[str, str, str, str, str], ...]:
        """(source_process, location, sink_process, location, material) for each demand material."""
        return tuple(
            (self.demand_source_process, self.demand_location,
             self.demand_sink_process, self.demand_location, m)
            for m in self.demand_materials
        )

    @property
    def capacity_exempt_processes(self) -> frozenset[str]:
        """Processes not subject to capacity limits (the demand source/sink nodes)."""
        return frozenset({self.demand_source_process, self.demand_sink_process})

    def data_path(self, key: str, *, base: Path | None = None) -> Path:
        """Resolve a named data file (e.g. 'cost') under the case data dir."""
        if key not in self.data_files:
            raise KeyError(f"case {self.case!r}: no data file named {key!r}; "
                           f"declared: {sorted(self.data_files)}")
        root = (base or Path()) / self.data_dir
        return root / self.data_files[key]


def _require(d: dict, key: str, ctx: str) -> Any:
    if key not in d or d[key] is None:
        raise ValueError(f"case config: missing required '{key}' in {ctx}")
    return d[key]


def _as_periods(v: Any) -> tuple[int, ...]:
    if isinstance(v, int):
        return tuple(range(v))
    if isinstance(v, (list, tuple)):
        return tuple(int(x) for x in v)
    raise ValueError(f"case config: 'time_periods' must be an int or a list, got {type(v).__name__}")


def load_case_config(path: str | Path) -> CaseConfig:
    """Parse a ``<case>.case.yaml`` into a :class:`CaseConfig` (with validation)."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    demand = _require(raw, "demand", "top level")
    data = _require(raw, "data", "top level")
    files = data.get("files", {}) or {}

    def _tuple(v):
        return tuple(v) if v is not None else None

    return CaseConfig(
        case=str(_require(raw, "case", "top level")),
        description=str(raw.get("description", "")),
        units=str(raw.get("units", "kg")),
        time_periods=_as_periods(_require(raw, "time_periods", "top level")),
        flow_scale=float(raw.get("flow_scale", 1.0)),
        demand_location=str(_require(demand, "location", "demand")),
        demand_materials=tuple(_require(demand, "materials", "demand")),
        demand_source_process=str(_require(demand, "source_process", "demand")),
        demand_sink_process=str(_require(demand, "sink_process", "demand")),
        demand_flow=str(demand.get("flow", "")),
        demand_slack_penalty=float(demand.get("slack_penalty", 1.0e9)),
        solver_candidates=tuple(raw.get("solver", {}).get("candidates", DEFAULT_SOLVER_CANDIDATES)),
        flow_tolerance=float(raw.get("solver", {}).get("flow_tolerance", 1e-7)),
        data_dir=str(_require(data, "dir", "data")),
        results_csv=str(data.get("results_csv", "model_results.csv")),
        baseline_scenario=str(raw.get("baseline_scenario", "")),
        processes=_tuple(raw.get("processes")),
        materials=_tuple(raw.get("materials")),
        locations=_tuple(raw.get("locations")),
        active_process_locations=(
            {k: tuple(v) for k, v in raw["active_process_locations"].items()}
            if raw.get("active_process_locations") else None
        ),
        data_files={k: str(v) for k, v in files.items()},
        params=dict(raw.get("params", {}) or {}),
    )
