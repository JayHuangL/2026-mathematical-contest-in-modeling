"""Question 1: conservative radial finite volumes + implicit BDF integration.

Run from this directory: python solve_q1.py
Dependencies: numpy, scipy, openpyxl (read-only), matplotlib.
result1.xlsx is exported separately; the solver regenerates the numerical
payloads and validation records in the results folder.
"""
from pathlib import Path
import argparse
import json
import time
import zipfile
import xml.etree.ElementTree as ET
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
from scipy.sparse import diags, bmat, csr_matrix
try:
    import openpyxl
except ImportError:  # The standard-library reader below keeps this solver reproducible.
    openpyxl = None

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent.parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
from artifact_names import artifact_name, figure_name
from kirchhoff_flux import scalar_face
OUT = PACKAGE / 'results' / 'q1'
INPUT = PACKAGE / 'data' / '附件1.xlsx'
FIGURE_OUT = PACKAGE / 'figures' / 'q1'
OUT.mkdir(parents=True, exist_ok=True)
FIGURE_OUT.mkdir(parents=True, exist_ok=True)
R, RHO, CP, K, H, HM = 0.02, 820.0, 2600.0, 0.36, 25.0, 8e-7
ALPHA = K / (RHO * CP)
TIMES = np.arange(1801, dtype=float)
REPORT_TIMES = np.array([100, 300, 600, 900, 1200, 1500, 1800])
# The workbook keeps the required 0.1 cm radial output. A denser radial
# sampling is retained separately for the continuous colour-field figure.
PLOT_RADIAL_POINTS = 201
# 第一问只使用附件1的前1800 s数据拟合边界；第二问及以后由各自的
# boundary_stage.py 使用完整附件1数据拟合，再在稳定分界点前调用该拟合曲线。
DEFAULT_FIT_WINDOW_S = 1800.0


def read_environment():
    """Read Attachment 1 without requiring a writable spreadsheet application."""
    path = INPUT
    if openpyxl is not None:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        records = list(wb.active.values)
        wb.close()
        data = np.array(records[1:], dtype=float)
    else:
        # The supplied first worksheet has one header row followed by three numeric columns.
        namespace = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        records = []
        for row in root.findall('.//x:sheetData/x:row', namespace):
            values = []
            for cell in row.findall('x:c', namespace):
                value = cell.find('x:v', namespace)
                if value is not None:
                    values.append(float(value.text))
            if len(values) == 3:
                records.append(values)
        data = np.array(records[1:], dtype=float)
    assert data.shape[1] == 3 and np.isfinite(data).all()
    assert np.all(np.diff(data[:, 0]) > 0)
    assert data[0, 0] == 0 and data[-1, 0] >= 1800
    return data


def stretched_exponential(t_s, y0, amplitude, tau_h, exponent):
    """Monotone input smoother, with time expressed in seconds at the interface."""
    tau_s = 3600.0 * tau_h
    return y0 + amplitude * (1.0 - np.exp(-(t_s / tau_s) ** exponent))


def fit_environment(environment, fit_window_s):
    """在指定数据窗口内拟合两个环境边界，并返回连续输入。"""
    if not (1800.0 <= fit_window_s <= environment[-1, 0]):
        raise ValueError('fit_window_s must lie between 1800 s and the last attachment record.')
    fit_mask = environment[:, 0] <= fit_window_s
    q1_mask = environment[:, 0] <= 1800.0
    smooth = environment.copy()
    diagnostics = {'method_name': 'stretched_exp',
                   'family': '初值固定的拉伸指数模型',
                   'fit_window_s': float(fit_window_s), 'series': {}}
    for column, name, scale in [(1, 'T_infty_C', 22.0), (2, 'C_infty_kg_per_kg', 0.03)]:
        t_fit = environment[fit_mask, 0]
        y_fit = environment[fit_mask, column]
        y0 = float(y_fit[0])

        def residual(x):
            return stretched_exponential(t_fit, y0, *x) - y_fit

        solution = least_squares(
            residual, x0=[scale, 0.7, 1.1],
            bounds=([1e-12, 1e-5, 0.1], [100.0, 100.0, 5.0]),
            xtol=1e-13, ftol=1e-13, gtol=1e-13, max_nfev=100000,
        )
        if not solution.success:
            raise RuntimeError(f'Boundary fit failed for {name}: {solution.message}')
        amplitude, tau_h, exponent = map(float, solution.x)
        fitted_all = stretched_exponential(environment[:, 0], y0, *solution.x)
        fitted_window = fitted_all[fit_mask]
        fitted_q1 = fitted_all[q1_mask]
        residual_window = fitted_window - y_fit
        residual_q1 = fitted_q1 - environment[q1_mask, column]
        smooth[:, column] = fitted_all
        diagnostics['series'][name] = {
            'initial_value': y0, 'amplitude': amplitude, 'tau_h': tau_h,
            'exponent': exponent,
            'fit_rmse': float(np.sqrt(np.mean(residual_window ** 2))),
            'fit_max_abs_error': float(np.max(np.abs(residual_window))),
            'q1_rmse': float(np.sqrt(np.mean(residual_q1 ** 2))),
            'q1_max_abs_error': float(np.max(np.abs(residual_q1))),
            'value_at_1800_s': float(fitted_all[np.flatnonzero(environment[:, 0] == 1800.0)[0]]),
        }
    return smooth, diagnostics


