import argparse
import glob
import os
from pathlib import Path
import pandas as pd
_HERE = Path(__file__).parent

def _parse_args():
    """Parse CLI arguments for data dir, output dir, CSV path, and Excel path.

    :returns: Parsed arguments with fields: data (Path), out (Path or None), csv (Path or None), excel (Path or None).
    :rtype: argparse.Namespace
    """
    _a = argparse.ArgumentParser(description='BLEECAM Pareto visualiser (no re-solve)')
    _a.add_argument('--data', type=Path, default=_HERE / 'data', help='Data/output directory (default: <script dir>/data)')
    _a.add_argument('--out', type=Path, default=None, help='Output directory for HTML files (default: same as source file)')
    _a.add_argument('--csv', type=Path, default=None, help='Explicit path to pareto_results.csv')
    _a.add_argument('--excel', type=Path, default=None, help='Explicit path to PyAUGMECON Excel (.xlsx) log file')
    return _a.parse_args()

def _load_from_csv(path):
    """Read a Pareto results CSV and return a DataFrame with standardized objective columns.

    :param path: Path to the Pareto results CSV file.
    :type path: Path
    :returns: DataFrame with columns cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :rtype: pd.DataFrame
    """
    _a = pd.read_csv(path)
    _a.columns = _a.columns.str.strip()
    _b = {}
    for _c in _a.columns:
        _d = _c.lower()
        if 'cost' in _d:
            _b[_c] = 'cost_usd'
        elif 'gwp' in _d or 'co2' in _d or 'emission' in _d:
            _b[_c] = 'gwp_kg_co2eq'
        elif 'child' in _d or 'labor' in _d or 'labour' in _d or ('slca' in _d):
            _b[_c] = 'child_labor_hrs'
    _a = _a.rename(columns=_b)
    return _a[['cost_usd', 'gwp_kg_co2eq', 'child_labor_hrs']].dropna()

def _load_from_excel(path):
    """Read the PyAUGMECON Excel log and return a DataFrame with the three Pareto objective columns.

    :param path: Path to the PyAUGMECON Excel (.xlsx) log file.
    :type path: Path
    :returns: DataFrame with columns cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :rtype: pd.DataFrame
    """
    _a = pd.ExcelFile(path)
    _b = 'unique_pareto_sols' if 'unique_pareto_sols' in _a.sheet_names else _a.sheet_names[0]
    _c = _a.parse(_b)
    if set(_c.columns[:3]) == {0, 1, 2} or list(_c.columns[:3]) == [0, 1, 2]:
        _c = _c.rename(columns={0: 'cost_usd', 1: 'gwp_kg_co2eq', 2: 'child_labor_hrs'})
    elif 'Unnamed: 0' in _c.columns:
        _c = _c.iloc[:, 1:4]
        _c.columns = ['cost_usd', 'gwp_kg_co2eq', 'child_labor_hrs']
    return _c[['cost_usd', 'gwp_kg_co2eq', 'child_labor_hrs']].dropna()

def _auto_find_excel(logs_dir):
    """Return the most-recently-modified .xlsx file in the given directory, or None.

    :param logs_dir: Directory to search for .xlsx files.
    :type logs_dir: Path
    :returns: Path to the most-recently-modified .xlsx file, or None if none found.
    :rtype: Path or None
    """
    _a = sorted(glob.glob(str(logs_dir / '*.xlsx')), key=os.path.getmtime, reverse=True)
    return Path(_a[0]) if _a else None

