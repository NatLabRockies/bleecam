"""Drive the full bridge for both stub scenarios and run the BLEECAM REE case on each.

Maps the ReEDS 5-year snapshots onto the REE case's 5 model periods (2030..2050 -> 0..4),
writes a BLEECAM demand file per scenario, runs the REE case (ipopt), and prints a summary.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reeds2bleecam.bridge import load_reeds, capacity_to_ree, to_bleecam_demand, run_bleecam, DATA  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
STUB = DATA / "reeds_stub_capacity.csv"

# 5 ReEDS build-intervals onto the case's 5 model periods (num_time_periods = 5)
PERIOD_MAP = {2030: 0, 2035: 1, 2040: 2, 2045: 3, 2050: 4}
SCENARIOS = ["Reference", "HighRE"]

summaries = {}
for s in SCENARIOS:
    ree = capacity_to_ree(load_reeds(STUB, s))
    demand_csv = OUT / f"Demand_Input_{s}_5period.csv"
    to_bleecam_demand(ree, demand_csv, period_map=PERIOD_MAP)
    print(f"\n{'='*70}\n[{s}] demand -> {demand_csv.name}; running REE case...\n{'='*70}")
    res = run_bleecam(demand_csv, OUT / f"run_{s}")
    summaries[s] = res["run_summary"]
    print(f"[{s}] objective_real_usd = {res['objective_real_usd']:,.2f}  "
          f"n_periods={res['n_periods']}  results={Path(res['results_csv']).name}")

(OUT / "scenario_summaries.json").write_text(json.dumps(summaries, indent=2))
print(f"\n{'='*70}\nCROSS-SCENARIO SUMMARY\n{'='*70}")
for s, sm in summaries.items():
    print(f"{s:10s}  cost=${sm['objective_real_usd']:,.0f}  "
          f"flow_rows={sm['n_flow_rows']}  total_flow={sm['total_flow_volume']:,.1f}  "
          f"unused_oxides_kg={sm['unused_oxides_kg']:,.1f}")
print("\nwrote", OUT / "scenario_summaries.json")
