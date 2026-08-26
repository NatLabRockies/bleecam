# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Registry for the BLEECAM criticality constraint library.

Each entry is a named, documented, parameterized constraint that a user can
*view* (``list`` / ``describe`` / generated catalog) and *apply* to a run via a
YAML scenario file — without writing Python. Constraints encode recurring
critical-mineral issues (by-product / co-product handling, economic allocation,
chemistry / yield, capacity / policy / circularity) and are composed by the
scenario runner.

The metadata carried here (scope, meaning, parameters, example) is the single
source of truth for the documentation catalog — the catalog is *generated* from
the registry so it stays in sync (see ``catalog.py``).

An ``apply`` function has the signature ``apply(model, loaded_data, **params)``
and adds Pyomo constraints to ``model.constraints`` (or fixes variables).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Param:
    """One parameter of a criticality constraint."""

    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""


@dataclass(frozen=True)
class CriticalityConstraint:
    """A registered, parameterized criticality constraint (and its documentation)."""

    id: str
    family: str
    summary: str            # one line (shown by `list`)
    scope: str              # the real-world issue it represents
    meaning: str            # what it does to the model
    params: tuple[Param, ...]
    apply: Callable[..., None]
    example: str = ""       # a YAML `params:` example
    notes: str = ""         # optional caveats / interpretation

    def validate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check required params are present and reject unknown ones; fill defaults."""
        known = {p.name for p in self.params}
        unknown = set(params) - known
        if unknown:
            raise ValueError(f"{self.id}: unknown parameter(s) {sorted(unknown)}; expected {sorted(known)}")
        resolved = dict(params)
        for p in self.params:
            if p.name not in resolved:
                if p.required:
                    raise ValueError(f"{self.id}: missing required parameter '{p.name}'")
                resolved[p.name] = p.default
        return resolved


REGISTRY: dict[str, CriticalityConstraint] = {}


def register(id: str, family: str, summary: str, scope: str, meaning: str,
             params: list[Param], example: str = "", notes: str = "") -> Callable:
    """Decorator: register an ``apply`` function as a documented criticality constraint."""

    def _deco(fn: Callable[..., None]) -> Callable[..., None]:
        if id in REGISTRY:
            raise ValueError(f"criticality constraint id '{id}' already registered")
        REGISTRY[id] = CriticalityConstraint(
            id=id, family=family, summary=summary, scope=scope, meaning=meaning,
            params=tuple(params), apply=fn, example=example, notes=notes,
        )
        return fn

    return _deco


def get(id: str) -> CriticalityConstraint:
    if id not in REGISTRY:
        raise KeyError(f"unknown criticality constraint '{id}'. Available: {sorted(REGISTRY)}")
    return REGISTRY[id]


def all_constraints() -> list[CriticalityConstraint]:
    return sorted(REGISTRY.values(), key=lambda c: (c.family, c.id))


def families() -> list[str]:
    return sorted({c.family for c in REGISTRY.values()})


def describe(id: str) -> str:
    c = get(id)
    lines = [f"{c.id}  [{c.family}]", f"  scope:   {c.scope}", f"  meaning: {c.meaning}", "  parameters:"]
    for p in c.params:
        req = "required" if p.required else f"optional (default {p.default!r})"
        lines.append(f"    - {p.name} ({p.type}, {req}): {p.description}")
    if c.example:
        lines.append(f"  example: {c.example}")
    if c.notes:
        lines.append(f"  note:    {c.notes}")
    return "\n".join(lines)