def load_results(args):
    """Resolve and load Pareto results from explicit CSV, Excel, or auto-detected sources.

    :param args: Parsed CLI arguments.
    :type args: argparse.Namespace
    :returns: Tuple of (DataFrame with Pareto results, Path to source file).
    :rtype: tuple[pd.DataFrame, Path]
    :raises FileNotFoundError: If no Pareto results file can be located.
    """
    if args.csv and args.csv.exists():
        print(f'Loading CSV: {args.csv}')
        return (_load_from_csv(args.csv), args.csv)
    if args.excel and args.excel.exists():
        print(f'Loading Excel: {args.excel}')
        return (_load_from_excel(args.excel), args.excel)
    _a = args.data / 'pareto_results.csv'
    if _a.exists():
        print(f'Auto-detected CSV: {_a}')
        return (_load_from_csv(_a), _a)
    _b = _HERE / 'logs'
    _c = _auto_find_excel(_b)
    if _c:
        print(f'Auto-detected Excel: {_c}')
        return (_load_from_excel(_c), _c)
    raise FileNotFoundError('No Pareto results found. Run pareto.py first, or pass --csv / --excel explicitly.')

def plot_3d(df, out_path):
    """Write an interactive 3D Pareto scatter plot to an HTML file.

    :param df: Pareto results with cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :type df: pd.DataFrame
    :param out_path: Output HTML file path.
    :type out_path: Path
    :returns: None
    :rtype: NoneType
    """
    import plotly.graph_objects as go
    _a = go.Figure(data=[go.Scatter3d(x=df['cost_usd'], y=df['gwp_kg_co2eq'], z=df['child_labor_hrs'], mode='markers', marker=dict(size=6, color=df['cost_usd'], colorscale='Viridis', colorbar=dict(title='Cost (USD)', thickness=15, len=0.6), opacity=0.88, line=dict(width=0.4, color='white')), hovertemplate='<b>Pareto Point</b><br>Cost:        $%{x:,.0f}<br>GWP:          %{y:,.0f} kg CO₂-eq<br>Child Labor:  %{z:.6f} hrs<extra></extra>', name='Pareto solutions')])
    _a.update_layout(title=dict(text=f'BLEECAM 3D Pareto Front — {len(df)} solutions  |  Cost / GWP / Child Labor', font=dict(size=16)), scene=dict(xaxis=dict(title='Cost (USD)', tickformat=',.0f'), yaxis=dict(title='GWP (kg CO₂-eq)', tickformat=',.0f'), zaxis=dict(title='Child Labor (hrs)'), camera=dict(eye=dict(x=1.6, y=1.6, z=0.9)), aspectmode='auto'), margin=dict(l=0, r=0, b=0, t=60), width=1100, height=800)
    _a.write_html(str(out_path))
    print(f'3D plot  → {out_path}')

