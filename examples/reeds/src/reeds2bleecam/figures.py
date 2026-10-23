"""Report figures for the ReEDS x BLEECAM prototype.

Three figures (see PROTOTYPE_BRIEF.md report outline):
  1. REE demand by energy scenario  — the wind story (NdFeB new-build trajectory).
  2. BLEECAM supply-chain response  — cost, GWP, import / China exposure.
  3. Supply gap                      — where magnet demand outruns the supply chain.

build_figures() reads the CSVs compare() writes (comparison_summary.csv,
comparison_by_period.csv) plus the REE demand it recomputes from the stub, and saves PNGs.
"""
from __future__ import annotations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import pandas as pd

from .bridge import load_reeds, capacity_to_ree, DATA, OUTPUTS

# consistent, colourblind-safe scenario palette (stub names + real Standard-Scenarios pair)
SCEN_COLOR = {
    "Reference": "#4C72B0", "HighRE": "#DD8452",
    "Mid_Case": "#4C72B0", "Mid_Case_100by2035": "#DD8452",
}
_GREY = "#444444"


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def fig_ree_demand(scenarios, stub_path, ax, loader=load_reeds, years=None):
    """NdFeB new-build demand trajectory by ReEDS year (tonnes) — the wind story."""
    for s in scenarios:
        cap = loader(stub_path, s)
        if years is not None:
            cap = cap[cap["year"].isin(years)].copy()
        ree = capacity_to_ree(cap)
        d = ree[ree["ndfeb_kg"] > 0]
        ax.plot(d["year"], d["ndfeb_kg"] / 1000.0, marker="o", linewidth=2.4,
                color=SCEN_COLOR.get(s, _GREY), label=s, zorder=3)
    _style(ax)
    ax.set_title("REE demand by energy scenario", fontweight="bold", loc="left")
    ax.set_xlabel("ReEDS year")
    ax.set_ylabel("NdFeB new-build demand (tonnes / interval)")
    ax.legend(frameon=False)


def fig_supply_chain(summary, ax_triplet):
    """BLEECAM response: cost ($B), GWP (Mt CO2e), import & China share (%)."""
    scen = summary["scenario"].tolist()
    colors = [SCEN_COLOR.get(s, _GREY) for s in scen]
    x = range(len(scen))

    ax0, ax1, ax2 = ax_triplet
    ax0.bar(x, summary["bleecam_cost_usd"] / 1e9, color=colors, zorder=3)
    ax0.set_title("Supply-chain cost", fontweight="bold", loc="left")
    ax0.set_ylabel("Total cost ($ billion)")

    ax1.bar(x, summary["gwp_total_kgco2e"] / 1e9, color=colors, zorder=3)
    ax1.set_title("Life-cycle GWP", fontweight="bold", loc="left")
    ax1.set_ylabel("GWP (Mt CO₂e)")

    width = 0.38
    ax2.bar([i - width / 2 for i in x], summary["import_share"] * 100, width,
            color=colors, zorder=3, label="Imported")
    ax2.bar([i + width / 2 for i in x], summary["china_share"] * 100, width,
            color=colors, alpha=0.5, zorder=3, label="From China")
    ax2.set_title("Import dependence", fontweight="bold", loc="left")
    ax2.set_ylabel("Share of magnet supply (%)")
    ax2.legend(frameon=False, fontsize=8)

    for ax in ax_triplet:
        _style(ax)
        ax.set_xticks(list(x))
        ax.set_xticklabels(scen)


def fig_supply_gap(by_period, ax):
    """Supply gap (required - delivered magnet) by model period, per scenario."""
    scen = list(by_period["scenario"].unique())
    periods = sorted(by_period["time_period"].unique())
    width = 0.8 / max(len(scen), 1)
    for i, s in enumerate(scen):
        sub = by_period[by_period["scenario"] == s].set_index("time_period").reindex(periods)
        offs = [p + (i - (len(scen) - 1) / 2) * width for p in range(len(periods))]
        ax.bar(offs, sub["supply_gap_kg"].fillna(0) / 1000.0, width,
               color=SCEN_COLOR.get(s, _GREY), label=s, zorder=3)
    _style(ax)
    ax.set_title("Supply gap: unmet magnet demand", fontweight="bold", loc="left")
    ax.set_xlabel("BLEECAM model period")
    ax.set_ylabel("Unmet demand (tonnes NdFeB)")
    ax.set_xticks(range(len(periods)))
    ax.set_xticklabels(periods)
    ax.legend(frameon=False)


def build_figures(scenarios=("Reference", "HighRE"), out_root: str | Path = OUTPUTS,
                  stub_path: str | Path = DATA / "reeds_stub_capacity.csv",
                  figdir: str | Path | None = None, loader=load_reeds,
                  years=None, suffix: str = "") -> list[Path]:
    """Render all three report figures. Expects compare() to have written the comparison CSVs.

    loader/years feed the demand-trajectory figure (fig1) the same source compare() used.
    suffix is appended to filenames (e.g. '_real') to keep stub and real figures side by side.
    """
    scenarios = list(scenarios)
    out_root = Path(out_root)
    figdir = Path(figdir) if figdir else Path(__file__).resolve().parents[2] / "report" / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    summary = pd.read_csv(out_root / "comparison_summary.csv")
    by_period = pd.read_csv(out_root / "comparison_by_period.csv")
    saved = []

    f1, a1 = plt.subplots(figsize=(7, 4.5))
    fig_ree_demand(scenarios, stub_path, a1, loader=loader, years=years)
    f1.tight_layout(); p1 = figdir / f"fig1_ree_demand{suffix}.png"; f1.savefig(p1, dpi=150); plt.close(f1)
    saved.append(p1)

    f2, a2 = plt.subplots(1, 3, figsize=(12, 4))
    fig_supply_chain(summary, a2)
    f2.suptitle("BLEECAM supply-chain response", fontweight="bold", x=0.02, ha="left")
    f2.tight_layout(); p2 = figdir / f"fig2_supply_chain{suffix}.png"; f2.savefig(p2, dpi=150); plt.close(f2)
    saved.append(p2)

    f3, a3 = plt.subplots(figsize=(7, 4.5))
    fig_supply_gap(by_period, a3)
    f3.tight_layout(); p3 = figdir / f"fig3_supply_gap{suffix}.png"; f3.savefig(p3, dpi=150); plt.close(f3)
    saved.append(p3)

    return saved
