# Gallium Pollutant Profile Generation Report

Generated: 2026-05-26 18:31:44

## Purpose

Create REE-dashboard-compatible Gallium pollutant profiles from the successful LiAISON patch-v2 raw outputs. These profiles populate the dashboard Pollutant Inventory tab.

## Source

- LiAISON run folder: LiAISON local masterfile folder / liaison_lcia_results_gallium_topology_expanded_patch_v2
- Raw index: raw_file_index.csv
- Scope used: total_life_cycle
- Raw file type used: characterized_inventory

## Important Interpretation

The generated pollutant profile is a LiAISON/Brightway characterized inventory profile, not a raw uncharacterized physical emissions inventory. Amounts are per kg topology production output and are already characterized by TRACI2.1 category units. For example, nitrogen oxides under acidification are reported as kg SO2-Eq contribution, while carbon dioxide under GWP100 is reported as kg CO2-Eq contribution.

The successful Gallium LCIA run excluded direct foreground biosphere rows because of biosphere mapping fragility. These profiles therefore reflect technosphere/background inventory contributions from the successful run.

## Outputs Created

- data/gallium/lcia/gallium_pollutant_flow_characterized.csv
- data/gallium/pollutant_flow.csv
- data/gallium/lcia/gallium_pollutant_profile_summary_by_node.csv
- data/gallium/lcia/audits/gallium_pollutant_profile_generation_audit.csv

Dashboard copies written to:

- outputs/gallium/dashboard/ree_style_inputs/cost_optimized_baseline/pollutant_flow.csv
- outputs/gallium/dashboard/ree_style_inputs/policy_china_capacity_shutdown/pollutant_flow.csv
- outputs/gallium/dashboard/ree_style_inputs/policy_total_system_cost/pollutant_flow.csv

## Counts

- Total topology variants processed: 52
- Variants with generated profiles: 45
- Raw characterized contribution rows read: 81,000
- Aggregated pollutant profile rows: 675
- Unique analyzed process profiles: 10
- Unique process-location profiles: 45
- Unique flow/category profile names: 15

## TRACI Categories Included

| lcia_category                                 | flow_unit    |   profile_rows |
|:----------------------------------------------|:-------------|---------------:|
| Acidification Potential (Ap)                  | kg SO2-Eq    |             45 |
| Ecotoxicity: Freshwater                       | CTUe         |            135 |
| Eutrophication Potential                      | kg N-Eq      |             45 |
| Global Warming Potential (Gwp100)             | kg CO2-Eq    |             45 |
| Human Toxicity: Carcinogenic                  | CTUh         |             45 |
| Human Toxicity: Non-Carcinogenic              | CTUh         |            135 |
| Maximum Incremental Reactivity (Mir)          | kg O3-Eq     |             45 |
| Ozone Depletion Potential (Odp)               | kg CFC-11-Eq |            135 |
| Particulate Matter Formation Potential (Pmfp) | PM2.5-Eq     |             45 |

## Empty or Missing Variants

| process            | process_location   | flow                      | file_path                                                                                                                                                                                                                                                                                                                     |   raw_rows |   profile_rows | status                        | notes                                                                                    |
|:-------------------|:-------------------|:--------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------:|---------------:|:------------------------------|:-----------------------------------------------------------------------------------------|
| Zinc concentration | AU                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__AU__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |
| Zinc concentration | CA                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__CA__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |
| Zinc concentration | CN                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__CN__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |
| Zinc concentration | JP                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__JP__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |
| Zinc concentration | KR                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__KR__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |
| Zinc concentration | KZ                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__KZ__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |
| Zinc concentration | US                 | Zn_sphalerite_concentrate | LiAISON local masterfile folder/liaison_lcia_results_gallium_topology_expanded_patch_v2/raw/gallium_topology_expanded_patch_v2_total_life_cycle__Zinc_concentration__US__Zn_sphalerite_concentrate_characterized_inventory.csv |          0 |              0 | empty_characterized_inventory | No characterized inventory contributions were present for this total-life-cycle variant. |

## Dashboard Note

The REE dashboard computes pollutant totals by multiplying these per-kg characterized profile amounts by BLEECAM material flow quantities. A Gallium-specific process/material map is still required when rendering the REE-style dashboard because the upstream dashboard renderer has REE process names hard-coded.
