"""Unit tests for the capacity -> REE demand math, run on the shipped stub.

These cover the piece that needs no solver: load_reeds + capacity_to_ree. The expected
numbers are derived by hand from data/reeds_stub_capacity.csv and ree_intensity_matrix.csv,
so they double as a regression guard on both the math and the data contracts.
"""
import pandas as pd
import pytest

from reeds2bleecam.bridge import (
    tech_key, load_reeds, capacity_to_ree, to_bleecam_demand, BLEECAM_DEMAND_COLS, DATA,
    _import_share, _by_period_demand,
)

STUB = DATA / "reeds_stub_capacity.csv"

# Intensity values the stub ships with (keep in sync with ree_intensity_matrix.csv).
OFS_KG_PER_MW = 600.0
ONS_KG_PER_MW = 120.0
ND_FRAC, PR_FRAC, DY_FRAC = 0.23, 0.05, 0.03


@pytest.fixture
def ref():
    return load_reeds(STUB, "Reference")


@pytest.fixture
def highre():
    return load_reeds(STUB, "HighRE")


# --- tech_key mapping ---------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("wind-ons_1", "wind-ons"),
    ("wind-ons_10", "wind-ons"),
    ("wind-ofs_5", "wind-ofs"),
    ("upv_1", "upv"),
    ("battery_4", "battery"),
    ("gas-cc", "gas-cc"),
    ("nuclear", "nuclear"),
    (" wind-ofs_15 ", "wind-ofs"),  # whitespace tolerated
])
def test_tech_key_collapses_resource_classes(raw, expected):
    assert tech_key(raw) == expected


# --- load_reeds ---------------------------------------------------------------

def test_load_reeds_filters_scenario_and_converts_to_MW(highre):
    assert (highre["scenario"] == "HighRE").all()
    # GW -> MW
    row = highre[(highre["technology"] == "wind-ons_1") & (highre["year"] == 2025)].iloc[0]
    assert row["capacity_MW"] == pytest.approx(78 * 1000.0)


# --- capacity_to_ree: structure ----------------------------------------------

def test_output_schema_and_year_coverage(highre):
    out = capacity_to_ree(highre)
    assert list(out.columns) == ["year", "ndfeb_kg", "nd_kg", "pr_kg", "dy_kg", "ree_bearing_MW"]
    assert out["year"].tolist() == [2025, 2030, 2035, 2040, 2045, 2050]
    assert out["year"].is_monotonic_increasing


def test_ree_bearing_mw_is_wind_only(highre):
    """ree_bearing_MW must equal the wind new-build MW (non-wind carries no magnets)."""
    out = capacity_to_ree(highre)
    # 2030 HighRE wind new build: ons (220-140) + ofs (20-0.2) GW -> MW
    exp = ((220 - 140) + (20 - 0.2)) * 1000.0
    assert out[out["year"] == 2030]["ree_bearing_MW"].iloc[0] == pytest.approx(exp)


def test_demand_is_non_negative(highre):
    out = capacity_to_ree(highre)
    assert (out[["ndfeb_kg", "nd_kg", "pr_kg", "dy_kg"]].to_numpy() >= 0).all()


def test_non_wind_contributes_zero_ree():
    """A build of only solar/battery/gas/nuclear must yield exactly zero REE."""
    non_wind = pd.DataFrame({
        "tech_key": ["upv", "battery", "gas-cc", "nuclear"],
        "year": [2030, 2030, 2030, 2030],
        "capacity_MW": [1e6, 1e6, 1e6, 1e6],
    })
    # cumulative so the single year counts directly
    out = capacity_to_ree(non_wind, basis="cumulative")
    assert out["ndfeb_kg"].sum() == 0.0


# --- capacity_to_ree: incremental (new-build) basis ---------------------------

def test_incremental_first_year_is_zero(highre):
    """First modelled year has no prior stock reference -> 0 new-build demand."""
    out = capacity_to_ree(highre, basis="incremental")
    first = out[out["year"] == 2025].iloc[0]
    assert first[["ndfeb_kg", "nd_kg", "pr_kg", "dy_kg"]].to_numpy() == pytest.approx(0.0)


