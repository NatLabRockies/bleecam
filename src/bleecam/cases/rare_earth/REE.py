import argparse
from pathlib import Path
import pandas as pd
from pyomo.environ import ConcreteModel, Set, Var, NonNegativeReals, ConstraintList, Objective, minimize, SolverFactory, value
from pyomo.opt import TerminationCondition
import pyomo.environ as pyo
from .config import list_of_processes, locations, materials, DEMAND_LOCATION, ALLOY, num_time_periods, time_stamp, PENALTY_UNUSED_OXIDE_COST, PENALTY_UNUSED_OXIDE_GWP, PENALTY_UNUSED_OXIDE_SLCA, DEFAULT_MAX_STOCK_CAPACITY, DEFAULT_STOCK_HOLDING_COST, FLOW_SCALE
from .data_loader import load_all_data, validate_csvs, validate_slca
from .constraints import fix_inactive_process_locations, fix_disallowed_trade_flows, clay_mining_constraints, clay_refining_constraints, beneficiation_constraints, sulfuric_acid_digestion_constraints, hydrochloric_acid_digestion_constraints, molten_salt_electrolysis_constraints, metallothermic_reduction_constraints, chemical_transformation_constraints, magnet_manufacturing_constraints, magnet_market_mix_constraints, demand_fulfillment_constraints, weibull_historic_retirement, use_phase_stock_constraints, fix_eol_outflows_at_t0, direct_reuse_constraints, magnet_to_magnet_recycling_constraints, hydrometallurgical_constraints, pyrometallurgical_constraints, cryogenic_constraints, add_stock_constraints, apply_capacity_constraints, add_unused_oxides_tracking
from .html_export import export_diagnostic_html

def _parse_args():
    """Parse CLI arguments for the single-objective BLEECAM solve.

    :returns: Parsed command-line arguments with 'data' and 'out' fields.
    :rtype: argparse.Namespace
    """
    _a = argparse.ArgumentParser()
    _a.add_argument('--data', type=Path, default=Path(__file__).parent / 'data')
    _a.add_argument('--out', type=Path, default=Path(__file__).parent / 'data')
    return _a.parse_args()


# ── Reusable API for the scenario runner + criticality library ────────────────
# These build the CLEAN base model (no report supply-shock overrides) and expose
# the generic contracts (`_arc_unit_cost`, `_bleecam_objective`) the library uses.
# `main()` is intentionally left untouched so the ipopt golden stays byte-identical;
# a later pass unifies main() onto build_model once the golden is reconfirmed.
def load_inputs(data_dir, out_dir=None):
    """Load REE data and expose a generic demand_df (FLOW_SCALE units, hp_magnet)."""
    data = load_all_data(data_dir)
    data['_data_dir'] = Path(data_dir)
    data['demand_df'] = pd.DataFrame([
        {'time_period': int(t), 'material': 'hp_magnet',
         'demand_kg': float(data['high_perf_magnet_required'].get(t, 0.0))}
        for t in time_stamp
    ])
    return data


