# Case study: rare-earth magnets

The rare-earth case models the supply chain for NdFeB permanent magnets
(neodymium and dysprosium), from ore through finished magnet delivered to U.S.
demand. It is the richer of the two shipped cases and exercises the nonlinear
solver path.

## Supply chain

The chain runs end to end across primary acquisition, separation, metal and alloy
processing, magnet manufacturing, use, and end-of-life:

```
mining → separation / refining (REO) → metallization (RE metal)
      → alloying (NdFeB strip) → magnet manufacturing → demand (US)
                                                     ↘ recycling / recovery
```

Materials tracked include the rare-earth oxides and metals (Nd, Dy) and the NdFeB
alloy/magnet. Locations span the major producing and processing countries; the
feasible arcs are defined in the topology file.

## Data

Inputs live in `src/bleecam/cases/rare_earth/data/`:

```{list-table}
:header-rows: 1

* - File
  - Contents
* - `trade_topology.csv`
  - Feasible `(process, location) → (process, location)` arcs per material. Cites USGS Mineral Commodity Summaries (Rare Earth Elements) and U.S. DOE.
* - `Demand_Input_Template.csv`
  - Finished-magnet demand by period and location.
* - `Capacity_Template*.csv`
  - Per-`(period, process, location, material)` capacity upper bounds.
* - `Cost_Parameters*.csv`
  - Fixed per-country processing costs (combined with transport, shipping, tariffs).
* - `Shipping_Costs.csv`, `Yield_Factor.csv`, `Recovery_Rates.csv`
  - Cross-border shipping, per-stage yields, and recycling recovery.
* - `EF_Template*.csv`, `Social_LCA_template.csv`
  - Environmental (LCA-derived) and social factors via the LCA contract.
* - `lci/`, `combined_lcia_data.csv`, `lcia_results.csv`
  - Life-cycle inventory (literature-derived, mapped to ecoinvent UUIDs) and characterized results. See [Data & provenance](../data_provenance).
```

## Running the case

```bash
bleecam-ree --data src/bleecam/cases/rare_earth/data
```

The rare-earth model includes nonlinear terms, so it uses ipopt
(see [Installation → Solvers](../installation.md#solvers)). The run reports the
cost-optimized configuration and its economic, environmental, and social metrics.

## Two useful baselines

Descriptive "as-is" (current state)
: A pinned scenario that fixes each stage's country mix to today's real capacity
  shares (e.g. magnet manufacturing dominated by one country). This describes what
  the world looks like now — it is *not* optimized.

Cost-optimized baseline
: The unconstrained cost minimizer, which re-routes flows to the cheapest feasible
  configuration. The gap between the two is the headroom optimization would capture,
  and is dominated by tariffs and country-specific processing premiums.

Both are expressed as scenario YAMLs and run with `bleecam-run` using levers from
the [criticality library](../criticality_library) (for example `max_source_share`
to pin country mixes).

## Scenarios

Typical rare-earth scenarios include supply shocks (export restrictions on a
dominant supplier) and allied build-out. Point `bleecam-run` at a scenario file:

```bash
bleecam-run scenarios/<your_ree_scenario>.yaml
```

See [Add a material](../adding_a_material) for the scenario and case-file schema.
