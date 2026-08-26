#!/usr/bin/env python3
"""
lcia_pipeline_full.py
=====================
Builds a single wide EF_Template_full.csv containing all three LCIA methods:
  - ReCiPe    (18 categories)  → columns: EF_RECIPE__<category>
  - IMPACT World+ (26 cats)    → columns: EF_IW__<category>
  - TRACI2.1  (9 non-"No Lt")  → columns: EF_TRACI__<category>

The file keeps the same row structure as EF_Template.csv:
    time_period | source | location | material | ... EF columns ...

REE.py compatibility
--------------------
REE.py currently reads one column to build ef_factor:

    ef_factor = {
        (int(row['time_period']), str(row['source']),
         str(row['location']), str(row['material'])):
            row['EF_weighted__Global Warming Potential (Gwp1000)']   # <-- change this
        for _, row in emission_factor_df.iterrows()
    }

To switch objective method, change ONLY that column name to any of:

    ReCiPe GWP (1000yr):
        EF_RECIPE__Global Warming Potential (Gwp1000)

    IMPACT World+ climate change — short-term fossil (best GWP100 analogue):
        EF_IW__Climate change, short term, fossil

    IMPACT World+ climate change — long-term fossil:
        EF_IW__Climate change, long term, fossil

    IMPACT World+ water scarcity:
        EF_IW__Water scarcity

    TRACI2.1 GWP100:
        EF_TRACI__Global Warming Potential (Gwp100)

    ... any other column in the file.

IMPACT World+ behaviour notes
------------------------------
- 26 midpoint categories covering climate, toxicity, land, water, energy.
- "Climate change, short term, fossil" is the closest IW+ analogue to ReCiPe GWP1000
  (short-term 100yr characterisation, fossil-only component).
- "CO2 uptake" categories are NEGATIVE (carbon sequestration credits) — correct LCA sign.
- "Adaptation to resources services loss" and "Resources services deficit" are
  resource-related endpoint-style metrics (MJ and kg deficit), useful for criticality.
- All values are per kg of functional unit (same as ReCiPe).

Pending locations
-----------------
BR, CA, EE, MM, MY have no HPC results yet → "Not available" in all EF columns.
When results arrive, just add them to the compiled CSV and rerun this script.

Usage
-----
    python lcia_pipeline_full.py --lcia lcia_resultsALL_ACTIVITIES_ecoinvent_2020_SSP2-Base_ALL_LOCATIONS.csv --out  EF_Template_full.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Category definitions per method
# ─────────────────────────────────────────────────────────────────────────────

RECIPE_CATEGORIES = [
    "Agricultural Land Occupation (Lop)",
    "Fossil Fuel Potential (Ffp)",
    "Freshwater Ecotoxicity Potential (Fetp)",
    "Freshwater Eutrophication Potential (Fep)",
    "Global Warming Potential (Gwp1000)",
    "Human Toxicity Potential (Htpc)",
    "Human Toxicity Potential (Htpnc)",
    "Ionising Radiation Potential (Irp)",
    "Marine Ecotoxicity Potential (Metp)",
    "Marine Eutrophication Potential (Mep)",
    "Ozone Depletion Potential (Odpinfinite)",
    "Particulate Matter Formation Potential (Pmfp)",
    "Photochemical Oxidant Formation Potential: Ecosystems (Eofp)",
    "Photochemical Oxidant Formation Potential: Humans (Hofp)",
    "Surplus Ore Potential (Sop)",
    "Terrestrial Acidification Potential (Tap)",
    "Terrestrial Ecotoxicity Potential (Tetp)",
    "Water Consumption Potential (Wcp)",
]

IW_CATEGORIES = [
    "Adaptation to resources services loss (beta)",
    "Climate change, long term, CO2 uptake",
    "Climate change, long term, biogenic",
    "Climate change, long term, fossil",
    "Climate change, long term, land transformation",
    "Climate change, short term, CO2 uptake",
    "Climate change, short term, biogenic",
    "Climate change, short term, fossil",
    "Climate change, short term, land transformation",
    "Fossil and nuclear energy use",
    "Freshwater acidification",
    "Freshwater ecotoxicity",
    "Freshwater eutrophication",
    "Human toxicity cancer",
    "Human toxicity non-cancer",
    "Ionizing radiations",
    "Land occupation, biodiversity",
    "Land transformation, biodiversity",
    "Marine eutrophication",
    "Mineral resources use",
    "Ozone layer depletion",
    "Particulate matter formation",
    "Photochemical ozone formation",
    "Resources services deficit (beta)",
    "Terrestrial acidification",
    "Water scarcity",
]

# TRACI2.1: exclude "No Lt" variants (short-term only) to keep one row per category
TRACI_CATEGORIES = [
    "Acidification Potential (Ap)",
    "Ecotoxicity: Freshwater",
    "Eutrophication Potential",
    "Global Warming Potential (Gwp100)",
    "Human Toxicity: Carcinogenic",
    "Human Toxicity: Non-Carcinogenic",
    "Maximum Incremental Reactivity (Mir)",
    "Ozone Depletion Potential (Odp)",
    "Particulate Matter Formation Potential (Pmfp)",
]

# Column prefixes
RECIPE_PREFIX = "EF_RECIPE__"
IW_PREFIX     = "EF_IW__"
TRACI_PREFIX  = "EF_TRACI__"

# Backward-compatible alias: the column REE.py currently reads
# We write BOTH the new-prefix column AND this alias pointing to the same value.
COMPAT_COL = "EF_weighted__Global Warming Potential (Gwp1000)"
COMPAT_SRC = "EF_RECIPE__Global Warming Potential (Gwp1000)"   # alias source

# ─────────────────────────────────────────────────────────────────────────────
# Process mapping: LCA process name → (BLEECAM source, BLEECAM material)
# ─────────────────────────────────────────────────────────────────────────────

# Single-process mappings: one HPC process → one BLEECAM (source, output material)
# Note: material is always the OUTPUT of the BLEECAM process, not its input feedstock.
# SAD and HCAD NdOx/DyOx outputs are handled via AVERAGING_GROUPS below.
PROCESS_MAP = {
    # Mining
    "BM Mining":
        ("mining",                       "bastnasite"),
    "Monazite Mining":
        ("mining",                       "monazaite"),
    "IAC Mining & Leaching":
        ("clay mining",                  "ion adsorption clay"),
    # Beneficiation — flurocarbonate averaged with BM Beneficiation in AVERAGING_GROUPS
    "Bastanasite Beneficiation":
        ("beneficiation",                "flurocarbonate"),
    "Monazite Beneficiation":
        ("beneficiation",                "phosphate"),
    # Clay refining (IAC route)
    "IAC SX & Calcination [allocated to dysprosium oxide]":
        ("clay refining",                "dysprosium_oxide"),
    "IAC SX & Calcination [allocated to neodymium oxide]":
        ("clay refining",                "neodynium_oxide"),
    # Metal reduction and downstream
    "Molten Salt Electrolysis":
        ("molten_salt electrolysis",     "neodynium"),
    "Metallothermic Reduction":
        ("metallothermic reduction",     "dysprosium"),
    "Chemical Transformation":
        ("chemical transformation",      "neodynium dysprosium iron alloy"),
    "Magnet Manufacturing":
        ("magnet manufacturing",         "hp_magnet"),
}

# Averaging groups: multiple HPC processes averaged → one BLEECAM (source, material) row.
# Monazite Calcination [allocated to *] is intentionally excluded: its GWP (~3109 kg CO2/kg)
# is a location-invariant thorium allocation artefact that would dominate and distort averages.
AVERAGING_GROUPS = {
    ("sulfuric acid digestion", "neodynium_oxide"): [
        "BM Roasting",
        "BM SX & Calcination [allocated to neodymium oxide]",
        "Bastanasite SX",
        "Monazite Roasting",
        "Monazite SX",
    ],
    ("sulfuric acid digestion", "dysprosium_oxide"): [
        "BM Roasting",
        "BM SX & Calcination [allocated to dysprosium oxide]",
        "Bastanasite SX",
        "Monazite Roasting",
        "Monazite SX",
    ],
    ("hydrochloric acid digestion", "neodynium_oxide"): [
        "Bastanasite HCL Digestion",
        "Monazite HCL Digestion",
        "Bastanasite SX",
        "Monazite SX",
    ],
    ("hydrochloric acid digestion", "dysprosium_oxide"): [
        "Bastanasite HCL Digestion",
        "Monazite HCL Digestion",
        "Bastanasite SX",
        "Monazite SX",
    ],
    # BM Beneficiation averaged with Bastanasite Beneficiation for flurocarbonate
    ("beneficiation", "flurocarbonate"): [
        "BM Beneficiation",
        "Bastanasite Beneficiation",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Location sets
# ─────────────────────────────────────────────────────────────────────────────

# Active process-location combinations — mirrors ACTIVE_PROCESS_LOCATIONS in REE.py.
# Only these combinations produce rows in the output; this eliminates the ~455 extra
# rows that appeared when all 9 locations were generated for every process.
ACTIVE_PROCESS_LOCATIONS = {
    "mining":                        ["CN", "AU", "US", "CA", "BR"],
    "clay mining":                   ["CN", "AU", "MM", "BR"],
    "beneficiation":                 ["CN", "AU", "US"],
    "clay refining":                 ["CN", "AU", "MM", "BR"],
    "sulfuric acid digestion":       ["CN", "AU", "US", "MY", "EE"],
    "hydrochloric acid digestion":   ["CN", "AU", "US", "MY", "EE"],
    "molten_salt electrolysis":      ["CN", "JP", "US", "EE"],
    "metallothermic reduction":      ["CN", "JP", "US", "EE"],
    "chemical transformation":       ["CN", "JP", "US", "EE"],
    "magnet manufacturing":          ["CN", "JP", "US", "EE"],
}

ACTIVE_PROCESS_LOCATIONS = {
    "mining":                        ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "clay mining":                   ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "beneficiation":                 ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "clay refining":                 ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "sulfuric acid digestion":       ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "hydrochloric acid digestion":   ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "molten_salt electrolysis":      ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "metallothermic reduction":      ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "chemical transformation":       ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
    "magnet manufacturing":          ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"],
}

ALL_BLEECAM_LOCS = ["AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"]
LCA_LOCS         = {"AU", "BR", "CA", "CN", "EE", "JP", "MM", "MY", "US"}
PENDING_LOCS     = {"CA"}  # CA has no HPC results — all EF columns set to "Not available"

# EoL / use-phase rows → all EF columns = 0.0, US only
EOL_ROWS = [
    ("cryogenic",                  "US", "neodynium dysprosium iron alloy"),
    ("direct reuse",               "US", "hp_magnet"),
    ("hydrometallurgical",         "US", "neodynium dysprosium iron alloy"),
    ("magnet-to-magnet recycling", "US", "hp_magnet"),
    ("magnet_market_mix",          "US", "hp_magnet"),
    ("pyrometallurgical",          "US", "neodynium dysprosium iron alloy"),
    ("use phase",                  "US", "hp_magnet"),
]

NUM_TIME_PERIODS = 5


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_lookup(lcia_path: Path) -> dict:
    """Build a nested dictionary mapping LCIA data by method, process/location, and category.

    :param lcia_path: Path to LCIA data CSV file.
    :type lcia_path: Path
    :returns: Nested dict mapping (method_key, category) → {process_location_key: ef_value}.
    :rtype: dict
    """
    df = pd.read_csv(lcia_path)
    lookup: dict = {}
    for _, row in df.iterrows():
        method = str(row["method"])
        key    = (str(row["process"]), str(row["location"]))
        cat    = str(row["lcia"])
        val    = float(row["value"])
        lookup.setdefault(method, {}).setdefault(key, {})[cat] = val
    return lookup


def get_averaged_ef(lookup: dict, method_key: str, categories: list,
                    prefix: str, hpc_processes: list, location: str) -> dict:
    """Average EF values across multiple HPC processes for a given location.

    :param lookup: Nested dict from build_lookup mapping method → (process, location) → category → value.
    :type lookup: dict
    :param method_key: LCIA method key (e.g., 'RECIPE', 'IW+').
    :type method_key: str
    :param categories: List of LCIA category names to average.
    :type categories: list
    :param prefix: Column name prefix for output (e.g., 'EF_RECIPE__').
    :type prefix: str
    :param hpc_processes: List of HPC process names to average over.
    :type hpc_processes: list
    :param location: Location code to filter processes.
    :type location: str
    :returns: Dict mapping column_name → averaged_float for all categories. Missing combinations are skipped from average.
    :rtype: dict
    """
    method_lookup = lookup.get(method_key, {})
    result = {}
    for cat in categories:
        col = f"{prefix}{cat}"
        vals = []
        for proc in hpc_processes:
            v = method_lookup.get((proc, location), {}).get(cat)
            if v is not None:
                vals.append(v)
        result[col] = sum(vals) / len(vals) if vals else 0.0
    return result


def get_lca_process(source: str, material: str) -> str | None:
    """Map a BLEECAM process/material pair to its corresponding LCA process name.

    :param source: BLEECAM process name.
    :type source: str
    :param material: BLEECAM material name.
    :type material: str
    :returns: Corresponding LCA process name string, or None if not mapped.
    :rtype: str or None
    """
    for lca_proc, (s, m) in PROCESS_MAP.items():
        if s == source and m == material:
            return lca_proc
    return None


def build_upstream_rows() -> list[tuple[str, str, str]]:
    """Build all upstream process/location/material rows to include in output.

    Rows are filtered by ACTIVE_PROCESS_LOCATIONS so only process-location combinations
    that exist in REE.py are emitted. Covers both PROCESS_MAP (single-process) and
    AVERAGING_GROUPS entries.

    :returns: List of (source, location, material) tuples for all upstream process/location/material combinations.
    :rtype: list[tuple[str, str, str]]
    """
    # Collect all unique (source, material) pairs from both mapping structures
    source_mat_pairs: set = set()
    for lca_proc, (src, mat) in PROCESS_MAP.items():
        source_mat_pairs.add((src, mat))
    for (src, mat) in AVERAGING_GROUPS:
        source_mat_pairs.add((src, mat))

    rows = []
    for src, mat in sorted(source_mat_pairs):
        active_locs = ACTIVE_PROCESS_LOCATIONS.get(src, ALL_BLEECAM_LOCS)
        for loc in active_locs:
            rows.append((src, loc, mat))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Core builder
# ─────────────────────────────────────────────────────────────────────────────

def build_output(lookup: dict):
    """Build and write the complete EF template output with all LCIA methods and categories.

    :param lookup: Dict from build_lookup mapping LCIA data by method, process/location, and category.
    :type lookup: dict
    :returns: None (builds and writes output CSV rows).
    """
    upstream_rows = build_upstream_rows()
    eol_set       = set(EOL_ROWS)
    all_rows      = upstream_rows + EOL_ROWS

    # All EF output columns
    recipe_cols = [f"{RECIPE_PREFIX}{c}" for c in RECIPE_CATEGORIES]
    iw_cols     = [f"{IW_PREFIX}{c}"     for c in IW_CATEGORIES]
    traci_cols  = [f"{TRACI_PREFIX}{c}"  for c in TRACI_CATEGORIES]
    all_ef_cols = recipe_cols + iw_cols + traci_cols

    records = []
    stats   = {"data": [], "pending": [], "zero": [], "warn": []}

    for t in range(NUM_TIME_PERIODS):
        for (source, location, material) in all_rows:

            row: dict = {
                "time_period": t,
                "source":      source,
                "location":    location,
                "material":    material,
            }

            # ── EoL / use-phase → all zeros ───────────────────────────────
            if (source, location, material) in eol_set:
                for col in all_ef_cols:
                    row[col] = 0.0
                row[COMPAT_COL] = 0.0
                if t == 0:
                    stats["zero"].append((source, location, material))
                records.append(row)
                continue

            # ── Pending location → "Not available" ────────────────────────
            if location in PENDING_LOCS:
                for col in all_ef_cols:
                    row[col] = "Not available"
                row[COMPAT_COL] = "Not available"
                if t == 0:
                    stats["pending"].append((source, location, material))
                records.append(row)
                continue

            # ── Data available ────────────────────────────────────────────
            avg_key = (source, material)

            if avg_key in AVERAGING_GROUPS:
                # --- Averaged entry: mean across multiple HPC processes ---
                hpc_procs = AVERAGING_GROUPS[avg_key]
                row.update(get_averaged_ef(lookup, "RECIPE",        RECIPE_CATEGORIES, RECIPE_PREFIX, hpc_procs, location))
                row.update(get_averaged_ef(lookup, "IMPACT World+", IW_CATEGORIES,     IW_PREFIX,     hpc_procs, location))
                row.update(get_averaged_ef(lookup, "TRACI2.1",      TRACI_CATEGORIES,  TRACI_PREFIX,  hpc_procs, location))
                row[COMPAT_COL] = row.get(COMPAT_SRC, 0.0)
                if t == 0:
                    stats["data"].append((source, location, material, f"avg({', '.join(hpc_procs)})"))

            else:
                # --- Single-process entry ---
                lca_proc = get_lca_process(source, material)
                if lca_proc is None:
                    print(f"  WARNING: no LCA mapping for ({source}, {material})")
                    for col in all_ef_cols:
                        row[col] = 0.0
                    row[COMPAT_COL] = 0.0
                    stats["warn"].append((source, location, material))
                    records.append(row)
                    continue

                def fill_method(method_key, categories, prefix):
                    method_lookup = lookup.get(method_key, {})
                    lca_key = (lca_proc, location)
                    vals = method_lookup.get(lca_key, {})
                    if not vals:
                        print(f"  WARNING: no {method_key} data for {lca_key}")
                    for cat in categories:
                        col = f"{prefix}{cat}"
                        row[col] = vals.get(cat, 0.0)

                fill_method("RECIPE",        RECIPE_CATEGORIES, RECIPE_PREFIX)
                fill_method("IMPACT World+", IW_CATEGORIES,     IW_PREFIX)
                fill_method("TRACI2.1",      TRACI_CATEGORIES,  TRACI_PREFIX)
                row[COMPAT_COL] = row.get(COMPAT_SRC, 0.0)
                if t == 0:
                    stats["data"].append((source, location, material, lca_proc))

            records.append(row)

    # Build DataFrame with consistent column order
    col_order = (
        ["time_period", "source", "location", "material", COMPAT_COL]
        + recipe_cols + iw_cols + traci_cols
    )
    df = pd.DataFrame(records)
    # Ensure all expected columns exist (defensive)
    for c in col_order:
        if c not in df.columns:
            df[c] = 0.0
    df = df[col_order]
    return df, stats, all_ef_cols


# ─────────────────────────────────────────────────────────────────────────────
# Summary report
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(stats, n_per_period, n_cols, out_path):
    """Print a summary of EF template coverage, data availability, and how to switch methods.

    :param stats: Dict containing coverage statistics (data, pending, zero, warn keys).
    :type stats: dict
    :param n_per_period: Number of rows per time period.
    :type n_per_period: int
    :param n_cols: Number of EF columns in output.
    :type n_cols: int
    :param out_path: Output CSV path.
    :type out_path: Path
    :returns: None
    """
    print("\n── Summary ──────────────────────────────────────────────────────────")
    print(f"  Output          : {out_path}")
    print(f"  Periods         : {NUM_TIME_PERIODS}  (0–{NUM_TIME_PERIODS-1})")
    print(f"  Rows / period   : {n_per_period}")
    print(f"  Total rows      : {NUM_TIME_PERIODS * n_per_period}")
    print(f"  EF columns      : {n_cols}  ({len(RECIPE_CATEGORIES)} ReCiPe"
          f" + {len(IW_CATEGORIES)} IW+ + {len(TRACI_CATEGORIES)} TRACI2.1)"
          f"  + 1 compat alias")
    print()
    print(f"  ✅  Data rows (t=0): {len(stats['data'])}")
    for src, loc, mat, lca in sorted(stats["data"]):
        print(f"       {src:42s} | {loc:4s} | {mat:38s} ← {lca}")
    print()
    print(f"  ⏳  Not available — pending HPC (t=0): {len(stats['pending'])}")
    for src, loc, mat in sorted(stats["pending"]):
        print(f"       {src:42s} | {loc:4s} | {mat}")
    print()
    print(f"  ○   Zero (EoL / use-phase): {len(stats['zero'])}")
    if stats["warn"]:
        print(f"\n  ⚠️   Warnings: {len(stats['warn'])}")
        for item in stats["warn"]:
            print(f"       {item}")
    print()
    print("  ── How to switch objective method in REE.py ─────────────────────")
    print("  Change the column name in the ef_factor dict construction:")
    print()
    print("  ReCiPe GWP1000 (current / default):")
    print(f"      row['{COMPAT_COL}']")
    print()
    print("  ReCiPe (explicit new-prefix name, same value):")
    print(f"      row['{RECIPE_PREFIX}Global Warming Potential (Gwp1000)']")
    print()
    print("  IMPACT World+ — short-term fossil GHG (≈ GWP100):")
    print(f"      row['{IW_PREFIX}Climate change, short term, fossil']")
    print()
    print("  IMPACT World+ — long-term fossil GHG:")
    print(f"      row['{IW_PREFIX}Climate change, long term, fossil']")
    print()
    print("  IMPACT World+ — water scarcity:")
    print(f"      row['{IW_PREFIX}Water scarcity']")
    print()
    print("  IMPACT World+ — mineral resource depletion:")
    print(f"      row['{IW_PREFIX}Mineral resources use']")
    print()
    print("  TRACI2.1 GWP100:")
    print(f"      row['{TRACI_PREFIX}Global Warming Potential (Gwp100)']")
    print("────────────────────────────────────────────────────────────────────\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Entry point for building the full EF template with all LCIA methods (ReCiPe, IW+, TRACI2.1).

    :returns: None
    """
    parser = argparse.ArgumentParser(
        description="Build wide EF_Template_full.csv with ReCiPe + IW+ + TRACI2.1."
    )
    parser.add_argument(
        "--lcia", type=Path,
        default=Path("lcia_resultsALL_ACTIVITIES_ecoinvent_2020_SSP2-Base_ALL_LOCATIONS.csv"),
        help="Compiled LCA results CSV (all methods)",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path("EF_Template_full.csv"),
        help="Output CSV path",
    )
    args = parser.parse_args()

    if not args.lcia.exists():
        print(f"[ERROR] LCA file not found: {args.lcia}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading LCA data: {args.lcia}")
    lookup = build_lookup(args.lcia)
    for method, combos in lookup.items():
        print(f"  {method}: {len(combos)} (process, location) combinations")

    print("\nBuilding output table...")
    df_out, stats, ef_cols = build_output(lookup)

    n_per_period = len(df_out) // NUM_TIME_PERIODS
    print(f"Writing: {args.out}  ({len(df_out)} rows × {len(df_out.columns)} columns)")
    df_out.to_csv(args.out, index=False)

    print_summary(stats, n_per_period, len(ef_cols), args.out)
    print("Done.")


if __name__ == "__main__":
    main()