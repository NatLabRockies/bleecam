# LCIA Pre-EF Conversion Patch v2 Report

Generated: 2026-05-26T17:37:00

## Scope

This targeted patch pass used the no-biosphere Gallium topology-expanded run file and created a new patched runnable copy only. The public master LCI was not overwritten, and biosphere rows were not reintroduced.

Patched run file: `LiAISON local masterfile folder/gallium_lci_compiled_topology_expanded_no_biosphere_patch_v2.csv`
Patch-v2 output folder: `data/gallium/lcia`

## Patch Status

1. **Bauxite mining:** successfully assigned a separate burden. Four topology variants (AU, CN, GR, KZ) now include `bauxite mine operation | bauxite | GLO | kilogram`; process_location remains the BLEECAM topology location and supplying geography is GLO.
2. **Bayer process / alumina refining:** made bauxite-excluded for the runnable patch. The previous black-box aluminium oxide production proxy was replaced with extracted unit-process exchanges, with the bauxite input burden excluded/foregrounded out so that bauxite mining and alumina/Bayer refining are not double counted.
3. **Zinc concentration:** remains zero intentionally. The local database search did not identify a separate concentration-only zinc dataset; the combined zinc concentrate burden remains assigned to ZS mining, while Zinc concentration is retained as a zero-burden placeholder to avoid double counting.
4. **GaN single-Si wafer:** linked successfully using the exact local activity `market for single-Si wafer, for electronics | single-Si wafer, for electronics | GLO | square meter`; no direct LCIA fallback was used. The run log recorded 4 exact-link successes for this exchange and 0 generic `Failed - Not found` messages overall.

## LiAISON Rerun

- Status: success
- Input rows: 813
- Production variants expected from patched LCI: 52
- Production variants with total-life-cycle GWP output: 52
- Successful scope-node runs: 156
- Failed scope-node runs: 0
- Raw output files: 312
- Runtime seconds: 1410.474

All 52 topology production variants have non-missing total-life-cycle TRACI GWP100 output in the patch-v2 node summary.

## Non-Targeted Rerun Shifts

The patch-v2 rerun also changed 12 non-targeted total-life-cycle GWP values. These shifts are not new scientific assumptions in the patch file; they appear to come from LiAISON/Brightway resolving multiple matching background activities differently during the fresh rerun. The affected rows are Bayer liquor refining CA/GR/KZ, ZS mining AU/CA/CN/KZ/US, and Zinc smelting/refining CN/JP/KR/US. Before final EF ingestion, freeze or review the selected background activities for the ambiguous sulfuric acid, zinc mine operation, and primary zinc production from concentrate matches if those values are material to the scenario.

## Key GWP100 Values

Values are total-life-cycle TRACI2.1 Global Warming Potential (Gwp100), in kg CO2-Eq per kg topology material output unless the underlying node-specific LCI unit notes say otherwise.

| Process | Location | Material | Old GWP100 | Patched GWP100 | Difference |
|---|---:|---|---:|---:|---:|
| Bauxite mining | AU | bauxite | 0 | 0.0121642 | 0.0121642 |
| Bayer process / alumina refining | CN | Bayer_liquor | 2.87292 | 2.79691 | -0.0760152 |
| Bayer liquor refining | CN | 4N_Ga | 243.546 | 243.546 | 0 |
| High-purity gallium refining | CN | 6N_Ga | 0.394967 | 0.394967 | 1.96837e-09 |
| TMG synthesis | CN | TMG | 37.917 | 37.917 | 2.36533e-10 |
| Wafer manufacturing | CN | GaAs_wafer | 1013.77 | 1013.77 | 3.24358e-07 |
| Wafer manufacturing | CN | GaN_wafer | 52867.2 | 53663.6 | 796.348 |
| ZS mining | CN | Zn_sphalerite_concentrate | 0.134814 | 0.437859 | 0.303044 |
| Zinc concentration | CN | Zn_sphalerite_concentrate | 0 | 0 | 0 |
| Zinc smelting/refining | CN | ZLR_Zn_residue | 2.69078 | 3.36347 | 0.672695 |
| ZLR refining | CN | 4N_Ga | 439.488 | 439.488 | 2.05491e-07 |
| ZLR refining | US | 4N_Ga | 428.22 | 428.22 | 1.45679e-07 |

## Remaining Zero Variants

| Process | Location | Material | Patched GWP100 | Reason |
|---|---:|---|---:|---|
| Zinc concentration | AU | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |
| Zinc concentration | CA | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |
| Zinc concentration | CN | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |
| Zinc concentration | JP | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |
| Zinc concentration | KR | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |
| Zinc concentration | KZ | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |
| Zinc concentration | US | Zn_sphalerite_concentrate | 0 | Intentional zero placeholder to avoid double counting combined zinc concentrate proxy. |

## Audit Artifacts

- Zero variant audit: `LiAISON local masterfile folder/lcia_zero_variant_boundary_audit_v2.csv`
- Bauxite/alumina boundary audit: `LiAISON local masterfile folder/bauxite_alumina_boundary_patch_audit_v1.csv`
- Zinc mining/concentration boundary audit: `LiAISON local masterfile folder/zinc_mining_concentration_boundary_audit_v1.csv`
- GaN Si wafer background audit: `LiAISON local masterfile folder/gan_si_wafer_background_patch_audit_v2.csv`
- Patched LCIA node summary: `data/gallium/lcia/gallium_lcia_node_summary_patch_v2.csv`
- Old-vs-patched comparison: `LiAISON local masterfile folder/lcia_patch_v2_comparison_summary.csv`

## Notes Before EF_Template Conversion

- The patched file remains no-biosphere, matching the successful troubleshooting run boundary.
- Bauxite mining uses a GLO supplier proxy for all topology process locations.
- Alumina/Bayer refining now represents a topology proxy with bauxite burden excluded, not a physical Luo 2025 Bayer-liquor-to-4N_Ga foreground boundary.
- Zinc concentration zeros should be carried forward deliberately or documented as zero-burden placeholders in EF conversion.
- The patch-v2 results are structurally ready for conversion to the Gallium `EF_Template.csv`, with two caveats: Zinc concentration should remain labeled as a boundary-overlap zero rather than interpreted as measured zero impact, and the non-targeted zinc/sulfuric-acid background matcher shifts should be reviewed or frozen before treating the EF file as final.
