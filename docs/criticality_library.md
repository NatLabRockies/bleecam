# BLEECAM Criticality Constraint Library

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


---

## Constraint catalog

### `byproduct_cap` — family: `byproduct`

- **Scope.** A by-product production limit — a critical mineral recovered as a by-product (e.g. gallium from bauxite/alumina or zinc) can only be produced in proportion to the host metal's output.
- **Meaning.** For each location and period, caps output of (process, material) at ratio x output of (host_process, host_material) at the same location and period.
- **Parameters.**
  - `process` (str, required) — by-product producing process
  - `material` (str, required) — by-product material
  - `host_process` (str, required) — host-material producing process
  - `host_material` (str, required) — host material (its throughput bounds the by-product)
  - `ratio` (float, required) — max by-product per unit host material (e.g. recovery yield / grade)
  - `location` (str, optional, default `None`) — restrict to one location; default = all locations
- **Example.** `params: {process: "Bayer liquor refining", material: 4N_Ga, host_process: "Bayer process / alumina refining", host_material: Bayer_liquor, ratio: 0.0007}`
- **Note.** Applied per location where both the by-product and host node exist.

### `capacity_ramp` — family: `capacity_policy`

- **Scope.** A change in a process's available production capacity at a location over time — a country capacity ramp-down, expansion, or shutdown (supply-shock and policy scenarios).
- **Meaning.** For the named (process, location[, material]), caps total output in each period at baseline_capacity x factor[period]. Tightens the existing capacity limit only.
- **Parameters.**
  - `process` (str, required) — producing process name
  - `location` (str, required) — process location / country code
  - `factors` (list[float], required) — per-period multiplier on baseline capacity; last value reused if shorter than the horizon
  - `material` (str, optional, default `None`) — restrict to one output material; default = all from this node
- **Example.** `params: {process: "Wafer manufacturing", location: CN, factors: [1.0, 0.8, 0.5, 0.2, 0.05, 0.05]}`
- **Note.** A capacity cap only binds if it falls below actual utilization; where capacity is heavily over-provisioned (e.g. Chinese gallium ~1.6% utilization) capacity haircuts bind weakly.

### `min_domestic_production` — family: `capacity_policy`

- **Scope.** An onshoring / domestic-content policy floor — require a minimum amount of a material to be produced domestically each period.
- **Meaning.** For the named material at location (default US), requires production >= min_share x demand (or >= min_kg) each period, forcing domestic activity the cost-optimum would avoid.
- **Parameters.**
  - `material` (str, required) — material to require domestic production of
  - `min_share` (float, optional, default `None`) — minimum fraction of that period's demand (0-1)
  - `min_kg` (float, optional, default `None`) — minimum absolute kg per period
  - `location` (str, optional, default `'US'`) — domestic location / country code
  - `process` (str, optional, default `None`) — producing process to count (recommended); default = any
- **Example.** `params: {material: GaN_wafer, process: "Wafer manufacturing", location: US, min_share: 0.25}`
- **Note.** Provide either min_share or min_kg.

### `max_source_share` — family: `diversification`

- **Scope.** A supply-diversification / de-risking limit — cap how much of a material may come from any single country, to reduce concentration and single-source dependence.
- **Meaning.** For the named material at location, requires production <= max_share x demand each period, forcing the balance to other locations.
- **Parameters.**
  - `material` (str, required) — material to limit
  - `location` (str, required) — source location / country code to cap
  - `max_share` (float, required) — maximum fraction of that period's demand from this source (0-1)
  - `process` (str, optional, default `None`) — producing process to count (recommended); default = any
- **Example.** `params: {material: GaN_wafer, location: CN, process: "Wafer manufacturing", max_share: 0.6}`

### `price_support` — family: `economic_policy`