def test_incremental_2030_matches_hand_calc(highre):
    """HighRE 2030 new-build, computed by hand from the stub.

    wind-ons: (wind-ons_1 120+... ) 2025 = 78+62 = 140 GW; 2030 = 120+100 = 220 GW -> +80 GW
    wind-ofs: 2025 = 0.2+0 = 0.2 GW; 2030 = 12+8 = 20 GW -> +19.8 GW
    """
    out = capacity_to_ree(highre, basis="incremental")
    built_ons_MW = (220 - 140) * 1000.0
    built_ofs_MW = (20 - 0.2) * 1000.0
    exp_ndfeb = built_ons_MW * ONS_KG_PER_MW + built_ofs_MW * OFS_KG_PER_MW
    row = out[out["year"] == 2030].iloc[0]
    assert row["ndfeb_kg"] == pytest.approx(exp_ndfeb)
    assert row["nd_kg"] == pytest.approx(exp_ndfeb * ND_FRAC)
    assert row["pr_kg"] == pytest.approx(exp_ndfeb * PR_FRAC)
    assert row["dy_kg"] == pytest.approx(exp_ndfeb * DY_FRAC)


def test_element_fractions_track_magnet_mass(highre):
    out = capacity_to_ree(highre)
    built = out[out["ndfeb_kg"] > 0]
    assert (built["nd_kg"] / built["ndfeb_kg"]).round(6).eq(ND_FRAC).all()
    assert (built["dy_kg"] / built["ndfeb_kg"]).round(6).eq(DY_FRAC).all()


def test_retirements_do_not_create_demand():
    """A declining tech (negative delta) must not produce negative or phantom demand."""
    declining = pd.DataFrame({
        "tech_key": ["wind-ofs", "wind-ofs"],
        "year": [2025, 2030],
        "capacity_MW": [10_000.0, 4_000.0],  # 6 GW retired
    })
    out = capacity_to_ree(declining, basis="incremental")
    assert (out["ndfeb_kg"] >= 0).all()
    assert out["ndfeb_kg"].sum() == 0.0  # nothing built, only retired


# --- the money chart: HighRE > Reference --------------------------------------

def test_highre_builds_more_ree_than_reference(ref, highre):
    ref_total = capacity_to_ree(ref)["ndfeb_kg"].sum()
    high_total = capacity_to_ree(highre)["ndfeb_kg"].sum()
    assert high_total > ref_total


def test_cumulative_at_least_incremental(highre):
    """Cumulative (stock) demand should not be below incremental new-build demand."""
    inc = capacity_to_ree(highre, basis="incremental")["ndfeb_kg"].sum()
    cum = capacity_to_ree(highre, basis="cumulative")["ndfeb_kg"].sum()
    assert cum >= inc


def test_bad_basis_rejected(highre):
    with pytest.raises(ValueError):
        capacity_to_ree(highre, basis="nonsense")


# --- to_bleecam_demand --------------------------------------------------------

def _synthetic_template(path, n_periods=26, dc_magnet=1000.0):
    """A minimal 26-period (2025..2050 annual) stand-in for BLEECAM's template."""
    rows = [{
        "time_period": p, "hp_magnet_demand": 0.0, "unit": "kg/MW",
        "Deployment Curve MW": 0.0, "mass ratio Nd": 0.3, "mass ratio Dy": 0.02,
        "total magnet required": 0.0, "Data Center Nd kg": 500.0 + p,
        "Data center magnet kg": dc_magnet + p,
    } for p in range(n_periods)]
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture
def template(tmp_path):
    return _synthetic_template(tmp_path / "tmpl.csv")


def test_demand_file_schema_and_periods(highre, template, tmp_path):
    out = capacity_to_ree(highre)
    p = to_bleecam_demand(out, tmp_path / "demand.csv", template_path=template)
    df = pd.read_csv(p)
    assert list(df.columns) == BLEECAM_DEMAND_COLS
    assert df["time_period"].tolist() == list(range(26))  # 2025..2050 annual


def test_demand_reproduces_bleecam_formula(highre, template, tmp_path):
    """Per period, hp_magnet_demand * Deployment Curve MW == total magnet required."""
    out = capacity_to_ree(highre)
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=template))
    lhs = df["hp_magnet_demand"] * df["Deployment Curve MW"]
    assert lhs.to_numpy() == pytest.approx(df["total magnet required"].to_numpy())


def test_demand_conserves_total_magnet(highre, template, tmp_path):
    """Annualization spreads but does not create/destroy magnet mass."""
    out = capacity_to_ree(highre)
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=template))
    assert df["total magnet required"].sum() == pytest.approx(out["ndfeb_kg"].sum())
    assert df["Deployment Curve MW"].sum() == pytest.approx(out["ree_bearing_MW"].sum())