def make_fitted_boundary(diagnostics):
    """Return the analytical, rather than knot-wise interpolated, fitted boundary."""
    series_for_column = {1: diagnostics['series']['T_infty_C'],
                         2: diagnostics['series']['C_infty_kg_per_kg']}

    def boundary(t_s, column):
        item = series_for_column[column]
        return stretched_exponential(t_s, item['initial_value'], item['amplitude'],
                                     item['tau_h'], item['exponent'])

    return boundary


def solve_field(n, field, environment, rtol=2e-10, atol=2e-12, max_step=5.0,
                h_factor=1.0, hm_factor=1.0, d_factor=1.0, boundary=None):
    """N intervals, N+1 nodes including r=0 and r=R.

    Last state integrates the area-average boundary exchange for a balance check.
    Moisture interfaces use the Kirchhoff flux; all fluxes telescope.
    """
    assert n % 20 == 0
    r = np.linspace(0, R, n + 1)
    dr = R / n
    faces = (r[:-1] + r[1:]) / 2
    edges = np.r_[0.0, faces, R]
    volumes = np.diff(edges**2) / 2  # volume / (2*pi*length)
    area = R**2 / 2
    factor = faces / dr
    initial, beta, column = ((28.0, h_factor * H / (RHO * CP), 1)
                             if field == 'T' else (2.55, hm_factor * HM, 2))
    boundary_jac = csr_matrix(([-R * beta / area], ([0], [n])), shape=(1, n + 1))

    def coefficients(u):
        if field == 'T':
            return np.full_like(u, ALPHA), np.zeros_like(u)
        if np.min(u) <= 0:
            raise ValueError('Nonpositive moisture encountered; no clipping is applied.')
        diffusivity = d_factor * 7e-9 * np.exp(-0.89 / u)
        return diffusivity, diffusivity * 0.89 / u**2

    def rhs(t, state):
        u = state[:-1]
        flux = np.empty(n + 2)
        flux[0] = 0.0
        if field == 'T':
            face = np.full(n, ALPHA)
        else:
            face, _, _ = scalar_face(u[:-1], u[1:], coefficients)
        flux[1:-1] = factor * face * np.diff(u)
        ambient = boundary(t, column) if boundary is not None else np.interp(
            t, environment[:, 0], environment[:, column])
        flux[-1] = R * beta * (ambient - u[-1])
        return np.r_[np.diff(flux) / volumes, flux[-1] / area]

    def jac(t, state):
        u = state[:-1]
        delta = np.diff(u)
        if field == 'T':
            df = np.full(n, ALPHA)
            df_left = df_right = np.zeros(n)
        else:
            df, df_left, df_right = scalar_face(u[:-1], u[1:], coefficients)
        left = factor * (df_left * delta - df)
        right = factor * (df_right * delta + df)
        main = np.r_[left, -R * beta] - np.r_[0.0, right]
        matrix = diags((-left / volumes[1:], main / volumes, right / volumes[:-1]),
                       offsets=(-1, 0, 1), format='csr')
        return bmat([[matrix, None], [boundary_jac, csr_matrix((1, 1))]], format='csc')

    state = np.r_[np.full(n + 1, initial), 0.0]
    sampled = np.empty((1801, 21))
    sampled[0] = initial
    plot_count = min(PLOT_RADIAL_POINTS, n + 1)
    plot_indices = np.linspace(0, n, plot_count).round().astype(int)
    plot_values = np.empty((1801, plot_count))
    plot_values[0] = initial
    averages = np.empty(1801)
    averages[0] = initial
    snapshots = {}
    indices = np.arange(21) * (n // 20)
    max_balance_error, evaluations = 0.0, 0
    breaks = (np.array([0.0, 1800.0]) if boundary is not None else
              np.unique(np.r_[0, environment[(environment[:, 0] > 0) &
                                              (environment[:, 0] < 1800), 0], 1800]))
    for start, stop in zip(breaks[:-1], breaks[1:]):
        evaluation_times = TIMES[(TIMES > start) & (TIMES <= stop)]
        sol = solve_ivp(rhs, (start, stop), state, method='BDF', t_eval=evaluation_times,
                        rtol=rtol, atol=atol, max_step=max_step, jac=jac)
        if not sol.success:
            raise RuntimeError(sol.message)
        evaluations += sol.nfev
        # Attachment knots are integer seconds; no interpolation of the terminal state needed.
        assert evaluation_times[-1] == stop
        state = sol.y[:, -1]
        rows = evaluation_times.astype(int)
        sampled[rows] = sol.y[indices].T
        plot_values[rows] = sol.y[plot_indices].T
        mean = volumes @ sol.y[:-1] / area
        averages[rows] = mean
        max_balance_error = max(max_balance_error,
                                float(np.max(np.abs(mean - initial - sol.y[-1]))))
        for t in REPORT_TIMES[(REPORT_TIMES > start) & (REPORT_TIMES <= stop)]:
            snapshots[int(t)] = sol.y[:-1, np.flatnonzero(rows == t)[0]].copy()
    assert np.isfinite(sampled).all()
    return dict(values=sampled, r=r, plot_r=r[plot_indices], plot_values=plot_values,
                profiles=np.array([snapshots[int(t)] for t in REPORT_TIMES]),
                mean=averages, balance_error=max_balance_error, nfev=evaluations)


def endpoint_metrics(result_t, result_c):
    """Scalar outcomes used consistently in the input/parameter sensitivity table."""
    return {
        'T_center_1800_C': float(result_t['values'][-1, 0]),
        'T_surface_1800_C': float(result_t['values'][-1, -1]),
        'T_mean_1800_C': float(result_t['mean'][-1]),
        'C_center_1800_kg_per_kg': float(result_c['values'][-1, 0]),
        'C_surface_1800_kg_per_kg': float(result_c['values'][-1, -1]),
        'C_mean_1800_kg_per_kg': float(result_c['mean'][-1]),
    }


def metric_difference(candidate, reference):
    return {name: float(candidate[name] - reference[name]) for name in reference}


def run_sensitivity(n, raw_environment, fit_window_s, reference_t=None, reference_c=None):
    """One-at-a-time scenario analysis; it is model-form/parameter sensitivity, not solver error."""
    primary_environment, primary_fit = fit_environment(raw_environment, fit_window_s)
    primary_boundary = make_fitted_boundary(primary_fit)
    if reference_t is None or reference_c is None:
        reference_t = solve_field(n, 'T', primary_environment, boundary=primary_boundary)
        reference_c = solve_field(n, 'C', primary_environment, boundary=primary_boundary)
    reference = endpoint_metrics(reference_t, reference_c)
    scenarios = []

    def add(name, description, result_t, result_c):
        metrics = endpoint_metrics(result_t, result_c)
        scenarios.append({'name': name, 'description': description, 'metrics': metrics,
                          'delta_from_reference': metric_difference(metrics, reference)})

    linear_t = solve_field(n, 'T', raw_environment)
    linear_c = solve_field(n, 'C', raw_environment)
    add('linear_input', '附件1的60 s观测节点，采用分段线性插值。',
        linear_t, linear_c)

    for window_s in (3600.0, 7200.0):
        scenario_environment, scenario_fit = fit_environment(raw_environment, window_s)
        scenario_boundary = make_fitted_boundary(scenario_fit)
        scenario_t = solve_field(n, 'T', scenario_environment, boundary=scenario_boundary)
        scenario_c = solve_field(n, 'C', scenario_environment, boundary=scenario_boundary)
        add(f'fit_window_{int(window_s)}s',
            f'初值固定的拉伸指数模型，使用附件1的0–{int(window_s)} s数据。',
            scenario_t, scenario_c)

    for factor in (0.8, 1.2):
        scenario_t = solve_field(n, 'T', primary_environment, h_factor=factor,
                                 boundary=primary_boundary)
        add(f'h_factor_{factor:.1f}', f'换热系数 h 乘以 {factor:.1f}。',
            scenario_t, reference_c)
    for factor in (0.8, 1.2):
        scenario_c = solve_field(n, 'C', primary_environment, hm_factor=factor,
                                 boundary=primary_boundary)
        add(f'hm_factor_{factor:.1f}', f'有效传质系数 h_m 乘以 {factor:.1f}。',
            reference_t, scenario_c)
    for factor in (0.8, 1.2):
        scenario_c = solve_field(n, 'C', primary_environment, d_factor=factor,
                                 boundary=primary_boundary)
        add(f'D_factor_{factor:.1f}', f'内部水分扩散系数 D(C) 乘以 {factor:.1f}。',
            reference_t, scenario_c)

    return {'reference': {'description': f'0–{int(fit_window_s)} s nonlinear boundary fit',
                          'grid_intervals': int(n), 'metrics': reference,
                          'boundary_fit': primary_fit}, 'scenarios': scenarios}


def make_boundary_figures(raw_environment, boundary_info):
    """Save the two boundary figures used by section 5.1.1.

    The first figure is deliberately raw data only (the complete 0--14400 s
    record).  The second is restricted to the Q1 fitting window and contains
    only the selected stretched-exponential curve.  Keeping these plots
    separate avoids visually mixing model selection with the later field
    solution.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    t_s = np.asarray(raw_environment[:, 0], dtype=float)
    labels = [('烘房温度', '温度 / °C', 1, '#9b1c1f'),
              ('环境水分浓度', '水分浓度 / (kg/kg)', 2, '#2166ac')]

    # Figure 1: no curve is overlaid; it is an honest view of the supplied
    # 60 s observations and the later plateau.
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.5), constrained_layout=True)
    for ax, (title, ylabel, column, color) in zip(axes, labels):
        ax.scatter(t_s, raw_environment[:, column], s=14,
                   color=color, alpha=0.78, linewidths=0, label='附件1观测散点')
        ax.set(title=f'{title}：0–14400 s原始数据', xlabel='时间 / s', ylabel=ylabel,
               xlim=(0.0, float(t_s[-1])))
        ax.grid(alpha=0.22)
        ax.legend(fontsize=8, loc='best')
    fig.savefig(FIGURE_OUT / figure_name('q1', 'boundary_raw'), dpi=220)
    plt.close(fig)

    # Figure 2: selected fit only, using the same 0--1800 s observations
    # used for the Q1 identification.  No competing curves are drawn here.
    if not boundary_info.get('series'):
        return
    fit_mask = t_s <= DEFAULT_FIT_WINDOW_S + 1e-9
    t_fit = t_s[fit_mask]
    grid = np.linspace(0.0, DEFAULT_FIT_WINDOW_S, 500)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.5), constrained_layout=True)
    for ax, (title, ylabel, column, _color), name in zip(
            axes, labels, ('T_infty_C', 'C_infty_kg_per_kg')):
        item = boundary_info['series'][name]
        y_fit = raw_environment[fit_mask, column]
        y_curve = stretched_exponential(grid, item['initial_value'], item['amplitude'],
                                        item['tau_h'], item['exponent'])
        ax.scatter(t_fit, y_fit, s=16, color='#444444', alpha=0.82,
                   linewidths=0, label='0–1800 s观测散点')
        ax.plot(grid, y_curve, color='#c51b8a', lw=2.0,
                label='初值固定的拉伸指数曲线')
        rmse = item['q1_rmse']
        rmse_text = f'RMSE={rmse:.6g}' if column == 1 else f'RMSE={rmse:.3e}'
        ax.set(title=f'{title}：拉伸指数拟合（0–1800 s）', xlabel='时间 / s', ylabel=ylabel,
               xlim=(0.0, DEFAULT_FIT_WINDOW_S))
        ax.text(0.03, 0.95, rmse_text, transform=ax.transAxes, va='top',
                bbox={'facecolor': 'white', 'alpha': 0.8, 'edgecolor': '0.7'})
        ax.grid(alpha=0.22)
        ax.legend(fontsize=8, loc='best')
    fig.savefig(FIGURE_OUT / figure_name('q1', 'boundary_fit'), dpi=220)
    plt.close(fig)


def make_figures(result_t, result_c, env):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, PowerNorm

    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    # The workbook stores 21 radii (0--2 cm at 0.1 cm intervals), while the
    # figure uses the denser samples retained by solve_field.
    time_min = TIMES / 60.0
    temperature_values = result_t.get('plot_values', result_t['values'])
    moisture_values = result_c.get('plot_values', result_c['values'])
    plot_r = result_t.get('plot_r')
    if plot_r is None:
        plot_r = np.linspace(0.0, R, temperature_values.shape[1])
    r_cm = np.asarray(plot_r) * 100.0
    temperature = temperature_values.T
    moisture = moisture_values.T

    temperature_cmap = LinearSegmentedColormap.from_list(
        'temperature_blue_red',
        ['#08306b', '#2171b5', '#f7f7f7', '#cb181d', '#67000d'])
    moisture_cmap = LinearSegmentedColormap.from_list(
        'moisture_gray_blue',
        ['#f0f0f0', '#bdbdbd', '#9ecae1', '#3182bd', '#08519c'])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), constrained_layout=True)
    temp_mesh = axes[0].pcolormesh(
        time_min, r_cm, temperature, shading='nearest', cmap=temperature_cmap,
        vmin=float(np.min(temperature)), vmax=float(np.max(temperature)))
    moisture_mesh = axes[1].pcolormesh(
        time_min, r_cm, moisture, shading='nearest', cmap=moisture_cmap,
        norm=PowerNorm(gamma=1.8, vmin=float(np.min(moisture)),
                       vmax=float(np.max(moisture))))

    axes[0].set(title='温度场', xlabel='时间 / min', ylabel='距中心距离 / cm',
                ylim=(0, R * 100.0))
    axes[1].set(title='水分浓度场', xlabel='时间 / min', ylabel='距中心距离 / cm',
                ylim=(0, R * 100.0))
    for ax in axes:
        ax.set_xlim(float(time_min[0]), float(time_min[-1]))
        ax.set_yticks(np.arange(0, R * 100.0 + 0.01, 0.5))

    temp_bar = fig.colorbar(temp_mesh, ax=axes[0], pad=0.02)
    temp_bar.set_label('温度 / °C')
    moisture_bar = fig.colorbar(moisture_mesh, ax=axes[1], pad=0.02)
    moisture_bar.set_label('水分浓度 / (kg/kg)')
    fig.savefig(FIGURE_OUT / figure_name('q1', 'temperature_moisture_field'), dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grids', type=int, nargs='+', default=[800, 1600, 3200, 6400])
    parser.add_argument('--check-time', action='store_true')
    parser.add_argument('--boundary-mode', choices=('fit', 'linear'), default='fit',
                        help='Use the nonlinear boundary fit (default) or the backed-up linear input.')
    parser.add_argument('--fit-window-s', type=float, default=DEFAULT_FIT_WINDOW_S,
                        help='Attachment-1 fitting window; the solver still stops at 1800 s.')
    parser.add_argument('--sensitivity-grid', type=int, default=800,
                        help='Radial intervals used for one-at-a-time sensitivity scenarios.')
    parser.add_argument('--skip-sensitivity', action='store_true')
    args = parser.parse_args()
    raw_env = read_environment()
    if args.boundary_mode == 'fit':
        env, boundary_info = fit_environment(raw_env, args.fit_window_s)
        boundary_info['mode'] = 'nonlinear_fit'
        boundary_evaluator = make_fitted_boundary(boundary_info)
    else:
        env = raw_env.copy()
        boundary_info = {'mode': 'piecewise_linear', 'fit_window_s': None,
                         'series': {}, 'family': 'Attachment-1 piecewise-linear interpolation'}
        boundary_evaluator = None
    # Section 5.1.1 uses these two plots to separate raw-data inspection,
    # model comparison, and the final selected boundary representation.
    make_boundary_figures(raw_env, boundary_info)
    previous = None
    convergence = []
    results_by_grid = {}
    for n in args.grids:
        start = time.perf_counter()
        rt = solve_field(n, 'T', env, boundary=boundary_evaluator)
        rc = solve_field(n, 'C', env, boundary=boundary_evaluator)
        record = {'intervals': n, 'dr_m': R / n,
                  'balance_T': rt['balance_error'], 'balance_C': rc['balance_error']}
        if previous is not None:
            for name, cur, prev in [('T', rt, previous[0]), ('C', rc, previous[1])]:
                record[f'max_diff_{name}'] = float(np.max(np.abs(cur['values'] - prev['values'])))
                record[f'table_diff_{name}'] = float(np.max(np.abs(
                    cur['values'][REPORT_TIMES][:, ::5] - prev['values'][REPORT_TIMES][:, ::5])))
        convergence.append(record)
        previous = rt, rc
        results_by_grid[n] = (rt, rc)
        print(json.dumps(record), f'elapsed={time.perf_counter() - start:.2f}s', flush=True)

    time_check = {}
    if args.check_time:
        for name, baseline in [('T', rt), ('C', rc)]:
            tight = solve_field(args.grids[-1], name, env, rtol=2e-11, atol=2e-13,
                                max_step=2.0, boundary=boundary_evaluator)
            time_check[name] = float(np.max(np.abs(baseline['values'] - tight['values'])))
        print('Time convergence:', time_check, flush=True)
    assert np.min(rt['values']) >= 28 - 1e-8
    assert np.max(rt['values']) <= np.max(env[env[:, 0] <= 1800, 1]) + 1e-8
    assert np.min(rc['values']) > 0 and np.max(rc['values']) <= 2.55 + 1e-8
    assert np.min(np.diff(rt['values'], axis=1)) > -1e-7
    assert np.max(np.diff(rc['values'], axis=1)) < 1e-7

    sensitivity = None
    if not args.skip_sensitivity and args.boundary_mode == 'fit':
        reference_t, reference_c = results_by_grid.get(args.sensitivity_grid, (None, None))
        sensitivity = run_sensitivity(args.sensitivity_grid, raw_env, args.fit_window_s,
                                      reference_t, reference_c)
    elif not args.skip_sensitivity:
        print('Sensitivity report is skipped for --boundary-mode linear; run the default fit mode.',
              flush=True)

    payload = {'r_cm': np.round(np.linspace(0, 2, 21), 1).tolist(),
               't_s': TIMES[1:].astype(int).tolist(),
               'T': np.round(rt['values'][1:], 4).tolist(),
               'C': np.round(rc['values'][1:], 4).tolist()}
    (OUT / artifact_name('q1', 'result_data')).write_text(
        json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    summary = {'model': '1D radial; Kirchhoff moisture flux; effective Robin moisture boundary; no latent heat',
               'moisture_face_flux': '8-point Gauss-Legendre Kirchhoff average in C',
               'alpha_m2_s': ALPHA, 'D_initial_m2_s': float(7e-9 * np.exp(-0.89 / 2.55)),
               'grid_intervals': args.grids[-1], 'rtol': 2e-10, 'atol': 2e-12,
               'max_step_s': 5, 'boundary': boundary_info,
               'selected_boundary_method': 'stretched_exp',
               'boundary_method_comparison': artifact_name('q1', 'boundary_cv'),
               'fit_endpoint_comparison': artifact_name('q1', 'boundary_endpoint_comparison'),
               'environment_1800': env[env[:, 0] == 1800][0].tolist(),
               'raw_environment_1800': raw_env[raw_env[:, 0] == 1800][0].tolist(),
               'convergence': convergence, 'time_check': time_check,
               'mean_T_1800': float(rt['mean'][-1]), 'mean_C_1800': float(rc['mean'][-1]),
               'table_times': REPORT_TIMES.tolist(), 'table_r_cm': [0, 0.5, 1, 1.5, 2],
               'table_T': rt['values'][REPORT_TIMES][:, ::5].tolist(),
               'table_C': rc['values'][REPORT_TIMES][:, ::5].tolist()}
    if sensitivity is not None:
        summary['sensitivity'] = sensitivity
    (OUT / artifact_name('q1', 'validation')).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez_compressed(
        OUT / artifact_name('q1', 'full_precision'), t=TIMES, r_cm=payload['r_cm'],
        T=rt['values'], C=rc['values'], mean_T=rt['mean'], mean_C=rc['mean'])
    make_figures(rt, rc, env)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
