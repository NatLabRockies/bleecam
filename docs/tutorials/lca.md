# LCA guide for Critical Minerals and Materials

ISO 14040 and ISO 14044 define life-cycle assessment as four phases: goal and
scope definition (which fixes the system boundary and functional unit),
life-cycle inventory analysis, life-cycle impact assessment, and interpretation.
This guide walks each phase for critical minerals and materials, shows where
BLEECAM fits, and explains how to pair the LiAISON LCA engine that produces the
impact factors BLEECAM consumes.

One framing point up front: BLEECAM is LCA-integrating, not an LCA tool. The
inventory and impact-assessment phases are performed in a dedicated LCA engine
(LiAISON, or openLCA); BLEECAM defines the system boundary through its
supply-chain network and carries out the interpretation phase as scenario
analysis. Each phase below is a separate section, and the final section covers
pairing LiAISON.

## 1. Goal, scope, and system boundary

ISO 14040 starts by fixing the goal, the functional unit, and the system
boundary — the set of unit processes included in the study. For critical
minerals and materials the boundary is usually one of:

- Cradle-to-gate: from mining through the refined material or component (e.g. a
  finished NdFeB magnet, a GaAs wafer).
- Cradle-to-grave: as above plus the use phase and end-of-life recycling.

A typical functional unit is a delivered quantity of finished product — for
example, 1 kg of NdFeB magnet supplied to U.S. demand, or one semiconductor
wafer.

In BLEECAM, the system boundary is the supply-chain network. The trade topology
(processes, locations, materials) determines which unit processes are inside the
study, and the demand node is the functional unit. Choosing the topology for a
case is, in LCA terms, drawing the system boundary. Two boundary decisions matter
especially for minerals:

- Co-production and allocation. Gallium is a byproduct of bauxite and zinc
  processing, so the burden carried into the gallium chain depends on an
  allocation choice; rare-earth separation yields several oxides from a shared
  feed. How co-products are allocated is a boundary decision made when the
  inventory is built.
- Recycling and recovery. Whether end-of-life recovery is inside the boundary
  (and how recycling credits are handled) sets whether the study is cradle-to-gate
  or cradle-to-grave.

## 2. Life-cycle inventory (LCI) development

The inventory phase compiles the inputs and outputs — energy, reagents, emissions,
intermediate flows — for every unit process inside the boundary. Inventories have
two layers:

- Foreground: technology-specific data for the processes you are studying (energy
  intensity, reagent use, yields), from literature, measurements, or expert
  consultation.
- Background: the upstream markets the foreground draws on (grid electricity,
  bulk chemicals, transport), taken from a life-cycle database such as ecoinvent,
  or from a prospective background when future energy systems are modeled.

Critical minerals make this phase hard: primary data are sparse, often
confidential, and vary by region and route, so proxies and expert judgment are
common. BLEECAM does not build inventories — that work happens in the LCA engine.
What lives in a BLEECAM case is the foreground inventory used to drive that engine
(the files under `.../data/.../lci/`), which use the same column schema LiAISON
expects (see §5), together with documented provenance.

Because inventory data carry licensing obligations, the public release keeps
literature- and expert-derived inventory but redacts values taken directly from
licensed ecoinvent datasets, retaining the dataset selections and flow UUIDs so a
licensed user can reproduce them. The full rationale is in
[Data & provenance](../data_provenance).

## 3. Life-cycle impact assessment (LCIA)

The impact-assessment phase converts the inventory into impact scores:
classification assigns flows to impact categories, and characterization multiplies
each flow by a characterization factor to give a score per category. Method
families such as ReCiPe and TRACI define these factors across midpoint categories —
global warming, human toxicity, water use, acidification, and others.

This phase runs in the LCA engine. LiAISON (built on Brightway2) links the
foreground inventory to the ecoinvent background, performs the characterization,
and emits an LCIA node summary — one row per process, location, flow, method, and
category. BLEECAM consumes the result through its emission-factor (EF) contract: a
table keyed by `(time_period, source, location, material)` with one `EF_…` column
per impact category, defaulting to `EF_weighted__Global Warming Potential
(Gwp1000)`.

BLEECAM applies these characterized factors to the flows it solves for. If the
model routes a flow $f_n$ through node
$n = (\text{period}, \text{process}, \text{location}, \text{material})$ with impact
factor $\text{EF}_n$, the configuration's impact is:

$$
\text{Impact} = \sum_{n} \text{EF}_n \times f_n
$$

This is the same structure BLEECAM uses for cost — only the coefficient changes
from `$/kg` to `kg CO₂e/kg` (or any category). A small illustrative EF slice:

| time_period | source | location | material | EF_weighted__GWP1000 |
|---|---|---|---|---|
| 0 | separation | CN | Nd_oxide | 8.4 |
| 0 | separation | AU | Nd_oxide | 3.2 |

Read row 1 as: producing 1 kg of Nd oxide by separation in CN carries 8.4 kg
CO₂e. Because BLEECAM only applies the factors it is given, the credibility of the
impact score rests on the provenance of this table.

## 4. Scenario analysis

