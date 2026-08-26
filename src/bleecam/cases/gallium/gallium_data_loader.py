# BLEECAM - Benchmarking Life Cycle Environmental, Economic, and Social Metrics
# for Critical and Advanced Minerals and Materials
# Copyright (C) 2026 Alliance for Energy Innovation, LLC
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


EXPECTED_TIME_PERIODS = (0, 1, 2, 3, 4, 5)
PERIOD5_NOTE = "Period 5 non-demand parameters are held constant from period 4."

REQUIRED_FILES = {
    "topology": "trade_topology_ga.csv",
    "demand": "demand_ga.csv",
    "capacity": "capacity_template_ga.csv",
    "cost": "cost_parameters_ga.csv",
    "yield": "yield_ga.csv",
    "shipping": "shipping_costs_ga.csv",
}

OPTIONAL_FILES = {
    "social_lca": "social_lca_template_ga.csv",
}

REQUIRED_COLUMNS = {
    "topology": ["process_from", "loc_from", "process_to", "loc_to", "material"],
    "demand": ["time_period", "scenario", "location", "material", "flow", "demand_kg"],
    "capacity": ["time_period", "process", "location", "material", "capacity"],
    "cost": [
        "time_period",
        "source",
        "location",
        "material",
        "destination",
        "destination_location",
        "processing cost",
        "transportation cost",
        "tariff_cost",
    ],
    "yield": ["time_period", "process", "location", "material", "yield"],
    "shipping": [
        "time_period",
        "loc_from",
        "loc_to",
        "mode",
        "distance_km",
        "shipping_cost_usd_per_kg",
    ],
    "social_lca": [
        "time_period",
        "source",
        "location",
        "material",
        "SLCA_EF - Child labor impact (worker hour/kg)",
        "SLCA_EF - Forced labor impact (worker hour/kg)",
        "SLCA_EF - Fatal injury impact (worker hour/kg)",
        "SLCA_EF - Non-fatal injury impact (worker hour/kg)",
        "SLCA_EF - Unemployment impact (worker hour/kg)",
    ],
}

SOCIAL_LCA_FACTOR_COLUMNS = REQUIRED_COLUMNS["social_lca"][4:]

BASELINE_SCENARIO = "baseline_Ga"
DEMAND_LOCATION = "US"
DEMAND_FLOW = "wafer_demand"
DEMAND_MATERIALS = ("GaAs_wafer", "GaN_wafer")

REQUIRED_TERMINAL_ARCS = (
    ("wafer_market_mix", "US", "wafer_demand", "US", "GaAs_wafer"),
    ("wafer_market_mix", "US", "wafer_demand", "US", "GaN_wafer"),
)

ISSUE_COLUMNS = [
    "issue_type",
    "severity",
    "file",
    "row_or_key",
    "current_value",
    "expected_value",
    "recommendation",
    "notes",
]

SEVERITY_ORDER = {"blocking": 0, "conditional_blocking": 1, "warning": 2, "info": 3}


@dataclass
class ValidationIssue:
    issue_type: str
    severity: str
    file: str
    row_or_key: str
    current_value: str
    expected_value: str
    recommendation: str
    notes: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "file": self.file,
            "row_or_key": self.row_or_key,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "recommendation": self.recommendation,
            "notes": self.notes,
        }


class GalliumValidationError(RuntimeError):
    pass


def _clean_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _clean_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in out.columns:
        if out[column].dtype == object:
            out[column] = out[column].map(_clean_str)
    return out


def _issue(
    issues: list[ValidationIssue],
    issue_type: str,
    severity: str,
    file: Path | str,
    row_or_key: Any,
    current_value: Any,
    expected_value: Any,
    recommendation: str,
    notes: str = "",
) -> None:
    issues.append(
        ValidationIssue(
            issue_type=issue_type,
            severity=severity,
            file=str(file),
            row_or_key=str(row_or_key),
            current_value=str(current_value),
            expected_value=str(expected_value),
            recommendation=recommendation,
            notes=notes,
        )
    )


def _read_csv(path: Path, issues: list[ValidationIssue], required: bool) -> pd.DataFrame | None:
    if not path.exists():
        if required:
            _issue(
                issues,
                "missing_required_file",
                "blocking",
                path,
                path.name,
                "not found",
                "readable CSV file",
                "Place the required Gallium input file in the flat input directory.",
            )
        return None
    try:
        return _clean_object_columns(pd.read_csv(path, keep_default_na=False))
    except Exception as exc:
        _issue(
            issues,
            "unreadable_csv",
            "blocking" if required else "conditional_blocking",
            path,
            path.name,
            type(exc).__name__,
            "readable CSV file",
            "Repair the CSV before loading the Gallium input package.",
            str(exc),
        )
        return None


