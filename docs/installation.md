# Installation

BLEECAM is a Python package (Python ≥ 3.10) built on a [Pyomo](https://www.pyomo.org/)
optimization core. Installing it takes two steps: install the package, then make sure a
math-programming **solver** is available. The package cannot solve a model without one.

## 1. Install the package

```bash
python -m pip install bleecam==0.1.0b1     # the current beta (pinned)
# or, for the latest published release:
python -m pip install bleecam
```

This pulls in the core dependencies (Pyomo, pandas, NumPy, SciPy, pyaugmecon) **and the
bundled HiGHS solver** (`highspy`), so the linear cases work immediately — see the next
section for the nonlinear case.

Optional extras:

```bash
python -m pip install "bleecam[viz]"       # + plotting (matplotlib, pycirclize, Pillow)
python -m pip install "bleecam[test]"       # + pytest, SALib (test / sensitivity suite)
python -m pip install "bleecam[viz,test]"   # both
```

## 2. Install a solver (required)

BLEECAM auto-selects any Pyomo-visible solver on your `PATH`. The two cases have different
needs:

```{list-table}
:header-rows: 1

* - Case
  - Model type
  - Solver
* - Gallium (and other linear cases)
  - LP / MILP
  - **HiGHS** — installed automatically with the package as the `highspy` pip wheel. No
    system binary, nothing extra to do. Works out of the box.
* - Rare earth (nonlinear terms) and Pareto runs
  - NLP
  - **ipopt** — required, and installed separately (it is not a pip wheel).
```

If you only run the gallium / linear cases, step 1 already gave you a working solver and you
can skip ahead to Verify. To run the **rare-earth case or any Pareto run**, install `ipopt`.
The simplest route is conda:

```bash
conda install -c conda-forge ipopt
```

Any other Pyomo-visible solver on your `PATH` (GLPK, CBC, …) is also picked up by BLEECAM's
auto-selection, so those are valid alternatives to ipopt for the linear cases.

## Install from source (for development)

If you want to modify BLEECAM or run against the bundled working tree, install editable from
a clone instead of from PyPI:

```bash
git clone https://github.com/NatLabRockies/bleecam.git
cd bleecam
python -m pip install -e ".[viz,test]"
```

The editable install (`-e`) resolves the bundled case data and console entry points against
your working tree. You still need a solver (step 2).

## 3. Verify

```bash
python -c "import bleecam; print('BLEECAM import OK')"
bleecam-lib list          # prints the criticality-constraint library
bleecam-ga --help         # linear (gallium) case — uses bundled HiGHS
pytest                    # golden-output regression suite (needs [test])
```

If `bleecam-lib` prints the lever catalogue and `bleecam-ga` runs, your linear-case setup is
ready. If you installed `ipopt`, confirm the nonlinear case finds it:

```bash
bleecam-ree --help
```

Continue to the [Quickstart](quickstart).
