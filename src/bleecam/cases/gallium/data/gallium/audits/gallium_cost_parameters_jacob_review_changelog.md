# Gallium Cost Parameters Jacob Review Changelog

Date: 2026-05-28

## Source Files

- Production file updated: `data/gallium/cost_parameters_ga.csv`
- Jacob-reviewed source: `/Users/skhalifa/Library/CloudStorage/OneDrive-NLR/Projects/BLEECAM/Literature & Data/Gallium Case Study/Gallium Demand/Jacob Expert Review/cost_parameters_Ga_JC.csv`
- Safety backup retained locally: `data/gallium/cost_parameters_ga.backup_before_jacob_review.csv`

## Summary

- Applied Jacob Cordell period-0 expert review edits to the tracked Gallium production cost input.
- Identified 39 reviewed period-0 cost edits: 26 processing-cost changes and 13 tariff-cost changes.
- Propagated those reviewed period-0 values to matching structural rows in time periods 1-4 for temporal consistency.
- Preserved existing repo-specific wafer demand structural rows and did not alter unrelated rows.
- Updated notes on changed rows with reviewed_planning technical notes; no standalone confidence column exists in this CSV.

## Jamaica Row Decision

- Jacob introduced `Bauxite mining | JM | bauxite` in period 0 of the reviewed file.
- `JM` / Jamaica was not found in `data/gallium/trade_topology_ga.csv`, `data/gallium/capacity_template_ga.csv`, `data/gallium/demand_ga.csv`, `data/gallium/shipping_costs_ga.csv`, or LCIA node summary inputs.
- The Jamaica row was excluded from the production cost file for now to avoid adding a cost-only node without topology/capacity confirmation.
- Follow-up needed: confirm whether Jamaica should be added as a Gallium bauxite node across topology, capacity, yield, shipping, and any downstream validation inputs.

## Validation Summary

- Validation status: `PASS`
- Final row count: `975`
- Row counts by time period: `{'0': 195, '1': 195, '2': 195, '3': 195, '4': 195}`
- Duplicate structural rows per time period: `0`
- Missing required field values, excluding optional destination fields and notes: `0`
- Reviewed-value cross-period mismatches: `0`
- Jamaica included: `False`

Note: the final file has 195 rows per period because the tracked BLEECAM production file already includes two repo-specific `wafer_market_mix -> wafer_demand` structural rows per period. Excluding Jamaica therefore preserves 975 rows rather than reverting to the older 965-row external copy.

## Affected Processes, Materials, and Locations

- Processes: `['Bayer liquor refining', 'High-purity gallium refining', 'New manufacturing scrap recovery', 'Wafer manufacturing', 'ZLR refining']`
- Materials: `['4N_Ga', '6N_Ga', 'GaAs_wafer', 'GaN_wafer']`
- Locations: `['CA', 'CN', 'GR', 'JP', 'KR', 'KZ', 'US']`

## Affected Structural Rows

| source | location | material | destination | destination_location | changed column | old period-0 value | reviewed value |
|---|---|---|---|---|---|---:|---:|
| Bayer liquor refining | CA | 4N_Ga |  |  | processing cost | 97.75 | 300 |
| Bayer liquor refining | CN | 4N_Ga |  |  | processing cost | 72.25 | 280 |
| Bayer liquor refining | CN | 4N_Ga | High-purity gallium refining | US | tariff_cost | 28 | 0 |
| Bayer liquor refining | GR | 4N_Ga |  |  | processing cost | 89.25 | 330 |
| Bayer liquor refining | GR | 4N_Ga | High-purity gallium refining | US | tariff_cost | 3 | 0 |
| Bayer liquor refining | KZ | 4N_Ga |  |  | processing cost | 80.75 | 332 |
| Bayer liquor refining | KZ | 4N_Ga | High-purity gallium refining | US | tariff_cost | 3 | 0 |
| Bayer liquor refining | US | 4N_Ga |  |  | processing cost | 102 | 422 |
| High-purity gallium refining | CA | 6N_Ga |  |  | processing cost | 207 | 420 |
| High-purity gallium refining | CN | 6N_Ga |  |  | processing cost | 153 | 350 |
| High-purity gallium refining | CN | 6N_Ga | TMG synthesis | US | tariff_cost | 28 | 0 |
| High-purity gallium refining | CN | 6N_Ga | Wafer manufacturing | US | tariff_cost | 28 | 0 |
| High-purity gallium refining | JP | 6N_Ga |  |  | processing cost | 207 | 440 |
| High-purity gallium refining | JP | 6N_Ga | TMG synthesis | US | tariff_cost | 3 | 0 |
| High-purity gallium refining | JP | 6N_Ga | Wafer manufacturing | US | tariff_cost | 3 | 0 |
| High-purity gallium refining | US | 6N_Ga |  |  | processing cost | 216 | 390 |
| New manufacturing scrap recovery | CA | 6N_Ga |  |  | processing cost | 161 | 322 |
| New manufacturing scrap recovery | CN | 6N_Ga |  |  | processing cost | 119 | 238 |
| New manufacturing scrap recovery | CN | 6N_Ga | TMG synthesis | US | tariff_cost | 28 | 0 |
| New manufacturing scrap recovery | CN | 6N_Ga | Wafer manufacturing | US | tariff_cost | 28 | 0 |
| New manufacturing scrap recovery | JP | 6N_Ga |  |  | processing cost | 161 | 322 |
| New manufacturing scrap recovery | JP | 6N_Ga | TMG synthesis | US | tariff_cost | 3 | 0 |
| New manufacturing scrap recovery | JP | 6N_Ga | Wafer manufacturing | US | tariff_cost | 3 | 0 |
| New manufacturing scrap recovery | KR | 6N_Ga |  |  | processing cost | 147 | 296 |
| New manufacturing scrap recovery | US | 6N_Ga |  |  | processing cost | 168 | 336 |
| Wafer manufacturing | CN | GaAs_wafer |  |  | processing cost | 1020 | 3000 |
| Wafer manufacturing | CN | GaN_wafer |  |  | processing cost | 1275 | 24000 |
| Wafer manufacturing | JP | GaAs_wafer |  |  | processing cost | 1380 | 3500 |
| Wafer manufacturing | JP | GaN_wafer |  |  | processing cost | 1725 | 48000 |
| Wafer manufacturing | KR | GaAs_wafer |  |  | processing cost | 1260 | 3500 |
| Wafer manufacturing | KR | GaN_wafer |  |  | processing cost | 1575 | 48000 |
| Wafer manufacturing | US | GaAs_wafer |  |  | processing cost | 1440 | 3500 |
| Wafer manufacturing | US | GaN_wafer |  |  | processing cost | 1800 | 48000 |
| ZLR refining | CN | 4N_Ga |  |  | processing cost | 102 | 280 |
| ZLR refining | CN | 4N_Ga | High-purity gallium refining | US | tariff_cost | 28 | 0 |
| ZLR refining | JP | 4N_Ga |  |  | processing cost | 138 | 340 |
| ZLR refining | JP | 4N_Ga | High-purity gallium refining | US | tariff_cost | 3 | 0 |
| ZLR refining | KR | 4N_Ga |  |  | processing cost | 126 | 320 |
| ZLR refining | US | 4N_Ga |  |  | processing cost | 144 | 509 |

## S-LCA Use Warning

This file supports BLEECAM cost optimization and can serve as a process-location node map for S-LCA development, but it is not itself the final S-LCA inventory.