def _require_columns(
    file_key: str,
    path: Path,
    df: pd.DataFrame | None,
    issues: list[ValidationIssue],
) -> bool:
    if df is None:
        return False
    missing = [column for column in REQUIRED_COLUMNS[file_key] if column not in df.columns]
    for column in missing:
        _issue(
            issues,
            "missing_required_column",
            "blocking" if file_key != "social_lca" else "conditional_blocking",
            path,
            column,
            list(df.columns),
            column,
            f"Add the `{column}` column using the Gallium v2 schema.",
        )
    return not missing


def _coerce_time_periods(
    file_key: str,
    path: Path,
    df: pd.DataFrame,
    issues: list[ValidationIssue],
) -> pd.DataFrame:
    out = df.copy()
    periods = pd.to_numeric(out["time_period"], errors="coerce")
    invalid = periods.isna() | (periods % 1 != 0)
    for idx in out.index[invalid]:
        _issue(
            issues,
            "invalid_time_period",
            "blocking" if file_key != "social_lca" else "conditional_blocking",
            path,
            f"row {idx + 2}",
            out.at[idx, "time_period"],
            "integer time_period",
            "Use integer time periods 0,1,2,3,4,5.",
        )
    if not invalid.any():
        out["time_period"] = periods.astype(int)
    return out


def _period_values(df: pd.DataFrame | None) -> list[int]:
    if df is None or "time_period" not in df.columns:
        return []
    values = pd.to_numeric(df["time_period"], errors="coerce").dropna().astype(int)
    return sorted(set(values.tolist()))


def _append_period5_from_period4(
    file_key: str,
    path: Path,
    df: pd.DataFrame,
    issues: list[ValidationIssue],
) -> tuple[pd.DataFrame, bool]:
    periods = _period_values(df)
    if periods == list(EXPECTED_TIME_PERIODS):
        return df, False
    if periods == [0, 1, 2, 3, 4]:
        period4_rows = df[df["time_period"] == 4].copy()
        period4_rows["time_period"] = 5
        if "notes" in period4_rows.columns:
            period4_rows["notes"] = period4_rows["notes"].map(
                lambda value: (str(value).strip() + " | " if str(value).strip() else "")
                + PERIOD5_NOTE
            )
        out = pd.concat([df, period4_rows], ignore_index=True)
        _issue(
            issues,
            "period5_extension_created",
            "info",
            path,
            file_key,
            "time_periods 0-4",
            "time_periods 0-5",
            "Generated period-5 rows in the runtime output by copying period-4 non-demand parameters.",
            PERIOD5_NOTE,
        )
        return out, True
    _issue(
        issues,
        "time_period_coverage_mismatch",
        "blocking" if file_key != "social_lca" else "conditional_blocking",
        path,
        file_key,
        periods,
        list(EXPECTED_TIME_PERIODS),
        "Provide exactly time_period values 0,1,2,3,4,5.",
    )
    return df, False


def _check_no_blank_required_fields(
    file_key: str,
    path: Path,
    df: pd.DataFrame,
    issues: list[ValidationIssue],
) -> None:
    required = REQUIRED_COLUMNS[file_key]
    for column in required:
        if column not in df.columns:
            continue
        if file_key == "cost" and column in {"destination", "destination_location"}:
            continue
        blank = df[column].map(lambda value: _clean_str(value) == "")
        for idx in df.index[blank]:
            _issue(
                issues,
                "blank_required_field",
                "blocking" if file_key != "social_lca" else "conditional_blocking",
                path,
                f"row {idx + 2}; column {column}",
                "",
                "nonblank value",
                f"Populate `{column}` before loading the Gallium package.",
            )


def _check_numeric_nonnegative(
    file_key: str,
    path: Path,
    df: pd.DataFrame,
    columns: list[str],
    issues: list[ValidationIssue],
) -> None:
    for column in columns:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors="coerce")
        non_numeric = values.isna()
        for idx in df.index[non_numeric]:
            _issue(
                issues,
                "non_numeric_value",
                "blocking" if file_key != "social_lca" else "conditional_blocking",
                path,
                f"row {idx + 2}; column {column}",
                df.at[idx, column],
                "numeric value",
                f"Convert `{column}` to a numeric value.",
            )
        negative = values < 0
        for idx in df.index[negative]:
            _issue(
                issues,
                "negative_value",
                "blocking" if file_key != "social_lca" else "conditional_blocking",
                path,
                f"row {idx + 2}; column {column}",
                df.at[idx, column],
                ">= 0",
                f"Remove the negative `{column}` value unless it has an explicit model justification.",
            )


