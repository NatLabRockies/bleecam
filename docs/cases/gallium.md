# Case study: gallium

The gallium case models the supply chain for **GaAs / GaN semiconductor wafers**,
from bauxite through high-purity gallium to finished wafers delivered to U.S.
demand. It is a linear case and solves quickly with the bundled HiGHS solver.

## Supply chain

Gallium is a **byproduct** metal, so the chain begins in aluminium (and zinc)
production and proceeds through purification, precursor chemistry, and wafer
fabrication:

```
bauxite → alumina (Bayer process) → crude gallium (≈4N)
        → high-purity gallium (≈6N) → precursors (e.g. TMG)
        → GaAs / GaN wafers → demand (US)
```

A secondary **zinc-residue** route to crude gallium is also represented. Materials
tracked span bauxite, alumina/Bayer liquor, crude and high-purity gallium,
precursors, and the finished wafers.

## Data

Inputs live in `src/bleecam/cases/gallium/data/gallium/`:

```{list-table}
:header-rows: 1

* - File
  - Contents
* - `trade_topology_ga.csv`
  - Feasible arcs per material. Cites USGS Mineral Commodity Summaries (Gallium), DOE, and producer sources.
* - demand / capacity / cost tables
  - Wafer demand to the U.S. by period; per-stage capacity upper bounds; fixed processing costs plus shipping.
* - `lci/gallium_master_lci_liaison_ready.csv`
  - Life-cycle inventory. ecoinvent-sourced background values are redacted (UUIDs and selections retained); literature/foreground values are kept. See [Data & provenance](../data_provenance).
* - emission-factor / social templates
  - Environmental and social factors via the LCA contract.
```

:::{admonition} Tariffs are not modeled in the gallium case
:class: warning
Unlike the rare-earth case, gallium arc costs carry **no tariff term** in this beta
(tariffs are zero). Cost-optimal routing therefore reflects processing and shipping
economics only. Keep this in mind when comparing gallium routing to real-world trade
policy.
:::

## Running the case

```bash
# Linear model — HiGHS is bundled, no extra solver needed
bleecam-ga --input-dir src/bleecam/cases/gallium/data/gallium --solver auto
```

## Multi-objective (Pareto) frontier

The gallium case supports a 3-objective trade-off surface
(cost × GWP × a social metric) via AUGMECON2. This path needs **ipopt**:

```bash
bleecam-ga-pareto \
  --data src/bleecam/cases/gallium/data/gallium \
  --out outputs/gallium_pareto \
  --grid 50
```

## Descriptive "as-is" baseline

As with rare earth, a pinned scenario can fix each stage to today's real capacity
shares (for example, wafer fabrication split across the current producing
countries). Because gallium is byproduct-driven and cost-optimal routing tends to
concentrate at the cheapest byproduct source, the pinned "as-is" view is the more
faithful description of the present-day chain; the cost-optimized run shows where
the economics alone would push it. See [Data & provenance](../data_provenance) for
how the underlying shares are sourced.
