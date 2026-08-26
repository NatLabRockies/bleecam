#!/usr/bin/env python3
"""
Build EF table for 2025–2050 from RECIPE-only LCIA data and EF template.

Steps:
 1) Load `combined_lcia_data.csv` and `EF_template_updated_TJ.csv`
 2) Filter to RECIPE only
 3) Pivot to wide: one row per process, columns = LCIA categories, values = `value`
 4) Merge onto template twice:
      - by "Process Name 1 LCIA"  -> columns prefixed "EF1__"
      - by "Process Name 2 LCIA"  -> columns prefixed "EF2__"
 5) For each LCIA category, compute a normalized weighted average:
      EF_weighted__<LCIA> = (w1*EF1 + w2*EF2) / (w1 + w2)
      where w1 = "Market Average 1 LCIA (metric tons produced)"
            w2 = "Market average 2 LCIA (metric tons produced)"
 6) Expand rows for years 2025..2050 with identical EF values
 7) Save a long-format CSV with column `time_period` set to the year
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np


COLS = {
    "process": "process",
    "lcia": "lcia",
    "value": "value",
    "method": "method",
    "proc1": "Process Name 1 LCIA",
    "proc2": "Process Name 2 LCIA",
    "w1": "Market Average 1 LCIA (metric tons produced)",
    "w2": "Market average 2 LCIA (metric tons produced)",
    "time": "time_period",
}


def load_data(combined_path: Path, template_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load combined LCIA data and EF template from CSV files.

    :param combined_path: Path to combined_lcia_data.csv containing all LCIA results.
    :type combined_path: Path
    :param template_path: Path to EF_template_updated_TJ.csv containing the row template.
    :type template_path: Path
    :returns: Tuple of (combined DataFrame, template DataFrame).
    :rtype: tuple[pd.DataFrame, pd.DataFrame]
    """
    combined = pd.read_csv(combined_path)
    template = pd.read_csv(template_path)
    return combined, template


def build_pivot_recipe(combined: pd.DataFrame) -> pd.DataFrame:
    """Build a wide-format DataFrame with one row per process and one column per LCIA category (RECIPE method only).

    :param combined: Combined LCIA data with columns for process, lcia category, value, and method.
    :type combined: pd.DataFrame
    :returns: Wide-format DataFrame with one row per process and one column per LCIA category.
    :rtype: pd.DataFrame
    :raises ValueError: If no rows with method == 'RECIPE' are found.
    """
    # Filter to RECIPE only (case-insensitive)
    mask = combined[COLS["method"]].astype(str).str.upper() == "RECIPE"
    recipe = combined.loc[mask].copy()

    if recipe.empty:
        raise ValueError("No rows found with method == 'RECIPE'. Check your input file.")

    # Pivot: one row per process, columns per LCIA category
    pivot = recipe.pivot_table(
        index=COLS["process"],
        columns=COLS["lcia"],
        values=COLS["value"],
        aggfunc="mean"  # If duplicates exist, average them
    ).reset_index()

    return pivot


def merge_template_with_efs(template: pd.DataFrame, pivot: pd.DataFrame) -> pd.DataFrame:
    """Merge EF values onto template using process name lookups.

    :param template: EF template rows with process name columns for LCIA merge.
    :type template: pd.DataFrame
    :param pivot: RECIPE pivot from build_pivot_recipe.
    :type pivot: pd.DataFrame
    :returns: Template DataFrame with EF1__ and EF2__ columns merged in for both process name lookups.
    :rtype: pd.DataFrame
    """
    tpl = template.copy()

    # Merge for Process Name 1 LCIA
    left1 = pivot.add_prefix("EF1__").rename(columns={"EF1__" + COLS["process"]: COLS["proc1"]})
    tpl = tpl.merge(left1, how="left", on=COLS["proc1"])

    # Merge for Process Name 2 LCIA
    left2 = pivot.add_prefix("EF2__").rename(columns={"EF2__" + COLS["process"]: COLS["proc2"]})
    tpl = tpl.merge(left2, how="left", on=COLS["proc2"])

    return tpl


