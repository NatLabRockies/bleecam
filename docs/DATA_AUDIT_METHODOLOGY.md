# BLEECAM Data Audit Methodology

*How BLEECAM input data is traced, versioned, and made defensible for public
release. This is the governing process; per-case source documentation lives in
each case's `DATA_SOURCES.md`, and machine-readable provenance in
`<case>/data/provenance/`.*

---

## 1. Purpose

Every number that enters a BLEECAM model must be **traceable to a citable primary
source, a named expert judgement, or a documented calculation.** The audit makes
that true, records the uncertainty of each input, and does so **without changing
the input files or the golden results until a change is deliberate and documented.**

Two downstream deliverables depend on this audit: the dashboard's *real vs.
provisional* provenance badges, and WS4's *uncertainty* propagation (the ranges
recorded here become the input distributions for the Sobol analysis).

## 2. Non-negotiable principles

1. **No value is self-certifying.** A value is either **SOURCED** — it traces to a
   citation, a named expert judgement, or a documented calculation — or **OPEN**
   (source pending, a release blocker). Provisional or automatically populated values
   carry no provenance and remain OPEN until a source of record is attached.
2. **Reproducibility ≠ validity.** The golden tests certify that the code
   reproduces the same output from the same inputs. They do **not** certify the
   numbers. Sourcing will change some values — and the golden *should* move when it
   does (see §6).
3. **Additive only.** The audit never edits the input CSVs. Provenance lives in a
   parallel layer (`data/provenance/`) and in `DATA_SOURCES.md`. Inputs change only
   via a deliberate, documented version bump.
4. **Always reversible.** At any moment we can verify against, and revert to, the
   frozen **v0** baseline (§6).

## 3. The provenance schema

Recorded per **`(table, field, source-cluster)`** — the coarsest granularity that
is still accurate (see §4), with per-key overrides only where a cell has a distinct
origin:

| Field | Meaning |
|---|---|
| `table` / `field` | which input and column |
| `key_selector` | which rows this record covers (e.g. `material in [Nd,Dy]`, or `*`) |
| `role_in_model` | what it drives (cost, yield, GWP/EF, S-LCA, capacity, topology, demand, recovery) |
| `source` | citation / dataset (name + version) / named expert / calculation ref |
| `source_type` | `peer_reviewed` · `dataset` · `gov` · `gray_literature` · `expert` · `bottom_up_TEA` |
| `vintage` | data year |
| `method` | how the value was derived (measured, modeled + which model, literature, estimated) |
| `units` | unit + consistency check |
| `status` | **SOURCED** or **OPEN** |
| `confidence` | for SOURCED only: **A** peer-reviewed/authoritative · **B** gov/industry/gray · **C** documented expert estimate or bottom-up TEA |
| `uncertainty` | range (min/max), ±%, or distribution — feeds WS4; blank while OPEN |
| `validation` | reconciled? cross-checked against an independent source? open issue? |
| `notes` | assumptions, caveats, and process notes (e.g. "provisionally populated, source pending") |

## 4. Granularity rule (so the audit does not balloon)

Provenance clusters: most factors of one type from one method share one source.
Audit at `(table, field, source-cluster)`, not per cell — a single record can cover
thousands of rows. Add per-key overrides only where a specific value genuinely has a
different origin. This is the difference between a bounded audit and an infinite one.

## 5. Canonical-file resolution (step zero of any case)

Before auditing values, pin **which file the model actually consumes** and retire or
clearly mark the rest. Duplicated or stale files are themselves a provenance hazard.
(For REE, this is already resolved — see `rare_earth/DATA_SOURCES.md`.)

## 6. Data versioning & walk-back protocol

The frozen starting state is **v0 — provisional but reproducible.**

- **v0 anchor:** `<case>/data/provenance/baseline_v0.sha256` (checksums of every input
  file) plus the recorded golden values. Verify anytime with `sha256sum -c
  baseline_v0.sha256`; a mismatch means an input drifted from step zero.
- **Snapshot:** tag the repository state, e.g. `git tag ree-data-v0`, so the entire
  step-zero state is one command away.
- **Every correction is a documented change:** an entry in the case's data changelog
  recording the field, the **source**, the **before/after** value, the rationale, and
  the resulting **golden delta**. Then re-run and update the golden to `v1`, `v2`, …
- **Walk back anytime:** `git checkout ree-data-v0 -- <data paths>` (or revert the
  change commit), then `sha256sum -c baseline_v0.sha256` to confirm you are exactly at
  step zero. Nothing changes silently; the golden is a tripwire, not a truth.

## 7. Roles

- **Research & verification:** identify and *verify* citable sources, cross-check each
  placed value against published ranges, flag divergences, and inventory the mechanical
  fields (coverage, units, ranges). Where no source is found, the value is marked
  **OPEN** — never invented.
- **Adjudication & sign-off (maintainers):** attach the source of record and sign off
  the confidence tier and uncertainty. Bottom-up TEA and expert judgements are
  documented as **C** with their calculations and assumptions.

## 8. Phased plan

- **Phase A — framework (this step):** lock this methodology, stand up
  `DATA_SOURCES.md` and `data/provenance/`, freeze **v0**, and build the
  auto-inventory tool that pre-fills the mechanical fields.
- **Phase B — audit by category (the long part):** LCI/LCIA + social first (highest
  risk), then cost/TEA, tariffs, shipping distances, topology, capacity, demand,
  yield, recovery. Per category: research and cross-check → maintainer adjudication →
  documented change + golden re-baseline.
- **Phase C — consolidate for release:** complete `DATA_SOURCES.md`, close all
  **OPEN** items or record them as explicit, bounded limitations, finalize the
  uncertainty ranges (hand off to WS4), and publish the re-baselined golden.

## 9. Release acceptance criteria

A case is release-ready on data grounds when: every consumed input field is
**SOURCED** with a confidence tier and (where reasonable) an uncertainty range, or is
recorded as an explicit known limitation; `DATA_SOURCES.md` is complete; and the
golden is re-baselined and versioned with a full changelog back to v0.
