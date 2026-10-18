# BLEECAM × ReEDS linkage prototype — scoping brief

**Goal.** Show how power-sector energy-mix scenarios drive upstream critical-mineral
demand, by feeding ReEDS capacity-expansion output into BLEECAM's supply-chain
optimizer. MVP scope: **rare-earth (REE) content across all foreground power-sector
technologies**, with a synthetic ReEDS stub first and real ReEDS outputs wired later.
Deliverable: a short report + figures.

## The idea in one line

ReEDS tells you *what gets built* (MW by technology, region, year, under a policy/cost
scenario). A material-intensity layer converts that to *how much mineral that needs*
(kg of Nd/Dy/Pr). BLEECAM then tells you *what the supply chain does about it* — cost,
life-cycle environmental and social impact, import dependence, and where it breaks.

```
ReEDS scenario  ──►  capacity by tech/year  ──►  × REE-intensity matrix  ──►
  REE demand (Nd/Dy/Pr, by period)  ──►  BLEECAM demand input  ──►  BLEECAM REE case  ──►
  cost / GWP / S-LCA / import-share / supply gap, compared across energy scenarios
```

The seam already exists on the BLEECAM side: the REE case's demand is **already**
`magnet_intensity (kg NdFeB/MW) × deployment_trajectory (MW)`, with Reference and
deep-decarbonization pathways. ReEDS simply supplies a better-grounded deployment
trajectory. The genuinely new artifact is the **material-intensity bridge**.

## Why "REE in all technologies" is the right first cut

Keep BLEECAM's existing REE case (Nd/Dy → NdFeB magnet) as the backend, but compute REE
demand from the *entire* generation + storage build, not just wind. The expected result
is itself the story: essentially all power-sector REE rides on **wind**, and almost all of
*that* on **direct-drive / permanent-magnet** machines (offshore especially). Solar,
batteries, gas, nuclear carry ~0 REE in their foreground. So "energy mix → REE demand"
collapses to "how much direct-drive wind," which is a clean, defensible headline and a
natural lead-in to later multi-mineral work (PV silver/tellurium, battery Li/Co/Ni/graphite).

## Data contracts (keep these stable; everything hangs off them)

### 1. ReEDS output (stub now, real later) — `data/reeds_stub_capacity.csv`
Tidy long format, one row per scenario × technology × region × year:
`scenario, technology, region, year, capacity_GW`
The stub ships two scenarios (Reference, HighRE) and national (US) resolution, and uses
**ReEDS's real technology-class names** (`wind-ons_1…`, `wind-ofs_1…`, `upv_1…`, `battery_*`,
`gas-cc`, `nuclear`, …) so the tech→intensity mapping is built against reality from day one.

Real ReEDS (github.com/ReEDS-Model/ReEDS; Python+GAMS+Julia, GAMS/CPLEX license needed) writes
each run to `runs/{case}/outputs/`. The capacity file is **`outputs/cap.csv`** with columns
roughly `i` (technology), `r` (region/BA), `t` (year), `MW` (or GW) — plus `gen_ann.csv` for
generation. The adapter should: (a) read `cap.csv`; (b) **aggregate the numbered resource
classes** (`wind-ons_1…10` → `wind-ons`, `wind-ofs_1…15` → `wind-ofs`, `upv_1…` → `upv`) to
the intensity matrix's tech keys; (c) treat `r` as a dimension to sum over for the national
demo. Published scenario outputs are available via NLR's Standard Scenarios / Scenario Viewer
without running GAMS — the fastest path to a real scenario pair in P2.

### 2. REE-intensity matrix — `data/ree_intensity_matrix.csv`
One row per technology: `technology, ndfeb_kg_per_MW, ndpr_frac, dy_frac, pr_frac,
drivetrain_note, source`. NdFeB composition fractions are mass fractions of the magnet.
Starter values (MVP placeholders — refine against the cited sources):
- Offshore wind ~600 kg NdFeB/MW (mostly direct-drive PMSG).
- Onshore wind ~120 kg NdFeB/MW (blended; ~20–40% PMSG, rest geared/DFIG).
- All non-wind technologies 0 (REE in generators/electronics is trace at this boundary).
- NdFeB composition: NdPr ≈ 0.31, Dy ≈ 0.03 by mass.
Sources to anchor on: Carrara et al. 2020 (JRC, *Raw materials demand for wind and solar*),
IEA 2021/2022 critical-minerals reports, and BLEECAM's own material-intensity layer
(Demand_Input_Template). Treat these as **illustrative** until sourced to publication grade.

