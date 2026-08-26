# BLEECAM — Positioning & Framing

*Canonical framing for the README, executive materials, and any external description.
Agreed with the PI (S. Khalifa), 2026. Hold this line consistently.*

## One-line

BLEECAM is a **multi-objective optimization framework that benchmarks global
critical-mineral supply chains** across economic, environmental, and social
dimensions — it evaluates and optimizes whole supply-chain *scenarios*, not
single products.

## Fuller statement

BLEECAM is an **optimization-driven benchmarking and evaluation framework for
global critical-mineral and material (CMM) supply chains**. Given a scenario —
baseline, disruption, or policy — it *solves* for the supply-chain configuration
that best meets demand under real-world constraints (capacity, trade topology,
tariffs, yields), and reports integrated **economic (TEA/LCC), environmental
(LCA-derived), and social (S-LCA)** metrics for it, including the multi-objective
trade-off frontier. It benchmarks technologies, routes, and countries against
each other and against state-of-the-art references.

## Why "optimization-driven benchmarking" (not just "benchmarking")

Most benchmarking is retrospective scoring: you hand it fixed configurations and
it grades them. BLEECAM benchmarks **prescriptively** — its engine is
optimization, so it finds the best-achievable configuration under constraints and
quantifies the trade-offs between objectives (e.g., what buying down emissions
costs in dollars, and vice versa). The optimization is the differentiator; the
benchmarking is what it delivers.

## What BLEECAM is NOT — the LCA-tool distinction (hold this line)

BLEECAM is **not an LCA tool**. An LCA tool *computes* life-cycle inventories and
impacts (openLCA, SimaPro, Brightway/LiAISON). BLEECAM **consumes** life-cycle
impact factors as one of its three metric dimensions; it performs no inventory
modeling and no impact characterization.

- Correct terms: **"LCA-informed"**, **"LCA-integrating."**
- Line for colleagues: *"BLEECAM isn't an LCA tool — it's a supply-chain
  optimization and benchmarking framework that integrates life-cycle impact
  factors (from a dedicated LCA engine like LiAISON or openLCA) alongside
  techno-economic and social metrics. The LCA is an input, not the tool."*

## Intent / provenance (from the original proposal)

The goal was never to build another LCA tool. It was to **apply LCA to critical
minerals and establish solid, defensible methods for LCA of CMMs** — alongside
techno-economic and supply-chain analysis — to inform DOE/AMMTO decision-making.

## Engine-agnostic by design

The environmental dimension is supplied via a documented EF (impact-factor)
contract. LiAISON is the first-party, integrated provider; **openLCA** is the
natural fully-open provider; any tool that emits to the contract works. BLEECAM
depends on the contract, never on a specific LCA engine.
