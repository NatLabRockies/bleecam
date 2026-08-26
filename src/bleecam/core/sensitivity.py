# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One-at-a-time (OAT) elasticity screen — which inputs move an objective most.

A *screening* method that ranks input factor-groups by influence with minimal
assumptions: perturb one factor by a small fraction, re-solve, and measure the
elasticity of the objective (percent change in the objective per percent change
in the input). It is deliberately the first step of WS4 — a low-assumption screen
to prioritise the data audit — ahead of a full variance-based (Sobol) analysis,
which needs the credible input ranges the audit produces.

Design:

- **Non-destructive.** Perturbation scales a column in a *temp copy* of the data;
  the original input files are never touched.
- **Case-agnostic.** A factor is ``(file, column)`` and is applied through each
  case's normal file loader, so the same harness screens any case.
- **Audit-aligned.** A factor-group maps 1:1 onto a provenance cluster in the
  case's ``DATA_SOURCES.md`` — the ranking says which cluster to source first.
- **Per objective.** Run once per output (cost, gwp, a social metric); a factor
  only registers under the objective it actually feeds.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from .scenario import run_scenario


def _scale_column(csv_path: Path, column: str, mult: float, where: dict | None = None) -> bool:
    """Scale numeric entries of ``column`` by ``mult`` in place, optionally only on
    rows matching every ``{col: value}`` in ``where`` (e.g. one process)."""
    df = pd.read_csv(csv_path, keep_default_na=False)
    if column not in df.columns:
        return False
    vals = pd.to_numeric(df[column], errors="coerce")
    mask = vals.notna()
    for key, value in (where or {}).items():
        if key not in df.columns:
            return False
        mask &= df[key].astype(str).str.strip() == str(value)
    if not mask.any():
        return False
    df[column] = df[column].astype(object)  # avoid int/float dtype clash on assignment
    df.loc[mask, column] = (vals[mask] * mult).values
    df.to_csv(csv_path, index=False)
    return True


def oat_elasticities(config: dict, factors: list[dict], *, delta: float = 0.1,
                     solver: str = "auto") -> dict[str, Any]:
    """Rank ``factors`` by the elasticity of the scenario's objective.

    ``config`` is a scenario dict (case, data_dir, objective, constraints). Each
    factor is ``{label, file, column}``. Returns the baseline objective and a list
    of factors sorted by absolute elasticity (percent change in the objective per
    percent change in the input).
    """
    data_dir = Path(config["data_dir"])
    work = Path(tempfile.mkdtemp(prefix="bleecam_sens_"))
    tmp_data = work / "data"
    shutil.copytree(data_dir, tmp_data)
    try:
        base = run_scenario({**config, "data_dir": str(tmp_data)}, solver=solver, out_dir=work / "base")
        obj0 = base.get("objective_value")
        rows: list[dict[str, Any]] = []
        for f in factors:
            label, fname, column = f["label"], f["file"], f["column"]
            target, original = tmp_data / fname, data_dir / fname
            if not original.exists():
                rows.append({"factor": label, "elasticity": None, "note": "file not found"})
                continue
            if not _scale_column(target, column, 1.0 + delta, f.get("where")):
                shutil.copy(original, target)
                rows.append({"factor": label, "elasticity": None, "note": "no matching numeric rows"})
                continue
            r = run_scenario({**config, "data_dir": str(tmp_data)}, solver=solver, out_dir=work / "p")
            obj1 = r.get("objective_value")
            shutil.copy(original, target)  # restore before the next factor
            if obj0 in (None, 0) or obj1 is None:
                el, pct = None, None
            else:
                pct = (obj1 - obj0) / obj0 * 100.0
                el = ((obj1 - obj0) / obj0) / delta
            rows.append({"factor": label, "file": fname, "column": column,
                         "where": f.get("where"), "elasticity": el, "obj_change_pct": pct})
        ranked = sorted(rows, key=lambda x: (x["elasticity"] is None, -abs(x["elasticity"] or 0.0)))
        return {"objective": config.get("objective", "cost"), "delta": delta,
                "baseline_objective": obj0, "factors": ranked}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _default_factor_spec(case: str) -> Path:
    import bleecam
    return Path(bleecam.__file__).parent / "cases" / case / "sensitivity_factors.yaml"


def main() -> int:
    import argparse
    import json

    import yaml

    ap = argparse.ArgumentParser(
        prog="bleecam-sensitivity",
        description="OAT elasticity screen: rank inputs by how much they move the objective.",
    )
    ap.add_argument("scenario", help="scenario YAML (case, data_dir, objective, constraints)")
    ap.add_argument("--factors", default=None, help="factor-group YAML (default: cases/<case>/sensitivity_factors.yaml)")
    ap.add_argument("--delta", type=float, default=0.1, help="fractional perturbation (default 0.1 = 10%%)")
    ap.add_argument("--solver", default="auto")
    ap.add_argument("--json", default=None, help="also write the ranked result to this JSON path")
    args = ap.parse_args()

    config = yaml.safe_load(Path(args.scenario).read_text())
    spec_path = Path(args.factors) if args.factors else _default_factor_spec(str(config["case"]))
    factors = (yaml.safe_load(spec_path.read_text()) or {}).get("factors", [])
    res = oat_elasticities(config, factors, delta=args.delta, solver=args.solver)

    b = res["baseline_objective"]
    print(f"\nOAT elasticity screen — objective: {res['objective']}  |  delta: ±{res['delta']*100:.0f}%  "
          f"|  baseline: {b:,.2f}" if b is not None else "baseline: n/a")
    print(f"{'factor':34}{'elasticity':>13}{'obj change':>13}")
    print("-" * 60)
    for r in res["factors"]:
        el = "n/a" if r.get("elasticity") is None else f"{r['elasticity']:+.4f}"
        dp = "" if r.get("obj_change_pct") is None else f"{r['obj_change_pct']:+.3f}%"
        note = f"  ({r['note']})" if r.get("note") else ""
        print(f"{r['factor']:34}{el:>13}{dp:>13}{note}")
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