def compute_weighted_avgs(tpl: pd.DataFrame, pivot: pd.DataFrame, fill_missing_zero: bool = False) -> tuple[pd.DataFrame, list[str]]:
    """Compute weighted averages of EF columns for each LCIA category.

    :param tpl: Merged template with EF1__ and EF2__ columns.
    :type tpl: pd.DataFrame
    :param pivot: RECIPE pivot used to identify LCIA category names.
    :type pivot: pd.DataFrame
    :param fill_missing_zero: If True, fills NaN weighted EF values with 0.0.
    :type fill_missing_zero: bool
    :returns: Tuple of (DataFrame with EF_weighted__ columns added, list of new column names).
    :rtype: tuple[pd.DataFrame, list[str]]
    """
    # Build list of LCIA categories from pivot columns (excluding the 'process' col)
    lcia_categories = [c for c in pivot.columns if c != COLS["process"]]

    weighted_cols = []
    w1 = tpl[COLS["w1"]] if COLS["w1"] in tpl.columns else pd.Series(np.nan, index=tpl.index)
    w2 = tpl[COLS["w2"]] if COLS["w2"] in tpl.columns else pd.Series(np.nan, index=tpl.index)

    for lcia in lcia_categories:
        c1 = f"EF1__{lcia}"
        c2 = f"EF2__{lcia}"
        x1 = tpl[c1] if c1 in tpl.columns else pd.Series(np.nan, index=tpl.index)
        x2 = tpl[c2] if c2 in tpl.columns else pd.Series(np.nan, index=tpl.index)

        denom = (w1.fillna(0) + w2.fillna(0)).replace(0, np.nan)
        weighted = (w1.fillna(0) * x1.fillna(0) + w2.fillna(0) * x2.fillna(0)) / denom

        new_col = f"EF_weighted__{lcia}"
        tpl[new_col] = weighted
        weighted_cols.append(new_col)

    if fill_missing_zero:
        tpl[weighted_cols] = tpl[weighted_cols].fillna(0)

    return tpl, weighted_cols


def expand_years(tpl: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Replicate template rows for each year in the given range.

    :param tpl: Single-year template DataFrame to replicate.
    :type tpl: pd.DataFrame
    :param start_year: First year to include (inclusive).
    :type start_year: int
    :param end_year: Last year to include (inclusive).
    :type end_year: int
    :returns: Long-format DataFrame with one copy of tpl per year and a time_period column set to the year.
    :rtype: pd.DataFrame
    """
    years = list(range(start_year, end_year + 1))
    pieces = []
    for y in years:
        t = tpl.copy()
        # ensure time_period column exists & set to year
        t[COLS["time"]] = y
        pieces.append(t)
    return pd.concat(pieces, ignore_index=True)


def main():
    """Entry point for building the EF table from RECIPE-only LCIA data and template.

    :returns: None
    """
    parser = argparse.ArgumentParser(description="Build EF table from RECIPE-only LCIA and template.")
    parser.add_argument("--combined", type=Path, default=Path("combined_lcia_data.csv"),
                        help="Path to combined_lcia_data.csv")
    parser.add_argument("--template", type=Path, default=Path("EF_template_updated_TJ.csv"),
                        help="Path to EF_template_updated_TJ.csv")
    parser.add_argument("--out", type=Path, default=Path("EF_final_RECIPE_2025_2050_long.csv"),
                        help="Output CSV path")
    parser.add_argument("--start-year", type=int, default=2025, help="Start year (inclusive)")
    parser.add_argument("--end-year", type=int, default=2050, help="End year (inclusive)")
    parser.add_argument("--fill-missing-zero", action="store_true",
                        help="Fill missing weighted EF values with 0 instead of leaving blanks")
    args = parser.parse_args()

    print("Loading data...")
    combined, template = load_data(args.combined, args.template)

    print("Building RECIPE pivot...")
    pivot = build_pivot_recipe(combined)

    print("Merging template with EF1/EF2...")
    merged = merge_template_with_efs(template, pivot)

    print("Computing weighted averages...")
    merged, weighted_cols = compute_weighted_avgs(merged, pivot, fill_missing_zero=args.fill_missing_zero)

    print(f"Computed {len(weighted_cols)} weighted EF columns.")
    if weighted_cols:
        print("Example weighted columns:", ", ".join(weighted_cols[:10]), ("..." if len(weighted_cols) > 10 else ""))

    print(f"Expanding to years {args.start_year}..{args.end_year}...")
    final_long = expand_years(merged, args.start_year, args.end_year)

    print(f"Writing output to {args.out} ({len(final_long)} rows)...")
    final_long.to_csv(args.out, index=False)

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