ISO's fourth phase is interpretation: drawing conclusions, finding hotspots, and
testing how robust they are. BLEECAM operationalizes interpretation as scenario
analysis, which is where life-cycle assessment meets supply-chain optimization.
Rather than scoring a single fixed configuration, BLEECAM solves for
configurations and compares them:

- Baseline, disruption, and policy scenarios — for example a supply shock on a
  dominant supplier, or an allied build-out — each solved and scored on the same
  impact categories.
- Hotspots — the per-stage and per-country breakdown of the impact, which shows
  where the footprint concentrates and where intervention would help most.
- Trade-offs — reporting cost and impact together on each configuration, and
  tracing the full cost-versus-impact frontier with the multi-objective
  (AUGMECON2) method (see [Multi-objective methods](../methods_multiobjective)).

Sensitivity analysis then tests how much the conclusions depend on uncertain
inputs, prioritizing which inventory to refine first.

## 5. Pairing the LiAISON tool

LiAISON (Lifecycle Analysis Integration into Scalable Opensource Numerical models)
is NLR's open-source LCA framework, built on Brightway2. It links a foreground
inventory to a background database (ecoinvent) automatically, and can run
prospective LCA — updating the background with Integrated Assessment Model
scenarios through PREMISE to produce temporally explicit impact factors. It is the
first-party engine behind BLEECAM's environmental data. 

### Requirements

- Python 3.9–3.11
- A licensed ecoinvent 3 database (the examples use ecoinvent 3.8, cut-off)
- Brightway2, and `premise` for prospective runs
- For prospective (PREMISE/IAM) runs, an encryption key requested from the LiAISON
  developers

### Install

From a clone of the LiAISON repository, create its conda environment (Miniconda or
Anaconda required). From the repository's `conda/` folder:

```bash
conda env create -f environment_tutorial.yml -n liaison-24
conda activate liaison-24
pip install premise==1.8.1
pip install bw2io==0.8.7        # the bw2io version matched to ecoinvent 3.8
```

Then place your licensed ecoinvent 3.8 (cut-off) datasets under LiAISON's
`data/inputs/ecoinvent/` as the repository README describes. A manual conda route
is documented there if the environment file does not resolve on your platform.

### Define the foreground inventory

This is the inventory from §2. LiAISON reads a foreground-inventory CSV whose
columns are exactly those in a BLEECAM `lci/*.csv` file —
`process, flow, unit, value, year, input, type, process_location,
supplying_location` — plus three bridge files that link your foreground to
ecoinvent:

- `process_bridge` — maps each technosphere input flow to the ecoinvent activity
  that supplies it (best practice: give the ecoinvent code).
- `emission_bridge` — maps biosphere/emission flows to ecoinvent biosphere flows.
- `location_bridge` — maps location names.

A run is configured by a YAML file (see `example1.yaml`–`example3.yaml`) that names
these inputs and sets `scenario_parameters` — base database, functional unit, year,
location, and, for prospective runs, the IAM model and `model_key`.

### Run

```bash
# one-time smoke test, from the repository root
chmod +x test_run.sh
./test_run.sh

# a real run: edit run.sh (DATADIR, CODEDIR, and yaml = your config file), then
chmod +x run.sh
./run.sh
```

On the first run set `read_base_lci_database: True` in the config so LiAISON reads
and caches ecoinvent 3.8; on later runs set it to `False` and the run is much
faster. Results are written to `data/output/` as the LCIA node-level results.

### Hand off to BLEECAM

BLEECAM's adapter turns LiAISON's LCIA node summary into a case-ready EF table.
This step is part of BLEECAM and is stable:

```python
from bleecam.core.lca_import import build_ef_table

result = build_ef_table(
    "data/output/lcia_results.csv",   # LiAISON's tidy LCIA node summary
    time_periods=[0, 1, 2, 3, 4, 5],
    scope="total_life_cycle",
)

# EF table keyed by (time_period, source, location, material) + EF_ columns
result.ef_table.to_csv("EF_template.csv", index=False)

# provenance (methods, databases, source files) travels with the table
print(result.provenance)
```

The adapter expects the node summary's columns
(`scope, process, process_location, flow, lcia_method, lcia_category, value, unit,
database, raw_file`) and maps them onto BLEECAM's
`(time_period, source, location, material)` keys with one `EF_…` column per
category. Drop the resulting `EF_template.csv` into the case's data folder and run
on the environmental objective (`objective: gwp`, or any category the table
provides). Because prospective LiAISON runs are temporally explicit, the same
pipeline can populate period-specific factors rather than replicating a single
static set.

Any engine that emits the same EF columns works (openLCA is the natural fully open
alternative); BLEECAM depends on the contract, not on LiAISON specifically.

## Recap

The four ISO phases map cleanly onto a BLEECAM study: the topology draws the system
boundary and functional unit; LiAISON builds the inventory and runs the impact
assessment; BLEECAM applies the characterized factors as Σ(factor × flow) and
carries out interpretation as scenario analysis across baseline, disruption, and
policy cases. The EF contract is the seam between the LCA engine and the optimizer.