### 3. BLEECAM demand input — what the adapter must emit
BLEECAM REE case reads `Demand_Input_Template.csv`: `hp_magnet_demand` (kg NdFeB per period
to U.S. demand) plus Nd/Dy mass ratios, by `time_period`. The adapter's job is to produce
this file (or a scenario-specific copy) from the REE demand it computed. Keep BLEECAM's
other inputs (topology, capacity, cost, EF, yields) untouched — only demand changes.

## Adapter design — `reeds2bleecam`

A thin, testable pipeline (see `src/reeds2bleecam/bridge.py` skeleton):
1. `load_reeds(path, scenario)` → capacity by tech/year (GW→MW).
2. `capacity_to_ree(capacity, intensity)` → Nd/Dy/Pr demand by year, per technology, then
   summed. Decide **incremental vs cumulative**: ReEDS reports installed capacity; magnet
   demand is driven by *new builds* (Δ capacity year-over-year), plus eventually
   replacements/retirements. Start with incremental new builds.
3. `to_bleecam_demand(ree_demand)` → write `Demand_Input_Template.csv` in BLEECAM's schema,
   mapping ReEDS years onto BLEECAM periods (see time-horizon note below).
4. `run_bleecam(scenario_yaml)` → call `bleecam-run` and collect `run_summary.json` +
   results (cost, LCIA, S-LCA, import share, unmet demand).
5. `compare(scenarios)` → assemble the cross-scenario table + figures.

## Two design decisions to settle early

- **Time horizon.** ReEDS runs to 2050; the BLEECAM REE beta uses 6 periods (2025–2030).
  Options: (a) run the demo on the 2025–2030 window only; (b) extend BLEECAM's periods to
  2050 (capacity/cost/EF tables would need period extension); (c) annualize and loop. Start
  with (a) for the MVP, flag (b) as the real fix.
- **Capacity → demand basis.** New-build Δ capacity × intensity for the MVP. Note the
  omissions (repowering, 20-yr magnet retirements feeding recycling, stock dynamics) — these
  are exactly where BLEECAM's recycling/stock features become the richer second phase.

## Stub scenarios (ship in the repo)

`Reference` vs `HighRE`: identical total load growth, but HighRE builds far more offshore
and onshore wind (and more storage), while Reference leans on gas + solar. The REE demand
gap between them is the demo's money chart.

## Report outline (the deliverable)

1. One-paragraph framing: energy transition is mineral-intensive; which scenarios, which
   minerals, how much, and can the supply chain take it.
2. Method: the ReEDS → intensity → BLEECAM chain, with the data contracts and caveats.
3. Result 1 — REE demand by energy scenario (the wind story; Reference vs HighRE Nd/Dy).
4. Result 2 — BLEECAM supply-chain response: cost, GWP, import dependence / China exposure,
   and where demand outruns capacity (supply gap) under HighRE.
5. Caveats + next steps (period extension, multi-mineral: PV and batteries).

## Build phases

- **P0 (interface):** adapter runs end-to-end on the stub, emits a BLEECAM demand file,
  runs the REE case for both scenarios. Numbers can be rough.
- **P1 (substance):** real intensity values with citations; incremental-build basis;
  cross-scenario comparison table + 3 figures.
- **P2 (report):** short write-up; wire a real ReEDS scenario pair; flag the period-extension
  and multi-mineral extensions.

## How BLEECAM is accessed

- Install: `pip install bleecam==0.1.0b1` (public beta on PyPI). Needs a solver — HiGHS is
  bundled for the linear cases; the REE case needs `ipopt` (`conda install -c conda-forge ipopt`).
- Run a scenario: `bleecam-run <scenario.yaml>`; REE case entry point `bleecam-ree`.
- Public repo: github.com/NatLabRockies/bleecam · Docs: bleecam.readthedocs.io ·
  DOI 10.11578/dc.20260831.2.
- For development against the demand files, a local editable clone is easiest
  (`pip install -e ".[viz,test]"`), since you'll be writing `Demand_Input_Template.csv`.

## Open questions for Sherif

- Which real ReEDS scenario pair to target in P2 (Standard Scenarios? a custom NLR run?).
- Keep REE-only for the prototype, or reserve hooks now for PV (Ag/Te) and batteries
  (Li/Co/Ni/graphite) so the matrix generalizes cleanly.
- Regional resolution: national for the demo, or carry ReEDS BA/state through to show
  siting/logistics (BLEECAM is country-level today, so U.S. = one node).
