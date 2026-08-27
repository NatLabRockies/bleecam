# BLEECAM Documentation

Benchmarking Life Cycle Environmental, Economic, and Social Metrics for Critical and Advanced Minerals and Materials

:::{admonition} Public beta — v0.1.0-beta.1
:class: warning
BLEECAM is released as a beta for transparency and community feedback. Public
APIs, input data (the "golden inputs"), and numerical results may change between
releases without notice. All outputs are illustrative analytical results, not
decision-grade guidance for policy, investment, or operations — see the
[Disclaimer](disclaimer). Please report problems and suggestions via
[GitHub Issues](https://github.com/NatLabRockies/bleecam/issues).
:::

BLEECAM is an optimization-driven benchmarking and evaluation framework for
global critical-mineral and material (CMM) supply chains, developed at the
National Laboratory of the Rockies (NLR) with funding from the
U.S. Department of Energy's Advanced Materials and Manufacturing Technologies
Office (DOE AMMTO).

Given a scenario — baseline, disruption, or policy — BLEECAM *solves* for the
supply-chain configuration that best meets demand under real-world constraints
(capacity, trade topology, tariffs, yields), and reports integrated economic
(TEA/LCC), environmental (LCA-derived), and social (S-LCA) metrics,
including the multi-objective trade-off frontier.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} 🚀 Get started
:link: quickstart
:link-type: doc
Install BLEECAM and run the rare-earth and gallium baselines in a few commands.
:::

:::{grid-item-card} 🧭 Core concepts
:link: concepts
:link-type: doc
Optimization-driven benchmarking, the three objectives, and the LCA contract.
:::

:::{grid-item-card} 🧪 Case studies
:link: cases/rare_earth
:link-type: doc
Worked rare-earth magnet and gallium wafer supply chains, end to end.
:::

:::{grid-item-card} ➕ Add a material
:link: adding_a_material
:link-type: doc
Benchmark a different mineral — a case YAML and CSVs, no engine changes.
:::
::::

## What BLEECAM is — and is not

BLEECAM is LCA-integrating, not an LCA tool. It *consumes* life-cycle impact
factors as one of its three metric dimensions; it performs no inventory modeling
and no impact characterization. Those factors arrive through a documented
emission-factor contract, from the first-party LiAISON engine or any tool
(e.g. openLCA) that emits to that contract. The optimization is the
differentiator; the benchmarking is what it delivers.

```{toctree}
:maxdepth: 2
:caption: Getting started
:hidden:

installation
quickstart
concepts
```

```{toctree}
:maxdepth: 2
:caption: Tutorials
:hidden:

tutorials/index
```

```{toctree}
:maxdepth: 2
:caption: Case studies
:hidden:

cases/rare_earth
cases/gallium
```

```{toctree}
:maxdepth: 2
:caption: Methods & data
:hidden:

methods_multiobjective
criticality_library
data_provenance
DATA_AUDIT_METHODOLOGY
```

```{toctree}
:maxdepth: 2
:caption: Extending & reference
:hidden:

adding_a_material
api/index
changelog
disclaimer
```

## Citing BLEECAM

If you use BLEECAM in your work, please cite it via the repository's
[`CITATION.cff`](https://github.com/NatLabRockies/bleecam/blob/main/CITATION.cff).
Developed at NLR with funding from DOE AMMTO (NLR Software Record SWR 25-125).
BLEECAM™ is a trademark of the Alliance for Energy Innovation, LLC / NLR.