def _check_duplicates(
    file_key: str,
    path: Path,
    df: pd.DataFrame,
    key_columns: list[str],
    issues: list[ValidationIssue],
) -> None:
    if not all(column in df.columns for column in key_columns):
        return
    duplicated = df[df.duplicated(key_columns, keep=False)]
    for idx, row in duplicated.iterrows():
        key = tuple(row[column] for column in key_columns)
        _issue(
            issues,
            "duplicate_key",
            "blocking" if file_key != "social_lca" else "conditional_blocking",
            path,
            f"row {idx + 2}",
            key,
            "unique key",
            "Remove or consolidate duplicate rows before loading the Gallium package.",
        )


def _tuple_set(df: pd.DataFrame, columns: list[str]) -> set[tuple[Any, ...]]:
    return set(map(tuple, df[columns].drop_duplicates().values.tolist()))


def _validate_demand(
    path: Path,
    demand_df: pd.DataFrame,
    topology_df: pd.DataFrame,
    issues: list[ValidationIssue],
) -> None:
    _check_no_blank_required_fields("demand", path, demand_df, issues)
    _check_numeric_nonnegative("demand", path, demand_df, ["demand_kg"], issues)
    _check_duplicates(
        "demand",
        path,
        demand_df,
        ["time_period", "scenario", "location", "material", "flow"],
        issues,
    )

    periods = _period_values(demand_df)
    if periods != list(EXPECTED_TIME_PERIODS):
        _issue(
            issues,
            "demand_time_period_mismatch",
            "blocking",
            path,
            "time_period",
            periods,
            list(EXPECTED_TIME_PERIODS),
            "Demand must contain exactly time_period values 0,1,2,3,4,5.",
        )

    scenarios = sorted(set(demand_df["scenario"].map(_clean_str)))
    if scenarios != [BASELINE_SCENARIO]:
        _issue(
            issues,
            "demand_scenario_mismatch",
            "blocking",
            path,
            "scenario",
            scenarios,
            [BASELINE_SCENARIO],
            f"Use `{BASELINE_SCENARIO}` for the finalized Gallium baseline demand scenario.",
        )

    for column in ["scenario", "location", "material", "flow"]:
        total_mask = demand_df[column].astype(str).str.contains("total", case=False, na=False)
        for idx in demand_df.index[total_mask]:
            _issue(
                issues,
                "demand_total_row",
                "blocking",
                path,
                f"row {idx + 2}; column {column}",
                demand_df.at[idx, column],
                "no total rows",
                "Remove aggregate total rows; BLEECAM should load disaggregated terminal demand rows.",
            )

    demand_materials = sorted(set(demand_df["material"].map(_clean_str)))
    if demand_materials != sorted(DEMAND_MATERIALS):
        _issue(
            issues,
            "demand_material_set_mismatch",
            "blocking",
            path,
            "material",
            demand_materials,
            sorted(DEMAND_MATERIALS),
            "Demand must include only GaAs_wafer and GaN_wafer for this baseline package.",
        )

    demand_flows = sorted(set(demand_df["flow"].map(_clean_str)))
    if demand_flows != [DEMAND_FLOW]:
        _issue(
            issues,
            "demand_flow_mismatch",
            "blocking",
            path,
            "flow",
            demand_flows,
            [DEMAND_FLOW],
            f"Demand flow must be `{DEMAND_FLOW}`.",
        )

    demand_locations = sorted(set(demand_df["location"].map(_clean_str)))
    if demand_locations != [DEMAND_LOCATION]:
        _issue(
            issues,
            "demand_location_mismatch",
            "blocking",
            path,
            "location",
            demand_locations,
            [DEMAND_LOCATION],
            "Demand location must be US for the current Gallium_Global baseline.",
        )

    present_period_materials = {
        (int(row.time_period), _clean_str(row.material)) for row in demand_df.itertuples()
    }
    for period in EXPECTED_TIME_PERIODS:
        for material in DEMAND_MATERIALS:
            if (period, material) not in present_period_materials:
                _issue(
                    issues,
                    "missing_demand_material_period",
                    "blocking",
                    path,
                    (period, material),
                    "missing",
                    "one demand row",
                    "Add one demand row for each of GaAs_wafer and GaN_wafer in every time_period.",
                )

    allowed_arcs = _tuple_set(
        topology_df,
        ["process_from", "loc_from", "process_to", "loc_to", "material"],
    )
    for arc in REQUIRED_TERMINAL_ARCS:
        if arc not in allowed_arcs:
            _issue(
                issues,
                "required_terminal_arc_missing",
                "blocking",
                path,
                arc,
                "missing",
                "present in trade_topology_ga.csv",
                "Add the required wafer_market_mix -> wafer_demand terminal arc to the topology.",
            )

    for idx, row in demand_df.iterrows():
        candidate = (
            "wafer_market_mix",
            _clean_str(row["location"]),
            _clean_str(row["flow"]),
            _clean_str(row["location"]),
            _clean_str(row["material"]),
        )
        if candidate not in allowed_arcs:
            _issue(
                issues,
                "demand_terminal_arc_missing",
                "blocking",
                path,
                f"row {idx + 2}",
                candidate,
                "valid terminal topology arc",
                "Make demand material, flow, and location match a terminal topology arc.",
            )


