# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""BLEECAM criticality constraint library (registry + constraints)."""
from .registry import (
    CriticalityConstraint,
    Param,
    all_constraints,
    describe,
    get,
    register,
)
from . import library  # noqa: F401  — importing populates the registry

__all__ = [
    "CriticalityConstraint",
    "Param",
    "all_constraints",
    "describe",
    "get",
    "register",
]
