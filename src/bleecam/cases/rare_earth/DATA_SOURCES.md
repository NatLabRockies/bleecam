# Rare-Earth Case — Data Sources & Provenance

*Authoritative guide to the origin, method, vintage, and uncertainty of every input
the REE (NdFeB magnet) model consumes. Governed by
[`docs/DATA_AUDIT_METHODOLOGY.md`](../../../../docs/DATA_AUDIT_METHODOLOGY.md).
Fields marked `[TO SOURCE]` / **OPEN** are release blockers to be resolved in Phase B.*

**Status legend.** **SOURCED** (citation / named expert / documented calculation) ·
**OPEN** (source pending). Confidence for SOURCED: **A** peer-reviewed/authoritative ·
**B** gov/industry/gray · **C** documented expert estimate or bottom-up TEA.

**Baseline:** all values below are frozen at **v0** — see
[`data/provenance/BASELINE_v0.md`](data/provenance/BASELINE_v0.md). Nothing here changes
the input files; corrections happen only via a documented version bump.

---

## Canonical files (resolved)

These 9 files are the inputs the model actually reads (`data_loader.load_all_data`):

| Input | Canonical file | Drives |
|---|---|---|
| Demand + Nd/Dy mass ratios | `Demand_Input_Template.csv` | hp_magnet demand, alloy composition |
| Yield factors | `Yield_Factor.csv` | process mass balance |
| Recovery rates | `Recovery_Rates.csv` | end-of-life recycling |
| Cost parameters | `Cost_Parameters.csv` | processing, transport, tariff |
| Capacity | `Capacity_Template.csv` | per-node output ceilings |
| Environmental factors | `EF_template.csv` | GWP / LCIA objectives |
| Trade topology | `trade_topology.csv` (192 arcs) | allowed routes |
| Shipping | `Shipping_Costs.csv` | inter-country freight |
| Social factors | `Social_LCA_template.csv` | S-LCA objectives |

**Not consumed by the model** (redundant, upstream, or output — flag for archival/clarity):
`Cost_Parameters_reconciled.csv` and `Capacity_Template_reconciled.csv` (byte-identical to
their canonical twins), `trade_topology_reconciled.csv` (a *different* 123-arc variant — the
model uses the 192-arc file, not this one), `EF_Template_with_SLCA.csv` (superset; model reads
EF and S-LCA separately), `market_share_template.csv` (not loaded), `combined_lcia_data.csv` /
`lcia_results.csv` / `pollutant_flow.csv` (LCA build artifacts — upstream provenance for
`EF_template.csv`), `model_results_multilocation.csv` (a model *output*).

---

## By data category

### 1. Life-cycle inventory & impact factors (`EF_template.csv`)
- **Drives:** the environmental objective(s); default GWP uses `EF_weighted__Global Warming
  Potential (Gwp1000)`. ~60 categories present across **ReCiPe**, **IMPACT World+**, and
  **TRACI** methods.
- **Upstream build:** `combined_lcia_data.csv`, `lcia_results.csv`, `pollutant_flow.csv` carry
  `year` / `method` / `source_file` — harvest these as provenance during Phase B.
- **Source:** `[TO SOURCE]` — literature LCI build + LCA-engine characterization (LiAISON /
  Brightway2). Record the underlying LCI datasets (name + version + year) per process/material.
- **Vintage / method / uncertainty:** `[TO SOURCE]` · **Status: OPEN** (the flagged
  not-yet-publication-grade area — highest Phase B priority).

### 2. Social LCA (`Social_LCA_template.csv`)
- **Drives:** S-LCA objectives — child labour, forced labour, fatal & non-fatal injury,
  unemployment (worker-hour/kg).
- **Source / method / vintage:** `[TO SOURCE]` — database (e.g. PSILCA / SHDB) or expert?
  Record per indicator. **Status: OPEN.**

### 3. Cost — processing & transport (`Cost_Parameters.csv`)
- **Drives:** processing cost, domestic transport cost per (process, location, material).
- **Method:** bottom-up TEA where developed in-house; literature/vendor elsewhere.
- **Source / vintage / uncertainty:** `[TO SOURCE]` — attach the TEA calculation refs (tier
  **C**) and any literature (tier **B**). **Status: OPEN.**

