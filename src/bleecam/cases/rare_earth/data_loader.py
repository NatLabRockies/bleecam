import pandas as pd
from pathlib import Path
from .config import ACTIVE_PROCESS_LOCATIONS, FLOW_SCALE
_SLCA_COLS = {'child_labor': 'SLCA_EF - Child labor impact (worker hour/kg)', 'forced_labor': 'SLCA_EF - Forced labor impact (worker hour/kg)', 'fatal_injury': 'SLCA_EF - Fatal injury impact (worker hour/kg)', 'nonfatal_injury': 'SLCA_EF - Non-fatal injury impact (worker hour/kg)', 'unemployment': 'SLCA_EF - Unemployment impact (worker hour/kg)'}

def load_all_data(data_dir='./data'):
    """Load all CSV input data and return as a dict scaled by FLOW_SCALE.

    :param data_dir: Path to the CSV data directory.
    :type data_dir: str
    :returns: Dictionary with keys: demand_df (DataFrame), high_perf_magnet_required (dict[int, float]), yield_factor (dict), recovery_rate (dict), processing_cost (dict), domestic_transport_cost (dict), shipping_cost (dict), tariff_cost (dict), ef_factor (dict), ct_mass_ratio_by_t (dict), allowed_trade_arcs (set), max_output_capacity (dict), slca_factors (dict). All flow quantities scaled by FLOW_SCALE.
    :rtype: dict
    """
    _a = Path(data_dir)
    _b = pd.read_csv(_a / 'Demand_Input_Template.csv')
    _c = pd.read_csv(_a / 'Yield_Factor.csv')
    _d = pd.read_csv(_a / 'Recovery_Rates.csv')
    _e = pd.read_csv(_a / 'Cost_Parameters.csv')
    _f = pd.read_csv(_a / 'Capacity_Template.csv')
    _g = pd.read_csv(_a / 'EF_template.csv')
    _h = pd.read_csv(_a / 'trade_topology.csv')
    _i = pd.read_csv(_a / 'Shipping_Costs.csv')
    _j = pd.read_csv(_a / 'Social_LCA_template.csv')
    _m = {_l['time_period']: (_l['hp_magnet_demand'] * _l['Deployment Curve MW'] + _l['Data center magnet kg']) / FLOW_SCALE for (_k, _l) in _b.iterrows()}
    _n = {(int(_l['time_period']), str(_l['process']), str(_l['location']), str(_l['material'])): float(_l['yield']) for (_k, _l) in _c.iterrows()}
    _o = {(int(_l['time_period']), str(_l['source']), str(_l['source_location']), str(_l['destination']), str(_l['destination_location']), str(_l['material'])): float(_l['recovery_rate']) for (_k, _l) in _d.iterrows()}
    _p = {(int(_l['time_period']), str(_l['source']), str(_l['location']), str(_l['material'])): float(_l['processing cost']) for (_k, _l) in _e.iterrows()}
    _q = {(int(_l['time_period']), str(_l['source']), str(_l['location']), str(_l['material'])): float(_l['transportation cost']) for (_k, _l) in _e.iterrows()}
    _r = {(int(_l['time_period']), str(_l['loc_from']), str(_l['loc_to'])): float(_l['shipping_cost_usd_per_kg']) for (_k, _l) in _i.iterrows()}
    _s = {(int(_l['time_period']), str(_l['source']), str(_l['location']), str(_l['destination']), str(_l['destination_location']), str(_l['material'])): float(_l['tariff_cost']) for (_k, _l) in _e.iterrows() if float(_l.get('tariff_cost', 0.0)) != 0.0 and str(_l.get('destination', '')).strip() != '' and (str(_l.get('destination_location', '')).strip() != '')}
    _t = {(int(_l['time_period']), str(_l['source']), str(_l['location']), str(_l['material'])): float(_l['EF_weighted__Global Warming Potential (Gwp1000)']) for (_k, _l) in _g.iterrows() if str(_l['EF_weighted__Global Warming Potential (Gwp1000)']).strip() != 'Not available'}
    _wt = {}
    for (_wk, _wl) in _g.iterrows():
        _wv = _wl.get('EF_RECIPE__Water Consumption Potential (Wcp)', 'Not available')
        if str(_wv).strip() not in ('Not available', 'nan', 'NaN', ''):
            try:
                _wt[(int(_wl['time_period']), str(_wl['source']), str(_wl['location']), str(_wl['material']))] = float(_wv)
            except (ValueError, TypeError):
                pass
    _x = {int(_u): (float(_v), float(_w)) for (_u, _v, _w) in zip(_b['time_period'], _b['mass ratio Nd'], _b['mass ratio Dy'])}
    _y = set()
    for (_k, _l) in _h.iterrows():
        _y.add((str(_l['process_from']), str(_l['loc_from']), str(_l['process_to']), str(_l['loc_to']), str(_l['material'])))
    _z = {}
    for (_k, _l) in _f.iterrows():
        _aa = (str(_l['process']), str(_l['location']), str(_l['material']))
        _u = int(_l['time_period'])
        _ab = float(_l['capacity']) / FLOW_SCALE
        if _aa not in _z:
            _z[_aa] = {}
        _z[_aa][_u] = _ab
    _ad = {_ac: {} for _ac in _SLCA_COLS}
    for (_k, _l) in _j.iterrows():
        _aa = (int(_l['time_period']), str(_l['source']), str(_l['location']), str(_l['material']))
        for (_ae, _af) in _SLCA_COLS.items():
            _ag = _l.get(_af, 'Not available')
            if str(_ag).strip() != 'Not available':
                _ad[_ae][_aa] = float(_ag)
    print(f'Capacity map loaded: {len(_z)} keys.')
    print(f'Trade topology loaded: {len(_y)} arcs.')
    print(f'Loaded EF factors: {len(_t)}')
    print(f'Loaded water factors (ReCiPe WCP, m3): {len(_wt)}')
    for (_ae, _ah) in _ad.items():
        print(f'Loaded SLCA {_ae}: {len(_ah)} entries')
    return dict(demand_df=_b, high_perf_magnet_required=_m, yield_factor=_n, recovery_rate=_o, processing_cost=_p, domestic_transport_cost=_q, shipping_cost=_r, tariff_cost=_s, ef_factor=_t, water_factor=_wt, ct_mass_ratio_by_t=_x, allowed_trade_arcs=_y, max_output_capacity=_z, slca_factors=_ad)
