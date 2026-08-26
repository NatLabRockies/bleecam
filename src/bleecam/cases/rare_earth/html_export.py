import json
import datetime
import pandas as pd
from .config import locations
_UNUSED_OXIDE_KEYS_SET: 0 = set()
for _l1 in locations:
    for _l2 in locations:
        for _src in ['sulfuric acid digestion', 'hydrochloric acid digestion', 'clay refining']:
            _UNUSED_OXIDE_KEYS_SET.add((_src, _l1, 'molten_salt electrolysis', _l2, 'dysprosium_oxide'))
            _UNUSED_OXIDE_KEYS_SET.add((_src, _l1, 'metallothermic reduction', _l2, 'neodynium_oxide'))
UNUSED_OXIDE_KEYS = _UNUSED_OXIDE_KEYS_SET
LOC_COLOR = {'CN': '#e74c3c', 'JP': '#3498db', 'AU': '#f39c12', 'US': '#27ae60', 'MM': '#9b59b6', 'MY': '#1abc9c', 'EE': '#34495e', 'CA': '#e67e22', 'BR': '#16a085', '': '#95a5a6'}
MAT_COLOR = {'hp_magnet': '#8e44ad', 'neodynium dysprosium iron alloy': '#2c3e50', 'neodynium': '#1abc9c', 'dysprosium': '#e67e22', 'neodynium_oxide': '#16a085', 'dysprosium_oxide': '#d35400', 'phosphate': '#7f8c8d', 'flurocarbonate': '#bdc3c7', 'monazaite': '#95a5a6', 'bastnasite': '#a0522d', 'ion adsorption clay': '#c8a96e', 'iron': '#555555'}

