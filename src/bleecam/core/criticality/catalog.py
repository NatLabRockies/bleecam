# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate the criticality-library documentation catalog from the registry.

The catalog is generated from the registered constraints' metadata so it never
drifts from the code. Regenerate with ``bleecam-lib docs --write
docs/criticality_library.md``; ``tests/test_criticality_scenario.py`` asserts the
committed file matches this output.
"""
from __future__ import annotations

from .registry import all_constraints, families

# Known families and their purpose (status is computed from the registry).
FAMILY_DESCRIPTIONS: list[tuple[str, str]] = [
    ("capacity_policy", "Capacity ramps / shutdowns and onshoring / domestic-content floors"),
    ("diversification", "Limits on single-source concentration and dependence"),
    ("byproduct", "Output bounded by host-metal throughput (e.g. Ga from bauxite / zinc)"),
    ("economic_policy", "Producer price support / subsidies to keep target producers competitive"),
    ("resilience", "Strategic reserves / stockpiles held against supply disruption"),
    ("coproduct", "Joint-production stoichiometry and unused-fraction handling (e.g. Nd / Dy oxides)"),
    ("economic_allocation", "Allocation of shared burdens across co- / by-products"),
    ("chemistry_yield", "Process-family stoichiometry / yield mass-balance templates"),
    ("circularity", "Recycling floors, EOL recovery targets"),
]

_HEADER = """# BLEECAM Criticality Constraint Library

*A material-agnostic library of named, parameterized constraints that encode
recurring critical-mineral supply-chain issues. Users select and configure them
in a YAML scenario file — no code — to run any scenario they need.*

> **This file is generated from the constraint registry** (the code is the source
> of truth). Regenerate with `bleecam-lib docs --write docs/criticality_library.md`.

The library lives in `src/bleecam/core/criticality/` (in **core**, because it is
shared across all cases, not specific to any one material).

## How to view and use it

- **View:** `bleecam-lib list` (summaries), `bleecam-lib describe <id>` (parameters),
  or this generated catalog.
- **Use:** reference a constraint by `id` under `constraints:` in a scenario YAML,
  with parameters, then run `bleecam-run scenario.yaml`.

```yaml
case: gallium
data_dir: src/bleecam/cases/gallium/data/gallium
objective: cost            # cost | gwp | child_labor | any EF/SLCA category
constraints:
  - id: min_domestic_production
    params: {material: GaN_wafer, process: "Wafer manufacturing", location: US, min_share: 0.25}
```

## Material-agnostic by design

Constraints operate on the generic model structure every case shares — flow arcs
keyed by `(time_period, process, location, material)`, the capacity map, and
demand — not on any material's chemistry. The same constraint applies to
different supply chains by changing its parameters. *(The scenario runner drives
both the Gallium and the rare-earth magnet cases — select with `case:` in the
scenario YAML.)*
"""

_CONTRIBUTOR = """## Adding a constraint (for contributors)

Register an `apply(model, loaded_data, **params)` function that adds Pyomo
constraints to `model.constraints`, with full metadata (scope, meaning, params,
example). It becomes automatically discoverable via `bleecam-lib`, usable in any
scenario YAML, and included in this catalog on the next regeneration — no other
wiring needed. See `src/bleecam/core/criticality/library.py` for examples.
"""


def _constraint_section(c) -> str:
    lines = [f"### `{c.id}` — family: `{c.family}`", ""]
    lines.append(f"- **Scope.** {c.scope}")
    lines.append(f"- **Meaning.** {c.meaning}")
    lines.append("- **Parameters.**")
    for p in c.params:
        req = "required" if p.required else f"optional, default `{p.default!r}`"
        lines.append(f"  - `{p.name}` ({p.type}, {req}) — {p.description}")
    if c.example:
        lines.append(f"- **Example.** `params: {c.example}`")
    if c.notes:
        lines.append(f"- **Note.** {c.notes}")
    lines.append("")
    return "\n".join(lines)


def _families_table() -> str:
    present = set(families())
    rows = ["## Constraint families", "", "| Family | Status | Purpose |", "|---|---|---|"]
    for fam, desc in FAMILY_DESCRIPTIONS:
        status = "implemented" if fam in present else "planned"
        rows.append(f"| `{fam}` | {status} | {desc} |")
    # any families present but not in the known list
    for fam in sorted(present - {f for f, _ in FAMILY_DESCRIPTIONS}):
        rows.append(f"| `{fam}` | implemented | (uncategorized) |")
    rows.append("")
    return "\n".join(rows)


def generate_catalog() -> str:
    parts = [_HEADER, "\n---\n", "## Constraint catalog", ""]
    for c in all_constraints():
        parts.append(_constraint_section(c))
    parts.append("---\n")
    parts.append(_families_table())
    parts.append(_CONTRIBUTOR)
    return "\n".join(parts).rstrip() + "\n"
