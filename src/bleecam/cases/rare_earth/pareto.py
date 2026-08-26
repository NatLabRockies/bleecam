import argparse
from pathlib import Path
import pandas as pd
from pyomo.environ import ConcreteModel, Set, Var, NonNegativeReals, ConstraintList, ObjectiveList, minimize
from pyaugmecon import PyAugmecon
from .config import list_of_processes, locations, materials, DEMAND_LOCATION, time_stamp, PENALTY_UNUSED_OXIDE_COST, PENALTY_UNUSED_OXIDE_GWP, PENALTY_UNUSED_OXIDE_SLCA, DEFAULT_MAX_STOCK_CAPACITY, DEFAULT_STOCK_HOLDING_COST, FLOW_SCALE
slack_penalty_cost = 10000.0
from .data_loader import load_all_data
from .constraints import fix_inactive_process_locations, fix_disallowed_trade_flows, clay_mining_constraints, clay_refining_constraints, beneficiation_constraints, sulfuric_acid_digestion_constraints, hydrochloric_acid_digestion_constraints, molten_salt_electrolysis_constraints, metallothermic_reduction_constraints, chemical_transformation_constraints, magnet_manufacturing_constraints, magnet_market_mix_constraints, demand_fulfillment_constraints, weibull_historic_retirement, use_phase_stock_constraints, fix_eol_outflows_at_t0, direct_reuse_constraints, magnet_to_magnet_recycling_constraints, hydrometallurgical_constraints, pyrometallurgical_constraints, cryogenic_constraints, add_stock_constraints, apply_capacity_constraints, add_unused_oxides_tracking

def _parse_args():
    """Parse CLI arguments for data dir, output dir, grid points, and CPU count.

    :returns: Parsed arguments with fields: data (Path), out (Path), grid (int), cpus (int).
    :rtype: argparse.Namespace
    """
    _a = argparse.ArgumentParser(description='BLEECAM AUGMECON2 3-objective Pareto run')
    _a.add_argument('--data', type=Path, default=Path('./data'), help='Input data directory (default: ./data)')
    _a.add_argument('--out', type=Path, default=Path('./data'), help='Output directory for CSV + HTML (default: ./data)')
    _a.add_argument('--grid', type=int, default=50, help='Grid points per constrained objective (default: 50 → ~2401 max solves)')
    _a.add_argument('--cpus', type=int, default=14, help='CPU cores for parallel solves (default: 14)')
    return _a.parse_args()

