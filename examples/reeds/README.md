# bleecam-reeds

Prototype linkage between **ReEDS** (NLR's power-sector capacity-expansion model) and
**BLEECAM** (critical-mineral supply-chain optimizer). It converts an energy-mix scenario
into upstream rare-earth (REE) demand and runs it through BLEECAM to report cost, life-cycle
environmental and social impact, import dependence, and supply gaps — so you can see how
different power-sector futures stress the critical-mineral supply chain.

> Status: research prototype. Material-intensity values are illustrative placeholders pending
> publication-grade sourcing. Not decision-grade.

## The chain

```
ReEDS capacity (MW by tech/year)  ──×  REE-intensity matrix  ──►  REE demand (Nd/Dy/Pr)
  ──►  BLEECAM demand input  ──►  BLEECAM REE case  ──►  cost / GWP / S-LCA / import share / supply gap
```

In the power sector, REE demand is almost entirely a **wind** story (direct-drive permanent
magnets), so "energy mix → REE demand" is driven by how much wind — especially offshore — gets
built. Illustrative finding on the NREL 2024 Standard Scenarios Mid-Case vs a clean-by-2035
mandate: the mandate front-loads wind and magnet demand (~+15% NdFeB over the horizon, peaking
~26% higher near 2032), with ~22% higher supply-chain cost and China exposure rising ~6.6% → 11.6%.

## Quickstart

```bash
conda create -n bleecam-reeds python=3.11 && conda activate bleecam-reeds
pip install -e ".[test]"
conda install -c conda-forge ipopt      # BLEECAM REE case needs ipopt; HiGHS is bundled
pytest                                   # unit tests on the capacity->demand math
python -m reeds2bleecam.bridge           # smoke test on the stub scenario
```

## Data contracts (`data/`)

- `reeds_stub_capacity.csv` — synthetic 2-scenario capacity, real ReEDS tech-class names.
- `ree_intensity_matrix.csv` — kg NdFeB/MW + Nd/Pr/Dy mass fractions per technology (PLACEHOLDER).
- `reeds_standard_scenarios_2024/` — real NREL Standard Scenarios national capacity (OEDI 6453).

Real ReEDS runs write `runs/{case}/outputs/cap.csv`; the adapter normalizes both the stub and
the real file to one schema, so the pipeline is source-agnostic.

## Attribution & license

Built on **BLEECAM** (DOI 10.11578/dc.20260831.2; github.com/NatLabRockies/bleecam) and **ReEDS**
(github.com/ReEDS-Model/ReEDS). Standard Scenarios data via NLR/OEDI (dataset 6453) under its own
terms. Material intensities to be sourced to Carrara et al. 2020 (JRC) and IEA critical-minerals
reports. Released under **AGPL-3.0-or-later** to match BLEECAM.
