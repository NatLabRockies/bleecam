# Gallium EF Template Generation Report

Generated: 2026-05-26T18:00:22

## Inputs

- LCIA node summary: `data/gallium/lcia/gallium_lcia_node_summary.csv`
- Topology: `data/gallium/trade_topology_ga.csv`
- REE schema reference: `data/EF_template.csv` and `data/EF_Template_with_SLCA.csv`

## Outputs

- Active optimizer file: `data/gallium/EF_Template.csv`
- Descriptive copy: `data/gallium/EF_Template_Ga_from_LiAISON.csv`
- LCIA source audit: `data/gallium/lcia/audits/gallium_ef_lcia_source_audit.csv`
- Topology completeness audit: `data/gallium/lcia/audits/gallium_ef_topology_completeness_audit.csv`
- Value sanity check: `data/gallium/lcia/audits/gallium_ef_value_sanity_check.csv`

## Conversion Choices

- LCIA scope used: `total_life_cycle`.
- EF key: `time_period + source + location + material`.
- `source = process`, `location = process_location`, `material = flow`.
- Static LCIA node factors were replicated across time periods: [0, 1, 2, 3, 4].
- Duplicate LCIA method/category labels were collapsed only when duplicate values were identical. This affected ReCiPe `Agricultural Land Occupation (Lop)`, which appeared three times per node variant with identical values.
- Active GWP alias source: `EF_RECIPE__Global Warming Potential (Gwp1000)`.
- TRACI GWP100 mapped into Gwp1000 alias for compatibility: no.

## Counts

- LCIA node variants: 52
- Time periods: 5
- EF rows: 260
- EF indicator columns, excluding active alias: 25
- Total EF columns including traceability: 35
- Missing topology blockers: 0
- Intentional zero rows: 35
- Scenario-only excluded topology rows in audit: 55
- Large-value flags in EF rows: 25

## Active GWP Alias

`EF_weighted__Global Warming Potential (Gwp1000)` is populated from `EF_RECIPE__Global Warming Potential (Gwp1000)`.

Because ReCiPe GWP1000 is available in the Gallium LiAISON output, the optimizer alias does not use TRACI GWP100.

## Intentional Zero Rows

Zinc concentration rows are retained with zero active GWP values and the traceability label `ZERO_BURDEN_PLACEHOLDER_TO_AVOID_DOUBLE_COUNTING_WITH_ZINC_CONCENTRATE_PROXY`. These rows are intentional placeholders because the available zinc concentrate proxy already includes combined mining/concentration burden.

## Major Caveats

- The Gallium EF file is node-level and step-wise; it should not be interpreted as cumulative route totals except through optimizer path summation.
- Bauxite mining uses a GLO ecoinvent bauxite mine operation proxy while `location` follows BLEECAM topology.
- Bayer process / alumina refining excludes bauxite burden to avoid double counting.
- GaN wafer manufacturing can be very high because the Vauche GaN-on-Si wafer/device processing benchmark is normalized per kg processed wafer.
- The LCIA package was generated from the successful no-biosphere LiAISON patch-v2 run; biosphere rows were excluded because direct biosphere mapping was fragile, while technosphere/background burdens were retained.
- ZLR refining is a process-derived candidate inventory, not a measured industrial foreground LCI.
- The prior LCIA patch report flagged non-targeted shifts from ambiguous zinc/sulfuric-acid background matching. Review those selected background activities before treating final scenario EFs as publication-grade.

## Readiness

`data/gallium/EF_Template.csv` is ready for optimizer use.