def build_model(loaded_data, objective='cost'):
    """Build the clean REE base model (no report overrides) with generic contracts."""
    high_perf_magnet_required = loaded_data['high_perf_magnet_required']
    yield_factor = loaded_data['yield_factor']
    recovery_rate = loaded_data['recovery_rate']
    processing_cost = loaded_data['processing_cost']
    domestic_transport_cost = loaded_data['domestic_transport_cost']
    shipping_cost = loaded_data['shipping_cost']
    tariff_cost = loaded_data['tariff_cost']
    ef_factor = loaded_data['ef_factor']
    water_factor = loaded_data.get('water_factor', {})
    ct_mass_ratio_by_t = loaded_data['ct_mass_ratio_by_t']
    allowed_trade_arcs = loaded_data['allowed_trade_arcs']
    max_output_capacity = loaded_data['max_output_capacity']
    slca_factors = loaded_data['slca_factors']
    data_dir = loaded_data.get('_data_dir', Path(__file__).parent / 'data')

    model = ConcreteModel(name='Magnet Material Flow Model — Multi-Location')
    model.TimePeriods = Set(initialize=time_stamp)
    model.Processes = Set(initialize=list_of_processes)
    model.Processes2 = Set(initialize=list_of_processes)
    model.materials = Set(initialize=materials)
    model.Locations = Set(initialize=locations)
    model.T_max = max(model.TimePeriods)
    model.T_min = min(model.TimePeriods)
    model.StockMaterials = Set(initialize=['hp_magnet'])
    _UB = 50000000 / FLOW_SCALE
    model.flowQ = Var(model.TimePeriods, model.Processes, model.Locations, model.Processes2, model.Locations, model.materials, domain=NonNegativeReals, bounds=(0, _UB), initialize=0)
    model.stock_level = Var(model.TimePeriods, model.StockMaterials, domain=NonNegativeReals, bounds=(0, _UB), initialize=0)
    model.flow_to_stock = Var(model.TimePeriods, model.StockMaterials, domain=NonNegativeReals, bounds=(0, _UB), initialize=0)
    model.flow_from_stock = Var(model.TimePeriods, model.StockMaterials, domain=NonNegativeReals, bounds=(0, _UB), initialize=0)
    model.use_stock = Var(model.TimePeriods, domain=NonNegativeReals, bounds=(0, _UB))
    model.demand_slack_pos = Var(model.TimePeriods, domain=NonNegativeReals, initialize=0)
    model.demand_slack_neg = Var(model.TimePeriods, domain=NonNegativeReals, initialize=0)
    model.constraints = ConstraintList()
    slack_penalty_cost = 1000.0
    validate_csvs(time_periods=list(model.TimePeriods), yield_factor=yield_factor, recovery_rate=recovery_rate, processing_cost=processing_cost, domestic_transport_cost=domestic_transport_cost, ef_factor=ef_factor)
    validate_slca(list(model.TimePeriods), slca_factors)
    initial_stock = {'hp_magnet': 0.0}
    max_stock_capacity = {}
    stock_holding_cost = {}
    for t in model.TimePeriods:
        for mat in model.StockMaterials:
            max_stock_capacity[t, mat] = DEFAULT_MAX_STOCK_CAPACITY
            stock_holding_cost[t, mat] = DEFAULT_STOCK_HOLDING_COST
    for mat in model.StockMaterials:
        model.constraints.add(model.stock_level[model.T_min, mat] == initial_stock[mat])
    fix_inactive_process_locations(model)
    fix_disallowed_trade_flows(model, allowed_trade_arcs)
    demand_fulfillment_constraints(model, high_perf_magnet_required)
    _weibull_raw = weibull_historic_retirement(model, data_dir)
    _weibull_scaled = {t: v / FLOW_SCALE for (t, v) in _weibull_raw.items()}
    use_phase_stock_constraints(model, retirement_rate=0.02, initial_use_stock=0.0, historic_retirements_by_t=_weibull_scaled)
    clay_mining_constraints(model)
    clay_refining_constraints(model, yield_factor)
    beneficiation_constraints(model, yield_factor)
    sulfuric_acid_digestion_constraints(model, yield_factor)
    hydrochloric_acid_digestion_constraints(model, yield_factor)
    molten_salt_electrolysis_constraints(model, yield_factor)
    metallothermic_reduction_constraints(model, yield_factor)
    chemical_transformation_constraints(model, yield_factor, ct_mass_ratio_by_t, list_of_processes)
    magnet_manufacturing_constraints(model, yield_factor)
    fix_eol_outflows_at_t0(model)
    direct_reuse_constraints(model, recovery_rate)
    magnet_to_magnet_recycling_constraints(model, recovery_rate)
    hydrometallurgical_constraints(model, recovery_rate)
    pyrometallurgical_constraints(model, recovery_rate)
    cryogenic_constraints(model, recovery_rate)
    magnet_market_mix_constraints(model, high_perf_magnet_required)
    apply_capacity_constraints(model, max_output_capacity)
    add_stock_constraints(model, initial_stock, max_stock_capacity)
    add_unused_oxides_tracking(model, locations)

    def total_cost_rule(m):
        _g = sum(((processing_cost.get((int(a), str(b), str(c), str(f)), 0.0) + domestic_transport_cost.get((int(a), str(b), str(c), str(f)), 0.0) + (shipping_cost.get((int(a), str(c), str(e)), 0.0) if str(c) != str(e) else 0.0) + tariff_cost.get((int(a), str(b), str(c), str(d), str(e), str(f)), 0.0)) * m.flowQ[a, b, c, d, e, f] for (a, b, c, d, e, f) in m.flowQ))
        _i = sum((stock_holding_cost.get((a, h), 0) * m.stock_level[a, h] for a in m.TimePeriods for h in m.StockMaterials))
        _j = PENALTY_UNUSED_OXIDE_COST * m.total_unused_oxides
        _k = slack_penalty_cost * sum((m.demand_slack_pos[a] + m.demand_slack_neg[a] for a in m.TimePeriods))
        return _g + _i + _j + _k

    def total_emissions_rule(m):
        _g = sum((ef_factor.get((int(a), str(b), str(c), str(f)), 0.0) * m.flowQ[a, b, c, d, e, f] for (a, b, c, d, e, f) in m.flowQ))
        _h = PENALTY_UNUSED_OXIDE_GWP * m.total_unused_oxides
        _i = slack_penalty_cost * sum((m.demand_slack_pos[a] + m.demand_slack_neg[a] for a in m.TimePeriods))
        return _g + _h + _i

    def total_child_labor_rule(m):
        _g = sum((slca_factors['child_labor'].get((int(a), str(b), str(c), str(f)), 0.0) * m.flowQ[a, b, c, d, e, f] for (a, b, c, d, e, f) in m.flowQ))
        _h = PENALTY_UNUSED_OXIDE_SLCA * m.total_unused_oxides
        _i = slack_penalty_cost * sum((m.demand_slack_pos[a] + m.demand_slack_neg[a] for a in m.TimePeriods))
        return _g + _h + _i

    def total_water_rule(m):
        _g = sum((water_factor.get((int(a), str(b), str(c), str(f)), 0.0) * m.flowQ[a, b, c, d, e, f] for (a, b, c, d, e, f) in m.flowQ))
        _h = PENALTY_UNUSED_OXIDE_GWP * m.total_unused_oxides
        _i = slack_penalty_cost * sum((m.demand_slack_pos[a] + m.demand_slack_neg[a] for a in m.TimePeriods))
        return _g + _h + _i

    _OBJ_RULES = {'cost': (total_cost_rule, 'total_cost_incl_holding'), 'gwp': (total_emissions_rule, 'total_emissions'), 'water': (total_water_rule, 'total_water_m3'), 'slca': (total_child_labor_rule, 'total_child_labor')}
    if objective not in _OBJ_RULES:
        raise ValueError(f"unknown REE objective {objective!r}; expected one of {sorted(_OBJ_RULES)}")
    (_rule, _obj_name) = _OBJ_RULES[objective]
    model.obj = Objective(rule=_rule, sense=minimize, name=_obj_name)
    model._bleecam_objective = 'cost' if objective == 'cost' else _obj_name
    model._arc_unit_cost = {
        (a, b, c, d, e, f): float(
            processing_cost.get((int(a), str(b), str(c), str(f)), 0.0)
            + domestic_transport_cost.get((int(a), str(b), str(c), str(f)), 0.0)
            + (shipping_cost.get((int(a), str(c), str(e)), 0.0) if str(c) != str(e) else 0.0)
            + tariff_cost.get((int(a), str(b), str(c), str(d), str(e), str(f)), 0.0))
        for (a, b, c, d, e, f) in model.flowQ
    }
    return model


