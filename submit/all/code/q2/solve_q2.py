"""Question 2: coupled radial heat/moisture transport, Appendix 3 throughout.

Run from this directory with ``python solve_q2.py --check-time``.
Input: data/附件1.xlsx. Excel export: export_result2.py.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

import numpy as np
import openpyxl
from scipy.integrate import solve_ivp
from scipy.signal import savgol_filter
from scipy.sparse import diags, bmat, csr_matrix
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent.parent
ROOT = PACKAGE
OUT = PACKAGE / 'results' / 'q2'
DATA = PACKAGE / 'data'
OUT.mkdir(parents=True, exist_ok=True)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from boundary_stage import build_boundaries
R, H, HM = 0.02, 25.0, 8e-7
T0, C0 = 28.0, 2.55
END_TIME = 10800
REPORT_TIMES = np.arange(1800, END_TIME + 1, 1800)
PLOT_RADIAL_POINTS = 201


def read_environment():
    path = DATA / '附件1.xlsx'
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = list(wb.active.values)
    wb.close()
    env = np.array(rows[1:], dtype=float)
    assert env.shape[1] == 3 and np.isfinite(env).all()
    assert env[0, 0] == 0 and np.all(np.diff(env[:, 0]) > 0)
    assert env[-1, 0] >= END_TIME
    return env


def properties(T, C):
    """T is stored in Celsius. Only the Arrhenius factor uses Kelvin.

    Return b=rho*cp, k, D and their partial derivatives.
    Complex input is supported for an independent complex-step Jacobian check.
    """
    kelvin = T + 273.15
    if np.min(np.real(C)) <= 0 or np.min(np.real(kelvin)) <= 0:
        raise ValueError('Nonphysical state; no clipping or silent replacement is applied.')
    rho = 650 + 128 * C
    cp = 1450 + 2736 * C / (C + 1)
    k = 0.21 + 0.38 * C / (C + 1)
    d = 2.4e-3 * np.exp(-0.45 / C - 3850 / kelvin)
    b = rho * cp
    b_c = 128 * cp + rho * 2736 / (C + 1)**2
    k_c = 0.38 / (C + 1)**2
    d_c = d * 0.45 / C**2
    d_t = d * 3850 / kelvin**2
    return b, k, d, b_c, k_c, d_c, d_t


class CoupledModel:
    def __init__(self, n, env, tail='hold_last', boundary=None):
        assert n % 20 == 0
        self.n, self.m, self.env, self.tail = n, n + 1, env, tail
        self.boundary = boundary
        self.r = np.linspace(0, R, n + 1)
        self.dr = R / n
        self.faces = (self.r[:-1] + self.r[1:]) / 2
        self.w = np.diff(np.r_[0.0, self.faces, R]**2) / 2
        self.area = R**2 / 2
        self.factor = self.faces / self.dr
        self.balance_c = csr_matrix(([-R * HM / self.area], ([0], [n])), shape=(1, self.m))
        self.zero_row = csr_matrix((1, self.m))

    def ambient(self, t):
        if self.boundary is not None:
            return float(self.boundary[0](t)), float(self.boundary[1](t))
        if t > self.env[-1, 0] and self.tail != 'hold_last':
            raise ValueError('Environment data exhausted. Explicitly select a tail assumption.')
        # np.interp holds the final observation outside the provided time range.
        # This is explicit via tail='hold_last' and is unused during Q2's first 3 h.
        return np.interp(t, self.env[:, 0], self.env[:, 1]), np.interp(t, self.env[:, 0], self.env[:, 2])

    def rhs(self, t, state):
        m = self.m
        T, C = state[:m], state[m:2*m]
        b, k, d, *_ = properties(T, C)
        ta, ca = self.ambient(t)
        ft = np.empty(m + 1, dtype=state.dtype)
        fc = np.empty_like(ft)
        ft[0] = fc[0] = 0
        ft[1:-1] = self.factor * (k[:-1] + k[1:]) / 2 * np.diff(T)
        fc[1:-1] = self.factor * (d[:-1] + d[1:]) / 2 * np.diff(C)
        ft[-1] = R * H * (ta - T[-1])
        fc[-1] = R * HM * (ca - C[-1])
        return np.r_[np.diff(ft) / (self.w * b), np.diff(fc) / self.w, fc[-1] / self.area]

    def flux_jacobian(self, left, right, boundary, denominator):
        diagonal = np.r_[left, boundary] - np.r_[0.0, right]
        return diags((-left / denominator[1:], diagonal / denominator,
                      right / denominator[:-1]), (-1, 0, 1), format='csr')

    def jac(self, t, state):
        m = self.m
        T, C = state[:m], state[m:2*m]
        b, k, d, bc, kc, dc, dt = properties(T, C)
        delta_t, delta_c = np.diff(T), np.diff(C)
        kface, dface = (k[:-1] + k[1:]) / 2, (d[:-1] + d[1:]) / 2
        factor = self.factor
        jtt = self.flux_jacobian(-factor*kface, factor*kface, -R*H, self.w*b)
        jtc = self.flux_jacobian(factor*0.5*kc[:-1]*delta_t,
                                factor*0.5*kc[1:]*delta_t, 0.0, self.w*b)
        jtc -= diags(self.rhs(t, state)[:m] * bc / b, format='csr')
        jcc = self.flux_jacobian(factor*(0.5*dc[:-1]*delta_c-dface),
                                factor*(0.5*dc[1:]*delta_c+dface), -R*HM, self.w)
        jct = self.flux_jacobian(factor*0.5*dt[:-1]*delta_c,
                                factor*0.5*dt[1:]*delta_c, 0.0, self.w)
        return bmat([[jtt, jtc, None], [jct, jcc, None],
                     [self.zero_row, self.balance_c, csr_matrix((1, 1))]], format='csc')


def check_jacobian(env):
    model = CoupledModel(40, env)
    fraction = model.r / R
    state = np.r_[28 + 7*fraction**2, 2.55 - 0.8*fraction**2, 0.0]
    analytic = model.jac(1200, state)
    rng = np.random.default_rng(2026)
    errors = []
    for _ in range(3):
        direction = rng.normal(size=len(state))
        expected = np.imag(model.rhs(1200, state.astype(complex) + 1e-25j*direction)) / 1e-25
        actual = analytic @ direction
        errors.append(float(np.max(np.abs(actual-expected)) / max(np.max(np.abs(expected)), 1e-30)))
    assert max(errors) < 1e-11, errors
    return max(errors)


def solve_model(n, env, rtol=2e-10, atol=2e-12, max_step=5.0, end_time=END_TIME,
                boundary=None):
    model = CoupledModel(n, env, boundary=boundary)
    m, w, area = model.m, model.w, model.area
    times = np.arange(end_time + 1, dtype=float)
    indices = np.arange(21) * (n // 20)
    plot_count = min(PLOT_RADIAL_POINTS, m)
    plot_indices = np.linspace(0, n, plot_count).round().astype(int)
    state = np.r_[np.full(m, T0), np.full(m, C0), 0.0]
    temperatures = np.empty((len(times), 21))
    moistures = np.empty_like(temperatures)
    temperatures[0], moistures[0] = T0, C0
    plot_temperatures = np.empty((len(times), plot_count))
    plot_moistures = np.empty_like(plot_temperatures)
    plot_temperatures[0], plot_moistures[0] = T0, C0
    mean_t, mean_c = np.empty(len(times)), np.empty(len(times))
    mean_t[0], mean_c[0] = T0, C0
    profile_t, profile_c = {}, {}
    balance_error, heat_rate_error = 0.0, 0.0
    nfev, nlu = 0, 0
    breaks = np.unique(np.r_[0, env[(env[:, 0] > 0) & (env[:, 0] < end_time), 0], end_time])
    for start, stop in zip(breaks[:-1], breaks[1:]):
        evaluation_times = times[(times > start) & (times <= stop)]
        assert evaluation_times[-1] == stop, 'Environment knots must be integer seconds.'
        sol = solve_ivp(model.rhs, (start, stop), state, method='BDF', jac=model.jac,
                        t_eval=evaluation_times, rtol=rtol, atol=atol, max_step=max_step,
                        first_step=min(0.001, stop-start))
        if not sol.success:
            raise RuntimeError(sol.message)
        state = sol.y[:, -1]
        nfev += sol.nfev
        nlu += sol.nlu
        rows = evaluation_times.astype(int)
        temperatures[rows] = sol.y[indices].T
        moistures[rows] = sol.y[m+indices].T
        plot_temperatures[rows] = sol.y[plot_indices].T
        plot_moistures[rows] = sol.y[m+plot_indices].T
        avg_t = np.sum(w[:, None] * sol.y[:m], axis=0) / area
        avg_c = np.sum(w[:, None] * sol.y[m:2*m], axis=0) / area
        mean_t[rows], mean_c[rows] = avg_t, avg_c
        balance_error = max(balance_error, float(np.max(np.abs(avg_c-C0-sol.y[-1]))))
        derivative = model.rhs(stop, state)
        capacity = properties(state[:m], state[m:2*m])[0]
        input_rate = R*H*(model.ambient(stop)[0]-state[m-1])
        heat_rate_error = max(heat_rate_error, float(abs(np.sum(w*capacity*derivative[:m])-input_rate)))
        for report_t in REPORT_TIMES[(REPORT_TIMES > start) & (REPORT_TIMES <= stop)]:
            j = np.flatnonzero(rows == report_t)[0]
            profile_t[int(report_t)] = sol.y[:m, j].copy()
            profile_c[int(report_t)] = sol.y[m:2*m, j].copy()
        if stop % 3600 == 0:
            print(f'N={n}, t={stop/3600:g} h, T_center={state[0]:.6f}, '
                  f'C_surface={state[2*m-1]:.6f}', flush=True)
    assert np.isfinite(temperatures).all() and np.isfinite(moistures).all()
    return dict(T=temperatures, C=moistures, t=times, r=model.r,
                plot_T=plot_temperatures, plot_C=plot_moistures,
                plot_r=model.r[plot_indices],
                mean_T=mean_t, mean_C=mean_c,
                profiles_T=np.array([profile_t[int(t)] for t in REPORT_TIMES if t <= end_time]),
                profiles_C=np.array([profile_c[int(t)] for t in REPORT_TIMES if t <= end_time]),
                moisture_balance_error=balance_error, heat_rate_balance_error=heat_rate_error,
                nfev=nfev, nlu=nlu)


def make_figures(result, env):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, PowerNorm
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    time_h = result['t'] / 3600.0
    r_cm = result.get('plot_r', result['r']) * 100.0
    temperature = result.get('plot_T', result['T']).T
    moisture = result.get('plot_C', result['C']).T
    temperature_cmap = LinearSegmentedColormap.from_list(
        'temperature_blue_red', ['#08306b', '#2171b5', '#f7f7f7', '#cb181d', '#67000d'])
    moisture_cmap = LinearSegmentedColormap.from_list(
        'moisture_gray_blue', ['#f0f0f0', '#bdbdbd', '#9ecae1', '#3182bd', '#08519c'])
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), constrained_layout=True)
    temp_mesh = axes[0].pcolormesh(
        time_h, r_cm, temperature, shading='nearest', cmap=temperature_cmap,
        vmin=float(np.min(temperature)), vmax=float(np.max(temperature)))
    moisture_mesh = axes[1].pcolormesh(
        time_h, r_cm, moisture, shading='nearest', cmap=moisture_cmap,
        norm=PowerNorm(gamma=1.8, vmin=float(np.min(moisture)),
                       vmax=float(np.max(moisture))))
    axes[0].set(title='温度场', xlabel='时间 / h', ylabel='距中心距离 / cm', ylim=(0, R * 100.0))
    axes[1].set(title='水分浓度场', xlabel='时间 / h', ylabel='距中心距离 / cm', ylim=(0, R * 100.0))
    for ax in axes:
        ax.set_xlim(float(time_h[0]), float(time_h[-1]))
        ax.set_yticks(np.arange(0, R * 100.0 + 0.01, 0.5))
    temp_bar = fig.colorbar(temp_mesh, ax=axes[0], pad=0.02)
    temp_bar.set_label('温度 / °C')
    moisture_bar = fig.colorbar(moisture_mesh, ax=axes[1], pad=0.02)
    moisture_bar.set_label('水分浓度 / (kg/kg)')
    fig.savefig(OUT/'第二问结果图.png', dpi=180)
    plt.close(fig)


def make_boundary_stage_figure(raw_env, boundary_info):
    """Show how the two stable points are detected from smoothed data."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    specs = [
        (1, boundary_info['phase_temperature'], '烘房温度 / °C', '#9b1c1f'),
        (2, boundary_info['phase_moisture'], '环境水分浓度 / (kg/kg)', '#2166ac'),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    for ax, (column, phase, ylabel, color) in zip(axes, specs):
        y = raw_env[:, column]
        smooth_window = int(phase['smoothing_window_points'])
        smoothed = savgol_filter(y, smooth_window, 2, mode='interp')
        ax.scatter(raw_env[:, 0], y, s=10, color=color, alpha=0.45,
                   linewidths=0, label='原始观测散点')
        ax.plot(raw_env[:, 0], smoothed, color='#444444', lw=1.5,
                label=f'{smooth_window}点 Savitzky–Golay 平滑')
        for index, window in enumerate(phase['windows']):
            ax.axvspan(window['start_s'], window['start_s'] + phase['window_s'],
                       color='#f0a202', alpha=0.10 if index else 0.24,
                       label='连续稳定窗口' if index == 0 else None)
        ax.axvline(phase['phase_s'], color='#d62728', ls='--', lw=1.3,
                    label=f"判定分界点 {phase['phase_s']:.0f} s")
        ax.text(0.015, 0.08,
                f"极差阈值={phase['range_tol']:.3g}\n斜率阈值={phase['slope_tol']:.3g}",
                transform=ax.transAxes, va='bottom',
                bbox={'facecolor': 'white', 'alpha': 0.82, 'edgecolor': '0.7'})
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8, ncol=3, loc='best')
    axes[1].set_xlabel('时间 / s')
    fig.suptitle('独立稳定分界点的探索：平滑、窗口极差与斜率判据（相差1500 s）')
    fig.savefig(OUT/'边界独立分界图.png', dpi=180)
    plt.close(fig)


