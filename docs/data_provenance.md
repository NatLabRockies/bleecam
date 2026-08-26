# Data & provenance

BLEECAM's credibility rests on being explicit about where every input comes from —
and about what could not be redistributed. This page documents the provenance of
each data dimension and the licensing decisions made for the public beta.

:::{admonition} Beta data status
:class: note
The bundled environmental and social factors are under active refinement and should
be treated as **provisional** pending finalization. The optimization machinery is
reproducible independent of the specific factor values.
:::

## Trade topology

The feasible supply-chain graph (which processes, locations, and arcs exist) is
compiled from public primary sources, principally the **USGS Mineral Commodity
Summaries** for the relevant commodities and **U.S. Department of Energy** supply-
chain assessments. The topology files (`trade_topology.csv` for rare earth,
`trade_topology_ga.csv` for gallium) cite these sources directly; no arc depends on
proprietary or unattributed data.

## Techno-economic (cost) data

Processing costs are fixed per-country techno-economic values by
`(process, material, location)`, combined at solve time with domestic transport,
cross-border shipping, and tariffs. Because these values are fixed, a change in a
reported per-tonne cost reflects a change in **routing** (which countries and
processes the optimizer selected), not a change in the underlying TEA value.

## Environmental (LCA) data — licensing and redaction

The environmental dimension is delivered as characterized impact factors through the
[LCA contract](concepts.md#the-lca-contract). The underlying life-cycle inventories
were assembled from literature, expert judgment, and — where no other source
existed — background datasets. This raises a redistribution question, handled as
follows for the public release:

Literature- / expert-derived inventory — **retained**
: Where inventory values come from published literature or expert consultation
  (including the rare-earth inventory, which was extracted from primary literature
  and then *mapped* to ecoinvent flow UUIDs for characterization), the values are
  kept in the repository. These are the project's own data.

ecoinvent-sourced inventory values — **redacted**
: Where a value is taken directly from a licensed **ecoinvent** dataset (e.g. a
  background "black-box" proxy for an upstream process), the numeric value is
  **removed** and replaced with a redaction marker. ecoinvent's license does not
  permit redistribution of its inventory data.

Reproducibility preserved
: For every redacted row, the **ecoinvent dataset selection and flow UUID are kept**,
  along with the accompanying comments. A user with their own valid ecoinvent
  license can therefore reconstruct the exact values from the retained UUIDs and
  selections — the modeling choices are transparent even though the licensed numbers
  are not shipped.

Characterized results (LCIA) — **shareable**
: Aggregated, characterized impact results (the emission-factor contract that
  BLEECAM actually consumes) are shareable under the applicable terms and are
  included so results are runnable out of the box.

The full audit trail of these decisions is in
[Data audit methodology](DATA_AUDIT_METHODOLOGY).

## Social (S-LCA) data

Social-risk factors (child labor, forced labor, injury, and related indicators) are
attached per `(process, location, material)` through the social-LCA template and
follow the same contract pattern as the environmental factors.

## Reproducing the redacted factors

1. Obtain a valid **ecoinvent** license (matching the version noted in the LCI
   comments).
2. For each redacted row, look up the retained **dataset selection + flow UUID** in
   your ecoinvent copy to recover the inventory value.
3. Re-run the characterization (via LiAISON or openLCA) to regenerate the emission-
   factor contract, then run BLEECAM as usual.

This keeps the public artifact honest about licensing while leaving the analysis
fully reproducible for licensed users.