def _validate_topology_driven_coverage(
    paths: dict[str, Path],
    frames: dict[str, pd.DataFrame],
    issues: list[ValidationIssue],
) -> None:
    topology = frames["topology"]
    capacity = frames["capacity"]
    yield_df = frames["yield"]
    cost = frames["cost"]
    shipping = frames["shipping"]

    topology_source_keys = _tuple_set(
        topology.rename(columns={"process_from": "process", "loc_from": "location"}),
        ["process", "location", "material"],
    )
    capacity_keys = _tuple_set(capacity, ["process", "location", "material"])
    yield_keys = _tuple_set(yield_df, ["process", "location", "material"])

    for key in sorted(topology_source_keys - capacity_keys):
        _issue(
            issues,
            "missing_capacity_source_key",
            "blocking",
            paths["capacity"],
            key,
            "missing",
            "capacity rows for each time_period",
            "Add capacity rows for every topology source process/location/material key.",
        )

    for key in sorted(topology_source_keys - yield_keys):
        _issue(
            issues,
            "missing_yield_source_key",
            "blocking",
            paths["yield"],
            key,
            "missing",
            "yield rows for each time_period",
            "Add yield rows for every topology source process/location/material key.",
        )

    cost_arc_keys = _tuple_set(
        cost[cost["destination"].map(_clean_str) != ""].rename(
            columns={
                "source": "process_from",
                "location": "loc_from",
                "destination": "process_to",
                "destination_location": "loc_to",
            }
        ),
        ["process_from", "loc_from", "process_to", "loc_to", "material"],
    )
    for arc in REQUIRED_TERMINAL_ARCS:
        if arc not in cost_arc_keys:
            _issue(
                issues,
                "missing_terminal_cost_arc",
                "blocking",
                paths["cost"],
                arc,
                "missing",
                "zero-cost structural terminal arc row for each time_period",
                "Add structural zero-cost cost rows for wafer_market_mix -> wafer_demand arcs.",
            )

    topology_pairs = _tuple_set(topology, ["loc_from", "loc_to"])
    shipping_pairs = _tuple_set(shipping, ["loc_from", "loc_to"])
    for pair in sorted(topology_pairs - shipping_pairs):
        _issue(
            issues,
            "missing_shipping_location_pair",
            "blocking",
            paths["shipping"],
            pair,
            "missing",
            "shipping row for each topology location pair and time_period",
            "Add the missing shipping pair. Same-location pairs should use zero distance and zero shipping cost.",
        )