_PROCESS_YIELD_MATERIALS = {'mining': ['monazaite', 'bastnasite'], 'clay mining': ['ion adsorption clay'], 'beneficiation': ['phosphate', 'flurocarbonate'], 'clay refining': ['neodynium_oxide', 'dysprosium_oxide'], 'sulfuric acid digestion': ['neodynium_oxide', 'dysprosium_oxide'], 'hydrochloric acid digestion': ['neodynium_oxide', 'dysprosium_oxide'], 'molten_salt electrolysis': ['neodynium'], 'metallothermic reduction': ['dysprosium'], 'chemical transformation': ['neodynium dysprosium iron alloy'], 'magnet manufacturing': ['hp_magnet'], 'magnet_market_mix': ['hp_magnet'], 'use phase': ['hp_magnet'], 'direct reuse': ['hp_magnet'], 'magnet-to-magnet recycling': ['hp_magnet'], 'hydrometallurgical': ['neodynium dysprosium iron alloy'], 'pyrometallurgical': ['neodynium dysprosium iron alloy'], 'cryogenic': ['neodynium dysprosium iron alloy']}
_EOL_ROUTES = [('use phase', 'US', 'direct reuse', 'US', 'hp_magnet'), ('use phase', 'US', 'magnet-to-magnet recycling', 'US', 'hp_magnet'), ('use phase', 'US', 'hydrometallurgical', 'US', 'hp_magnet'), ('use phase', 'US', 'pyrometallurgical', 'US', 'hp_magnet'), ('use phase', 'US', 'cryogenic', 'US', 'hp_magnet')]

