# CLAUDE.md — BLEECAM × ReEDS linkage prototype

Context and conventions for building this repo with Claude Code. Read `PROTOTYPE_BRIEF.md`
first — it is the spec; this file is the operating guide.

## What we're building

A thin adapter (`reeds2bleecam`) that turns ReEDS power-sector capacity-expansion output into
BLEECAM supply-chain demand, to show how energy-mix scenarios drive rare-earth (REE) demand
and what the supply chain does about it. MVP: REE across all power-sector technologies,
synthetic ReEDS stub first, deliverable is a short report + figures.

## The pipeline (keep it small and testable)

```
reeds cap.csv ──load──► capacity[tech,year] ──×intensity──► REE demand[Nd,Dy,Pr,period]
   ──write──► BLEECAM Demand_Input_Template.csv ──bleecam-run──► results ──compare──► report
```

Data contracts live in `data/` and must stay stable:
- `data/reeds_stub_capacity.csv` — scenario, technology, region, year, capacity_GW
- `data/ree_intensity_matrix.csv` — technology, ndfeb_kg_per_MW, ndpr_frac, dy_frac, pr_frac, source
Only BLEECAM's **demand** input changes between scenarios; leave topology/capacity/cost/EF/yields alone.

## Repo layout (target)

```
src/reeds2bleecam/
  bridge.py        # load_reeds, capacity_to_ree, to_bleecam_demand, run_bleecam, compare
  __init__.py
data/              # the two contracts above (shipped)
scenarios/         # BLEECAM scenario yamls, one per energy case
outputs/           # generated demand files, results, figures
report/            # short write-up + figures
tests/             # unit tests on the bridge math
```

## Key commands

- Env: `conda create -n bleecam-reeds python=3.11 && conda activate bleecam-reeds`
- BLEECAM: `pip install bleecam==0.1.0b1` (public beta). Solver: HiGHS bundled; the REE case
  needs ipopt → `conda install -c conda-forge ipopt`. For writing demand files, a local
  editable clone of BLEECAM is easier (`pip install -e ".[viz,test]"`).
- Run BLEECAM scenario: `bleecam-run scenarios/<case>.yaml` → reads `run_summary.json` + results.
- Run the bridge end-to-end: `python -m reeds2bleecam.bridge --scenario Reference` (build this CLI).

## Conventions

- Python 3.11, pandas for the data wrangling, pure functions in `bridge.py` (easy to unit-test
  the capacity→demand math before wiring BLEECAM).
- Everything a number touches gets a cited source or a `# PLACEHOLDER — refine` comment. The
  intensity values shipped are illustrative (Carrara 2020 JRC; IEA 2021/2022) — not final.
- Write the capacity→REE math first and test it on the stub, then wire `bleecam-run`.
- Don't hardcode results; regenerate demand files and rerun BLEECAM for each scenario.

## BLEECAM facts you'll need

- REE case demand = magnet_intensity (kg NdFeB/MW) × deployment (MW), by period, in
  `Demand_Input_Template.csv` (fields: `hp_magnet_demand` + Nd/Dy mass ratios, by `time_period`).
- BLEECAM REE beta uses 6 periods (2025–2030). ReEDS runs to 2050 — for the MVP, map onto the
  2025–2030 window; extending BLEECAM's periods is the real fix (flagged in the brief).
- Public repo github.com/NatLabRockies/bleecam · docs bleecam.readthedocs.io · DOI 10.11578/dc.20260831.2.
- BLEECAM is country-level (U.S. = one demand node), so ReEDS regions sum to national for now.

## Two decisions to make early (see brief)

1. Time horizon: MVP on 2025–2030 window vs extend BLEECAM periods to 2050.
2. Capacity→demand basis: new-build Δ capacity (start here) vs cumulative; retirements/
   repowering feed the later recycling/stock phase.

## Definition of done (MVP)

Adapter runs on the stub for both scenarios, emits BLEECAM demand files, runs the REE case,
and produces a cross-scenario comparison (REE demand + BLEECAM cost/GWP/import-share/supply-gap)
with 3 figures and a short report. Then swap the stub for a real ReEDS Standard-Scenarios pair.