def _validate_social_lca(
    path: Path,
    social_lca_df: pd.DataFrame | None,
    issues: list[ValidationIssue],
) -> tuple[pd.DataFrame | None, bool]:
    if social_lca_df is None:
        _issue(
            issues,
            "social_lca_excluded_from_baseline",
            "info",
            path,
            "social_lca_template_ga.csv",
            "not provided",
            "optional complete numeric Social LCA CSV",
            "Baseline load will exclude Social LCA factors.",
        )
        return None, False

    if not _require_columns("social_lca", path, social_lca_df, issues):
        return None, False

    social_lca_df = _coerce_time_periods("social_lca", path, social_lca_df, issues)
    _check_no_blank_required_fields("social_lca", path, social_lca_df, issues)
    _check_duplicates(
        "social_lca",
        path,
        social_lca_df,
        ["time_period", "source", "location", "material"],
        issues,
    )

    periods = _period_values(social_lca_df)
    if periods != list(EXPECTED_TIME_PERIODS):
        _issue(
            issues,
            "social_lca_time_period_mismatch",
            "conditional_blocking",
            path,
            "time_period",
            periods,
            list(EXPECTED_TIME_PERIODS),
            "Provide complete Social LCA rows for time_period values 0,1,2,3,4,5 or omit the file.",
            "Social LCA is excluded from baseline unless the CSV is complete.",
        )

    complete = True
    for column in SOCIAL_LCA_FACTOR_COLUMNS:
        raw = social_lca_df[column].map(_clean_str)
        unavailable = raw.isin(["", "Not available", "not available", "NA", "N/A", "nan"])
        for idx in social_lca_df.index[unavailable]:
            complete = False
            _issue(
                issues,
                "social_lca_factor_not_numeric",
                "conditional_blocking",
                path,
                f"row {idx + 2}; column {column}",
                social_lca_df.at[idx, column],
                "numeric nonnegative value",
                "Populate numeric Social LCA factors or omit this optional file for baseline runs.",
            )
        numeric = pd.to_numeric(social_lca_df.loc[~unavailable, column], errors="coerce")
        for idx in numeric.index[numeric.isna()]:
            complete = False
            _issue(
                issues,
                "social_lca_factor_not_numeric",
                "conditional_blocking",
                path,
                f"row {idx + 2}; column {column}",
                social_lca_df.at[idx, column],
                "numeric nonnegative value",
                "Populate numeric Social LCA factors or omit this optional file for baseline runs.",
            )
        for idx in numeric.index[numeric < 0]:
            complete = False
            _issue(
                issues,
                "negative_social_lca_factor",
                "conditional_blocking",
                path,
                f"row {idx + 2}; column {column}",
                social_lca_df.at[idx, column],
                ">= 0",
                "Remove negative Social LCA factors unless explicitly justified.",
            )

    if complete and periods == list(EXPECTED_TIME_PERIODS):
        return social_lca_df, True

    _issue(
        issues,
        "social_lca_excluded_from_baseline",
        "info",
        path,
        "social_lca_template_ga.csv",
        "incomplete or nonnumeric",
        "complete numeric file",
        "Baseline load will exclude Social LCA factors.",
    )
    return None, False


