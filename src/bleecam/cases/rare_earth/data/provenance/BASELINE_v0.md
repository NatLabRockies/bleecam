# REE Data — Baseline v0 (step zero)

*The frozen, provisional-but-reproducible starting state of the REE input data.
This is the point we can verify against and walk back to at any time. See
[`docs/DATA_AUDIT_METHODOLOGY.md`](../../../../../docs/DATA_AUDIT_METHODOLOGY.md) §6.*

**v0 is provisional.** Values are not yet fully sourced; the audit (Phase B) will
correct them under a documented version bump. v0 exists so that every later change
is measurable against a fixed, verifiable reference.

## Frozen golden anchors (v0)

| Case | Golden metric | Value |
|---|---|---|
| REE | **cost objective (real $)** | **`$397,092,809.24`** — flow cost `$369,510,261` + stock/unused-oxide/slack penalties |
| REE | flow-table fingerprint (secondary) | total flow volume `95,889,531.277` kg — 130 flow rows, 5 periods |
| Gallium | cost objective | `816,577,036.110402` — demand met, optimal, 0 blocking issues |

> **Resolved (golden recording correction):** `tests/golden/ree.json` previously stored
> the flow *volume* (`95,889,531.277`) under `"objective"` — a mislabel; the REE cost
> objective is `$397,092,809.24`, not ~$96M. `bleecam-ree` now emits `run_summary.json`,
> and the regression anchors on the real cost objective (within 0.1%) with
> `n_flow_rows` / `n_periods` as exact invariants. This corrected what the golden
> *records*; it did **not** change v0 input data or the model.

These are reproducibility anchors for the **current** data. They are expected to
move as data is corrected; each move is recorded in the changelog with source and
rationale, and the golden is re-baselined (v1, v2, …).

## How to verify you are at step zero

The manifest covers the **input and source-data files only** — it deliberately
excludes `model_results_multilocation.csv`, which is a regenerable model *output*
(guarded by the golden test, not the checksum). So running `bleecam-ree` does not
cause false drift here.

```bash
cd src/bleecam/cases/rare_earth/data
sha256sum -c provenance/baseline_v0.sha256      # every listed file must report: OK
```

Any line that is not `OK` means that input has drifted from v0.

## How to walk back to step zero

```bash
# revert the REE input data to the tagged v0 snapshot, then verify
git checkout ree-data-v0 -- src/bleecam/cases/rare_earth/data
sha256sum -c src/bleecam/cases/rare_earth/data/provenance/baseline_v0.sha256
```

(Create the tag once, on the current v0 commit: `git tag ree-data-v0`.)

## v0 input fingerprints

Full checksums are in `baseline_v0.sha256`. Short fingerprints for reference:

| File | sha256 (first 16) | rows | role |
|---|---|---|---|
| `Demand_Input_Template.csv` | `12a884099534e9b8` | 25 | input (demand, mass ratios) |
| `Yield_Factor.csv` | `953d56c56c7ad470` | 355 | input (yields) |
| `Recovery_Rates.csv` | `8c0a4d8c2d952825` | 25 | input (EOL recovery) |
| `Cost_Parameters.csv` | `9250dadc6d8006f9` | 655 | input (cost, tariff) |
| `Capacity_Template.csv` | `f1ebecb3a3702b04` | 355 | input (capacity) |
| `EF_template.csv` | `100a464384529ed2` | 710 | input (environmental factors) |
| `trade_topology.csv` | `77aff59aa0e95572` | 192 | input (allowed arcs — canonical) |
| `Shipping_Costs.csv` | `d1d1e55f6f0654b4` | 360 | input (freight) |
| `Social_LCA_template.csv` | `b5acd1c720b3bbbc` | 710 | input (social factors) |
| `Cost_Parameters_reconciled.csv` | `9250dadc6d8006f9` | 655 | redundant (identical to canonical) |
| `Capacity_Template_reconciled.csv` | `f1ebecb3a3702b04` | 355 | redundant (identical to canonical) |
| `trade_topology_reconciled.csv` | `566ca353da223590` | 123 | not consumed (different variant) |
| `EF_Template_with_SLCA.csv` | `284008d00761c95e` | 710 | not consumed (superset) |
| `market_share_template.csv` | `7ac5f2937f1e285a` | 40 | not consumed |
| `combined_lcia_data.csv` | `a7a55097ef6a4c9d` | 756 | upstream LCA build artifact |
| `lcia_results.csv` | `eec5ac800184ded1` | 12275 | upstream LCA build artifact |
| `pollutant_flow.csv` | `a0292b0e3d531713` | 494533 | upstream LCA build artifact |
| `model_results_multilocation.csv` | `386e72a4a5435063` | 130 | model **output** (not input) |