def test_demand_period_zero_is_data_center_only(highre, template, tmp_path):
    """2025 (period 0) has no new-build magnet; only the data-center stream remains."""
    out = capacity_to_ree(highre)
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=template))
    row0 = df[df["time_period"] == 0].iloc[0]
    assert row0["total magnet required"] == pytest.approx(0.0)
    assert row0["Data center magnet kg"] == pytest.approx(1000.0)  # carried from template


def test_demand_carries_data_center_stream_unchanged(highre, template, tmp_path):
    out = capacity_to_ree(highre)
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=template))
    tmpl = pd.read_csv(template)
    assert df["Data center magnet kg"].tolist() == tmpl["Data center magnet kg"].tolist()
    assert df["Data Center Nd kg"].tolist() == tmpl["Data Center Nd kg"].tolist()


def test_demand_mass_ratios_use_ndpr_stream(highre, template, tmp_path):
    out = capacity_to_ree(highre)
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=template))
    total = out["ndfeb_kg"].sum()
    exp_nd = (out["nd_kg"] + out["pr_kg"]).sum() / total   # NdPr combined
    exp_dy = out["dy_kg"].sum() / total
    assert df["mass ratio Nd"].unique() == pytest.approx([exp_nd])
    assert df["mass ratio Dy"].unique() == pytest.approx([exp_dy])


def test_demand_period_map_places_snapshots_directly(highre, template, tmp_path):
    """period_map lines ReEDS snapshots up with a short model horizon, no annualization."""
    out = capacity_to_ree(highre)
    pmap = {2030: 0, 2035: 1, 2040: 2, 2045: 3, 2050: 4}
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=template, period_map=pmap))
    # period 0 should carry exactly the 2030 snapshot's incremental build, undivided
    exp_2030 = out[out["year"] == 2030]["ndfeb_kg"].iloc[0]
    assert df[df["time_period"] == 0]["total magnet required"].iloc[0] == pytest.approx(exp_2030)
    # periods >=5 carry no power-sector demand (2050 mapped to 4; nothing beyond)
    assert df[df["time_period"] >= 5]["total magnet required"].sum() == pytest.approx(0.0)
    # still conserves the mapped snapshots' total
    assert df["total magnet required"].sum() == pytest.approx(out["ndfeb_kg"].sum())


def test_demand_period_map_rejects_out_of_range(highre, template, tmp_path):
    out = capacity_to_ree(highre)
    with pytest.raises(ValueError):
        to_bleecam_demand(out, tmp_path / "d.csv", template_path=template,
                          period_map={2030: 99})  # 99 not a template period


def test_demand_roundtrips_through_bleecam_loader(highre, tmp_path):
    """Strongest check: feed our file to BLEECAM's own loader math and recover demand.

    Uses the installed rare-earth template (skipped if bleecam is absent).
    """
    bc = pytest.importorskip("bleecam")
    from pathlib import Path
    tmpl = Path(bc.__file__).resolve().parent / "cases" / "rare_earth" / "data" / "Demand_Input_Template.csv"
    if not tmpl.exists():
        pytest.skip("installed BLEECAM template not found")
    out = capacity_to_ree(highre)
    df = pd.read_csv(to_bleecam_demand(out, tmp_path / "d.csv", template_path=tmpl))
    # BLEECAM: magnet demand per period = hp_magnet_demand * Deployment Curve MW + Data center magnet kg
    bleecam_demand = (df["hp_magnet_demand"] * df["Deployment Curve MW"] + df["Data center magnet kg"]).sum()
    dc = pd.read_csv(tmpl)["Data center magnet kg"].sum()
    assert bleecam_demand == pytest.approx(out["ndfeb_kg"].sum() + dc)


# --- compare() helpers (solver-free) ------------------------------------------

def test_import_share_splits_by_source_location():
    res = pd.DataFrame({
        "source": ["magnet manufacturing"] * 3 + ["use phase"],
        "material": ["hp_magnet"] * 3 + ["hp_magnet"],
        "source_location": ["US", "CN", "JP", "US"],
        "flow_value": [60.0, 10.0, 30.0, 5.0],  # use-phase row must be ignored
    })
    imp, cn = _import_share(res)
    assert imp == pytest.approx(0.40)   # 40% not from US
    assert cn == pytest.approx(0.10)    # 10% from China


def test_import_share_nan_when_no_magnet():
    res = pd.DataFrame({"source": ["mining"], "material": ["iron"],
                        "source_location": ["AU"], "flow_value": [1.0]})
    imp, cn = _import_share(res)
    assert pd.isna(imp) and pd.isna(cn)