def make_staged_boundary_figure(raw_env, boundary_t, boundary_c, boundary_info):
    """Plot raw observations together with the final piecewise boundaries."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    grid = np.linspace(raw_env[0, 0], raw_env[-1, 0], 1600)
    specs = [
        (1, boundary_t, boundary_info['transition_temperature'],
         boundary_info['plateau_temperature'], '烘房温度 / °C', '#9b1c1f'),
        (2, boundary_c, boundary_info['transition_moisture'],
         boundary_info['plateau_moisture'], '环境水分浓度 / (kg/kg)', '#2166ac'),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, constrained_layout=True)
    for ax, (column, boundary, transition, plateau, ylabel, color) in zip(axes, specs):
        left, right = transition['left_s'], transition['right_s']
        pre = grid <= left
        blend = (grid >= left) & (grid <= right)
        post = grid >= right
        ax.scatter(raw_env[:, 0], raw_env[:, column], s=10, color=color, alpha=0.42,
                   linewidths=0, label='附件1原始散点')
        ax.plot(grid[pre], boundary(grid[pre]), color='#1f77b4', lw=2.0,
                label='过渡点1以前：拉伸指数拟合')
        ax.plot(grid[blend], boundary(grid[blend]), color='#f28e2b', lw=2.4,
                label='过渡区：线性平滑连接')
        ax.plot(grid[post], boundary(grid[post]), color='#2a9d8f', lw=2.0,
                label='过渡点2以后：稳定尾段均值')
        ax.axvspan(left, right, color='#f0a202', alpha=0.12, label='1800 s平滑过渡区')
        ax.axvline(left, color='#666666', ls=':', lw=1.0)
        ax.axvline(right, color='#666666', ls=':', lw=1.0)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8, ncol=2, loc='best')
    axes[1].set_xlabel('时间 / s')
    fig.suptitle('原始散点与最终分段环境边界（全观测区间）')
    fig.savefig(OUT/'分段边界整体拟合图.png', dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grids', type=int, nargs='+', default=[800, 1600, 3200, 6400])
    parser.add_argument('--check-time', action='store_true')
    parser.add_argument('--boundary-mode', choices=('staged', 'raw'), default='staged',
                        help='Use the detected smooth constant-stage boundary (default) or raw 60 s knots.')
    parser.add_argument('--fit-endpoint-s', type=float, default=None,
                        help='Optional common fit endpoint; when omitted, fit temperature/moisture to their own transition points.')
    args = parser.parse_args()
    raw_env = read_environment()
    boundary_t, boundary_c, env, boundary_info = build_boundaries(
        raw_env, mode=args.boundary_mode, fit_endpoint_s=args.fit_endpoint_s)
    boundary = None if args.boundary_mode == 'raw' else (boundary_t, boundary_c)
    jac_error = check_jacobian(env)
    print('Jacobian complex-step relative error:', jac_error, flush=True)
    convergence, previous = [], None
    for n in args.grids:
        start = time.perf_counter()
        result = solve_model(n, env, boundary=boundary)
        record = {'intervals': n, 'dr_m': R/n,
                  'moisture_balance_error': result['moisture_balance_error'],
                  'heat_rate_balance_error': result['heat_rate_balance_error']}
        if previous is not None:
            for key in ['T', 'C']:
                delta = np.abs(result[key]-previous[key])
                record[f'max_diff_{key}'] = float(np.max(delta))
                record[f'table_diff_{key}'] = float(np.max(delta[REPORT_TIMES][:, ::5]))
                index = np.unravel_index(np.argmax(delta), delta.shape)
                record[f'max_diff_location_{key}'] = {'time_s': int(index[0]), 'r_cm': float(index[1]/10)}
        record['elapsed_s'] = time.perf_counter()-start
        convergence.append(record)
        previous = result
        print(json.dumps(record), flush=True)
    time_check = {}
    if args.check_time:
        tight = solve_model(args.grids[-1], env, rtol=2e-11, atol=2e-13, max_step=2.0,
                            boundary=boundary)
        time_check = {key: float(np.max(np.abs(result[key]-tight[key]))) for key in ['T', 'C']}
        print('Time convergence:', time_check, flush=True)
    assert np.min(result['T']) >= T0-1e-8
    assert np.max(result['T']) <= np.max(env[env[:, 0] <= END_TIME, 1])+1e-8
    assert np.min(result['C']) > 0 and np.max(result['C']) <= C0+1e-8
    assert np.max(np.diff(result['C'], axis=1)) < 1e-7
    # Temperature can locally reverse gradient under measured chamber fluctuations.
    payload = {'r_cm': np.round(np.linspace(0, 2, 21), 1).tolist(),
               't_s': result['t'][1:].astype(int).tolist(),
               'T': np.round(result['T'][1:], 4).tolist(),
               'C': np.round(result['C'][1:], 4).tolist()}
    (OUT/'result2_data.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    np.savez_compressed(
        OUT/'result2_full_precision.npz', t=result['t'], r_cm=payload['r_cm'],
        T=result['T'], C=result['C'], mean_T=result['mean_T'], mean_C=result['mean_C'])
    initial_props = properties(np.array([T0]), np.array([C0]))
    final_props = properties(result['T'][-1], result['C'][-1])
    summary = {'model': 'Appendix 3 throughout; 1D radial; effective moisture Robin boundary; no latent heat',
               'input_sha256': hashlib.sha256((DATA/'附件1.xlsx').read_bytes()).hexdigest(),
               'duration_s': END_TIME, 'grid_intervals': args.grids[-1],
               'rtol': 2e-10, 'atol': 2e-12, 'max_step_s': 5,
               'interpolation': ('detected independent stage boundaries: stretched exponential before '
                                 'the temperature/moisture-specific split, 1800 s blends, then separate '
                                 'measured tail means'
                                 if args.boundary_mode == 'staged' else
                                 'piecewise linear at original 60 s knots'),
               'boundary_mode': args.boundary_mode,
               'boundary_metadata': boundary_info,
               'raw_environment_sha256': hashlib.sha256((DATA/'附件1.xlsx').read_bytes()).hexdigest(),
               'tail_assumption': ('hold the detected tail mean after the 1800 s transition; '
                                   'the phase point and tail mean are recorded in boundary_metadata'
                                   if args.boundary_mode == 'staged' else
                                   'hold final observation after 14400 s'),
               'H_W_m2_K': H, 'HM_m_s': HM, 'jacobian_relative_error': jac_error,
               'convergence': convergence, 'time_check': time_check,
               'initial_properties': {key: float(value[0]) for key, value in zip(['rho_cp', 'k', 'D'], initial_props[:3])},
               'final_D_center_surface': [float(final_props[2][0]), float(final_props[2][-1])],
               'environment_10800': env[env[:, 0] == END_TIME][0].tolist(),
               'mean_T_10800': float(result['mean_T'][-1]), 'mean_C_10800': float(result['mean_C'][-1]),
               'table_times_h': (REPORT_TIMES/3600).tolist(), 'table_r_cm': [0, 0.5, 1, 1.5, 2],
               'table_T': result['T'][REPORT_TIMES][:, ::5].tolist(),
               'table_C': result['C'][REPORT_TIMES][:, ::5].tolist()}
    (OUT/'validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = []
    for title, key in [('表3：温度 / °C', 'T'), ('表4：干基含水率 / (kg/kg)', 'C')]:
        lines += [f'### {title}', '', '| 时间 / h | 0 cm | 0.5 cm | 1 cm | 1.5 cm | 2 cm |',
                  '|---:|---:|---:|---:|---:|---:|']
        for t, row in zip(REPORT_TIMES/3600, summary[f'table_{key}']):
            lines.append('| '+f'{t:.1f}'+' | '+' | '.join(f'{v:.4f}' for v in row)+' |')
        lines += ['']
    (OUT/'结果表.md').write_text('\n'.join(lines), encoding='utf-8')
    make_figures(result, env)
    if args.boundary_mode == 'staged':
        make_boundary_stage_figure(raw_env, boundary_info)
        make_staged_boundary_figure(raw_env, boundary_t, boundary_c, boundary_info)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    # Sparse banded systems do not benefit from an oversubscribed dense BLAS pool.
    with threadpool_limits(limits=1):
        main()