def build_model(data_dir, env_metric='gwp', env_scale=1.0):
    """Load all data, apply scenario overrides, construct and return the Pyomo ConcreteModel.

    :param env_metric: which environmental objective to use as the 2nd frontier axis —
        'gwp' (default, kg CO2e) or 'water' (ReCiPe Water Consumption Potential, m3).
    :param env_scale: multiply the environmental factor by this (water coefficients are
        tiny, ~1e-3; scaling to O(1) conditions ipopt). Divide the reported env value
        back by env_scale afterwards.

    :param data_dir: Directory containing all input CSV files.
    :type data_dir: Path or str
    :returns: Pyomo ConcreteModel with variables (flowQ, stock_level, flow_to_stock, flow_from_stock, use_stock, demand_slack_pos, demand_slack_neg), all constraints applied, and three deactivated objectives in obj_list (cost, GWP, child-labor SLCA).
    :rtype: pyomo.environ.ConcreteModel
    """
    _a = load_all_data(data_dir)
    _b = _a['high_perf_magnet_required']
    _c = _a['yield_factor']
    _d = _a['recovery_rate']
    _e = _a['processing_cost']
    _f = _a['domestic_transport_cost']
    _g = _a['shipping_cost']
    _h = _a['tariff_cost']
    _i = _a['ef_factor']
    _wi = _a.get('water_factor', {})
    _j = _a['ct_mass_ratio_by_t']
    _k = _a['allowed_trade_arcs']
    _l = _a['max_output_capacity']
    _m = _a['slca_factors']
    _n = ('metallothermic reduction', 'CN', 'dysprosium')
    _o = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _n in _l:
        _p = _l[_n].get(0, None)
        if _p is not None:
            for (_q, _r) in _o.items():
                if _q in _l[_n]:
                    _l[_n][_q] = _p * _r
                    print(f'[SCENARIO] CN metallothermic reduction (Dy) at t={_q}: {_p * _r:.1f} t ({_r * 100:.0f}% of baseline)')
    _s = ('sulfuric acid digestion', 'CN', 'dysprosium_oxide')
    _t = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _s in _l:
        _p = _l[_s].get(0, None)
        if _p is not None:
            for (_q, _r) in _t.items():
                if _q in _l[_s]:
                    _l[_s][_q] = _p * _r
                    print(f'[SCENARIO] CN H2SO4 digestion (DyOx)            at t={_q}: {_p * _r:.1f} t ({_r * 100:.0f}% of baseline)')
    _u = ('clay refining', 'CN', 'dysprosium_oxide')
    _v = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _u in _l:
        _p = _l[_u].get(0, None)
        if _p is not None:
            for (_q, _r) in _v.items():
                if _q in _l[_u]:
                    _l[_u][_q] = _p * _r
                    print(f'[SCENARIO] CN clay refining (DyOx)              at t={_q}: {_p * _r:.1f} t ({_r * 100:.0f}% of baseline)')
    _w = ('hydrochloric acid digestion', 'CN', 'dysprosium_oxide')
    _x = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2, 4: 0.05}
    if _w in _l:
        _p = _l[_w].get(0, None)
        if _p is not None:
            for (_q, _r) in _x.items():
                if _q in _l[_w]:
                    _l[_w][_q] = _p * _r
                    print(f'[SCENARIO] CN HCl digestion (DyOx)              at t={_q}: {_p * _r:.1f} t ({_r * 100:.0f}% of baseline)')
    _y = {0: 0.0, 1: 250.0, 2: 500.0, 3: 750.0, 4: 1000.0}
    _z = [('hydrometallurgical', 'US', 'neodynium dysprosium iron alloy'), ('pyrometallurgical', 'US', 'neodynium dysprosium iron alloy'), ('cryogenic', 'US', 'neodynium dysprosium iron alloy')]
    for _aa in _z:
        if _aa in _l:
            for (_q, _ab) in _y.items():
                if _q in _l[_aa]:
                    _l[_aa][_q] = _ab
                    print(f'[SCENARIO] US recycle alloy {_aa[0]:<28} at t={_q}: {_ab:.1f} t')
    _ac = {0: 0.0, 1: 125.0, 2: 250.0, 3: 375.0, 4: 500.0}
    _ad = [('direct reuse', 'US', 'hp_magnet'), ('magnet-to-magnet recycling', 'US', 'hp_magnet')]
    for _aa in _ad:
        if _aa in _l:
            for (_q, _ab) in _ac.items():
                if _q in _l[_aa]:
                    _l[_aa][_q] = _ab
                    print(f'[SCENARIO] US recycle hp_mag {_aa[0]:<28} at t={_q}: {_ab:.1f} t')
    _ae = {('metallothermic reduction', 'EE', 'dysprosium'): {0: 1.0, 1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0}, ('metallothermic reduction', 'JP', 'dysprosium'): {0: 1.0, 1: 1.5, 2: 2.5, 3: 3.5, 4: 4.5}}
    for (_aa, _af) in _ae.items():
        if _aa in _l:
            _p = _l[_aa].get(0, None)
            if _p is not None:
                for (_q, _r) in _af.items():
                    if _q in _l[_aa]:
                        _l[_aa][_q] = _p * _r
                        print(f'[SCENARIO] Allied {_aa[1]} metallothermic (Dy)       at t={_q}: {_p * _r:.1f} t (×{_r})')
    _ag = ConcreteModel(name='BLEECAM_Pareto')
    _ag.TimePeriods = Set(initialize=time_stamp)
    _ag.Processes = Set(initialize=list_of_processes)
    _ag.Processes2 = Set(initialize=list_of_processes)
    _ag.materials = Set(initialize=materials)
    _ag.Locations = Set(initialize=locations)
    _ag.T_max = max(_ag.TimePeriods)
    _ag.T_min = min(_ag.TimePeriods)
    _ag.StockMaterials = Set(initialize=['hp_magnet'])
    _ah = 50000000 / FLOW_SCALE
    _ag.flowQ = Var(_ag.TimePeriods, _ag.Processes, _ag.Locations, _ag.Processes2, _ag.Locations, _ag.materials, domain=NonNegativeReals, bounds=(0, _ah), initialize=0)
    _ag.stock_level = Var(_ag.TimePeriods, _ag.StockMaterials, domain=NonNegativeReals, bounds=(0, _ah), initialize=0)
    _ag.flow_to_stock = Var(_ag.TimePeriods, _ag.StockMaterials, domain=NonNegativeReals, bounds=(0, _ah), initialize=0)
    _ag.flow_from_stock = Var(_ag.TimePeriods, _ag.StockMaterials, domain=NonNegativeReals, bounds=(0, _ah), initialize=0)
    _ag.use_stock = Var(_ag.TimePeriods, domain=NonNegativeReals, bounds=(0, _ah))
    _ag.demand_slack_pos = Var(_ag.TimePeriods, domain=NonNegativeReals, initialize=0)
    _ag.demand_slack_neg = Var(_ag.TimePeriods, domain=NonNegativeReals, initialize=0)
    _ag.constraints = ConstraintList()
    _ai = {'hp_magnet': 0.0}
    _al = {(_aj, _ak): DEFAULT_MAX_STOCK_CAPACITY for _aj in time_stamp for _ak in ['hp_magnet']}
    for _ak in _ag.StockMaterials:
        _ag.constraints.add(_ag.stock_level[_ag.T_min, _ak] == _ai[_ak])
    fix_inactive_process_locations(_ag)
    fix_disallowed_trade_flows(_ag, _k)
    demand_fulfillment_constraints(_ag, _b)
    use_phase_stock_constraints(_ag, retirement_rate=0.02, initial_use_stock=0.0, historic_retirements_by_t=weibull_historic_retirement(_ag, data_dir))
    clay_mining_constraints(_ag)
    clay_refining_constraints(_ag, _c)
    beneficiation_constraints(_ag, _c)
    sulfuric_acid_digestion_constraints(_ag, _c)
    hydrochloric_acid_digestion_constraints(_ag, _c)
    molten_salt_electrolysis_constraints(_ag, _c)
    metallothermic_reduction_constraints(_ag, _c)
    chemical_transformation_constraints(_ag, _c, _j, list_of_processes)
    magnet_manufacturing_constraints(_ag, _c)
    fix_eol_outflows_at_t0(_ag)
    direct_reuse_constraints(_ag, _d)
    magnet_to_magnet_recycling_constraints(_ag, _d)
    hydrometallurgical_constraints(_ag, _d)
    pyrometallurgical_constraints(_ag, _d)
    cryogenic_constraints(_ag, _d)
    magnet_market_mix_constraints(_ag, _b)
    apply_capacity_constraints(_ag, _l)
    add_stock_constraints(_ag, _ai, _al)
    add_unused_oxides_tracking(_ag, locations)

    def _slack_penalty(m):
        """Return the total demand slack penalty term.

        :param m: Pyomo ConcreteModel.
        :type m: ConcreteModel
        :returns: Pyomo expression for total demand slack penalty.
        :rtype: pyomo expression
        """
        return slack_penalty_cost * sum((m.demand_slack_pos[__a] + m.demand_slack_neg[__a] for __a in m.TimePeriods))

    def _cost_expr(m):
        """Return the total cost objective expression including all cost components and penalties.

        :param m: Pyomo ConcreteModel.
        :type m: ConcreteModel
        :returns: Pyomo expression for total cost including processing, transport, shipping, tariff, stock holding, unused-oxide penalty, and slack penalty.
        :rtype: pyomo expression
        """
        __g = sum(((_e.get((int(__a), str(__b), str(__c), str(__f)), 0.0) + _f.get((int(__a), str(__b), str(__c), str(__f)), 0.0) + (_g.get((int(__a), str(__c), str(__e)), 0.0) if str(__c) != str(__e) else 0.0) + _h.get((int(__a), str(__b), str(__c), str(__d), str(__e), str(__f)), 0.0)) * m.flowQ[__a, __b, __c, __d, __e, __f] for (__a, __b, __c, __d, __e, __f) in m.flowQ))
        __h = sum((DEFAULT_STOCK_HOLDING_COST * m.stock_level[__a, __f] for __a in m.TimePeriods for __f in m.StockMaterials))
        return __g + __h + PENALTY_UNUSED_OXIDE_COST * m.total_unused_oxides + _slack_penalty(m)

    def _gwp_expr(m):
        """Return the GWP objective expression weighted by emission factors plus penalties.

        :param m: Pyomo ConcreteModel.
        :type m: ConcreteModel
        :returns: Pyomo expression for total GWP including emission factors, unused-oxide penalty, and slack penalty.
        :rtype: pyomo expression
        """
        _fac = _wi if env_metric == 'water' else _i
        _scl = env_scale if env_metric == 'water' else 1.0
        return _scl * sum((_fac.get((int(__a), str(__b), str(__c), str(__f)), 0.0) * m.flowQ[__a, __b, __c, __d, __e, __f] for (__a, __b, __c, __d, __e, __f) in m.flowQ)) + PENALTY_UNUSED_OXIDE_GWP * m.total_unused_oxides + _slack_penalty(m)

    def _slca_expr(m):
        """Return the child-labor SLCA objective expression plus penalties.

        :param m: Pyomo ConcreteModel.
        :type m: ConcreteModel
        :returns: Pyomo expression for child-labor SLCA impact including unused-oxide penalty and slack penalty.
        :rtype: pyomo expression
        """
        return sum((_m['child_labor'].get((int(__a), str(__b), str(__c), str(__f)), 0.0) * m.flowQ[__a, __b, __c, __d, __e, __f] for (__a, __b, __c, __d, __e, __f) in m.flowQ)) + PENALTY_UNUSED_OXIDE_SLCA * m.total_unused_oxides + _slack_penalty(m)
    _ag.obj_list = ObjectiveList()
    _ag.obj_list.add(expr=_cost_expr(_ag), sense=minimize)
    _ag.obj_list.add(expr=_gwp_expr(_ag), sense=minimize)
    _ag.obj_list.add(expr=_slca_expr(_ag), sense=minimize)
    for _am in range(len(_ag.obj_list)):
        _ag.obj_list[_am + 1].deactivate()
    return _ag

