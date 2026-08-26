import pandas as pd
import matplotlib.pyplot as plt
from pycirclize import Circos
from io import BytesIO
from PIL import Image
from pathlib import Path
FILE = 'model_results_no_slack_lag_factors_cost_imports.csv'
START_PERIOD = 0
VALUE_COL = 'flow_value'
ABS_MIN = 0.0
REL_MIN_FRAC = 0.0
LABEL_SIZE = 9
SPACE_DEG = 3
OUTFILE = f'chord_6pack_{START_PERIOD:02d}_{VALUE_COL}.png'
DELAY_SOURCES = {'direct reuse', 'magnet-to-magnet recycling', 'cryogenic', 'hydrometallurgical', 'pyrometallurgical'}
df = pd.read_csv(FILE)
df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
df['tp_label'] = df['time_period'] - df['source'].isin(DELAY_SOURCES).astype(int)

def make_label(name, tag):
    """Format a process name (wrapping long names to two lines) and append a period tag.

    :param name: Process name (underscores replaced with spaces).
    :type name: str
    :param tag: Time period tag to append to the label.
    :type tag: int or str
    :returns: Formatted label string with wrapped name and period tag e.g. "magnet\\nmanufacturing\\n(P 3)".
    :rtype: str
    """
    _a = name.replace('_', ' ').split()
    if len(_a) <= 2:
        _b = '\n'.join(_a)
    else:
        _c = len(_a) // 2
        _b = ' '.join(_a[:_c]) + '\n' + ' '.join(_a[_c:])
    return f'{_b}\n(P {tag})'

def slice_to_matrix(slc):
    """Pivot a time-period slice of the flow DataFrame into a source×destination matrix with formatted labels.

    :param slc: Filtered flow DataFrame for a single time period, with columns source, destination, flow_value, time_period, tp_label.
    :type slc: pd.DataFrame
    :returns: Pivot DataFrame with formatted source labels as index and destination labels as columns, suitable for a chord diagram.
    :rtype: pd.DataFrame
    """
    _a = slc.pivot_table(index='source', columns='destination', values=VALUE_COL, aggfunc='sum', fill_value=0).reindex(sorted(slc['source'].unique())).sort_index(axis=1)
    _b = slc.groupby('source')['time_period'].first()
    _c = slc.groupby('source')['tp_label'].first()
    _e = {_d: _c[_d] if _d in DELAY_SOURCES else _b[_d] for _d in _b.index}
    _f = slc.groupby('destination')['time_period'].first()
    _a.index = [make_label(_d, _e[_d]) for _d in _a.index]
    _a.columns = [make_label(_g, _f[_g]) for _g in _a.columns]
    return _a
(fig, axes) = plt.subplots(2, 3, figsize=(18, 10))
axes = axes.flatten()
for (slot, period) in enumerate(range(START_PERIOD, START_PERIOD + 6)):
    ax = axes[slot]
    slc = df[df['time_period'] == period].copy()
    slc = slc[slc[VALUE_COL] > ABS_MIN]
    if slc.empty:
        ax.set_visible(False)
        continue
    if REL_MIN_FRAC > 0:
        max_val = slc[VALUE_COL].max()
        slc = slc[slc[VALUE_COL] >= REL_MIN_FRAC * max_val]
    if slc.empty:
        ax.set_visible(False)
        continue
    mat = slice_to_matrix(slc)
    circ = Circos.chord_diagram(mat, space=SPACE_DEG, cmap='tab20', label_kws=dict(size=LABEL_SIZE, orientation='vertical', adjust_rotation=True), link_kws=dict(ec='black', lw=0.3))
    tmp = circ.plotfig()
    buf = BytesIO()
    tmp.savefig(buf, dpi=300, bbox_inches='tight')
    plt.close(tmp)
    buf.seek(0)
    ax.imshow(Image.open(buf))
    ax.axis('off')
    ax.set_title(f'Plot Period {period}', pad=8, fontsize=11)
for extra_ax in axes[slot + 1:]:
    extra_ax.set_visible(False)
fig.subplots_adjust(wspace=0.02, hspace=0.06)
fig.tight_layout(pad=0.4)
fig.savefig(OUTFILE, dpi=300, bbox_inches='tight')
plt.show()
print(f'✅ saved {OUTFILE}')