def export_diagnostic_html(df, unused_per_t, total_unused, unused_penalty, obj_value, obj_name, penalty_weight, path='model_diagnostic_report.html'):
    """Build and write a full interactive HTML diagnostic report for a solved scenario.

    :param df: Full flow results DataFrame with columns time_period, source, source_location, destination, destination_location, material, flow_value, and optional cost/EF columns.
    :type df: pd.DataFrame
    :param unused_per_t: List of (t, dyox_unused, ndox_unused) tuples per time period.
    :type unused_per_t: list[tuple]
    :param total_unused: Total unused co-product oxide volume across all periods (kg, unscaled).
    :type total_unused: float
    :param unused_penalty: Total monetized penalty for unused oxides.
    :type unused_penalty: float
    :param obj_value: Solver objective value for the displayed scenario.
    :type obj_value: float
    :param obj_name: Name of the minimized objective (e.g. 'cost', 'GWP', 'SLCA').
    :type obj_name: str
    :param penalty_weight: Cost penalty per kg of unused oxide.
    :type penalty_weight: float
    :param path: Output file path for the HTML report.
    :type path: str
    """
    df = df.copy()
    df['_unused'] = df.apply(lambda r: (r['source'], r['source_location'], r['destination'], r['destination_location'], r['material']) in _UNUSED_OXIDE_KEYS_SET, axis=1)
    df['_cross'] = df['source_location'] != df['destination_location']
    df['_total_cost'] = (df.get('process_cost', pd.Series(0, index=df.index)).fillna(0) + df.get('domestic_transport_cost', pd.Series(0, index=df.index)).fillna(0) + df.get('shipping_cost', pd.Series(0, index=df.index)).fillna(0) + df.get('tariff_cost', pd.Series(0, index=df.index)).fillna(0)) * df['flow_value']
    _b = [int(_a) for _a in sorted(df['time_period'].unique())]
    _c = int((~df['_unused']).sum())
    _d = int(df['_unused'].sum())
    _e = int(df['_cross'].sum())
    _f = float(df['flow_value'].sum())
    _g = float(df['_total_cost'].sum())
    _h = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def make_node_label(proc, loc):
        """Format a Sankey node label as process\\n(location).

        :param proc: Process name.
        :type proc: str
        :param loc: Location code, or empty string if none.
        :type loc: str
        :returns: Formatted label string as "proc\\n(loc)" or just "proc" if no location.
        :rtype: str
        """
        return f'{proc}\n({loc})' if loc else proc
    _i = []
    for _j in _b:
        _k = df[(df['time_period'] == _j) & (df['flow_value'] > 1e-06)].copy()
        if _k.empty:
            _i.append({'nodes': [], 'links': []})
            continue
        _k['src_node'] = _k['source'] + '||' + _k['source_location']
        _k['dst_node'] = _k['destination'] + '||' + _k['destination_location']
        _l = pd.unique(_k[['src_node', 'dst_node']].values.ravel())
        _o = {_n: _m for (_m, _n) in enumerate(_l)}
        _p = []
        _q = []
        for _n in _l:
            _r = _n.split('||')
            _s = _r[0]
            _t = _r[1] if len(_r) > 1 else ''
            _p.append(make_node_label(_s, _t))
            _q.append(LOC_COLOR.get(_t, '#95a5a6'))
        (_u, _v, _w, _x, _y) = ([], [], [], [], [])
        for (_z, _aa) in _k.iterrows():
            _u.append(_o[_aa['src_node']])
            _v.append(_o[_aa['dst_node']])
            _w.append(float(_aa['flow_value']))
            _ab = MAT_COLOR.get(_aa['material'], '#aaaaaa')
            _ac = '0.4' if _aa['_cross'] else '0.7'
            (_ad, _ae, _af) = (int(_ab[1:3], 16), int(_ab[3:5], 16), int(_ab[5:7], 16))
            _x.append(f'rgba({_ad},{_ae},{_af},{_ac})')
            _y.append(f"{_aa['material']}<br>{_aa['source_location']}→{_aa['destination_location']}<br>{_aa['flow_value']:,.4f} kg")
        _i.append({'nodes': {'label': _p, 'color': _q, 'pad': 15, 'thickness': 20}, 'links': {'source': _u, 'target': _v, 'value': _w, 'color': _x, 'label': _y}})
    _ag = json.dumps(_i)
    _ah = json.dumps(_b)
    _ai = df[df['_cross']].copy()
    _ai['arc'] = _ai['source_location'] + '→' + _ai['destination_location']
    _aj = {}
    for _j in _b:
        _k = _ai[_ai['time_period'] == _j]
        _aj[_j] = _k.groupby('arc')['flow_value'].sum().to_dict()
    _ao = json.dumps({int(_ak): {str(_am): float(_an) for (_am, _an) in _al.items()} for (_ak, _al) in _aj.items()})
    _ap = ''
    for _j in _b:
        _k = df[df['time_period'] == _j]
        _aq = _k[~_k['_unused']]
        _ar = _k[_k['_unused']]
        _as = _k[_k['_cross']]
        _at = float(_aq['_total_cost'].sum())
        _au = float(_ar['flow_value'].sum())
        _av = penalty_weight * _au
        _aw = float(_as['flow_value'].sum())
        _ax = f'<span class="badge bwarn">⚠ {_au:,.4f} kg unused</span>' if _au > 1e-09 else '<span class="badge bok">✓</span>'
        _ap += f"<tr><td>{_j}</td><td>{len(_aq)}</td><td>{_aq['flow_value'].sum():,.4f}</td><td>{_at:,.2f}</td><td>{len(_as)}</td><td>{_aw:,.4f}</td><td>{len(_ar)}</td><td>{_au:,.4f}</td><td>{_av:,.2f}</td><td>{_ax}</td></tr>\n"
    _ay = ''
    for (_j, _az, _ba) in unused_per_t:
        _bb = _az + _ba
        _bc = penalty_weight * _bb
        _ay += f'<tr><td>{_j}</td><td>{_az:,.6f}</td><td>{_ba:,.6f}</td><td>{_bb:,.6f}</td><td>{_bc:,.4f}</td></tr>\n'
    _bd = ''
    if not _ai.empty:
        _be = _ai.groupby(['time_period', 'source', 'source_location', 'destination', 'destination_location', 'material'])['flow_value'].sum().reset_index().sort_values(['time_period', 'source_location', 'destination_location'])
        for (_z, _ad) in _be.iterrows():
            _bd += f"""<tr><td>{int(_ad['time_period'])}</td><td>{_ad['source']}</td><td><span class="loc-badge" style="background:{LOC_COLOR.get(_ad['source_location'], '#aaa')}">{_ad['source_location']}</span></td><td>{_ad['destination']}</td><td><span class="loc-badge" style="background:{LOC_COLOR.get(_ad['destination_location'], '#aaa')}">{_ad['destination_location']}</span></td><td>{_ad['material']}</td><td>{_ad['flow_value']:,.4f}</td></tr>\n"""
    _bf = ''
    for (_m, (_z, _ad)) in enumerate(df.iterrows()):
        cls = ('unused' if _ad['_unused'] else '') + (' cross' if _ad['_cross'] else '') + (' alt' if _m % 2 == 0 else '')
        _bg = ''
        if _ad['_unused']:
            _bg = '<span class="badge bwarn">unused</span>'
        elif _ad['_cross']:
            _bg = '<span class="badge bcross">cross-border</span>'
        _bf += f'''<tr class="{cls.strip()}"><td>{_ad['time_period']}</td><td>{_ad['source']}</td><td><span class="loc-badge" style="background:{LOC_COLOR.get(_ad['source_location'], '#aaa')}">{_ad['source_location']}</span></td><td>{_ad['destination']}</td><td><span class="loc-badge" style="background:{LOC_COLOR.get(_ad['destination_location'], '#aaa')}">{_ad['destination_location']}</span></td><td>{_ad['material']}</td><td>{_ad['flow_value']:,.6f}</td><td>{(_ad.get('process_cost') if pd.notna(_ad.get('process_cost')) else '—')}</td><td>{(_ad.get('domestic_transport_cost') if pd.notna(_ad.get('domestic_transport_cost')) else '—')}</td><td>{(_ad.get('shipping_cost') if pd.notna(_ad.get('shipping_cost')) else '—')}</td><td>{(_ad.get('tariff_cost') if pd.notna(_ad.get('tariff_cost')) else '—')}</td><td>{(_ad.get('emission_factor') if pd.notna(_ad.get('emission_factor')) else '—')}</td><td>{_bg}</td></tr>\n'''
    _bj = ''.join((f'<span class="loc-badge" style="background:{_bi}">{_bh}</span> ' for (_bh, _bi) in LOC_COLOR.items() if _bh))
    _bl = ''.join((f'<span style="display:inline-block;width:12px;height:12px;background:{_bi};border-radius:2px;margin-right:3px;vertical-align:middle"></span><span style="font-size:11px;margin-right:10px">{_bk}</span>' for (_bk, _bi) in MAT_COLOR.items()))
    _bm = ''.join((f'<option value="{_bh}">{_bh}</option>' for _bh in ['CN', 'JP', 'AU', 'US', 'MM', 'MY', 'EE', 'CA', 'BR']))
    _bn = f"""<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<title>BLEECAM — Multi-Location Diagnostic Report</title>\n<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>\n<style>\n:root {{\n  --navy:#1F3864; --amber:#856404; --amber-bg:#fff8e1; --amber-row:#fff3cd;\n  --green-bg:#e8f4e8; --alt-bg:#f7f7f7; --border:#ddd;\n  --cn:#e74c3c; --jp:#3498db; --au:#f39c12; --us:#27ae60;\n}}\n*{{box-sizing:border-box;margin:0;padding:0}}\nbody{{font-family:'Segoe UI',Arial,sans-serif;font-size:13px;color:#222;background:#eef0f4}}\nheader{{background:var(--navy);color:#fff;padding:18px 32px;display:flex;align-items:center;gap:20px}}\nheader h1{{font-size:22px;font-weight:700}}\nheader p{{font-size:12px;opacity:.75;margin-top:3px}}\n.container{{max-width:1500px;margin:24px auto;padding:0 20px}}\n.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:22px}}\n.card{{background:#fff;border-radius:10px;padding:16px 22px;flex:1 1 160px;\n       box-shadow:0 1px 5px rgba(0,0,0,.08);border-top:4px solid var(--navy)}}\n.card.warn{{border-top-color:#e6a817}}.card.info{{border-top-color:#3498db}}\n.card.cross{{border-top-color:#8e44ad}}\n.card h3{{font-size:10px;text-transform:uppercase;color:#999;letter-spacing:.06em}}\n.card .val{{font-size:24px;font-weight:700;color:var(--navy);margin-top:5px}}\n.card.warn .val{{color:var(--amber)}}.card.cross .val{{color:#8e44ad}}\n.section{{background:#fff;border-radius:10px;padding:22px 26px;margin-bottom:22px;\n          box-shadow:0 1px 5px rgba(0,0,0,.08)}}\n.section h2{{font-size:15px;color:var(--navy);border-bottom:2px solid var(--navy);\n             padding-bottom:8px;margin-bottom:16px;display:flex;align-items:center;gap:8px}}\n.tbl-wrap{{overflow-x:auto}}\ntable{{border-collapse:collapse;width:100%;font-size:12px}}\nth{{background:var(--navy);color:#fff;padding:8px 10px;text-align:left;\n    position:sticky;top:0;white-space:nowrap}}\ntd{{padding:6px 10px;border-bottom:1px solid var(--border);vertical-align:middle}}\ntr.alt td{{background:var(--alt-bg)}}\ntr.unused td{{background:var(--amber-row)}}\ntr.cross td{{background:#f0e6ff}}\ntr.unused.cross td{{background:#ffe0cc}}\ntr:hover td{{filter:brightness(.96)}}\n.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}\n.bwarn{{background:#fff3cd;color:var(--amber);border:1px solid #e6a817}}\n.bok{{background:var(--green-bg);color:#145214;border:1px solid #4caf50}}\n.bcross{{background:#ede0ff;color:#6c3483;border:1px solid #8e44ad}}\n.loc-badge{{display:inline-block;padding:2px 7px;border-radius:4px;color:#fff;\n            font-size:11px;font-weight:700;letter-spacing:.04em}}\n.filter-bar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}}\n.filter-bar input{{padding:6px 10px;border:1px solid var(--border);border-radius:5px;\n                   font-size:12px;width:260px}}\n.filter-bar select{{padding:6px 8px;border:1px solid var(--border);border-radius:5px;font-size:12px}}\n.tbtn{{padding:5px 12px;border:1px solid var(--navy);border-radius:5px;\n       background:#fff;color:var(--navy);cursor:pointer;font-size:12px}}\n.tbtn.active{{background:var(--navy);color:#fff}}\n.sankey-ctrl{{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap}}\n.sankey-ctrl label{{font-size:12px;font-weight:600;color:var(--navy)}}\n.sankey-ctrl select{{padding:5px 8px;border:1px solid var(--border);border-radius:5px;font-size:12px}}\n.legend{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;font-size:11px}}\n.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:0}}\n@media(max-width:900px){{.charts-row{{grid-template-columns:1fr}}}}\n</style>\n</head>\n<body>\n\n<header>\n  <div>\n    <h1>🌐 BLEECAM — Multi-Location Supply Chain Report</h1>\n    <p>Generated: {_h} &nbsp;|&nbsp; Objective: <strong>{obj_name}</strong>\n       &nbsp;|&nbsp; Solver: IPOPT &nbsp;|&nbsp; Periods: {len(_b)}</p>\n  </div>\n</header>\n\n<div class="container">\n\n<!-- ── KPI Cards ── -->\n<div class="cards">\n  <div class="card">\n    <h3>Objective Value</h3>\n    <div class="val">{obj_value:,.2f}</div>\n  </div>\n  <div class="card">\n    <h3>Active Flows</h3>\n    <div class="val">{_c}</div>\n  </div>\n  <div class="card">\n    <h3>Total Flow Volume (kg)</h3>\n    <div class="val">{_f:,.2f}</div>\n  </div>\n  <div class="card">\n    <h3>Total Flow Cost ($)</h3>\n    <div class="val">{_g:,.2f}</div>\n  </div>\n  <div class="card cross">\n    <h3>Cross-Border Flows</h3>\n    <div class="val">{_e}</div>\n  </div>\n  <div class="card warn">\n    <h3>Unused Oxide Flows</h3>\n    <div class="val">{_d}</div>\n  </div>\n  <div class="card warn">\n    <h3>Total Unused Volume (kg)</h3>\n    <div class="val">{total_unused:,.4f}</div>\n  </div>\n  <div class="card warn">\n    <h3>Unused Penalty (penalty units)</h3>\n    <div class="val">{unused_penalty:,.2f}</div>\n  </div>\n</div>\n\n<!-- ── Sankey Diagram ── -->\n<div class="section">\n  <h2>🔀 Material Flow Sankey Diagram</h2>\n  <div class="sankey-ctrl">\n    <label>Time Period:</label>\n    <select id="sankeyPeriod" onchange="renderSankey()">\n      {''.join((f'<option value="{_j}">Period {_j}</option>' for _j in _b))}\n    </select>\n    <span style="font-size:11px;color:#888">Node colour = location &nbsp;|&nbsp; Link colour = material &nbsp;|&nbsp; Cross-border links are semi-transparent</span>\n  </div>\n  <div class="legend">\n    <strong style="font-size:11px">Locations:</strong> {_bj}\n  </div>\n  <div class="legend" style="margin-top:6px">\n    <strong style="font-size:11px">Materials:</strong> {_bl}\n  </div>\n  <div id="sankey" style="width:100%;height:600px;margin-top:14px"></div>\n</div>\n\n<!-- ── Country Flow Charts ── -->\n<div class="section">\n  <h2>🌍 Cross-Border Trade Volumes</h2>\n  <div class="sankey-ctrl">\n    <label>Time Period:</label>\n    <select id="barPeriod" onchange="renderBar()">\n      {''.join((f'<option value="{_j}">Period {_j}</option>' for _j in _b))}\n    </select>\n  </div>\n  <div class="charts-row">\n    <div id="barChart"  style="height:380px"></div>\n    <div id="lineChart" style="height:380px"></div>\n  </div>\n</div>\n\n<!-- ── Trade Arc Table ── -->\n<div class="section">\n  <h2>✈️ Cross-Border Trade Flows</h2>\n  <div class="filter-bar">\n    <input type="text" id="tradeFilter" placeholder="Filter source, destination, material…" oninput="filterTrade()">\n    <select id="tradeLocFrom" onchange="filterTrade()">\n      <option value="">All source locations</option>\n      {_bm}\n    </select>\n    <select id="tradeLocTo" onchange="filterTrade()">\n      <option value="">All dest locations</option>\n      {_bm}\n    </select>\n    <select id="tradePeriod" onchange="filterTrade()">\n      <option value="">All periods</option>\n      {''.join((f'<option value="{_j}">Period {_j}</option>' for _j in _b))}\n    </select>\n  </div>\n  <div class="tbl-wrap">\n  <table id="tradeTable">\n    <thead><tr>\n      <th>Period</th><th>Source Process</th><th>From</th>\n      <th>Dest Process</th><th>To</th><th>Material</th><th>Volume (kg)</th>\n    </tr></thead>\n    <tbody>{_bd}</tbody>\n  </table>\n  </div>\n</div>\n\n<!-- ── Unused Oxide Penalty ── -->\n<div class="section">\n  <h2>⚠️ Unused Co-product Oxide Penalty</h2>\n  <div style="background:var(--amber-bg);border-left:4px solid #e6a817;padding:12px 16px;\n              border-radius:4px;margin-bottom:14px;font-size:12px;color:#5c3d00;line-height:1.7">\n    <strong>Why these flows exist:</strong> SAD/HCAD/clay refining co-produce NdOx and DyOx in fixed ratios.\n    The co-flow ratio lock constraint forces both oxides to move together to each destination.\n    MSE only extracts value from NdOx; MR only from DyOx — so the opposite oxide at each reactor\n    is physically present but contributes no product. Penalised at ×{penalty_weight} per kg.\n  </div>\n  <div class="tbl-wrap">\n  <table>\n    <thead><tr>\n      <th>Period</th><th>DyOx→MSE (kg)</th><th>NdOx→MR (kg)</th>\n      <th>Total Unused (kg)</th><th>Penalty ($)</th>\n    </tr></thead>\n    <tbody>\n    {_ay}\n    <tr style="background:#e8eaf6;font-weight:700">\n      <td>TOTAL</td><td></td><td></td>\n      <td>{total_unused:,.6f}</td><td>{unused_penalty:,.4f}</td>\n    </tr>\n    </tbody>\n  </table>\n  </div>\n</div>\n\n<!-- ── Period Summary ── -->\n<div class="section">\n  <h2>📅 Period-by-Period Summary</h2>\n  <div class="tbl-wrap">\n  <table>\n    <thead><tr>\n      <th>Period</th><th>Active Flows</th><th>Active Volume (kg)</th><th>Active Cost ($)</th>\n      <th>Cross-Border Flows</th><th>Cross-Border Volume (kg)</th>\n      <th>Unused Flows</th><th>Unused Volume (kg)</th><th>Unused Penalty ($)</th><th>Status</th>\n    </tr></thead>\n    <tbody>{_ap}</tbody>\n  </table>\n  </div>\n</div>\n\n<!-- ── All Flows ── -->\n<div class="section">\n  <h2>📋 All Material Flows</h2>\n  <div class="filter-bar">\n    <input type="text" id="flowFilter" placeholder="Filter source, destination, material…" oninput="filterFlows()">\n    <select id="flowPeriod" onchange="filterFlows()">\n      <option value="">All periods</option>\n      {''.join((f'<option value="{_j}">Period {_j}</option>' for _j in _b))}\n    </select>\n    <select id="flowLoc" onchange="filterFlows()">\n      <option value="">All locations</option>\n      {_bm}\n    </select>\n    <button class="tbtn active" id="btnAll"    onclick="setFlowFilter('all')">All</button>\n    <button class="tbtn"        id="btnActive" onclick="setFlowFilter('active')">Active only</button>\n    <button class="tbtn"        id="btnCross"  onclick="setFlowFilter('cross')">Cross-border</button>\n    <button class="tbtn"        id="btnUnused" onclick="setFlowFilter('unused')">Unused only</button>\n  </div>\n  <div class="tbl-wrap">\n  <table id="flowTable">\n    <thead><tr>\n      <th>Period</th><th>Source</th><th>From</th><th>Destination</th><th>To</th>\n      <th>Material</th><th>Volume (kg)</th>\n      <th>Proc Cost ($/kg)</th><th>Dom. Transport ($/kg)</th><th>Intl. Shipping ($/kg)</th>\n      <th>Tariff ($/kg)</th><th>EF (GWP)</th><th>Type</th>\n    </tr></thead>\n    <tbody>{_bf}</tbody>\n  </table>\n  </div>\n</div>\n\n</div><!-- /container -->\n\n<script>\nvar SANKEY_FRAMES = {_ag};\nvar PERIODS       = {_ah};\nvar BAR_DATA      = {_ao};\n\nfunction renderSankey() {{\n  var t   = parseInt(document.getElementById('sankeyPeriod').value);\n  var idx = PERIODS.indexOf(t);\n  var f   = SANKEY_FRAMES[idx];\n  if (!f || !f.nodes || f.nodes.label.length === 0) {{\n    Plotly.purge('sankey');\n    document.getElementById('sankey').innerHTML =\n      '<p style="text-align:center;color:#999;padding:40px">No flows in this period.</p>';\n    return;\n  }}\n  var data = [{{\n    type: 'sankey', orientation: 'h', arrangement: 'snap',\n    node: {{\n      label: f.nodes.label, color: f.nodes.color,\n      pad: f.nodes.pad, thickness: f.nodes.thickness,\n      line: {{color:'#fff', width:0.5}}\n    }},\n    link: {{\n      source: f.links.source, target: f.links.target,\n      value: f.links.value, color: f.links.color, label: f.links.label,\n      hovertemplate: '%{{label}}<extra></extra>'\n    }}\n  }}];\n  var layout = {{\n    font: {{size:11, family:'Segoe UI,Arial,sans-serif'}},\n    paper_bgcolor: '#ffffff',\n    margin: {{l:10, r:10, t:10, b:10}}\n  }};\n  Plotly.react('sankey', data, layout, {{responsive:true, displayModeBar:false}});\n}}\nrenderSankey();\n\nfunction renderBar() {{\n  var t    = parseInt(document.getElementById('barPeriod').value);\n  var arcs = BAR_DATA[t] || {{}};\n  var labels = Object.keys(arcs);\n  var vals   = Object.values(arcs);\n  var barTrace = {{\n    type: 'bar', x: labels, y: vals,\n    marker: {{\n      color: labels.map(function(l) {{\n        var from = l.split('→')[0];\n        var cols = {{'CN':'#e74c3c','JP':'#3498db','AU':'#f39c12','US':'#27ae60',\n                    'MM':'#9b59b6','MY':'#1abc9c','EE':'#34495e','CA':'#e67e22','BR':'#16a085'}};\n        return cols[from] || '#aaa';\n      }}), opacity: 0.8\n    }},\n    text: vals.map(function(v){{return v.toFixed(2)+' kg'}}),\n    textposition: 'outside',\n    hovertemplate: '%{{x}}<br>%{{y:,.4f}} kg<extra></extra>'\n  }};\n  Plotly.react('barChart', [barTrace], {{\n    title:{{text:'Cross-Border Volume by Arc — Period '+t, font:{{size:13}}}},\n    xaxis:{{title:'Trade Arc', tickangle:-30}},\n    yaxis:{{title:'Volume (kg)'}},\n    paper_bgcolor:'#fff', plot_bgcolor:'#f9f9f9',\n    margin:{{l:60,r:20,t:40,b:80}}\n  }}, {{responsive:true, displayModeBar:false}});\n\n  var fromLocs = ['CN','JP','AU','US','MM','MY','EE','CA','BR'];\n  var lineTraces = fromLocs.map(function(loc) {{\n    var ys = PERIODS.map(function(tp) {{\n      var bd = BAR_DATA[tp] || {{}};\n      return Object.entries(bd)\n        .filter(function(kv){{return kv[0].startsWith(loc+'→')}})\n        .reduce(function(s,kv){{return s+kv[1]}}, 0);\n    }});\n    var cols = {{'CN':'#e74c3c','JP':'#3498db','AU':'#f39c12','US':'#27ae60',\n                 'MM':'#9b59b6','MY':'#1abc9c','EE':'#34495e','CA':'#e67e22','BR':'#16a085'}};\n    return {{\n      type:'scatter', mode:'lines+markers',\n      name: 'From '+loc, x: PERIODS, y: ys,\n      line:{{color:cols[loc]||'#aaa', width:2}},\n      marker:{{size:6}},\n      hovertemplate: 'Period %{{x}}<br>%{{y:,.4f}} kg<extra>From '+loc+'</extra>'\n    }};\n  }}).filter(function(tr){{return tr.y.some(function(v){{return v>0}})}});\n\n  Plotly.react('lineChart', lineTraces, {{\n    title:{{text:'Cross-Border Volume Over Time by Source Country', font:{{size:13}}}},\n    xaxis:{{title:'Period', dtick:1}},\n    yaxis:{{title:'Volume (kg)'}},\n    legend:{{orientation:'h', y:-0.2}},\n    paper_bgcolor:'#fff', plot_bgcolor:'#f9f9f9',\n    margin:{{l:60,r:20,t:40,b:60}}\n  }}, {{responsive:true, displayModeBar:false}});\n}}\nrenderBar();\n\nfunction filterTrade() {{\n  var q    = document.getElementById('tradeFilter').value.toLowerCase();\n  var locF = document.getElementById('tradeLocFrom').value;\n  var locT = document.getElementById('tradeLocTo').value;\n  var per  = document.getElementById('tradePeriod').value;\n  document.querySelectorAll('#tradeTable tbody tr').forEach(function(row) {{\n    var cells = row.cells;\n    var txt   = row.innerText.toLowerCase();\n    var matchQ = !q    || txt.includes(q);\n    var matchF = !locF || (cells[2] && cells[2].innerText.trim() === locF);\n    var matchT = !locT || (cells[4] && cells[4].innerText.trim() === locT);\n    var matchP = !per  || (cells[0] && cells[0].innerText.trim() === per);\n    row.style.display = (matchQ && matchF && matchT && matchP) ? '' : 'none';\n  }});\n}}\n\nvar _flowFilter = 'all';\nfunction setFlowFilter(f) {{\n  _flowFilter = f;\n  ['All','Active','Cross','Unused'].forEach(function(x) {{\n    var el = document.getElementById('btn'+x);\n    if(el) el.classList.remove('active');\n  }});\n  var sel = document.getElementById('btn'+f.charAt(0).toUpperCase()+f.slice(1));\n  if(sel) sel.classList.add('active');\n  filterFlows();\n}}\nfunction filterFlows() {{\n  var q   = document.getElementById('flowFilter').value.toLowerCase();\n  var per = document.getElementById('flowPeriod').value;\n  var loc = document.getElementById('flowLoc').value;\n  document.querySelectorAll('#flowTable tbody tr').forEach(function(row) {{\n    var cls   = row.className;\n    var isUnu = cls.includes('unused');\n    var isCrs = cls.includes('cross');\n    var txt   = row.innerText.toLowerCase();\n    var cells = row.cells;\n    var matchQ = !q   || txt.includes(q);\n    var matchP = !per || (cells[0] && cells[0].innerText.trim() === per);\n    var matchL = !loc || txt.includes(loc.toLowerCase());\n    var matchC =\n      _flowFilter === 'all'    ||\n      (_flowFilter === 'active' && !isUnu) ||\n      (_flowFilter === 'cross'  && isCrs)  ||\n      (_flowFilter === 'unused' && isUnu);\n    row.style.display = (matchQ && matchP && matchL && matchC) ? '' : 'none';\n  }});\n}}\n</script>\n</body>\n</html>"""
    with open(path, 'w', encoding='utf-8') as _bo:
        _bo.write(_bn)
    print(f'✅ HTML diagnostic report written to {path}')