def _plot_3d(df, out_path):
    """Generate and write a 3D Plotly scatter of the Pareto front to an HTML file.

    :param df: Pareto results with columns cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :type df: pd.DataFrame
    :param out_path: Output file path for the HTML plot.
    :type out_path: Path
    :returns: None
    :rtype: NoneType
    """
    import plotly.graph_objects as go
    import plotly.express as px
    _a = go.Scatter3d(x=df['cost_usd'], y=df['gwp_kg_co2eq'], z=df['child_labor_hrs'], mode='markers', marker=dict(size=5, color=df['cost_usd'], colorscale='Viridis', colorbar=dict(title='Cost (USD)', thickness=15, len=0.6), opacity=0.88, line=dict(width=0.3, color='white')), hovertemplate='<b>Pareto Point</b><br>Cost:        $%{x:,.0f}<br>GWP:          %{y:,.0f} kg CO₂-eq<br>Child Labor:  %{z:.6f} hrs<extra></extra>', name='Pareto solutions')
    _b = go.Figure(data=[_a])
    _b.update_layout(title=dict(text='BLEECAM 3D Pareto Front — Cost / GWP / Child Labor', font=dict(size=16)), scene=dict(xaxis=dict(title='Cost (USD)', tickformat=',.0f'), yaxis=dict(title='GWP (kg CO₂-eq)', tickformat=',.0f'), zaxis=dict(title='Child Labor (hrs)'), camera=dict(eye=dict(x=1.6, y=1.6, z=0.9)), aspectmode='auto'), margin=dict(l=0, r=0, b=0, t=60), width=1100, height=800)
    _b.write_html(str(out_path))
    print(f'3D Pareto plot → {out_path}')

