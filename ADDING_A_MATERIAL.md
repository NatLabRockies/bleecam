# Evaluate a different critical mineral — as simple as 1‑2‑3

BLEECAM is a **material-agnostic** critical-mineral supply-chain platform. Adding a
new mineral doesn't mean rebuilding the tool — you describe its supply chain and
supply its data, and you inherit the entire engine: the optimization, the no-code
**criticality constraint library**, multi-objective (economic / environmental /
social) analysis, the LiAISON ⇄ BLEECAM LCA integration, and the reporting.

The tool ships with two worked cases — **Gallium** (GaAs / GaN wafers) and
**rare-earth NdFeB magnets** — driven by exactly the workflow below.

---

## 1 · Describe your supply chain  →  a case YAML

Copy the template and fill it in — no Python. Choose where it lives:

- **Your own analysis (recommended):** keep the case file and its data in *your own*
  folder — you never edit the package. Point a scenario at it with `case_config:` (step 3).

  ```bash
  mkdir -p copper/data
  cp templates/case_template.yaml copper/copper.case.yaml
  ```

- **Contributing a case to BLEECAM:** place it under the package so the runner finds
  it automatically from `case: copper` (no `case_config:` needed).

  ```bash
  cp templates/case_template.yaml src/bleecam/cases/copper/copper.case.yaml
  ```

You declare the horizon, the demand (what's produced, where), the solver, and the
names of your data files. Sketch your chain as a flow graph first — processes,
materials, locations, the demand node — then write those in. See
`src/bleecam/cases/gallium/gallium.case.yaml` for a lean example (sets derived from
data) and `.../rare_earth/rare_earth.case.yaml` for a richer one (explicit sets).

## 2 · Provide the data  →  drop in CSVs

Put your data files (named in the YAML) in the folder your case file's `data.dir`
points to (e.g. `copper/data`), using the standard schema:

| File | Columns |
|---|---|
| `trade_topology` | `process_from, loc_from, process_to, loc_to, material` |
| `demand` | `time_period, location, material, demand_kg` |
| `capacity` | `time_period, process, location, material, capacity` |
| `cost` | `time_period, source, location, material, destination, destination_location, processing cost, transportation cost, tariff_cost` |
| `yield` | `time_period, process, location, material, yield` |
| `shipping` | `time_period, loc_from, loc_to, shipping_cost_usd_per_kg` |
| `emission_factors` | `time_period, source, location, material, EF_… columns` (from LiAISON / openLCA) |
| `social_lca` | `time_period, source, location, material, SLCA… columns` |

The generic loader reads these into the model automatically — the network
(processes, materials, locations, trade arcs) is inferred from your topology.
Gathering credible data is the real work here, as in any supply-chain LCA.

## 3 · Run  →  results and scenarios

A scenario is a small YAML — it names your case and any policy levers (no code):

```yaml
# copper/copper_baseline.yaml
case: copper
case_config: copper/copper.case.yaml   # out-of-tree case; omit for an in-tree case
objective: cost                        # cost | gwp | a social metric
constraints:                           # criticality-library levers
  - id: max_source_share
    params: {material: cathode, location: CL, max_share: 0.5}
```

(Data is read from the case file's `data.dir`; add `data_dir:` here only to override it.)

```bash
bleecam-run scenarios/copper_baseline.yaml
bleecam-lib list                     # all the policy levers you now have, for free
```

Available levers include `capacity_ramp`, `min_domestic_production`,
`max_source_share`, `byproduct_cap`, and `price_support`. Out comes least-cost
sourcing, the cost / environmental / social breakdown, and every "what-if" scenario.

---

## What you inherit for free

- **No-code scenarios** — the whole criticality constraint library (`bleecam-lib`).
- **Multi-objective optimization** — minimize cost, GWP, or a social metric; single or the AUGMECON frontier.
- **LCA integration** — LCIA/S-LCA factors flow in through the engine-agnostic contract (Brightway2 today, openLCA-capable).
- **Reproducibility** — the same golden-test and physics-closure discipline the shipped cases use.

## Two flavors of material

- **Standard flow-network mineral** (most cases — copper, nickel, lithium, cobalt): the generic loader and config cover it; the physics is your yield / capacity / topology data.
- **Bespoke physics** (co-production locks, lagged recycling, stock dynamics — like rare earths): add a thin case constraints module for the special chemistry; you still inherit everything else.

## Status — the full 1‑2‑3 is live

For a **standard flow-network mineral**, the whole path is implemented and tested:
the declarative config layer, the generic data loader, and the **generic no-code
runner**. You add a material with **no Python** — a case YAML, the data CSVs, and a
scenario. The proof: the generic builder, driven only by a case YAML and the generic
loader, reproduces a hand-written case's optimum *to the cent* (a golden regression
test). Minerals with **bespoke physics** (co-production locks, lagged recycling — like
rare earths) add a thin case constraints module for the special chemistry, and still
inherit the optimization, the library, multi-objective analysis, and LCA integration.

Questions or a mineral you'd like to see supported? See
[`CONTRIBUTING.md`](CONTRIBUTING.md).
