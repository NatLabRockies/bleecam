# Quickstart

This page runs the two shipped cases and a no-code scenario. It assumes you have
[installed](installation) BLEECAM (`pip install -e .`) from a clone of the repo.

## Run the baselines

```bash
# Rare-earth NdFeB magnet supply chain (cost-optimized baseline)
bleecam-ree --data src/bleecam/cases/rare_earth/data

# Gallium GaAs / GaN wafer supply chain (auto solver selection)
bleecam-ga --input-dir src/bleecam/cases/gallium/data/gallium --solver auto
```

Each command loads the case's golden inputs, builds the Pyomo model, solves the
cost-minimizing configuration, and writes results (flows, costs, and the three
metric dimensions) to the case's output folder.

## Multi-objective (Pareto) frontier

The gallium case can produce a 3-objective trade-off surface
(cost × GWP × a social metric) via the AUGMECON2 method. This needs `ipopt`
(see [Installation](installation.md#solvers)).

```bash
bleecam-ga-pareto \
  --data src/bleecam/cases/gallium/data/gallium \
  --out outputs/gallium_pareto \
  --grid 50
```

## Run a scenario — no code

A **scenario** is a small YAML that names a case and applies policy levers from
the criticality-constraint library. Nothing is hard-coded in Python.

```bash
bleecam-lib list                                  # browse every available lever
bleecam-run scenarios/gallium_china_shutdown.yaml # run a supply-shock scenario
```

A minimal scenario file looks like this:

```yaml
case: gallium
objective: cost                # cost | gwp | a social metric
constraints:                   # levers from the criticality library
  - id: max_source_share
    params: {material: high_purity_ga, location: CN, max_share: 0.5}
```

See [Add a material](adding_a_material) for the full scenario and case-file schema,
and [Core concepts](concepts) for what the objectives and constraints mean.

## Console entry points

```{list-table}
:header-rows: 1

* - Command
  - What it does
* - `bleecam-ree`
  - Solve the rare-earth case.
* - `bleecam-ga`
  - Solve the gallium case.
* - `bleecam-ga-pareto`
  - Gallium multi-objective (AUGMECON2) Pareto frontier.
* - `bleecam-run`
  - Run a scenario YAML against any case (no code).
* - `bleecam-lib`
  - List / inspect the no-code criticality-constraint library.
* - `bleecam-sensitivity`
  - Run the sensitivity analysis for a case.
```
