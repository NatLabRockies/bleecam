# Rare-Earth Case — Sensitivity Findings (data v0)

*Ranks inputs by influence on each objective to (1) prioritise the data audit
(Phase B in [`DATA_SOURCES.md`](DATA_SOURCES.md)) and (2) surface decision-grade RD&D
investment targets. Screen-first OAT elasticities at data **v0**; the full variance-based
(Sobol) analysis follows once the audit sets credible input ranges.*

**Method.** OAT elasticity — each factor is scaled **+10%** in a temp copy of the data and
the model is re-solved (ipopt); elasticity = percent change in the objective per percent
change in the input (sign = direction). Non-destructive: input files and the golden are
never touched. One screen per objective. Regenerate with `bleecam-sensitivity`.

---

## Headline — Yield is the universal hotspot

Aggregate factor screen, elasticities by objective (baselines, model units:
cost `410,102` · GWP `291,907` · S-LCA `7.14`):

| Factor group | Cost | GWP | S-LCA |
|---|---:|---:|---:|
| **Yield** | **−1.80** | **−2.03** | **−2.54** |
| Objective's own factor | processing cost **+0.87** | GWP factors **+0.98** | child-labour **+0.78** |
| Capacity | −0.18 | −0.04 | −0.11 |
| Magnet demand | +0.05 | +0.04 | +0.04 |
| Tariffs / Transport / Shipping / Recovery | ≈ 0 | ≈ 0 | ≈ 0 |

**Reading.** Yield dominates *every* objective — it sets the upstream throughput required
per magnet and **compounds across the multi-stage chain** (social elasticity −2.5, i.e.
super-unit). Each objective's own factor is the clear second. Cost/tariff/shipping/recovery
are second-order for the environmental and social answers.

Snapshot: [`data/provenance/sensitivity_cost_v0.json`](data/provenance/sensitivity_cost_v0.json).

---

## Which process? — per-process yield disaggregation

Aggregate "Yield" is not fundable; a **specific process's yield** is. The harness supports a
`where` row-filter, so each process becomes its own factor
(spec: [`sensitivity_yield_by_process.yaml`](sensitivity_yield_by_process.yaml)). Run:

```bash
bleecam-sensitivity scenarios/ree_baseline.yaml \
  --factors src/bleecam/cases/rare_earth/sensitivity_yield_by_process.yaml \
  --delta 0.1 --json ree_yield_by_process_cost.json
# repeat with ree_baseline_gwp.yaml / ree_baseline_social.yaml
```

### REE per-process yield — results (all three objectives)

| Process yield | Cost | GWP | S-LCA |
|---|---:|---:|---:|
| **Magnet manufacturing** | **−0.84** | **−0.75** | **−0.99** |
| **Chemical transformation (NdFeB alloy)** | **−0.64** | **−0.69** | **−0.86** |
| Molten-salt electrolysis (Nd metal) | −0.24 | −0.46 | −0.71 |
| Metallothermic reduction (Dy metal) | −0.33 | −0.09 | −0.05 |
| Sulfuric acid digestion | −0.13 | −0.11 | −0.19 |
| Beneficiation | −0.02 | −0.10 | −0.01 |
| Clay refining | ≈0 | −0.05 | ≈0 |
| Mining, clay mining, all recycling routes | ≈0 | ≈0 | ≈0 |

**Reading.** Yield losses **closest to the finished magnet** cost the most — they discard all
upstream value/burden already invested. **Magnet manufacturing** and **alloy (chemical
transformation)** are the universal hotspots across cost, GWP, and social. Objective-specific
nuance: **metallothermic reduction (Dy)** spikes for *cost* (Dy metal is expensive);
**molten-salt electrolysis (Nd)** spikes for *GWP/social* (energy-intensive). Upstream mining
and recycling yields barely move any objective at baseline.

*(Mechanism first validated on gallium: `wafer_market_mix −0.91`, `Wafer manufacturing −0.06`.)*

### Parameter drill-down — magnet manufacturing

Screening every parameter *within* the #1 process (GWP shown; cost/social analogous):

| Parameter (magnet mfg) | GWP elasticity |
|---|---:|
| **Yield** | **−0.75** |
| GWP (emission) factor | +0.19 |
| Capacity | −0.02 |
| Processing cost / transport / social | ≈ 0 |

Even inside the hotspot process, **yield is the lever** — larger than the emission factor
itself. The actionable target is magnet-manufacturing *yield*.

### Resolution boundary — a decision-grade data gap

The natural next question is finer still: *which sub-step* of magnet manufacturing (hydrogen
decrepitation, jet milling, pressing, sintering, machining, coating) drives the yield loss?
BLEECAM cannot resolve that today — and the reason is itself a finding:

- The model treats **magnet manufacturing as a single node** (one yield, one EF, one cost).
- Published LCI / EF data for NdFeB magnet production is typically reported **gate-to-gate for
  the whole magnet shop**, not per sub-step.

Sub-step sensitivity is therefore bounded by **data resolution, not the tool** — a model is
only as sharp as its data. This converts into a fundable recommendation: *the highest-leverage
data investment is sub-step LCI and yield characterization for NdFeB magnet manufacturing*
(decrepitation / milling / sintering). If that data can be built (bottom-up process engineering),
magnet manufacturing is decomposed into sub-process nodes and re-screened — at which point
BLEECAM resolves jet-milling vs sintering directly.

---

## Audit implications (Phase B priority)

1. **Yield — downstream processes first.** Priority from the per-process screen:
   **magnet manufacturing** and **chemical transformation (alloy)** yields (top hotspot on
   every objective), then **molten-salt electrolysis** and **metallothermic reduction**, then
   the acid digestions. Upstream mining and recycling yields are low priority (low influence).
   Source per-stage yields from process-metallurgy literature / expert, with uncertainty ranges.
2. **LCI/LCIA and Social factors** — highest data risk *and* each is the #2 driver of its own
   objective.
3. **Capacity, demand** — moderate; cost/tariff/shipping/recovery are low-influence.

## Decision-grade framing

Per-process yield elasticities translate directly into RD&D value: *"raising yield at
process X by 10% cuts [cost / GWP / social] by Y%."* That quantified, sourced statement is
the basis for a DOE funding-call priority — the core BLEECAM value proposition, and the
reason to audit the hotspot data to publication grade first.