def plot_pairwise(df, out_path):
    """Write a 1×3 pairwise Pareto trade-off plot with third-objective color axis to an HTML file.

    :param df: Pareto results with cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :type df: pd.DataFrame
    :param out_path: Output HTML file path.
    :type out_path: Path
    :returns: None
    :rtype: NoneType
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _a = make_subplots(rows=1, cols=3, subplot_titles=['Cost vs GWP', 'Cost vs Child Labor', 'GWP vs Child Labor'], horizontal_spacing=0.1)
    _b = [0.133, 0.5, 0.867]
    _c = 0.24
    _d = dict(orientation='h', thickness=14, len=_c, xanchor='center', y=-0.18, yanchor='top')
    _e = dict(size=7, opacity=0.8, showscale=True)
    _a.add_trace(go.Scatter(x=df['cost_usd'], y=df['gwp_kg_co2eq'], mode='markers', marker={**_e, 'color': df['child_labor_hrs'], 'colorscale': 'Plasma', 'colorbar': dict(**_d, title=dict(text='Child Labor (hrs)', side='bottom'), x=_b[0])}, name='Child Labor'), row=1, col=1)
    _a.add_trace(go.Scatter(x=df['cost_usd'], y=df['child_labor_hrs'], mode='markers', marker={**_e, 'color': df['gwp_kg_co2eq'], 'colorscale': 'Teal', 'colorbar': dict(**_d, title=dict(text='GWP (kg CO₂-eq)', side='bottom'), tickformat=',.0f', x=_b[1])}, name='GWP'), row=1, col=2)
    _a.add_trace(go.Scatter(x=df['gwp_kg_co2eq'], y=df['child_labor_hrs'], mode='markers', marker={**_e, 'color': df['cost_usd'], 'colorscale': 'Oranges', 'colorbar': dict(**_d, title=dict(text='Cost (USD)', side='bottom'), tickformat=',.0f', x=_b[2])}, name='Cost'), row=1, col=3)
    _a.update_xaxes(title_text='Cost (USD)', tickformat=',.0f', row=1, col=1)
    _a.update_xaxes(title_text='Cost (USD)', tickformat=',.0f', row=1, col=2)
    _a.update_xaxes(title_text='GWP (kg CO₂-eq)', tickformat=',.0f', row=1, col=3)
    _a.update_yaxes(title_text='GWP (kg CO₂-eq)', tickformat=',.0f', row=1, col=1)
    _a.update_yaxes(title_text='Child Labor (hrs)', row=1, col=2)
    _a.update_yaxes(title_text='Child Labor (hrs)', row=1, col=3)
    _a.update_layout(title=f'BLEECAM Pareto Front — Pairwise Trade-offs  ({len(df)} solutions)', showlegend=False, width=1500, height=580, margin=dict(b=110))
    _a.write_html(str(out_path))
    print(f'Pairwise → {out_path}')

def plot_parallel(df, out_path):
    """Write a parallel-coordinates Pareto plot to an HTML file.

    :param df: Pareto results with cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :type df: pd.DataFrame
    :param out_path: Output HTML file path.
    :type out_path: Path
    :returns: None
    :rtype: NoneType
    """
    import plotly.graph_objects as go
    _a = df.copy()
    for _b in ['cost_usd', 'gwp_kg_co2eq', 'child_labor_hrs']:
        (_c, _d) = (df[_b].min(), df[_b].max())
        _a[_b] = (df[_b] - _c) / (_d - _c) if _d > _c else 0.0
    _e = go.Figure(data=go.Parcoords(line=dict(color=df['cost_usd'], colorscale='Viridis', colorbar=dict(title='Cost (USD)', thickness=12), showscale=True), dimensions=[dict(label='Cost (USD)', values=df['cost_usd'], tickformat=',.0f'), dict(label='GWP (kg CO₂-eq)', values=df['gwp_kg_co2eq'], tickformat=',.0f'), dict(label='Child Labor (hrs)', values=df['child_labor_hrs'])]))
    _e.update_layout(title=f'BLEECAM Pareto Front — Parallel Coordinates  ({len(df)} solutions)', width=1000, height=550, margin=dict(l=80, r=80, t=60, b=40))
    _e.write_html(str(out_path))
    print(f'Parallel → {out_path}')

def print_summary(df):
    """Print min/max statistics for each of the three Pareto objectives.

    :param df: Pareto results with cost_usd, gwp_kg_co2eq, child_labor_hrs.
    :type df: pd.DataFrame
    :returns: None
    :rtype: NoneType
    """
    print(f"\n{'=' * 62}")
    print(f'  Pareto solutions loaded: {len(df)}')
    print(f"{'=' * 62}")
    print(f"  {'Objective':<22}  {'Min':>18}  {'Max':>18}")
    print(f"  {'-' * 60}")
    print(f"  {'Cost (USD)':<22}  {df['cost_usd'].min():>18,.0f}  {df['cost_usd'].max():>18,.0f}")
    print(f"  {'GWP (kg CO₂-eq)':<22}  {df['gwp_kg_co2eq'].min():>18,.0f}  {df['gwp_kg_co2eq'].max():>18,.0f}")
    print(f"  {'Child Labor (hrs)':<22}  {df['child_labor_hrs'].min():>18.6f}  {df['child_labor_hrs'].max():>18.6f}")
    print(f"{'=' * 62}\n")
if __name__ == '__main__':
    args = _parse_args()
    (df, source_path) = load_results(args)
    print_summary(df)
    out_dir = args.out if args.out else source_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_3d(df, out_dir / 'pareto_3d.html')
    plot_pairwise(df, out_dir / 'pareto_pairwise.html')
    plot_parallel(df, out_dir / 'pareto_parallel.html')
    print('\nDone — open any of the .html files in your browser.')