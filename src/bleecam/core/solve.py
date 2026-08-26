# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared Pyomo solver selection for BLEECAM cases.

Extracted from the Gallium case so every case can use the same auto-selection
logic (and so REE can drop its hard-coded ipopt dependency). A case may pass its
own ``candidates`` tuple; the default order prefers ipopt, then HiGHS, then the
open-source LP solvers.
"""
from __future__ import annotations

from typing import Any

# Importing pyomo.environ registers the solver plugins; without it,
# SolverFactory(...).available() raises "solver plugin was not registered"
# when this module is used before any other code imports pyomo.environ.
import pyomo.environ  # noqa: F401
from pyomo.environ import SolverFactory

# Default probe order. ipopt (NLP-capable) first for continuous models, then
# HiGHS and the classic open-source LP/MILP solvers as fallbacks.
DEFAULT_SOLVER_CANDIDATES: tuple[str, ...] = (
    "ipopt",
    "appsi_ipopt",
    "appsi_highs",
    "highs",
    "glpk",
    "cbc",
)


class SolverUnavailableError(RuntimeError):
    """Raised when none of the candidate Pyomo solvers is available."""


def available_solver(name: str):
    """Return an instantiated solver if ``name`` is available, else ``None``."""
    solver = SolverFactory(name)
    try:
        if solver.available(False):
            return solver
    except Exception:
        return None
    return None


def choose_solver(
    requested: str = "auto",
    candidates: tuple[str, ...] = DEFAULT_SOLVER_CANDIDATES,
) -> tuple[str, Any]:
    """Return ``(name, solver)`` for the first available candidate.

    When ``requested`` is ``"auto"`` the ``candidates`` list is probed in order;
    otherwise only the explicitly requested solver is tried.
    """
    probe = tuple(candidates) if requested == "auto" else (requested,)
    for candidate in probe:
        solver = available_solver(candidate)
        if solver is not None:
            return candidate, solver
    raise SolverUnavailableError(
        "No available Pyomo solver found. Tried: " + ", ".join(probe)
    )
