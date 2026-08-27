# BLEECAM Multi-Objective Methods

*How BLEECAM optimizes across economic, environmental, and social dimensions —
and a methodological lesson worth stating plainly, because it is easy to get
wrong.*

## The three dimensions

Every BLEECAM objective has the same shape: a per-unit factor applied to network
flow, summed over the supply chain.

- **Economic** — total system cost (processing + transport + shipping + tariff).
- **Environmental** — any LCIA category from the EF table (GWP by default; the
  full ReCiPe/TRACI suite is selectable). Factors come from an LCA engine
  (LiAISON, openLCA, …) via the EF contract; BLEECAM does not compute LCA.
- **Social** — S-LCA indicators (child labor, forced labor, fatal / non-fatal
  injury), in worker-hours per kg.

## The degeneracy problem 

**Minimizing a single impact directly is ill-posed for a supply-chain network.**
Every arc whose source node has a zero (or missing) impact factor is *free* under
that objective — transport arcs, market-mix arcs, and especially recycling loops.
With flow variables unbounded, the optimizer can push unlimited flow through those
free paths: the problem is literally **unbounded** (an impact-free recycling loop
admits infinite circulating flow), or, at best, lands on a degenerate vertex with
billions of kg of meaningless circulation. The minimum *impact value* is correct;
the *network* achieving it is not.

Cost does not have this problem — every arc costs something — so **cost is a
natural regularizer**.

### Worked evidence (Gallium)

| Objective | Optimal value | Naive network total flow | Demand |
|---|---|---|---|
| cost | $816.6M | 1.37M kg | 106k kg |
| GWP (naive) | 26.15M kg CO₂e | 8.3 **billion** kg | 106k kg |
| child labor (naive) | — | **unbounded** (solver error) | 106k kg |

GWP's larger factors (min ~1.2e-2) hid the problem as a huge-but-finite vertex;
child labor's tiny factors (min ~8e-9) exposed it as true unboundedness.

## Why REE never hit this — the lesson

The REE case (`pareto.py`) has the *same* zero-impact line items, yet never blew
up, for two reasons:

1. **It bounds every flow variable** (`bounds=(0, _UB)`). No arc can carry
   infinite flow, so no unbounded ray exists.
2. **It uses AUGMECON2** (augmented epsilon-constraint) — cost-driven with the
   impacts as constraints — which is cost-regularized by construction.

Gallium originally had *neither* (unbounded `flowQ`, and we tried a naive
single-impact objective), which is exactly why it exposed the issue. The fix
brings Gallium to parity with REE.

## What BLEECAM does about it

**1. Bounded flows (both cases).** Gallium bounds `flowQ` at a large multiple of
total demand (`flow_upper_bound()` — data-derived, ~1e6x demand, verified never
to bind), mirroring REE (whose `_UB = 50,000,000 / FLOW_SCALE` is the same idea,
just a hand-picked constant).

**Is the bound fundamental, or a band-aid? (root-cause note.)** It is a
band-aid. The unboundedness is *not* inherent to supply-chain network
optimization — it is a data gap. Two things were checked:

- The recycling loop is modeled correctly: its net yield is 0.1 x 0.95 = 0.095
  per pass (it loses ~90% each cycle), so it *cannot* sustain infinite flow.
  Cycles are not the cause.
- Several upstream capacities are effectively-unlimited placeholders (bauxite CN
  = 87 billion kg, Bayer CN = 93 billion kg). With effectively-infinite capacity
  and zero-impact arcs on some paths, the LP has unbounded directions.

**The physically-correct fix is realistic finite capacities.** Real process
throughput limits would make every flow capacity-bounded and the network
self-bounding — no artificial flow cap needed — and would also improve realism
(no bauxite mine produces 87 billion kg). Until those placeholders are tightened,
the demand-derived flow bound is the safety cap.

Separate the two issues cleanly: **unboundedness** is a capacity-data gap
(removable); **degeneracy** — the need for cost regularization / epsilon-constraint
to get a *unique, sensible* network — is inherent to multi-objective network
optimization and is warranted regardless of capacities.

**2. Two methods, both reported:**

- **Epsilon-constraint / AUGMECON — the reproducible baseline.** Keep cost as the
  driving objective and sweep caps on the impacts, tracing the Pareto frontier.
  Two-objective frontiers live in `core.multiobjective.epsilon_constraint_frontier`;
  the full **3-objective AUGMECON2** (cost × GWP × child labor) lives in
  `cases/gallium/gallium_pareto.py`, using the *same* `PyAugmecon` options as the
  REE case. This is the canonical, reproducible method — consistent across both
  cases and with the Phase 1 report.
- **Lexicographic — for comparison.** Minimize the impact (well-posed via
  normalized factors + a tiny flow regularizer), then minimize cost among
  min-impact solutions. Gives the true impact floor *and* a clean network. Use it
  to compare against the frontier endpoints.

## Results (Gallium, lexicographic corners)

| Dimension | Floor | Least cost to achieve |
|---|---|---|
| Economic (cost) | — | $816,577,036 (baseline) |
| Environmental (GWP) | 26,151,284 kg CO₂e | $851,761,258 |
| Social (child labor) | 613.4 worker-hr | $1,403,063,339 |

Epsilon-constraint frontiers (reproducible baseline):

- **cost ↔ GWP:** $816.6M @ 28.69M kg → $851.8M @ 26.15M kg (−8.8% GWP for +$35M).
- **cost ↔ child labor:** $816.6M @ 11,088 wh → $1.40B @ 613 wh (near-elimination
  is a +72% cost premium).

## Known follow-ups

- **Tighten placeholder capacities (data).** Several upstream Gallium capacities
  are effectively-unlimited placeholders (bauxite CN = 87e9 kg, Bayer CN = 93e9
  kg). Auditing these to realistic throughputs would make the network
  self-bounding (removing the need for the flow bound) and improve realism. It
  will not change the cost-optimal answer (those caps do not bind there).
- **Align the REE flow bound (guarded).** REE still uses the hand-picked
  `_UB = 50000000 / FLOW_SCALE` (in `REE.py` and `pareto.py`). Aligning it to the
  demand-derived form used in Gallium is desirable for consistency, but must be
  done carefully: REE's LP is likely degenerate, so a non-binding bound change
  can move ipopt to a different optimal vertex and shift the REE regression
  golden. Verify on ipopt in isolation before adopting.

## Reproducibility

The AUGMECON/epsilon baseline is the method of record. Single-impact (lexicographic)
runs are a comparison view, not the canonical output. The full 3-objective Gallium
Pareto is produced with `bleecam-ga-pareto` (needs ipopt + pyaugmecon, as the
report was), matching REE's `pareto.py` method exactly.
