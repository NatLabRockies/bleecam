"""Assemble the cross-scenario comparison and render the three report figures.

Reuses existing BLEECAM run outputs (outputs/run_<scenario>/) if present, so this is fast;
delete those dirs to force a fresh ipopt solve.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reeds2bleecam.bridge import compare  # noqa: E402
from reeds2bleecam.figures import build_figures  # noqa: E402

SCENARIOS = ["Reference", "HighRE"]

summary = compare(SCENARIOS, reuse_existing=True)
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)
print("=== cross-scenario comparison ===")
print(summary.to_string(index=False))

figs = build_figures(SCENARIOS)
print("\n=== figures ===")
for f in figs:
    print("wrote", f)