def solve_model(model, solver='auto', tee=False):
    """Solve the REE model. Prefers ipopt (the report solver), falls back to any LP solver."""
    from pyomo.environ import SolverFactory, value as _value
    candidates = ['ipopt', 'appsi_highs', 'highs', 'cbc', 'glpk'] if solver == 'auto' else [solver]
    opt = None
    for name in candidates:
        try:
            s = SolverFactory(name)
            if s is not None and s.available(exception_flag=False):
                opt = s
                break
        except Exception:
            continue
    if opt is None:
        raise RuntimeError(f"no solver available (tried {candidates})")
    results = opt.solve(model, tee=tee)
    obj = _value(model.obj, exception=False)
    slack = [(int(t), float(_value(model.demand_slack_pos[t]))) for t in model.TimePeriods
             if (_value(model.demand_slack_pos[t]) or 0) > 1e-6]
    return {'termination_condition': str(results.solver.termination_condition),
            'objective_value': None if obj is None else float(obj), 'demand_slack': slack}


def main():
    """Console-script entry point for the REE single-objective solve (see pyproject `bleecam-ree`)."""
    args = _parse_args()
    data = load_inputs(args.data)
    high_perf_magnet_required = data['high_perf_magnet_required']
    yield_factor = data['yield_factor']
    recovery_rate = data['recovery_rate']
    processing_cost = data['processing_cost']
    domestic_transport_cost = data['domestic_transport_cost']
    shipping_cost = data['shipping_cost']
    tariff_cost = data['tariff_cost']
    ef_factor = data['ef_factor']
    ct_mass_ratio_by_t = data['ct_mass_ratio_by_t']
    allowed_trade_arcs = data['allowed_trade_arcs']
    max_output_capacity = data['max_output_capacity']
    slca_factors = data['slca_factors']
    # ── Scenario override 1: CN metallothermic reduction (Dy) ramp-down ──────────
    # Simulates declining Chinese Dy metal refining capacity over the model horizon.
    # Each period's cap is set to a fraction of the t=0 baseline (100% → 5%).
    _CN_DY_METALLO_KEY = ('metallothermic reduction', 'CN', 'dysprosium')
    _CN_DY_RAMP_FACTORS = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _CN_DY_METALLO_KEY in max_output_capacity:
        _baseline_t0 = max_output_capacity[_CN_DY_METALLO_KEY].get(0, None)
        if _baseline_t0 is not None:
            # Apply each period's scaling factor relative to the t=0 capacity baseline
            for (_t, _factor) in _CN_DY_RAMP_FACTORS.items():
                if _t in max_output_capacity[_CN_DY_METALLO_KEY]:
                    _orig = max_output_capacity[_CN_DY_METALLO_KEY][_t]
                    max_output_capacity[_CN_DY_METALLO_KEY][_t] = _baseline_t0 * _factor
                    print(f'[SCENARIO] CN metallothermic reduction (Dy) at t={_t}: {_orig:.1f} → {_baseline_t0 * _factor:.1f} tonnes ({_factor * 100:.0f}% of baseline)')
        else:
            print(f'[SCENARIO WARNING] {_CN_DY_METALLO_KEY} / t=0 not found — no override applied.')
    else:
        print(f'[SCENARIO WARNING] Key {_CN_DY_METALLO_KEY} not found in capacity map — no override applied.')
    # ── Scenario override 2: CN sulfuric acid digestion (DyOx) ramp-down ─────────
    # Same ramp-down profile as metallothermic reduction — constrains Chinese H2SO4
    # DyOx separation capacity, forcing diversification to other countries/routes.
    _CN_SAD_DY_KEY = ('sulfuric acid digestion', 'CN', 'dysprosium_oxide')
    _CN_SAD_DY_FACTORS = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _CN_SAD_DY_KEY in max_output_capacity:
        _baseline_t0 = max_output_capacity[_CN_SAD_DY_KEY].get(0, None)
        if _baseline_t0 is not None:
            # Scale each period's capacity by the corresponding ramp factor
            for (_t, _factor) in _CN_SAD_DY_FACTORS.items():
                if _t in max_output_capacity[_CN_SAD_DY_KEY]:
                    _orig = max_output_capacity[_CN_SAD_DY_KEY][_t]
                    max_output_capacity[_CN_SAD_DY_KEY][_t] = _baseline_t0 * _factor
                    print(f'[SCENARIO] CN sulfuric acid digestion (DyOx) at t={_t}: {_orig:.1f} → {_baseline_t0 * _factor:.1f} tonnes ({_factor * 100:.0f}% of baseline)')
        else:
            print(f'[SCENARIO WARNING] {_CN_SAD_DY_KEY} / t=0 not found — no override applied.')
    else:
        print(f'[SCENARIO WARNING] Key {_CN_SAD_DY_KEY} not found in capacity map — no override applied.')
    # ── Scenario override 3: CN clay refining (DyOx) ramp-down ───────────────────
    # Constrains Chinese ion-adsorption clay DyOx output — the primary source of
    # heavy REE Dy — along the same declining trajectory as the other CN processes.
    _CN_CLAY_DY_KEY = ('clay refining', 'CN', 'dysprosium_oxide')
    _CN_CLAY_DY_FACTORS = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _CN_CLAY_DY_KEY in max_output_capacity:
        _baseline_t0 = max_output_capacity[_CN_CLAY_DY_KEY].get(0, None)
        if _baseline_t0 is not None:
            # Scale each period's capacity by the corresponding ramp factor
            for (_t, _factor) in _CN_CLAY_DY_FACTORS.items():
                if _t in max_output_capacity[_CN_CLAY_DY_KEY]:
                    _orig = max_output_capacity[_CN_CLAY_DY_KEY][_t]
                    max_output_capacity[_CN_CLAY_DY_KEY][_t] = _baseline_t0 * _factor
                    print(f'[SCENARIO] CN clay refining (DyOx)              at t={_t}: {_orig:.1f} → {_baseline_t0 * _factor:.1f} tonnes ({_factor * 100:.0f}% of baseline)')
        else:
            print(f'[SCENARIO WARNING] {_CN_CLAY_DY_KEY} / t=0 not found — no override applied.')
    else:
        print(f'[SCENARIO WARNING] Key {_CN_CLAY_DY_KEY} not found in capacity map — no override applied.')
    # ── Scenario override 4: CN HCl acid digestion (DyOx) ramp-down ──────────────
    # Applies the same CN decline trajectory to the HCl digestion route, which
    # processes bastnasite/monazite ore into DyOx alongside the H2SO4 route.
    _CN_HCL_DY_KEY = ('hydrochloric acid digestion', 'CN', 'dysprosium_oxide')
    _CN_HCL_DY_FACTORS = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _CN_HCL_DY_KEY in max_output_capacity:
        _baseline_t0 = max_output_capacity[_CN_HCL_DY_KEY].get(0, None)
        if _baseline_t0 is not None:
            # Scale each period's capacity by the corresponding ramp factor
            for (_t, _factor) in _CN_HCL_DY_FACTORS.items():
                if _t in max_output_capacity[_CN_HCL_DY_KEY]:
                    _orig = max_output_capacity[_CN_HCL_DY_KEY][_t]
                    max_output_capacity[_CN_HCL_DY_KEY][_t] = _baseline_t0 * _factor
                    print(f'[SCENARIO] CN HCl acid digestion (DyOx)         at t={_t}: {_orig:.1f} → {_baseline_t0 * _factor:.1f} tonnes ({_factor * 100:.0f}% of baseline)')
        else:
            print(f'[SCENARIO WARNING] {_CN_HCL_DY_KEY} / t=0 not found — no override applied.')
    else:
        print(f'[SCENARIO WARNING] Key {_CN_HCL_DY_KEY} not found in capacity map — no override applied.')
    # ── Scenario override 5: US alloy recycling ramp-up ──────────────────────────
    # Sets absolute (not fractional) capacity targets for all three US alloy
    # recycling routes (hydro/pyro/cryo), starting at zero and growing to 1000 t/period.
    # This represents build-out of domestic EOL alloy recovery infrastructure.
    _US_ALLOY_RECYCLE_RAMP = {0: 0.0, 1: 250.0, 2: 500.0, 3: 750.0, 4: 1000.0}
    _US_ALLOY_RECYCLE_KEYS = [('hydrometallurgical', 'US', 'neodynium dysprosium iron alloy'), ('pyrometallurgical', 'US', 'neodynium dysprosium iron alloy'), ('cryogenic', 'US', 'neodynium dysprosium iron alloy')]
    for _key in _US_ALLOY_RECYCLE_KEYS:
        if _key in max_output_capacity:
            # Override each period with the absolute capacity target (not relative to baseline)
            for (_t, _cap) in _US_ALLOY_RECYCLE_RAMP.items():
                if _t in max_output_capacity[_key]:
                    _orig = max_output_capacity[_key][_t]
                    max_output_capacity[_key][_t] = _cap
                    print(f'[SCENARIO] US recycle alloy {_key[0]:<28} at t={_t}: {_orig:.1f} → {_cap:.1f} t')
        else:
            print(f'[SCENARIO WARNING] Key {_key} not found in capacity map — no override applied.')
    # ── Scenario override 6: US hp_magnet recycling ramp-up ──────────────────────
    # Sets absolute capacity targets for whole-magnet recovery routes (direct reuse
    # and magnet-to-magnet), growing from 0 to 500 t/period — at half the rate of
    # alloy recycling, reflecting the smaller near-term magnet collection pipeline.
    _US_HPMAGNET_RECYCLE_RAMP = {0: 0.0, 1: 125.0, 2: 250.0, 3: 375.0, 4: 500.0}
    _US_HPMAGNET_RECYCLE_KEYS = [('direct reuse', 'US', 'hp_magnet'), ('magnet-to-magnet recycling', 'US', 'hp_magnet')]
    for _key in _US_HPMAGNET_RECYCLE_KEYS:
        if _key in max_output_capacity:
            # Override each period with the absolute capacity target
            for (_t, _cap) in _US_HPMAGNET_RECYCLE_RAMP.items():
                if _t in max_output_capacity[_key]:
                    _orig = max_output_capacity[_key][_t]
                    max_output_capacity[_key][_t] = _cap
                    print(f'[SCENARIO] US recycle hp_mag {_key[0]:<28} at t={_t}: {_orig:.1f} → {_cap:.1f} t')
        else:
            print(f'[SCENARIO WARNING] Key {_key} not found in capacity map — no override applied.')
    # ── Scenario override 7: Allied nation (EE, JP) Dy metallothermic scale-up ───
    # Counter-balances CN ramp-down by growing EE (Estonia) and JP (Japan) Dy
    # refining capacity as multiples of their t=0 baseline.  EE scales more
    # aggressively (×8 by t=4) than JP (×4.5) reflecting different investment paths.
    _ALLIED_DY_SCALE = {('metallothermic reduction', 'EE', 'dysprosium'): {0: 1.0, 1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0}, ('metallothermic reduction', 'JP', 'dysprosium'): {0: 1.0, 1: 1.5, 2: 2.5, 3: 3.5, 4: 4.5}}
    for (_key, _factors) in _ALLIED_DY_SCALE.items():
        if _key in max_output_capacity:
            _baseline_t0 = max_output_capacity[_key].get(0, None)
            if _baseline_t0 is not None:
                # Multiply baseline t=0 capacity by the per-period scale factor
                for (_t, _factor) in _factors.items():
                    if _t in max_output_capacity[_key]:
                        _orig = max_output_capacity[_key][_t]
                        max_output_capacity[_key][_t] = _baseline_t0 * _factor
                        print(f'[SCENARIO] Allied {_key[1]} metallothermic (Dy)       at t={_t}: {_orig:.1f} → {_baseline_t0 * _factor:.1f} t (×{_factor})')
            else:
                print(f'[SCENARIO WARNING] {_key} / t=0 not found — no override applied.')
        else:
            print(f'[SCENARIO WARNING] Key {_key} not found in capacity map — no override applied.')
    # ── Scenario override 8: Canada (CA) full exclusion ──────────────────────────
    # Zeroes out ALL Canadian process capacities across all time periods, effectively
    # removing CA from the solution space for this scenario run.
    _CA_EXCLUDE_KEYS = [k for k in max_output_capacity if k[1] == 'CA']
    if _CA_EXCLUDE_KEYS:
        # Set every time-period capacity to 0.0 for every CA process/material key
        for _key in _CA_EXCLUDE_KEYS:
            for _t in list(max_output_capacity[_key].keys()):
                max_output_capacity[_key][_t] = 0.0
        print(f'[OVERRIDE] Canada (CA) excluded: zeroed capacity for {len(_CA_EXCLUDE_KEYS)} key(s): ' + ', '.join((str(k) for k in sorted(_CA_EXCLUDE_KEYS))))
    else:
        print('[OVERRIDE] Canada (CA): no capacity keys found — no override needed.')
    ACTIVE_OBJECTIVE = 'cost'
    PENALTY_MAP = {'cost': PENALTY_UNUSED_OXIDE_COST, 'gwp': PENALTY_UNUSED_OXIDE_GWP, 'slca': PENALTY_UNUSED_OXIDE_SLCA}
    slack_penalty_cost = 1000.0
    # Model construction now lives in build_model() (single source of truth). The
    # eight capacity overrides above have already been applied to `data`, so the
    # model build_model() returns is identical to the former inline construction.
    model = build_model(data, objective=ACTIVE_OBJECTIVE)
    _obj_name = model.obj.name
    print(f'Objective: {_obj_name}  |  Penalty rate: {PENALTY_MAP[ACTIVE_OBJECTIVE]}')

    def print_diagnostics(model, high_perf_magnet_required, label='DIAGNOSTIC REPORT'):
        """Print a diagnostic summary of demand fulfillment, flows, and key variable values.

        :param model: Solved BLEECAM Pyomo model.
        :type model: pyomo.environ.ConcreteModel
        :param high_perf_magnet_required: Mapping of time period to required hp_magnet demand.
        :type high_perf_magnet_required: dict[int, float]
        :param label: Header label for the printed report.
        :type label: str
        """
        _a = '=' * 80

        def sv(var):
            try:
                __a = value(var)
                return float(__a) if __a is not None else None
            except Exception:
                return None

        def fmt(v, w=12):
            if v is None:
                return f"{'N/A':>{w}}"
            if abs(v) < 1e-09:
                return f"{'0':>{w}}"
            return f'{v:{w},.4f}'
        _b = DEMAND_LOCATION
        _c = 'hp_magnet'
        _d = 'magnet manufacturing'
        _e = ['magnet-to-magnet recycling', 'direct reuse']
        _f = ['direct reuse', 'magnet-to-magnet recycling', 'hydrometallurgical', 'pyrometallurgical', 'cryogenic', 'export']
        print(f'\n{_a}')
        print(f'  {label}')
        print(_a)
        print('\n  [1] DEMAND FULFILMENT & SLACK  (magnet_market_mix → use phase, hp_magnet @ US)')
        print(f"  {'t':>4}  {'Demand':>14}  {'Flow→UsePhase':>14}  {'slack_pos(short)':>17}  {'slack_neg(over)':>16}  {'Net gap':>10}")
        print(f"  {'-' * 4}  {'-' * 14}  {'-' * 14}  {'-' * 17}  {'-' * 16}  {'-' * 10}")
        _g = _h = 0.0
        # Per-period: compare required demand against actual market mix outflow,
        # and read slack variables to identify shortfalls or surplus supply.
        for _i in sorted(model.TimePeriods):
            _j = float(high_perf_magnet_required.get(_i, 0))          # required demand (FLOW_SCALE units)
            _k = (_i, 'magnet_market_mix', _b, 'use phase', _b, _c)   # flow key: market mix → use phase
            _l = sv(model.flowQ[_k]) if _k in model.flowQ else None    # actual flow value
            _m = sv(model.demand_slack_pos[_i])   # positive slack = unmet demand
            _n = sv(model.demand_slack_neg[_i])   # negative slack = over-supply
            _o = _m - _n if _m is not None and _n is not None else None  # net gap
            _g += _m or 0.0   # accumulate total shortfall across periods
            _h += _n or 0.0   # accumulate total surplus across periods
            _p = '  <<< UNMET DEMAND' if _m is not None and _m > 0.001 else '  <<< SURPLUS' if _n is not None and _n > 0.001 else ''
            print(f'  {_i:>4}  {fmt(_j, 14)}  {fmt(_l, 14)}  {fmt(_m, 17)}  {fmt(_n, 16)}  {fmt(_o, 10)}{_p}')
        print(f"  {'':4}  {'':14}  {'':14}  {fmt(_g, 17)}  {fmt(_h, 16)}  (totals)")
        print('\n  [2] MAGNET MARKET MIX MASS BALANCE  (inflow + from_stock = outflow + to_stock)')
        print(f"  {'t':>4}  {'mfg_in':>12}  {'eol_in':>12}  {'from_stk':>10}  {'LHS':>12}  {'outflow(use)':>14}  {'to_stk':>8}  {'RHS':>12}  {'err':>10}")
        print(f"  {'-' * 4}  {'-' * 12}  {'-' * 12}  {'-' * 10}  {'-' * 12}  {'-' * 14}  {'-' * 8}  {'-' * 12}  {'-' * 10}")
        # Per-period mass balance at the magnet_market_mix node.
        # LHS = new manufacture inflow + EOL recovery inflow + draw from stock buffer.
        # RHS = outflow to use phase + deposit to stock buffer.
        # Any non-zero LHS-RHS error indicates a constraint violation.
        for _i in sorted(model.TimePeriods):
            _r = sum((sv(model.flowQ[_i, _d, _q, 'magnet_market_mix', _b, _c]) or 0.0 for _q in model.Locations if (_i, _d, _q, 'magnet_market_mix', _b, _c) in model.flowQ))  # total mfg inflow from all locations
            _t = sum((sv(model.flowQ[_i, _s, _b, 'magnet_market_mix', _b, _c]) or 0.0 for _s in _e if (_i, _s, _b, 'magnet_market_mix', _b, _c) in model.flowQ))              # total EOL recovered inflow (m2m + reuse)
            _u = sv(model.flow_from_stock[_i, _c]) if (_i, _c) in model.flow_from_stock else 0.0  # draw from inventory buffer
            _v = sv(model.flow_to_stock[_i, _c]) if (_i, _c) in model.flow_to_stock else 0.0      # deposit into inventory buffer
            _w = (_i, 'magnet_market_mix', _b, 'use phase', _b, _c)
            _x = sv(model.flowQ[_w]) if _w in model.flowQ else 0.0  # outflow to use phase (= demand served)
            _y = (_r or 0) + (_t or 0) + (_u or 0)  # LHS total
            _z = (_x or 0) + (_v or 0)              # RHS total
            _aa = _y - _z                            # balance error (should be ~0)
            _ab = '  *** IMBALANCE' if abs(_aa or 0) > 0.001 else ''
            print(f'  {_i:>4}  {fmt(_r, 12)}  {fmt(_t, 12)}  {fmt(_u, 10)}  {fmt(_y, 12)}  {fmt(_x, 14)}  {fmt(_v, 8)}  {fmt(_z, 12)}  {fmt(_aa, 10)}{_ab}')
        print('\n  [3] INVENTORY STOCK BUFFER  (hp_magnet)')
        print(f"  {'t':>4}  {'stock_level':>12}  {'flow_to_stock':>14}  {'flow_from_stock':>16}")
        print(f"  {'-' * 4}  {'-' * 12}  {'-' * 14}  {'-' * 16}")
        # Report opening stock level and buffer movements each period.
        # stock_level is the carry-over inventory; flow_to/from_stock are the
        # charge and draw amounts that smooth supply across periods.
        for _i in sorted(model.TimePeriods):
            _ac = sv(model.stock_level[_i, _c]) if (_i, _c) in model.stock_level else None       # inventory at start of period
            _ad = sv(model.flow_to_stock[_i, _c]) if (_i, _c) in model.flow_to_stock else None   # magnets deposited into buffer
            _ae = sv(model.flow_from_stock[_i, _c]) if (_i, _c) in model.flow_from_stock else None  # magnets drawn from buffer
            print(f'  {_i:>4}  {fmt(_ac, 12)}  {fmt(_ad, 14)}  {fmt(_ae, 16)}')
        print('\n  [4] USE PHASE IN-SERVICE STOCK  (hp_magnet @ US)')
        print(f"  {'t':>4}  {'use_stock':>12}  {'inflow_from_mkt':>16}  {'total_eol_retirements':>22}")
        print(f"  {'-' * 4}  {'-' * 12}  {'-' * 16}  {'-' * 22}")
        # Track the installed magnet fleet: use_stock is the total in-service quantity,
        # inflow is newly deployed magnets, and total_eol is the sum of retirements
        # flowing out to all end-of-life routes (reuse, m2m, hydro, pyro, cryo).
        for _i in sorted(model.TimePeriods):
            _af = sv(model.use_stock[_i]) if _i in model.use_stock else None  # total in-service fleet size
            _ag = (_i, 'magnet_market_mix', _b, 'use phase', _b, _c)
            _ah = sv(model.flowQ[_ag]) if _ag in model.flowQ else None        # new magnets entering service
            # Sum outflows from use phase to all EOL routes for this period
            _aj = sum((sv(model.flowQ[_i, 'use phase', _b, _ai, _b, _c]) or 0.0 for _ai in _f if (_i, 'use phase', _b, _ai, _b, _c) in model.flowQ))
            print(f'  {_i:>4}  {fmt(_af, 12)}  {fmt(_ah, 16)}  {fmt(_aj, 22)}')
        print('\n  [5] KEY UPSTREAM FLOWS INTO magnet_market_mix  (hp_magnet)')
        print(f"  {'t':>4}  {'mfg_total':>12}  {'m2m_recov':>12}  {'reuse_recov':>12}  {'hydro':>10}  {'pyro':>10}  {'cryo':>10}")
        print(f"  {'-' * 4}  {'-' * 12}  {'-' * 12}  {'-' * 12}  {'-' * 10}  {'-' * 10}  {'-' * 10}")

        def _mkt_in(t, proc):
            # Sum inflow to magnet_market_mix from the given process across all source locations
            return sum((sv(model.flowQ[t, proc, __a, 'magnet_market_mix', _b, _c]) or 0.0 for __a in model.Locations if (t, proc, __a, 'magnet_market_mix', _b, _c) in model.flowQ))
        # Decompose the market mix supply by source process each period — shows
        # the share of demand met by new manufacture vs. each recycling pathway.
        for _i in sorted(model.TimePeriods):
            print(f"  {_i:>4}  {fmt(_mkt_in(_i, _d), 12)}  {fmt(_mkt_in(_i, 'magnet-to-magnet recycling'), 12)}  {fmt(_mkt_in(_i, 'direct reuse'), 12)}  {fmt(_mkt_in(_i, 'hydrometallurgical'), 10)}  {fmt(_mkt_in(_i, 'pyrometallurgical'), 10)}  {fmt(_mkt_in(_i, 'cryogenic'), 10)}")
        print(f'\n  [6] SUMMARY FLAGS')
        print(f"  Total unmet demand (slack_pos) : {_g:>14,.4f}  {('<<< DEMAND NOT FULLY MET' if _g > 0.001 else 'OK')}")
        print(f"  Total surplus      (slack_neg) : {_h:>14,.4f}  {('<<< OVER-SUPPLY DETECTED' if _h > 0.001 else 'OK')}")
        print(f'\n  [7] SLACK PENALTY DETAIL  (penalty rate = {slack_penalty_cost} $/tonne)')
        print(f"  {'t':>4}  {'slack_pos (t)':>14}  {'penalty cost':>14}  {'note':>10}")
        # Per-period shortfall and its cost contribution at the configured penalty rate.
        # A non-zero slack_pos means the solver could not fully meet demand that period
        # within the active capacity and flow constraints.
        for _i in sorted(model.TimePeriods):
            _ak = sv(model.demand_slack_pos[_i])      # unmet demand volume (FLOW_SCALE units)
            _al = slack_penalty_cost * _ak             # penalty cost contribution
            _am = '<<< UNMET' if _ak > 0.001 else ''
            print(f'  {_i:>4}  {_ak:>14,.4f}  {_al:>14,.2f}  {_am}')
        print(f'\n{_a}\n')
    solver = SolverFactory('ipopt')
    print(f'Solving with {solver.name}...')
    n_fixed = sum((1 for v in model.component_data_objects(pyo.Var, active=True) if v.is_fixed()))
    print(f'Fixed variables: {n_fixed:,}')
    results = solver.solve(model, tee=True, options={'tol': 1e-06, 'constr_viol_tol': 1e-06, 'dual_inf_tol': 1e-06, 'compl_inf_tol': 1e-06, 'bound_frac': 1e-06, 'bound_push': 1e-06})
    print(f'\nSolver status:      {results.solver.status}')
    print(f'Termination:        {results.solver.termination_condition}')
    if results.solver.termination_condition in (TerminationCondition.optimal, TerminationCondition.feasible):
        print(f'Objective value:    {model.obj():,.2f}')
        print_diagnostics(model, high_perf_magnet_required, label=f'SUCCESS DIAGNOSTIC  |  {ACTIVE_OBJECTIVE.upper()}  |  obj = {model.obj():,.4f}')

        def compute_unused_oxide_penalty(model, penalty_per_unit=None):
            if penalty_per_unit is None:
                penalty_per_unit = PENALTY_MAP[ACTIVE_OBJECTIVE]
            _a = ['sulfuric acid digestion', 'hydrochloric acid digestion', 'clay refining']
            (_b, _c) = (0.0, [])
            for _d in model.TimePeriods:
                # Sum DyOx routed to MSE (MSE only uses NdOx, so this DyOx is wasted co-product)
                _h = sum((value(model.flowQ[_d, _e, _f, 'molten_salt electrolysis', _g, 'dysprosium_oxide']) for _e in _a for _f in locations for _g in locations if (_d, _e, _f, 'molten_salt electrolysis', _g, 'dysprosium_oxide') in model.flowQ))
                # Sum NdOx routed to metallothermic reduction (MR only uses DyOx, so this NdOx is wasted)
                _i = sum((value(model.flowQ[_d, _e, _f, 'metallothermic reduction', _g, 'neodynium_oxide']) for _e in _a for _f in locations for _g in locations if (_d, _e, _f, 'metallothermic reduction', _g, 'neodynium_oxide') in model.flowQ))
                _c.append((_d, _h, _i))
                _b += _h + _i
            _j = penalty_per_unit * _b
            print(f'Unused oxides: {_b:,.6f}  |  Penalty: {_j:,.6f}')
            return (_c, _b, _j)
        (_unused_per_t, _total_unused, _unused_penalty) = compute_unused_oxide_penalty(model)
        records = []
        # Collect every non-trivial flow variable into a flat record list.
        # Skip near-zero values (≤ 0.0001 in FLOW_SCALE units) to keep the CSV lean.
        # Attach all relevant cost/EF parameters alongside each flow for diagnostics.
        for (idx, var) in model.flowQ.items():
            (t, p1, l1, p2, l2, mat) = idx
            val = var.value if var.value is not None else 0.0
            if abs(val) <= 0.0001:
                continue
            records.append({'time_period': t, 'source': p1, 'source_location': l1, 'destination': p2, 'destination_location': l2, 'material': mat, 'flow_value': float(val), 'process_cost': processing_cost.get((int(t), str(p1), str(l1), str(mat)), None), 'domestic_transport_cost': domestic_transport_cost.get((int(t), str(p1), str(l1), str(mat)), None), 'shipping_cost': shipping_cost.get((int(t), str(l1), str(l2)), None) if str(l1) != str(l2) else None, 'tariff_cost': tariff_cost.get((int(t), str(p1), str(l1), str(p2), str(l2), str(mat)), None), 'yield_factor': yield_factor.get((int(t), str(p1), str(l1), str(mat)), None), 'emission_factor': ef_factor.get((int(t), str(p1), str(l1), str(mat)), None)})
        # Append stock buffer movements (flow_to_stock / flow_from_stock) as pseudo-flows
        # so they appear in the results CSV and HTML alongside normal material flows.
        for t in model.TimePeriods:
            for smat in model.StockMaterials:
                # Check both directions: charging the buffer and drawing from it
                for (var, src, dst) in [(model.flow_to_stock[t, smat], 'magnet_market_mix', 'stock'), (model.flow_from_stock[t, smat], 'stock', 'magnet_market_mix')]:
                    v = var.value
                    if v is not None and abs(v) > 0.0001:
                        records.append({'time_period': t, 'source': src, 'source_location': DEMAND_LOCATION, 'destination': dst, 'destination_location': DEMAND_LOCATION, 'material': smat, 'flow_value': float(v), 'process_cost': None, 'domestic_transport_cost': None, 'shipping_cost': None, 'tariff_cost': None, 'yield_factor': None, 'emission_factor': None})
        if records:
            df_out = pd.DataFrame(records).sort_values(['time_period', 'source', 'source_location', 'destination', 'destination_location', 'material'])
            df_out = df_out[abs(df_out['flow_value']) > 0.0001]
            _EOL_SOURCES = {'direct reuse', 'magnet-to-magnet recycling', 'hydrometallurgical', 'pyrometallurgical', 'cryogenic'}
            _horizon_mask = (df_out['time_period'] == model.T_max) & (df_out['source'] == 'use phase') & df_out['destination'].isin(_EOL_SOURCES)
            if _horizon_mask.any():
                print(f'[RESULTS] Dropped {_horizon_mask.sum()} horizon-end EOL flow(s) at t={model.T_max} (outputs fall outside model horizon).')
            df_out = df_out[~_horizon_mask]
            df_out['flow_value'] = df_out['flow_value'] * FLOW_SCALE
            _total_unused_kg = _total_unused * FLOW_SCALE
            _unused_penalty_real = _unused_penalty * FLOW_SCALE
            _unused_per_t_kg = [(t, dy * FLOW_SCALE, nd * FLOW_SCALE) for (t, dy, nd) in _unused_per_t]
            _obj_real = model.obj() * FLOW_SCALE
            out_csv = args.out / 'model_results_multilocation.csv'
            args.out.mkdir(parents=True, exist_ok=True)
            df_out.to_csv(out_csv, index=False)
            print(f'Results written to {out_csv}')
            print(f'Objective value (real $): {_obj_real:,.2f}')
            # Machine-readable run summary so the golden anchors on the real cost
            # objective (not the flow-volume fingerprint). Additive output only.
            import json as _json
            (args.out / 'run_summary.json').write_text(_json.dumps({
                'objective_real_usd': round(float(_obj_real), 2),
                'objective_name': model.obj.name,
                'n_flow_rows': int(len(df_out)),
                'total_flow_volume': round(float(df_out['flow_value'].abs().sum()), 3),
                'n_periods': int(df_out['time_period'].nunique()),
                'unused_oxides_kg': round(float(_total_unused_kg), 3),
                'unused_penalty_real': round(float(_unused_penalty_real), 2),
            }, indent=2))
            print(f'Run summary written to {args.out / "run_summary.json"}')
            export_diagnostic_html(df_out, unused_per_t=_unused_per_t_kg, total_unused=_total_unused_kg, unused_penalty=_unused_penalty_real, obj_value=_obj_real, obj_name=model.obj.name, penalty_weight=PENALTY_MAP[ACTIVE_OBJECTIVE], path='model_diagnostic_report.html')
        else:
            print('No significant flows found.')
    else:
        print(f'No solution found.  Termination: {results.solver.termination_condition}')
        print('Printing partial/last-iterate variable values for diagnosis...')
        print_diagnostics(model, high_perf_magnet_required, label=f'FAILURE DIAGNOSTIC  |  Termination: {results.solver.termination_condition}')
    print('\nDone.')
    import subprocess, sys as _sys
    print('\nGenerating analytics dashboard...')
    subprocess.run([_sys.executable, str(Path(__file__).parents[2] / 'shared' / 'bleecam_dashboard.py'), '--data', str(args.out), '--out', 'bleecam_dashboard.html', '--obj-value', str(model.obj() * FLOW_SCALE), '--obj-name', _obj_name], check=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
