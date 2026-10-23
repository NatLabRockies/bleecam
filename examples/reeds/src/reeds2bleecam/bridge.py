"""
reeds2bleecam.bridge — ReEDS capacity-expansion output -> BLEECAM REE demand.

SKELETON for Claude Code to flesh out. The five functions below are the whole pipeline;
keep them pure where possible and unit-test the capacity->demand math on the stub before
wiring BLEECAM. See PROTOTYPE_BRIEF.md (spec) and CLAUDE.md (operating guide).
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
OUTPUTS = Path(__file__).resolve().parents[2] / "outputs"

# Default snapshot->period map: the 5 ReEDS build-intervals (2030..2050) onto the REE case's
# 5 model periods (rare_earth.case.yaml time_periods = 5). See to_bleecam_demand(period_map=).
DEFAULT_PERIOD_MAP = {2030: 0, 2035: 1, 2040: 2, 2045: 3, 2050: 4}


def tech_key(reeds_tech: str) -> str:
    """Map a ReEDS technology-class name to an intensity-matrix key.

    ReEDS names resource classes with numeric suffixes: 'wind-ons_1'..'wind-ons_10',
    'wind-ofs_1'..'wind-ofs_15', 'upv_1'.., 'battery_4'. Collapse the suffix:
        'wind-ofs_5' -> 'wind-ofs' ; 'battery_4' -> 'battery' ; 'gas-cc' -> 'gas-cc'.
    """
    base = re.sub(r"_\d+$", "", reeds_tech.strip())
    return {"battery": "battery"}.get(base, base)  # extend aliases as needed


def load_reeds(path: str | Path, scenario: str) -> pd.DataFrame:
    """Load a ReEDS capacity table for one scenario.

    Stub schema: scenario, technology, region, year, capacity_GW.
    Real ReEDS: runs/{case}/outputs/cap.csv with columns i (tech), r (region), t (year),
    MW -> normalize to the stub schema here so the rest of the pipeline is source-agnostic.
    Returns tidy rows with an added 'tech_key' column and capacity in MW.
    TODO: add a `from_reeds_cap_csv()` normalizer for the real file.
    """
    df = pd.read_csv(path)
    df = df[df["scenario"] == scenario].copy()
    df["tech_key"] = df["technology"].map(tech_key)
    df["capacity_MW"] = df["capacity_GW"] * 1000.0
    return df


# NREL 2024 Standard Scenarios national file uses friendly per-tech capacity columns (MW).
# Map the stripped column name (col without the trailing '_MW') -> intensity-matrix tech_key.
# Only wind carries REE at this boundary; everything else resolves to a key the matrix lacks
# (-> 0 intensity), so an unmapped tech is harmless.
_STDSCEN_TECH = {
    "wind_onshore": "wind-ons",
    "wind_offshore": "wind-ofs",
    "upv": "upv", "distpv": "upv",
    "battery_4": "battery", "battery_8": "battery",
    "gas_cc": "gas-cc", "gas_cc_ccs": "gas-cc", "gas_ct": "gas-cc",
    "nuclear": "nuclear", "nuclear_smr": "nuclear",
}


def from_stdscen_national(path: str | Path, scenario: str) -> pd.DataFrame:
    """Load one scenario from the NREL Standard Scenarios **annual national** CSV.

    This is the real-data path (e.g. data/.../StdScen24_annual_national.csv, OEDI submission
    6453). The file has two note rows, a human header, then a machine header; capacity columns
    end in '_MW' (generation columns end in '_MWh', loads too). We melt the per-tech capacity
    columns to the same tidy frame load_reeds returns (scenario, technology, region, year,
    capacity_GW, tech_key, capacity_MW), with region='US' since the file is already national.
    """
    raw = pd.read_csv(path, skiprows=[0, 1, 2])  # -> machine header (scenario, policy, t, ...)
    raw = raw[raw["scenario"] == scenario].copy()
    if raw.empty:
        raise ValueError(f"scenario {scenario!r} not found in {Path(path).name}")

    cap_cols = [c for c in raw.columns if c.endswith("_MW")]  # capacity only (not _MWh)
    long = raw.melt(id_vars=["scenario", "t"], value_vars=cap_cols,
                    var_name="technology", value_name="capacity_MW")
    long["technology"] = long["technology"].str.slice(0, -3)  # drop '_MW'
    long["tech_key"] = long["technology"].map(lambda t: _STDSCEN_TECH.get(t, t))
    long = long.rename(columns={"t": "year"})
    long["year"] = long["year"].astype(int)
    long["region"] = "US"
    long["capacity_MW"] = long["capacity_MW"].fillna(0.0).astype(float)
    long["capacity_GW"] = long["capacity_MW"] / 1000.0
    return long[["scenario", "technology", "region", "year", "capacity_GW", "tech_key", "capacity_MW"]]


def capacity_to_ree(cap: pd.DataFrame, intensity_path: str | Path = DATA / "ree_intensity_matrix.csv",
                    basis: str = "incremental") -> pd.DataFrame:
    """Convert capacity to REE demand (kg NdFeB, Nd, Pr, Dy) by year.

    Steps:
      1. Sum capacity_MW over region to get installed capacity per (tech_key, year).
      2. basis='incremental' (default): magnet demand is driven by NEW builds, so use the
         year-over-year delta of installed capacity per tech. The first year of each tech has
         no prior reference, so its built_MW is 0 (its capacity is pre-existing stock, not a
         build in the modelled window). Negative deltas (retirements) are clipped to 0 — they
         feed the later recycling/stock phase, not new-magnet demand.
         basis='cumulative': use installed capacity directly (upper-bound / stock view).
      3. Join the intensity matrix on tech_key; techs absent from the matrix contribute 0.
      4. ndfeb_kg = built_MW * ndfeb_kg_per_MW; element_kg = ndfeb_kg * element_frac.
      5. Sum over techs -> one row per year.

    Returns columns: year, ndfeb_kg, nd_kg, pr_kg, dy_kg, ree_bearing_MW
    (Nd+Pr are the NdPr magnet stream; ree_bearing_MW is the wind build that carries the magnets).
    """
    if basis not in ("incremental", "cumulative"):
        raise ValueError(f"basis must be 'incremental' or 'cumulative', got {basis!r}")

    intensity = pd.read_csv(intensity_path)

    # 1. installed capacity per tech_key, year (sum regions)
    g = (cap.groupby(["tech_key", "year"], as_index=False)["capacity_MW"].sum()
            .sort_values(["tech_key", "year"]))

    # 2. new-build basis
    if basis == "incremental":
        g["built_MW"] = g.groupby("tech_key")["capacity_MW"].diff().fillna(0.0).clip(lower=0.0)
    else:  # cumulative
        g["built_MW"] = g["capacity_MW"]

    # 3. join intensity (missing techs -> 0, i.e. no REE at this boundary)
    num_cols = ["ndfeb_kg_per_MW", "nd_frac", "pr_frac", "dy_frac"]
    m = g.merge(intensity[["technology", *num_cols]].rename(columns={"technology": "tech_key"}),
                on="tech_key", how="left")
    m[num_cols] = m[num_cols].fillna(0.0)

    # 4. per-element mass; track the REE-bearing (intensity>0) build MW separately — it is the
    #    deployment curve that actually drives magnet demand on the BLEECAM side.
    m["ndfeb_kg"] = m["built_MW"] * m["ndfeb_kg_per_MW"]
    m["nd_kg"] = m["ndfeb_kg"] * m["nd_frac"]
    m["pr_kg"] = m["ndfeb_kg"] * m["pr_frac"]
    m["dy_kg"] = m["ndfeb_kg"] * m["dy_frac"]
    m["ree_bearing_MW"] = m["built_MW"].where(m["ndfeb_kg_per_MW"] > 0, 0.0)

    # 5. sum techs -> per year
    out = (m.groupby("year", as_index=False)[["ndfeb_kg", "nd_kg", "pr_kg", "dy_kg", "ree_bearing_MW"]].sum()
            .sort_values("year")
            .reset_index(drop=True))
    return out


# BLEECAM's Demand_Input_Template.csv column order (rare_earth case). The REE case loader
# (bleecam/cases/rare_earth/data_loader.py) reads magnet demand as
#   hp_magnet_demand * `Deployment Curve MW` + `Data center magnet kg`
# per time_period, plus `mass ratio Nd` / `mass ratio Dy`. The remaining columns are
# human-reference only (not consumed), but we populate them to match the template.
BLEECAM_DEMAND_COLS = [
    "time_period", "hp_magnet_demand", "unit", "Deployment Curve MW",
    "mass ratio Nd", "mass ratio Dy", "total magnet required",
    "Data Center Nd kg", "Data center magnet kg",
]
BASE_YEAR = 2025  # ReEDS/BLEECAM period 0


def _bleecam_demand_template() -> Path:
    """Locate the installed BLEECAM rare-earth Demand_Input_Template.csv (editable clone or wheel)."""
    try:
        import bleecam  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - environment dependent
        raise FileNotFoundError(
            "bleecam is not importable; pass template_path= to to_bleecam_demand()."
        ) from e
    return Path(bleecam.__file__).resolve().parent / "cases" / "rare_earth" / "data" / "Demand_Input_Template.csv"


def to_bleecam_demand(ree: pd.DataFrame, out_path: str | Path,
                      template_path: str | Path | None = None,
                      base_year: int = BASE_YEAR,
                      period_map: dict[int, int] | None = None) -> Path:
    """Write a BLEECAM rare-earth Demand_Input_Template.csv from REE demand.

    The REE case models magnet demand per period as
        hp_magnet_demand (kg NdFeB/MW)  x  `Deployment Curve MW`  +  `Data center magnet kg`.
    We map the power-sector wind build onto that product and leave the independent
    data-center magnet stream untouched (only power-sector demand changes between scenarios):
      - `Deployment Curve MW` <- ree.ree_bearing_MW (the wind build carrying the magnets)
      - `hp_magnet_demand`    <- ndfeb_kg / ree_bearing_MW (capacity-weighted blended intensity)
        so the product reproduces our computed ndfeb_kg exactly.
      - `mass ratio Nd`       <- (nd_kg + pr_kg) / ndfeb_kg   (BLEECAM's single light-RE stream
        is NdPr; template default 0.3 ~ NdPr), `mass ratio Dy` <- dy_kg / ndfeb_kg.
      - `Data center magnet kg` / `Data Center Nd kg` are carried through from the template.

    Horizon / period mapping. The shipped template file has **26 annual rows (0..25 =
    2025..2050)**, but the REE *case* as configured (rare_earth.case.yaml: time_periods) solves
    only its first `num_time_periods` periods — so the brief's "6 periods 2025-2030" is stale on
    both counts. Two mapping modes:
      - period_map=None (default): annualize — spread each ReEDS 5-year interval's new build
        evenly across the annual periods in that interval (period = year - base_year), over the
        template's full period set. Total magnet conserved. Use when the case runs annual periods.
      - period_map={reeds_year: bleecam_period}: place each snapshot's incremental build directly
        at its mapped period, zero power-sector demand elsewhere. Use to line the ReEDS snapshots
        up with a short (e.g. 5-period) model horizon, e.g. {2030:0, 2035:1, 2040:2, 2045:3, 2050:4}.
    Either way the data-center stream and template period set are carried through unchanged.

    `ree` must be an incremental (new-build) frame from capacity_to_ree. Pass template_path to
    override the template used for the period set and data-center columns.
    """
    required = {"year", "ndfeb_kg", "nd_kg", "pr_kg", "dy_kg", "ree_bearing_MW"}
    missing = required - set(ree.columns)
    if missing:
        raise ValueError(f"ree frame is missing columns: {sorted(missing)}")

    template_path = Path(template_path) if template_path is not None else _bleecam_demand_template()
    tmpl = pd.read_csv(template_path)
    periods = sorted(int(p) for p in tmpl["time_period"])

    # per-period data-center stream (carried through unchanged); default 0 where absent
    dc_magnet = dict(zip(tmpl["time_period"].astype(int), tmpl["Data center magnet kg"]))
    dc_nd = dict(zip(tmpl["time_period"].astype(int), tmpl.get("Data Center Nd kg", pd.Series(dtype=float))))

    # constant mass ratios derived from our demand (fall back to template if no REE at all)
    total_ndfeb = float(ree["ndfeb_kg"].sum())
    if total_ndfeb > 0:
        nd_ratio = float((ree["nd_kg"] + ree["pr_kg"]).sum()) / total_ndfeb
        dy_ratio = float(ree["dy_kg"].sum()) / total_ndfeb
    else:
        nd_ratio = float(tmpl["mass ratio Nd"].iloc[0])
        dy_ratio = float(tmpl["mass ratio Dy"].iloc[0])

    r = ree.sort_values("year").reset_index(drop=True)
    magnet_by_p: dict[int, float] = {p: 0.0 for p in periods}
    deploy_by_p: dict[int, float] = {p: 0.0 for p in periods}

    if period_map is not None:
        # direct placement: snapshot's incremental build lands on its mapped period
        for _, row in r.iterrows():
            yr = int(row["year"])
            if yr not in period_map:
                continue
            p = period_map[yr]
            if p not in magnet_by_p:
                raise ValueError(f"period_map sends year {yr} to period {p}, "
                                 f"not in the template's periods {periods}")
            magnet_by_p[p] += float(row["ndfeb_kg"])
            deploy_by_p[p] += float(row["ree_bearing_MW"])
    else:
        # annualize: spread each ReEDS interval's magnet + deployment across its annual periods
        years = r["year"].tolist()
        for i in range(1, len(years)):
            y_prev, y = int(years[i - 1]), int(years[i])
            span = y - y_prev
            if span <= 0:
                continue
            magnet_per_yr = float(r["ndfeb_kg"].iloc[i]) / span
            deploy_per_yr = float(r["ree_bearing_MW"].iloc[i]) / span
            for c in range(y_prev + 1, y + 1):
                p = c - base_year
                if p in magnet_by_p:
                    magnet_by_p[p] += magnet_per_yr
                    deploy_by_p[p] += deploy_per_yr

    rows = []
    for p in periods:
        magnet = magnet_by_p[p]
        deploy = deploy_by_p[p]
        intensity = magnet / deploy if deploy > 0 else 0.0
        rows.append({
            "time_period": p,
            "hp_magnet_demand": intensity,
            "unit": "kg/MW",
            "Deployment Curve MW": deploy,
            "mass ratio Nd": nd_ratio,
            "mass ratio Dy": dy_ratio,
            "total magnet required": magnet,
            "Data Center Nd kg": float(dc_nd.get(p, 0.0) or 0.0),
            "Data center magnet kg": float(dc_magnet.get(p, 0.0) or 0.0),
        })

    out = pd.DataFrame(rows, columns=BLEECAM_DEMAND_COLS)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    return out_path


def _bleecam_case_data_dir() -> Path:
    """Installed BLEECAM rare-earth case data dir (holds all the non-demand input CSVs)."""
    import bleecam  # noqa: PLC0415
    return Path(bleecam.__file__).resolve().parent / "cases" / "rare_earth" / "data"


def run_bleecam(demand_path: str | Path, out_dir: str | Path,
                case_data_dir: str | Path | None = None,
                python: str | None = None, timeout: int = 1800) -> dict:
    """Run the BLEECAM rare-earth REE case on one scenario's demand file, return its summary.

    The REE entry point (`bleecam-ree`, = bleecam.cases.rare_earth.REE:main) takes a `--data`
    directory of input CSVs and writes results to `--out`. Only demand changes between energy
    scenarios (brief), so we stage a copy of the installed case data dir, drop in `demand_path`
    as Demand_Input_Template.csv, and run the case against that stage. main() hardcodes the ipopt
    solver (the report solver); ensure `conda install -c conda-forge ipopt`.

    Returns a dict: scenario out_dir, termination/objective from run_summary.json, the results
    CSV path, and the solver stdout tail. Raises RuntimeError if the solve did not produce results.

    NOTE: the case solves only `num_time_periods` periods (rare_earth.case.yaml); map the ReEDS
    snapshots onto exactly those periods in to_bleecam_demand (period_map=) or later rows are ignored.
    """
    import shutil
    import subprocess
    import sys

    demand_path = Path(demand_path).resolve()
    out_dir = Path(out_dir).resolve()
    case_data_dir = Path(case_data_dir).resolve() if case_data_dir else _bleecam_case_data_dir()
    python = python or sys.executable

    # stage a full copy of the case inputs, then overwrite demand with ours
    stage = out_dir / "data"
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(case_data_dir, stage)
    shutil.copyfile(demand_path, stage / "Demand_Input_Template.csv")

    # run the REE case against the staged inputs; write results into out_dir
    cmd = [python, "-m", "bleecam.cases.rare_earth.REE", "--data", str(stage), "--out", str(out_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=out_dir)

    results_csv = out_dir / "model_results_multilocation.csv"
    summary_json = out_dir / "run_summary.json"
    if proc.returncode != 0 or not summary_json.exists():
        tail = (proc.stdout or "")[-2000:] + "\n--- stderr ---\n" + (proc.stderr or "")[-2000:]
        raise RuntimeError(f"bleecam-ree failed (rc={proc.returncode}) for {demand_path.name}.\n{tail}")

    import json
    summary = json.loads(summary_json.read_text())
    return {
        "demand_file": str(demand_path),
        "out_dir": str(out_dir),
        "results_csv": str(results_csv) if results_csv.exists() else None,
        "run_summary": summary,
        "objective_real_usd": summary.get("objective_real_usd"),
        "objective_name": summary.get("objective_name"),
        "n_periods": summary.get("n_periods"),
        "stdout_tail": (proc.stdout or "")[-1500:],
    }


def _import_share(res: pd.DataFrame) -> tuple[float, float]:
    """From a results frame, share of hp_magnet manufacturing output that is imported / Chinese."""
    m = res[(res["source"] == "magnet manufacturing") & (res["material"] == "hp_magnet")]
    tot = float(m["flow_value"].sum())
    if tot <= 0:
        return (float("nan"), float("nan"))
    us = float(m.loc[m["source_location"] == "US", "flow_value"].sum())
    cn = float(m.loc[m["source_location"] == "CN", "flow_value"].sum())
    return (1.0 - us / tot, cn / tot)


def _by_period_demand(demand_csv: Path) -> dict[int, float]:
    """Required magnet per period from a BLEECAM demand file (hp_magnet*deployment + data-center)."""
    d = pd.read_csv(demand_csv)
    return {int(r["time_period"]): float(r["hp_magnet_demand"] * r["Deployment Curve MW"]
                                        + r["Data center magnet kg"]) for _, r in d.iterrows()}


def compare(scenarios: list[str], stub_path: str | Path = DATA / "reeds_stub_capacity.csv",
            out_root: str | Path = OUTPUTS, period_map: dict[int, int] | None = None,
            reuse_existing: bool = True, write_csv: bool = True,
            loader=load_reeds, years: list[int] | None = None) -> pd.DataFrame:
    """Run the whole chain for each energy scenario and assemble the cross-scenario comparison.

    For each scenario: load_reeds -> capacity_to_ree -> to_bleecam_demand -> run_bleecam, then
    read back BLEECAM's results. Returns a tidy one-row-per-scenario frame with the demo's money
    metrics: REE demand (our bridge) + BLEECAM cost / GWP / import share / supply gap (the solve).

    reuse_existing: skip the (slow) ipopt solve if run_<scenario>/run_summary.json already exists.
    Also writes comparison_summary.csv and comparison_by_period.csv under out_root (for figures).
    """
    period_map = period_map or DEFAULT_PERIOD_MAP
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    rows, per_period = [], []
    for s in scenarios:
        cap = loader(stub_path, s)
        if years is not None:
            cap = cap[cap["year"].isin(years)].copy()
        ree = capacity_to_ree(cap)
        demand_csv = out_root / f"Demand_Input_{s}.csv"
        to_bleecam_demand(ree, demand_csv, period_map=period_map)

        run_dir = out_root / f"run_{s}"
        summary_json = run_dir / "run_summary.json"
        if not (reuse_existing and summary_json.exists()):
            run_bleecam(demand_csv, run_dir)

        import json
        summary = json.loads(summary_json.read_text())
        res = pd.read_csv(run_dir / "model_results_multilocation.csv")

        gwp_total = float((res["flow_value"] * res["emission_factor"]).sum())
        import_share, cn_share = _import_share(res)

        # supply gap = required - delivered (magnet_market_mix -> use phase), per modelled period
        required = _by_period_demand(demand_csv)
        delivered = (res[(res["destination"] == "use phase") & (res["material"] == "hp_magnet")]
                     .groupby("time_period")["flow_value"].sum().to_dict())
        gap_total = 0.0
        for p in sorted(int(x) for x in res["time_period"].unique()):
            req, dlv = required.get(p, 0.0), float(delivered.get(p, 0.0))
            gap = max(req - dlv, 0.0)
            gap_total += gap
            per_period.append({"scenario": s, "time_period": p, "required_kg": req,
                               "delivered_kg": dlv, "supply_gap_kg": gap})

        rows.append({
            "scenario": s,
            "ree_ndfeb_kg": float(ree["ndfeb_kg"].sum()),
            "ree_nd_kg": float(ree["nd_kg"].sum()),
            "ree_pr_kg": float(ree["pr_kg"].sum()),
            "ree_dy_kg": float(ree["dy_kg"].sum()),
            "bleecam_cost_usd": summary.get("objective_real_usd"),
            "gwp_total_kgco2e": gwp_total,
            "import_share": import_share,
            "china_share": cn_share,
            "supply_gap_kg": gap_total,
            "unused_oxides_kg": summary.get("unused_oxides_kg"),
        })

    summary_df = pd.DataFrame(rows)
    if write_csv:
        summary_df.to_csv(out_root / "comparison_summary.csv", index=False)
        pd.DataFrame(per_period).to_csv(out_root / "comparison_by_period.csv", index=False)
    return summary_df


if __name__ == "__main__":
    # Smoke test the piece that needs no solver:
    cap = load_reeds(DATA / "reeds_stub_capacity.csv", "HighRE")
    print(cap.groupby("tech_key")["capacity_MW"].sum())
    print("\nNext: implement capacity_to_ree() and test REE demand on the stub before wiring BLEECAM.")
