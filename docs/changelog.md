# Changelog

All notable changes to BLEECAM are recorded here. The project follows
[semantic versioning](https://semver.org/) with pre-release tags during beta.

## v0.1.0-beta.1 — 2026-08-26

**Initial public beta.** First public release of BLEECAM as an optimization-driven
benchmarking framework for critical-mineral supply chains.

Included
: - Two demonstrated case studies: rare-earth permanent magnets (Nd/Dy) and gallium
    semiconductor wafers (GaN/GaAs).
  - Multi-objective optimization: single-objective corners and AUGMECON2 Pareto
    frontiers.
  - No-code criticality-constraint library and scenario runner (`bleecam-run`,
    `bleecam-lib`).
  - Engine-agnostic LCA integration via the emission-factor contract.
  - Golden-output regression tests for both cases.

Data
: - ecoinvent-licensed inventory values are redacted, with dataset selections and
    flow UUIDs retained for reproducibility; literature-derived inventory is
    included. See [Data & provenance](data_provenance).

Notes
: - Public APIs, input data, and numerical results may change between releases
    without notice. Outputs are illustrative analytical results, not decision-grade
    guidance — see the [Disclaimer](disclaimer).

Distributed under AGPL-3.0-or-later. Developed at the National Laboratory of the
Rockies with funding from DOE AMMTO (NLR Software Record SWR 25-125).
