# Gallium LCI and LCIA package

This folder contains the Gallium node-level LCI and LCIA outputs used to prepare BLEECAM optimizer emission factors.

## Boundary

LCIs are node-level and step-wise, consistent with BLEECAM topology. They should not be interpreted as cumulative cradle-to-gate route totals unless summed through the optimizer.

## Main files

- `data/gallium/lci/gallium_master_lci_liaison_ready.csv`
- `data/gallium/lcia/gallium_lcia_node_summary.csv`
- `data/gallium/lcia/reports/gallium_lcia_run_report.md`

## LCIA run status

LiAISON patch-v2 run completed successfully.

52 topology production variants generated LCIA output.

Biosphere rows were excluded from the successful run due to direct biosphere mapping fragility; technosphere/background burdens were retained.

## Important notes

- Bauxite mining burden is modeled separately using an ecoinvent bauxite mine operation proxy.
- Bayer process / alumina refining excludes bauxite burden to avoid double counting.
- Zinc concentration remains a zero-burden topology placeholder because the available zinc concentrate proxy already includes combined mining/concentration burden.
- GaN single-Si wafer background was patched using exact local activity matching.
- `process_location` follows BLEECAM topology; `supplying_location` follows ecoinvent/premise background geography.
- The LCIA summary is ready for conversion into `data/gallium/EF_Template.csv` using the REE-style schema, but EF_Template generation is not part of this package.

## Caveat

This package includes a mix of source-supported foreground LCIs, ecoinvent proxy nodes, ecoinvent-derived placeholders, and process-derived candidate inventories. Interpret node-level factors according to the notes and audits.