def _plot_pairwise(df, out_path):
    """Generate and write a 1×3 subplot HTML with pairwise Pareto trade-off scatter plots.

    :param df: Pareto results with columns cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :type df: pd.DataFrame
    :param out_path: Output file path for the HTML plot.
    :type out_path: Path
    :returns: None
    :rtype: NoneType
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _a = make_subplots(rows=1, cols=3, subplot_titles=['Cost vs GWP', 'Cost vs Child Labor', 'GWP vs Child Labor'])
    _b = dict(size=5, opacity=0.7)
    _a.add_trace(go.Scatter(x=df['cost_usd'], y=df['gwp_kg_co2eq'], mode='markers', marker=_b, name='Cost–GWP'), row=1, col=1)
    _a.add_trace(go.Scatter(x=df['cost_usd'], y=df['child_labor_hrs'], mode='markers', marker=_b, name='Cost–SLCA'), row=1, col=2)
    _a.add_trace(go.Scatter(x=df['gwp_kg_co2eq'], y=df['child_labor_hrs'], mode='markers', marker=_b, name='GWP–SLCA'), row=1, col=3)
    _a.update_xaxes(title_text='Cost (USD)', row=1, col=1, tickformat=',.0f')
    _a.update_xaxes(title_text='Cost (USD)', row=1, col=2, tickformat=',.0f')
    _a.update_xaxes(title_text='GWP (kg CO₂-eq)', row=1, col=3, tickformat=',.0f')
    _a.update_yaxes(title_text='GWP (kg CO₂-eq)', row=1, col=1, tickformat=',.0f')
    _a.update_yaxes(title_text='Child Labor (hrs)', row=1, col=2)
    _a.update_yaxes(title_text='Child Labor (hrs)', row=1, col=3)
    _a.update_layout(title='BLEECAM Pareto Front — Pairwise Trade-offs', showlegend=False, width=1400, height=500)
    _a.write_html(str(out_path))
    print(f'Pairwise plot  → {out_path}')
if __name__ == '__main__':
    args = _parse_args()
    print('=' * 60)
    print('BLEECAM AUGMECON2 — 3D Pareto Run')
    print(f'  Grid points : {args.grid}  (max solves ≈ {(args.grid - 1) ** 2})')
    print(f'  CPU cores   : {args.cpus}')
    print(f'  Data dir    : {args.data}')
    print(f'  Out dir     : {args.out}')
    print('=' * 60)
    print('\nBuilding BLEECAM model (this takes ~30s)...')
    model = build_model(args.data)
    print('Model built. Handing off to PyAUGMECON...\n')
    opts = {'name': 'BLEECAM_Pareto', 'grid_points': args.grid, 'nadir_ratio': 1.0, 'early_exit': True, 'bypass_coefficient': True, 'flag_array': True, 'cpu_count': args.cpus, 'penalty_weight': 0.001, 'solver_name': 'ipopt', 'solver_io': 'nl', 'output_excel': True, 'process_logging': False}
    pa = PyAugmecon(model, opts, solver_opts={'MIPGap': None})
    pa.solve()
    pareto_keys = pa.get_pareto_solutions()
    n = len(pareto_keys)
    print(f"\n{'=' * 60}")
    print(f'Pareto solutions : {n}')
    print(f'Models solved    : {pa.model.models_solved.value()}')
    print(f'Infeasibilities  : {pa.model.infeasibilities.value()}')
    print(f'Runtime          : {pa.runtime}s')
    print(f'Hypervolume      : {pa.hv_indicator:.6f}')
    print(f"{'=' * 60}")
    print('\nPayoff table (rows = optimizing each obj alone, cols = obj values):')
    pt = pa.get_payoff_table()
    print(f'  (raw = Pyomo objective;  scaled = × FLOW_SCALE = {FLOW_SCALE})')
    print(f'             Cost (USD)          GWP (kg CO2-eq)    Child Labor (hrs)')
    print(f'Min Cost:  {pt[0, 0] * FLOW_SCALE:>18,.2f}  {pt[0, 1] * FLOW_SCALE:>18,.2f}  {pt[0, 2] * FLOW_SCALE:>16.6f}')
    print(f'Min GWP:   {pt[1, 0] * FLOW_SCALE:>18,.2f}  {pt[1, 1] * FLOW_SCALE:>18,.2f}  {pt[1, 2] * FLOW_SCALE:>16.6f}')
    print(f'Min SLCA:  {pt[2, 0] * FLOW_SCALE:>18,.2f}  {pt[2, 1] * FLOW_SCALE:>18,.2f}  {pt[2, 2] * FLOW_SCALE:>16.6f}')
    df = pd.DataFrame([{'cost_usd': k[0] * FLOW_SCALE, 'gwp_kg_co2eq': k[1] * FLOW_SCALE, 'child_labor_hrs': k[2] * FLOW_SCALE} for k in pareto_keys]).sort_values('cost_usd').reset_index(drop=True)
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / 'pareto_results.csv'
    df.to_csv(csv_path, index=False)
    print(f'\nPareto CSV     → {csv_path}')
    _plot_3d(df, args.out / 'pareto_3d.html')
    _plot_pairwise(df, args.out / 'pareto_pairwise.html')
    print('\nDone.')