- **Scope.** A domestic / allied producer price-support policy — pay producers enough to stay competitive against a dominant supplier's low export price (e.g. the US guaranteeing gallium producers a competitive price). BLEECAM is a buyer-side least-cost model, so a floor is expressed as support to the producer, not a penalty on imports.
- **Meaning.** For the target material at location, lowers the effective per-kg cost the sourcing model sees down to target_price where its true cost is higher (equivalently a per-kg production subsidy), so the producer can be selected. Effective cost never goes below target_price (or below zero for a fixed subsidy), so the problem stays bounded. The subsidy outlay (true cost - target_price, x volume) is accumulated and reported separately as subsidy_usd; resource_cost_usd = subsidized objective + subsidy.
- **Parameters.**
  - `material` (str, required) — material whose production is supported
  - `location` (str, required) — producer location / country code to support (e.g. US)
  - `target_price` (float, optional, default `None`) — guaranteed competitive effective price ($/kg); per-kg subsidy = max(0, true_cost - target_price)
  - `subsidy` (float, optional, default `None`) — alternative to target_price: a fixed per-kg production subsidy ($/kg) on the target routes
  - `process` (str, optional, default `None`) — producing process to support (recommended); default = any
- **Example.** `params: {material: GaN_wafer, location: US, process: "Wafer manufacturing", target_price: 1200}`
- **Note.** Provide exactly one of target_price or subsidy. Only valid under the cost objective (an economic lever). China runs separate domestic and export price schemas; peg target_price to the export price the US would otherwise pay to reflect the true competitiveness gap.

### `strategic_reserve` — family: `resilience`

- **Scope.** A strategic stockpile / reserve policy — carry a minimum inventory of a finished material (NdFeB magnets, gallium wafers) as a buffer against supply disruption.
- **Meaning.** For the named material, requires the inventory buffer (model.stock_level) to hold at least the target each period: coverage_fraction x demand, coverage_periods x demand, or an absolute min_kg. The model pays to build and carry the reserve; under a supply-shock scenario it is drawn down to keep demand met.
- **Parameters.**
  - `material` (str, required) — finished material to stockpile
  - `coverage_fraction` (float, optional, default `None`) — reserve as a fraction of each period's demand (0.5 = half a period)
  - `coverage_periods` (float, optional, default `None`) — reserve as a multiple of a period's demand (2 = two periods of cover)
  - `min_kg` (float, optional, default `None`) — reserve as an absolute quantity (kg) per period
  - `from_period` (int, optional, default `None`) — first period the reserve must be held (default: all periods)
- **Example.** `params: {material: hp_magnet, coverage_periods: 1}`
- **Note.** Requires an inventory-capable case (a finished-good buffer, model.stock_level) — the gallium and rare-earth cases both provide one. Provide exactly one of coverage_fraction, coverage_periods, min_kg. If the case pins a period's opening inventory as a boundary condition (e.g. rare-earth fixes stock_level at t=0 to its initial stock), the reserve is skipped for that period instead of forcing an infeasible model; use from_period to control the first enforced period explicitly. To let the model size the reserve OPTIMALLY instead of imposing it, omit this lever and run a supply-shock scenario: the buffer is banked whenever its holding cost is less than the unmet demand it averts.

---

## Constraint families

| Family | Status | Purpose |
|---|---|---|
| `capacity_policy` | implemented | Capacity ramps / shutdowns and onshoring / domestic-content floors |
| `diversification` | implemented | Limits on single-source concentration and dependence |
| `byproduct` | implemented | Output bounded by host-metal throughput (e.g. Ga from bauxite / zinc) |
| `economic_policy` | implemented | Producer price support / subsidies to keep target producers competitive |
| `resilience` | implemented | Strategic reserves / stockpiles held against supply disruption |
| `coproduct` | planned | Joint-production stoichiometry and unused-fraction handling (e.g. Nd / Dy oxides) |
| `economic_allocation` | planned | Allocation of shared burdens across co- / by-products |
| `chemistry_yield` | planned | Process-family stoichiometry / yield mass-balance templates |
| `circularity` | planned | Recycling floors, EOL recovery targets |

## Adding a constraint (for contributors)

Register an `apply(model, loaded_data, **params)` function that adds Pyomo
constraints to `model.constraints`, with full metadata (scope, meaning, params,
example). It becomes automatically discoverable via `bleecam-lib`, usable in any
scenario YAML, and included in this catalog on the next regeneration — no other
wiring needed. See `src/bleecam/core/criticality/library.py` for examples.