def test_by_period_demand_matches_bleecam_formula(highre, template, tmp_path):
    out = capacity_to_ree(highre)
    pmap = {2030: 0, 2035: 1, 2040: 2, 2045: 3, 2050: 4}
    demand_csv = to_bleecam_demand(out, tmp_path / "d.csv", template_path=template, period_map=pmap)
    req = _by_period_demand(demand_csv)
    df = pd.read_csv(demand_csv)
    row0 = df[df["time_period"] == 0].iloc[0]
    assert req[0] == pytest.approx(row0["hp_magnet_demand"] * row0["Deployment Curve MW"]
                                   + row0["Data center magnet kg"])


def test_build_figures_smoke(tmp_path):
    """Figures render from synthetic comparison CSVs without a solver or display."""
    from reeds2bleecam.figures import build_figures
    (tmp_path / "comparison_summary.csv").write_text(
        "scenario,bleecam_cost_usd,gwp_total_kgco2e,import_share,china_share\n"
        "Reference,1.0e10,1.1e9,0.98,0.03\nHighRE,1.4e11,1.4e9,1.0,0.12\n")
    (tmp_path / "comparison_by_period.csv").write_text(
        "scenario,time_period,required_kg,delivered_kg,supply_gap_kg\n"
        "Reference,0,100,100,0\nReference,1,200,150,50\n"
        "HighRE,0,300,200,100\nHighRE,1,400,250,150\n")
    figs = build_figures(["Reference", "HighRE"], out_root=tmp_path, figdir=tmp_path / "figs")
    assert len(figs) == 3
    assert all(p.exists() and p.stat().st_size > 0 for p in figs)


# --- from_stdscen_national (real NREL Standard Scenarios national format) ------

def _synthetic_stdscen(path):
    """Mimic the 2024 national CSV: 2 note rows, a human header, a machine header, then data."""
    path.write_text(
        "Note line one about metric definitions\n"
        "Note line two about rounding\n"
        "Scenario,Policy,Country,Year,Onshore wind (MW),Offshore wind (MW),PV (MW),Nuclear (MW),PV gen (MWh)\n"
        "scenario,policy,country,t,wind_onshore_MW,wind_offshore_MW,upv_MW,nuclear_MW,upv_MWh\n"
        "Mid_Case,currentPolicies,USA,2026,100000,5000,150000,98000,300000000\n"
        "Mid_Case,currentPolicies,USA,2029,140000,12000,250000,97000,450000000\n"
        "Other,x,USA,2026,1,1,1,1,1\n")
    return path


def test_from_stdscen_national_parses_and_maps(tmp_path):
    from reeds2bleecam.bridge import from_stdscen_national
    f = _synthetic_stdscen(tmp_path / "nat.csv")
    df = from_stdscen_national(f, "Mid_Case")
    assert set(df["scenario"]) == {"Mid_Case"}          # scenario filtered
    assert set(df["year"]) == {2026, 2029}
    assert (df["region"] == "US").all()                  # national
    # _MWh generation column excluded; only capacity (_MW) techs present
    assert set(df["technology"]) == {"wind_onshore", "wind_offshore", "upv", "nuclear"}
    # tech_key mapping onto intensity keys
    tk = dict(zip(df["technology"], df["tech_key"]))
    assert tk == {"wind_onshore": "wind-ons", "wind_offshore": "wind-ofs",
                  "upv": "upv", "nuclear": "nuclear"}
    # MW -> GW and MW preserved
    row = df[(df["technology"] == "wind_onshore") & (df["year"] == 2026)].iloc[0]
    assert row["capacity_MW"] == pytest.approx(100000.0)
    assert row["capacity_GW"] == pytest.approx(100.0)


def test_from_stdscen_feeds_capacity_to_ree(tmp_path):
    """Normalizer output drops straight into capacity_to_ree (same tidy contract)."""
    from reeds2bleecam.bridge import from_stdscen_national
    f = _synthetic_stdscen(tmp_path / "nat.csv")
    ree = capacity_to_ree(from_stdscen_national(f, "Mid_Case"))
    # 2029 onshore new build = (140000-100000) MW * 120 kg/MW; offshore (12000-5000)*600
    exp = (140000 - 100000) * 120.0 + (12000 - 5000) * 600.0
    assert ree[ree["year"] == 2029]["ndfeb_kg"].iloc[0] == pytest.approx(exp)


def test_from_stdscen_unknown_scenario_raises(tmp_path):
    from reeds2bleecam.bridge import from_stdscen_national
    f = _synthetic_stdscen(tmp_path / "nat.csv")
    with pytest.raises(ValueError):
        from_stdscen_national(f, "Nope")