def _write_normalized_csvs(
    output_dir: Path,
    frames: dict[str, pd.DataFrame],
    social_lca_enabled: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_key, filename in REQUIRED_FILES.items():
        frames[file_key].to_csv(output_dir / filename, index=False)
    if social_lca_enabled and frames.get("social_lca") is not None:
        frames["social_lca"].to_csv(output_dir / OPTIONAL_FILES["social_lca"], index=False)


def _build_maps(frames: dict[str, pd.DataFrame], social_lca_enabled: bool) -> dict[str, Any]:
    topology = frames["topology"]
    demand = frames["demand"]
    capacity = frames["capacity"]
    cost = frames["cost"]
    yield_df = frames["yield"]
    shipping = frames["shipping"]
    social_lca = frames.get("social_lca") if social_lca_enabled else None

    allowed_trade_arcs = _tuple_set(
        topology,
        ["process_from", "loc_from", "process_to", "loc_to", "material"],
    )
    processes = sorted(
        set(topology["process_from"].map(_clean_str)) | set(topology["process_to"].map(_clean_str))
    )
    locations = sorted(
        set(topology["loc_from"].map(_clean_str)) | set(topology["loc_to"].map(_clean_str))
    )
    materials = sorted(set(topology["material"].map(_clean_str)))

    max_output_capacity: dict[tuple[str, str, str], dict[int, float]] = {}
    for row in capacity.itertuples(index=False):
        key = (_clean_str(row.process), _clean_str(row.location), _clean_str(row.material))
        max_output_capacity.setdefault(key, {})[int(row.time_period)] = float(row.capacity)

    yield_factor = {}
    for _, row in yield_df.iterrows():
        key = (
            int(row["time_period"]),
            _clean_str(row["process"]),
            _clean_str(row["location"]),
            _clean_str(row["material"]),
        )
        yield_factor[key] = float(row["yield"])

    arc_processing_cost = {}
    arc_transportation_cost = {}
    tariff_cost = {}
    for _, row in cost.iterrows():
        key = (
            int(row["time_period"]),
            _clean_str(row["source"]),
            _clean_str(row["location"]),
            _clean_str(row["destination"]),
            _clean_str(row["destination_location"]),
            _clean_str(row["material"]),
        )
        arc_processing_cost[key] = float(row["processing cost"])
        arc_transportation_cost[key] = float(row["transportation cost"])
        tariff = float(row["tariff_cost"])
        if tariff != 0.0:
            tariff_cost[key] = tariff

    shipping_cost = {
        (int(row.time_period), _clean_str(row.loc_from), _clean_str(row.loc_to)): float(
            row.shipping_cost_usd_per_kg
        )
        for row in shipping.itertuples(index=False)
    }
    shipping_distance_km = {
        (int(row.time_period), _clean_str(row.loc_from), _clean_str(row.loc_to)): float(
            row.distance_km
        )
        for row in shipping.itertuples(index=False)
    }
    shipping_mode = {
        (int(row.time_period), _clean_str(row.loc_from), _clean_str(row.loc_to)): _clean_str(
            row.mode
        )
        for row in shipping.itertuples(index=False)
    }

    social_lca_factors: dict[str, dict[tuple[int, str, str, str], float]] = {
        column: {} for column in SOCIAL_LCA_FACTOR_COLUMNS
    }
    if social_lca is not None:
        for _, row in social_lca.iterrows():
            key = (
                int(row["time_period"]),
                _clean_str(row["source"]),
                _clean_str(row["location"]),
                _clean_str(row["material"]),
            )
            for column in SOCIAL_LCA_FACTOR_COLUMNS:
                social_lca_factors[column][key] = float(row[column])

    return {
        "topology_df": topology,
        "demand_df": demand,
        "capacity_df": capacity,
        "cost_df": cost,
        "yield_df": yield_df,
        "shipping_df": shipping,
        "social_lca_df": social_lca,
        "social_lca_enabled": social_lca_enabled,
        "processes": processes,
        "locations": locations,
        "materials": materials,
        "time_periods": list(EXPECTED_TIME_PERIODS),
        "allowed_trade_arcs": allowed_trade_arcs,
        "max_output_capacity": max_output_capacity,
        "yield_factor": yield_factor,
        "arc_processing_cost": arc_processing_cost,
        "arc_transportation_cost": arc_transportation_cost,
        "tariff_cost": tariff_cost,
        "shipping_cost": shipping_cost,
        "shipping_distance_km": shipping_distance_km,
        "shipping_mode": shipping_mode,
        "social_lca_factors": social_lca_factors,
    }


def _validation_summary(frames: dict[str, pd.DataFrame], issues: list[ValidationIssue]) -> dict[str, Any]:
    return {
        "issue_counts_by_severity": dict(Counter(issue.severity for issue in issues)),
        "issue_counts_by_type": dict(Counter(issue.issue_type for issue in issues)),
        "row_counts": {key: len(df) for key, df in frames.items() if df is not None},
        "time_periods": {
            key: _period_values(df)
            for key, df in frames.items()
            if df is not None and "time_period" in df.columns
        },
    }


def write_validation_reports(
    report_md_path: Path,
    report_csv_path: Path,
    input_dir: Path,
    frames: dict[str, pd.DataFrame | None],
    issues: list[ValidationIssue],
    normalized_output_dir: Path | None,
    social_lca_enabled: bool,
) -> None:
    sorted_issues = sorted(
        issues,
        key=lambda issue: (
            SEVERITY_ORDER.get(issue.severity, 99),
            issue.issue_type,
            issue.file,
            issue.row_or_key,
        ),
    )
    with report_csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_COLUMNS)
        writer.writeheader()
        writer.writerows(issue.as_dict() for issue in sorted_issues)

    severity_counts = Counter(issue.severity for issue in sorted_issues)
    type_counts = Counter((issue.severity, issue.issue_type) for issue in sorted_issues)
    blocking_count = severity_counts.get("blocking", 0)
    conditional_count = severity_counts.get("conditional_blocking", 0)

    lines = [
        "# Gallium Loader Validation Report",
        "",
        f"Input directory: `{input_dir}`",
        f"Normalized output directory: `{normalized_output_dir}`" if normalized_output_dir else "Normalized output directory: not requested",
        "",
        "## Verdict",
        "",
    ]
    if blocking_count == 0:
        lines.append("**Baseline loader status:** PASS for required Gallium input checks.")
    else:
        lines.append("**Baseline loader status:** FAIL. Blocking issues must be resolved before optimization.")
    if social_lca_enabled:
        lines.append("**Social LCA:** enabled; complete numeric `social_lca_template_ga.csv` was provided.")
    else:
        lines.append("**Social LCA:** excluded from baseline; no complete numeric `social_lca_template_ga.csv` was loaded.")
    lines.extend(
        [
            "",
            "## Issue Counts",
            "",
            "| severity | count |",
            "|---|---:|",
        ]
    )
    for severity in ["blocking", "conditional_blocking", "warning", "info"]:
        lines.append(f"| {severity} | {severity_counts.get(severity, 0)} |")
    lines.append("")
    lines.append("## Input Row Counts")
    lines.append("")
    lines.append("| file | rows | time_periods |")
    lines.append("|---|---:|---|")
    for file_key in ["topology", "demand", "capacity", "cost", "yield", "shipping", "social_lca"]:
        df = frames.get(file_key)
        if df is None:
            continue
        periods = _period_values(df) if "time_period" in df.columns else []
        lines.append(f"| {file_key} | {len(df)} | {periods if periods else 'n/a'} |")
    lines.extend(
        [
            "",
            "## Key Checks",
            "",
            f"- Required time periods: `{list(EXPECTED_TIME_PERIODS)}`.",
            f"- Required demand scenario: `{BASELINE_SCENARIO}`.",
            f"- Required terminal arcs: `{list(REQUIRED_TERMINAL_ARCS)}`.",
            f"- Period-5 simplification text: `{PERIOD5_NOTE}`.",
            "",
            "## Issue Types",
            "",
            "| severity | issue_type | count |",
            "|---|---|---:|",
        ]
    )
    for (severity, issue_type), count in sorted(
        type_counts.items(), key=lambda item: (SEVERITY_ORDER.get(item[0][0], 99), item[0][1])
    ):
        lines.append(f"| {severity} | `{issue_type}` | {count} |")
    lines.extend(
        [
            "",
            "## Recommended Next Edits",
            "",
            "- Keep the original scientific CSVs unchanged; use the generated runtime folder for loader-ready inputs.",
            "- If any non-demand file has only periods 0-4, use the generated period-5 rows only as a documented runtime simplification.",
            "- Populate Social LCA factors only when running a Social LCA scenario; otherwise leave Social LCA excluded from baseline.",
            "",
            "## Machine-Readable Log",
            "",
            f"See `{report_csv_path.name}` for row-level validation details.",
        ]
    )
    report_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_gallium_data(
    input_dir: str | Path,
    *,
    normalized_output_dir: str | Path | None = None,
    allow_period5_extension: bool = True,
    report_md_path: str | Path = "gallium_loader_validation_report.md",
    report_csv_path: str | Path = "gallium_loader_validation_report.csv",
    strict: bool = True,
) -> dict[str, Any]:
    input_dir = Path(input_dir)
    normalized_output = Path(normalized_output_dir) if normalized_output_dir else None
    report_md = Path(report_md_path)
    report_csv = Path(report_csv_path)
    issues: list[ValidationIssue] = []

    paths = {key: input_dir / filename for key, filename in REQUIRED_FILES.items()}
    paths.update({key: input_dir / filename for key, filename in OPTIONAL_FILES.items()})

    frames: dict[str, pd.DataFrame | None] = {
        key: _read_csv(paths[key], issues, required=True) for key in REQUIRED_FILES
    }
    frames["social_lca"] = _read_csv(paths["social_lca"], issues, required=False)

    for file_key in REQUIRED_FILES:
        _require_columns(file_key, paths[file_key], frames[file_key], issues)

    missing_blockers = [issue for issue in issues if issue.severity == "blocking"]
    if missing_blockers:
        write_validation_reports(report_md, report_csv, input_dir, frames, issues, normalized_output, False)
        if strict:
            raise GalliumValidationError(
                f"Gallium input package failed validation with {len(missing_blockers)} blocking issue(s)."
            )
        return {
            "validation_issues": [issue.as_dict() for issue in issues],
            "validation_summary": _validation_summary(frames, issues),
        }

    for file_key in ["demand", "capacity", "cost", "yield", "shipping"]:
        frames[file_key] = _coerce_time_periods(file_key, paths[file_key], frames[file_key], issues)

    for file_key in ["capacity", "cost", "yield", "shipping"]:
        periods = _period_values(frames[file_key])
        if periods != list(EXPECTED_TIME_PERIODS):
            if allow_period5_extension and periods == [0, 1, 2, 3, 4]:
                frames[file_key], _ = _append_period5_from_period4(
                    file_key, paths[file_key], frames[file_key], issues
                )
            else:
                _issue(
                    issues,
                    "time_period_coverage_mismatch",
                    "blocking",
                    paths[file_key],
                    file_key,
                    periods,
                    list(EXPECTED_TIME_PERIODS),
                    "Provide periods 0-5 or enable generated period-5 runtime extension.",
                )

    frames["social_lca"], social_lca_enabled = _validate_social_lca(
        paths["social_lca"], frames["social_lca"], issues
    )

    for file_key in ["demand", "capacity", "cost", "yield", "shipping"]:
        _check_no_blank_required_fields(file_key, paths[file_key], frames[file_key], issues)

    _check_numeric_nonnegative("capacity", paths["capacity"], frames["capacity"], ["capacity"], issues)
    _check_numeric_nonnegative(
        "cost",
        paths["cost"],
        frames["cost"],
        ["processing cost", "transportation cost", "tariff_cost"],
        issues,
    )
    _check_numeric_nonnegative("yield", paths["yield"], frames["yield"], ["yield"], issues)
    _check_numeric_nonnegative(
        "shipping",
        paths["shipping"],
        frames["shipping"],
        ["distance_km", "shipping_cost_usd_per_kg"],
        issues,
    )

    _check_duplicates(
        "topology",
        paths["topology"],
        frames["topology"],
        ["process_from", "loc_from", "process_to", "loc_to", "material"],
        issues,
    )
    _check_duplicates(
        "capacity",
        paths["capacity"],
        frames["capacity"],
        ["time_period", "process", "location", "material"],
        issues,
    )
    _check_duplicates(
        "cost",
        paths["cost"],
        frames["cost"],
        ["time_period", "source", "location", "destination", "destination_location", "material"],
        issues,
    )
    _check_duplicates(
        "yield",
        paths["yield"],
        frames["yield"],
        ["time_period", "process", "location", "material"],
        issues,
    )
    _check_duplicates(
        "shipping",
        paths["shipping"],
        frames["shipping"],
        ["time_period", "loc_from", "loc_to"],
        issues,
    )

    _validate_demand(paths["demand"], frames["demand"], frames["topology"], issues)
    _validate_topology_driven_coverage(paths, frames, issues)

    if normalized_output:
        _write_normalized_csvs(normalized_output, frames, social_lca_enabled)

    write_validation_reports(
        report_md,
        report_csv,
        input_dir,
        frames,
        issues,
        normalized_output,
        social_lca_enabled,
    )

    blocking = [issue for issue in issues if issue.severity == "blocking"]
    if blocking and strict:
        raise GalliumValidationError(
            f"Gallium input package failed validation with {len(blocking)} blocking issue(s). "
            f"See {report_md} and {report_csv}."
        )

    loaded = _build_maps(frames, social_lca_enabled)
    loaded["validation_issues"] = [issue.as_dict() for issue in issues]
    loaded["validation_summary"] = _validation_summary(frames, issues)
    loaded["normalized_output_dir"] = str(normalized_output) if normalized_output else None
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Load and validate Gallium_Global BLEECAM inputs.")
    parser.add_argument("--input-dir", default=".", help="Flat directory containing Gallium CSV inputs.")
    parser.add_argument(
        "--normalized-output-dir",
        default=None,
        help="Optional generated runtime directory for normalized CSVs.",
    )
    parser.add_argument(
        "--no-period5-extension",
        action="store_true",
        help="Disable generated period-5 rows copied from period 4.",
    )
    parser.add_argument(
        "--report-md",
        default="gallium_loader_validation_report.md",
        help="Markdown validation report path.",
    )
    parser.add_argument(
        "--report-csv",
        default="gallium_loader_validation_report.csv",
        help="Machine-readable validation report path.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Write reports and return success even if blocking validation issues exist.",
    )
    args = parser.parse_args()

    data = load_gallium_data(
        args.input_dir,
        normalized_output_dir=args.normalized_output_dir,
        allow_period5_extension=not args.no_period5_extension,
        report_md_path=args.report_md,
        report_csv_path=args.report_csv,
        strict=not args.no_strict,
    )
    summary = data["validation_summary"]
    print("---- Gallium v2 loader validation ----")
    print(f"Input directory: {Path(args.input_dir)}")
    print(f"Processes: {len(data.get('processes', []))}")
    print(f"Locations: {len(data.get('locations', []))}")
    print(f"Materials: {len(data.get('materials', []))}")
    print(f"Time periods: {data.get('time_periods')}")
    print(f"Issue counts: {summary.get('issue_counts_by_severity', {})}")
    print(f"Social LCA enabled: {data.get('social_lca_enabled')}")
    print("--------------------------------------")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

