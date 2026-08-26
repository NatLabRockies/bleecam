# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared pytest fixtures and path helpers for the BLEECAM regression suite.

The suite implements a *golden-output* regression pattern: the first time a
case is run on a given machine, its baseline summary is captured to
``tests/golden/<case>.json``. Every subsequent run asserts the current result
matches that baseline within a solver-tolerant relative tolerance.

Because different solvers (ipopt vs. HiGHS) settle on numerically different
optimal vertices of the same LP, objective values are compared with a relative
tolerance and structural invariants (demand fully met, loader clean) are the
hard checks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Repo layout: tests/ is a sibling of src/
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"

# The repo directory itself is named "bleecam". If the repo root or its parent
# is on sys.path, `import bleecam` resolves to the repo root (a namespace dir
# with no cases/) instead of src/bleecam. Purge those shadowing entries, drop
# any namespace 'bleecam' already cached, and pin src/ at the front so the real
# regular package wins — regardless of how pytest was invoked.
for _shadow in (str(REPO_ROOT), str(REPO_ROOT.parent)):
    while _shadow in sys.path:
        sys.path.remove(_shadow)
sys.path.insert(0, str(SRC))
for _m in [m for m in sys.modules if m == "bleecam" or m.startswith("bleecam.")]:
    del sys.modules[_m]
# Eagerly import now — while sys.path is correct — so the resolved src/bleecam
# is cached in sys.modules before pytest re-inserts the shadowing repo-root
# entry ahead of test execution. This locks in the real package for all tests.
import bleecam  # noqa: E402,F401
import bleecam.cases  # noqa: E402,F401
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GOLDEN_DIR.mkdir(exist_ok=True)

# Relative tolerance that absorbs solver-to-solver vertex differences
# (observed ipopt vs HiGHS gap on Gallium ~1.5e-7) while still catching any
# real modeling regression (which moves objectives by >>0.1%).
OBJ_RTOL = 1e-3


def golden_path(case: str) -> Path:
    return GOLDEN_DIR / f"{case}.json"


def load_golden(case: str) -> dict | None:
    p = golden_path(case)
    if p.exists():
        return json.loads(p.read_text())
    return None


def save_golden(case: str, summary: dict) -> None:
    golden_path(case).write_text(json.dumps(summary, indent=2, sort_keys=True))


def assert_or_capture(case: str, summary: dict) -> None:
    """Compare ``summary`` to the stored golden, or capture it on first run.

    On first run (no golden yet) the baseline is written and the test is
    skipped with an explanatory message. On subsequent runs the objective is
    checked within OBJ_RTOL and every structural invariant must match exactly.
    """
    golden = load_golden(case)
    if golden is None:
        save_golden(case, summary)
        pytest.skip(
            f"[{case}] no golden baseline yet — captured {golden_path(case).name}. "
            "Commit it, then this test enforces regressions on future runs."
        )

    # Objective: solver-tolerant relative check.
    g_obj, c_obj = golden["objective"], summary["objective"]
    rel = abs(c_obj - g_obj) / max(abs(g_obj), 1.0)
    assert rel <= OBJ_RTOL, (
        f"[{case}] objective drifted {rel:.2e} (>{OBJ_RTOL:.0e}): "
        f"golden={g_obj:,.4f} current={c_obj:,.4f}"
    )

    # Structural invariants: must match exactly.
    for key in ("demand_fully_met", "blocking_issues", "n_periods"):
        if key in golden:
            assert summary.get(key) == golden[key], (
                f"[{case}] invariant '{key}' changed: "
                f"golden={golden[key]} current={summary.get(key)}"
            )


@pytest.fixture
def regression_check():
    """Return the golden-compare-or-capture helper (avoids importing conftest by name)."""
    return assert_or_capture


@pytest.fixture(scope="session")
def gallium_data_dir() -> Path:
    return SRC / "bleecam" / "cases" / "gallium" / "data" / "gallium"


@pytest.fixture(scope="session")
def ree_data_dir() -> Path:
    return SRC / "bleecam" / "cases" / "rare_earth" / "data"