def validate_csvs(time_periods, yield_factor, recovery_rate, processing_cost, domestic_transport_cost, ef_factor):
    """Check all active (process, location, material, time) combinations for missing data entries.

    :param time_periods: The model time period indices to check.
    :type time_periods: list[int]
    :param yield_factor: Yield values keyed by (t, process, location, material).
    :type yield_factor: dict
    :param recovery_rate: Recovery values keyed by (t, src, src_loc, dst, dst_loc, mat).
    :type recovery_rate: dict
    :param processing_cost: Processing cost values keyed by (t, process, location, material).
    :type processing_cost: dict
    :param domestic_transport_cost: Transport cost values keyed by (t, process, location, material).
    :type domestic_transport_cost: dict
    :param ef_factor: Emission factor values keyed by (t, process, location, material).
    :type ef_factor: dict
    :returns: None (prints warnings to stdout).
    :rtype: NoneType
    """
    (_a, _b, _c, _d, _e) = ([], [], [], [], [])
    for (_f, _g) in ACTIVE_PROCESS_LOCATIONS.items():
        for _h in _g:
            for _i in _PROCESS_YIELD_MATERIALS.get(_f, []):
                for _j in time_periods:
                    _k = (_j, _f, _h, _i)
                    if _k not in yield_factor:
                        _a.append(_k)
                    if _k not in processing_cost:
                        _c.append(_k)
                    if _k not in domestic_transport_cost:
                        _d.append(_k)
                    if _k not in ef_factor:
                        _e.append(_k)
    for (_l, _m, _n, _o, _i) in _EOL_ROUTES:
        for _j in time_periods:
            _k = (_j, _l, _m, _n, _o, _i)
            if _k not in recovery_rate:
                _b.append(_k)

    def _warn(label, items):
        """Print formatted warning if items list is non-empty, otherwise print OK status.

        :param label: Name of the CSV file being checked.
        :type label: str
        :param items: List of missing (t, process, location, material) tuples.
        :type items: list
        :returns: None (prints to stdout).
        :rtype: NoneType
        """
        if items:
            print(f"\n{'=' * 55}")
            print(f'  WARNING — {label}: {len(items)} missing entries')
            print(f"{'=' * 55}")
            for __a in sorted(items):
                print(f'    {__a}')
        else:
            print(f'  OK  {label}')
    print('\n---- CSV Completeness Check ----')
    _warn('Yield_Factor.csv', _a)
    _warn('Recovery_Rates.csv', _b)
    _warn('Cost_Parameters (proc)', _c)
    _warn('Cost_Parameters (trans)', _d)
    _warn('EF_template.csv', _e)
    print(f'  Total missing: {len(_a) + len(_b) + len(_c) + len(_d) + len(_e)}')
    print('--------------------------------\n')

def validate_slca(time_periods, slca_factors):
    """Check SLCA impact factor coverage for all active process/location/material/time combinations.

    :param time_periods: The model time period indices to check.
    :type time_periods: list[int]
    :param slca_factors: Impact category name mapped to {(t, process, location, material): float}.
    :type slca_factors: dict[str, dict]
    :returns: None (prints per-category status to stdout).
    :rtype: NoneType
    """
    print('\n---- SLCA Completeness Check ----')
    for _a in _SLCA_COLS:
        _b = slca_factors[_a]
        _c = []
        for (_d, _e) in ACTIVE_PROCESS_LOCATIONS.items():
            for _f in _e:
                for _g in _PROCESS_YIELD_MATERIALS.get(_d, []):
                    for _h in time_periods:
                        _i = (_h, _d, _f, _g)
                        if _i not in _b:
                            _c.append(_i)
        if _c:
            pass
        else:
            print(f'  OK  SLCA {_a}')
    print('--------------------------------\n')