# Installation

BLEECAM is a Python package (Python ≥ 3.10) built on a [Pyomo](https://www.pyomo.org/)
optimization core.

## Install from source

```bash
git clone https://github.com/NatLabRockies/bleecam.git
cd bleecam

python -m pip install -e .            # core install (Pyomo, pandas, HiGHS, ...)
python -m pip install -e ".[viz]"     # + plotting (matplotlib, pycirclize, Pillow)
python -m pip install -e ".[test]"    # + pytest, SALib (for the test/sensitivity suite)
```

The editable install (`-e`) is recommended so that the bundled case data and the
console entry points resolve against your working tree.

## Solvers

BLEECAM selects a math-programming solver automatically, but the two cases have
different needs:

```{list-table}
:header-rows: 1

* - Case
  - Model type
  - Solver
* - **Gallium** (and other linear cases)
  - LP / MILP
  - **HiGHS** — bundled as the `highspy` pip wheel, no system binary required. Works out of the box.
* - **Rare earth** (nonlinear terms) and **Pareto** runs
  - NLP
  - **ipopt** — installed separately (it is not a pip wheel).
```

The simplest way to obtain `ipopt` is via conda:

```bash
conda install -c conda-forge ipopt
```

Any Pyomo-visible solver on your `PATH` (GLPK, CBC, …) can also be used through
BLEECAM's auto-selection.

## Verify

```bash
python -c "import bleecam; print('BLEECAM import OK')"
bleecam-lib list          # prints the criticality-constraint library
pytest                    # runs the golden-output regression suite (needs [test])
```

If `bleecam-lib` prints the lever catalogue and `pytest` passes its golden tests
for both cases, your environment is ready. Continue to the [Quickstart](quickstart).