### 4. Tariffs (`Cost_Parameters.csv` → `tariff_cost`)
- **Drives:** cross-border cost penalty.
- **Source:** `[TO SOURCE]` — trade/tariff schedules (e.g. HTS / national schedules), by
  material and lane, with effective year. **Status: OPEN.**

### 5. Shipping distances & rates (`Shipping_Costs.csv`)
- **Drives:** inter-country freight ($/kg); columns include `mode`, `distance_km`.
- **Source:** `[TO SOURCE]` — port-to-port distance reference + freight-rate basis (year, mode).
  **Status: OPEN.**

### 6. Trade topology (`trade_topology.csv`, 192 arcs)
- **Drives:** which routes are physically/commercially allowed.
- **Source:** `[TO SOURCE]` — industry structure / expert judgement; document why the 192-arc
  file is canonical over the 123-arc reconciled variant. **Status: OPEN.**

### 7. Capacity (`Capacity_Template.csv`)
- **Drives:** per-node output ceilings by period.
- **Source:** `[TO SOURCE]` — USGS / industry capacity data / expert build, per node and year.
  **Status: OPEN.**

### 8. Demand & alloy composition (`Demand_Input_Template.csv`)
- **Drives:** hp_magnet demand and Nd/Dy mass ratios; columns include a deployment curve (MW).
- **Source:** `[TO SOURCE]` — deployment scenario (which?) + magnet-composition literature.
  **Status: OPEN.**

### 9. Yield factors (`Yield_Factor.csv`)
- **Drives:** process mass balance (output = yield × input).
- **Source:** `[TO SOURCE]` — process-metallurgy literature / expert, per process. **Status: OPEN.**

### 10. Recovery rates (`Recovery_Rates.csv`)
- **Drives:** end-of-life recovery for reuse / m2m / hydro / pyro / cryo routes.
- **Source:** `[TO SOURCE]` — recycling-process literature / expert. **Status: OPEN.**

---

## Phase B queue (risk × influence)

Ordering combines data **risk** (how provisional a value is) with **influence** from the
sensitivity screens. The COST screen is complete — see
[`data/provenance/sensitivity_cost_v0.json`](data/provenance/sensitivity_cost_v0.json)
(top cost drivers: **Yield −1.80**, **Processing cost +0.87**, Capacity −0.18; env/social/
recovery ≈ 0 for cost). The **GWP** and **S-LCA** screens are pending
(`scenarios/ree_baseline_gwp.yaml`, `scenarios/ree_baseline_social.yaml`) and will promote
whatever drives those objectives.

**Tier 1 — high influence, not yet fully sourced (source first):**
1. **Yield — downstream processes first** (`Yield_Factor.csv`). Per-process screen (all three
   objectives): **magnet manufacturing** (−0.84/−0.75/−0.99) and **chemical transformation /
   alloy** (−0.64/−0.69/−0.86) are the top hotspots, then **molten-salt electrolysis** and
   **metallothermic reduction**, then the acid digestions; upstream mining and recycling are
   low-influence. Source those stage yields to publication grade first. (See
   [`SENSITIVITY_FINDINGS.md`](SENSITIVITY_FINDINGS.md).)
2. **Processing cost / TEA** (`Cost_Parameters.csv`) — second cost driver (+0.87); bottom-up
   TEA plus literature.

**Tier 2 — highest data risk (most provisional; env/social influence pending their screens):**
3. **LCI / LCIA** (`EF_template.csv`) — the underlying LCI datasets behind each factor.
4. **Social / S-LCA** (`Social_LCA_template.csv`) — per-indicator source of record.

**Tier 3 — moderate/low cost influence:**
5. **Capacity** (`Capacity_Template.csv`) — partial binder (−0.18).
6. **Demand** (`Demand_Input_Template.csv`), **Tariffs** & **Transport** (`Cost_Parameters.csv`),
   **Shipping** (`Shipping_Costs.csv`), **Recovery** (`Recovery_Rates.csv`), **Trade topology**
   (`trade_topology.csv`) — low cost influence; audit as capacity allows.

Each item: research and cross-check against citable sources (flag divergences, propose
uncertainty ranges) → maintainer adjudication and source of record → documented change +
golden re-baseline.
