# Core concepts

This page explains the model behind BLEECAM: what it optimizes, over what network,
subject to what constraints, and how the three metric dimensions fit together.

## Optimization-driven benchmarking

Most benchmarking is retrospective scoring: you hand it fixed configurations and it
grades them. BLEECAM benchmarks prescriptively — its engine is optimization, so
it finds the best-achievable supply-chain configuration under constraints and
quantifies the trade-offs between objectives (for example, what buying down
emissions costs in dollars, and vice versa). The optimization is the differentiator;
the benchmarking is what it delivers.

## The supply-chain network

A case is a directed flow network. Its building blocks are:

Processes
: Stages of the chain — mining, separation/refining, metallization, alloying,
  component manufacturing, use, recycling.

Locations
: Countries or regions where a process can occur.

Materials
: The substances that flow between processes (ores, oxides, metals, alloys,
  finished components).

Arcs (trade topology)
: The permitted `(process_from, loc_from) → (process_to, loc_to)` links for a
  material. The topology is the feasible graph; the optimizer chooses flows on it.

Demand node
: The finished-product requirement to be met (e.g. NdFeB magnets to the U.S., or
  GaAs/GaN wafers to the U.S.), by period.

The decision variables are the material flows on each arc in each time period
(plus small stock/slack terms). The network — processes, materials, locations, and
arcs — is inferred automatically from your topology file.

## What is optimized

BLEECAM minimizes a single objective at a time (or explores several jointly; see
[multi-objective](#multi-objective-analysis)), subject to demand being met and
supply-chain physics respected. Conceptually, for flows $f_a$ on arcs $a$:

$$
\min_{f \ge 0}\; \sum_{a} c_a \, f_a
\quad\text{s.t.}\quad
\underbrace{\text{mass balance at every (process, location)}}_{\text{yields applied}},\;
\underbrace{\sum f \le \text{capacity}}_{\text{fixed upper bounds}},\;
\underbrace{\text{demand met}}_{\text{per period}} .
$$

Two modeling points worth internalizing:

- Capacity is a fixed exogenous upper bound, not a decision variable. The model
  routes flow within existing capacity; it does not build new capacity. (Capacity
  *expansion* is a natural next step for the framework, not part of the current
  beta.)
- Per-arc cost combines processing cost (charged at the source process),
  domestic transport, cross-border shipping, and tariffs.

## The three objectives

BLEECAM reports and can optimize on three dimensions, all evaluated on the same
solved configuration:

Economic — TEA / LCC
: Total supply-chain cost: processing + transport + shipping + tariffs, from
  fixed per-country techno-economic values.

Environmental — LCA-derived
: Life-cycle impact (GWP by default, or any of ~25 ReCiPe / TRACI categories),
  computed from emission factors supplied through the LCA contract — BLEECAM
  does not characterize impacts itself (see [below](#the-lca-contract)).

Social — S-LCA
: Social risk metrics (e.g. child labor, forced labor, injury) attached to
  processes and locations.

## Multi-objective analysis

BLEECAM supports both single-objective corners (optimize one dimension) and the
full multi-objective trade-off frontier via the AUGMECON2 ε-constraint method,
yielding a Pareto set that shows, for example, the dollar cost of each increment of
avoided emissions. The rationale for AUGMECON2 over naive weighting or lexicographic
ordering is given in [Multi-objective methods](methods_multiobjective).

## The criticality-constraint library

Policy and resilience questions are posed as no-code levers — small,
parameterized constraints you add to a scenario YAML rather than editing Python.
Examples include `max_source_share`, `min_domestic_production`, and `capacity_ramp`.
Browse the full catalogue with `bleecam-lib list`; each lever and its parameters are
documented in [The criticality constraint library](criticality_library).

## The LCA contract

BLEECAM is LCA-integrating, not an LCA tool. The environmental dimension enters
through a documented emission-factor (impact-factor) contract: a table of
characterized impacts per `(process, location, material)`. Any engine that emits to
that contract works — the first-party LiAISON adapter (which carries full
provenance) or a fully open engine such as openLCA. BLEECAM depends on the
contract, never on a specific LCA engine, and performs no inventory modeling or
impact characterization of its own. How the bundled factors were sourced — and what
was redacted for licensing — is covered in [Data & provenance](data_provenance).
