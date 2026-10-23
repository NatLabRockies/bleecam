"""P2: run the full bridge on a REAL NREL Standard Scenarios pair (2024), replacing the stub.

Pair: Mid_Case (reference) vs Mid_Case_100by2035 (100% clean grid by 2035 -> accelerated wind).
Source: data/reeds_standard_scenarios_2024/StdScen24_annual_national.csv (OEDI submission 6453).
The national file reports capacity every 3 years (2026..2050); we use the first six snapshots
(2026..2041), where the 100by2035 policy acceleration is sharpest, and map the five build-
intervals onto the REE case's five model periods.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reeds2bleecam.bridge import compare, from_stdscen_national, OUTPUTS  # noqa: E402
from reeds2bleecam.figures import build_figures  # noqa: E402

REAL_CSV = Path(__file__).resolve().parents[1] / "data" / "reeds_standard_scenarios_2024" / "StdScen24_annual_national.csv"
SCENARIOS = ["Mid_Case", "Mid_Case_100by2035"]
YEARS = [2026, 2029, 2032, 2035, 2038, 2041]
PERIOD_MAP = {2029: 0, 2032: 1, 2035: 2, 2038: 3, 2041: 4}
OUT = OUTPUTS / "real"

summary = compare(SCENARIOS, stub_path=REAL_CSV, out_root=OUT, period_map=PERIOD_MAP,
                  loader=from_stdscen_national, years=YEARS, reuse_existing=True)
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)
print("=== REAL cross-scenario comparison (2024 Standard Scenarios) ===")
print(summary.to_string(index=False))

figs = build_figures(SCENARIOS, out_root=OUT, stub_path=REAL_CSV,
                     loader=from_stdscen_national, years=YEARS, suffix="_real")
print("\n=== figures ===")
for f in figs:
    print("wrote", f)
