"""Question 1: conservative radial finite volumes + implicit BDF integration.

Run from any directory: python 第一问/solve_q1.py
Dependencies: numpy, scipy, openpyxl (read-only), matplotlib.
The separate build_workbook.mjs exports the prescribed Excel template.
"""
from pathlib import Path
import argparse
import json
import time

import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse import diags, bmat, csr_matrix
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
R, RHO, CP, K, H, HM = 0.02, 820.0, 2600.0, 0.36, 25.0, 8e-7
ALPHA = K / (RHO * CP)
TIMES = np.arange(1801, dtype=float)
REPORT_TIMES = np.array([100, 300, 600, 900, 1200, 1500, 1800])


def read_environment():
    wb = openpyxl.load_workbook(ROOT / '附件/附件1.xlsx', data_only=True, read_only=True)
    records = list(wb.active.values)
    wb.close()
    data = np.array(records[1:], dtype=float)
    assert data.shape[1] == 3 and np.isfinite(data).all()
    assert np.all(np.diff(data[:, 0]) > 0)
    assert data[0, 0] == 0 and data[-1, 0] >= 1800
    return data


def solve_field(n, field, environment, rtol=2e-10, atol=2e-12, max_step=5.0):
    """N intervals, N+1 nodes including r=0 and r=R.

    Last state integrates the area-average boundary exchange for a balance check.
    Interface diffusion coefficients use arithmetic averaging; all fluxes telescope.
    """
    assert n % 20 == 0
    r = np.linspace(0, R, n + 1)
    dr = R / n
    faces = (r[:-1] + r[1:]) / 2
    edges = np.r_[0.0, faces, R]
    volumes = np.diff(edges**2) / 2  # volume / (2*pi*length)
    area = R**2 / 2
    factor = faces / dr
    initial, beta, column = (28.0, H / (RHO * CP), 1) if field == 'T' else (2.55, HM, 2)
    boundary_jac = csr_matrix(([-R * beta / area], ([0], [n])), shape=(1, n + 1))

    def coefficients(u):
        if field == 'T':
            return np.full_like(u, ALPHA), np.zeros_like(u)
        if np.min(u) <= 0:
            raise ValueError('Nonpositive moisture encountered; no clipping is applied.')
        diffusivity = 7e-9 * np.exp(-0.89 / u)
        return diffusivity, diffusivity * 0.89 / u**2

    def rhs(t, state):
        u = state[:-1]
        d, _ = coefficients(u)
        flux = np.empty(n + 2)
        flux[0] = 0.0
        flux[1:-1] = factor * (d[:-1] + d[1:]) / 2 * np.diff(u)
        ambient = np.interp(t, environment[:, 0], environment[:, column])
        flux[-1] = R * beta * (ambient - u[-1])
        return np.r_[np.diff(flux) / volumes, flux[-1] / area]

    def jac(t, state):
        u = state[:-1]
        d, dp = coefficients(u)
        df = (d[:-1] + d[1:]) / 2
        delta = np.diff(u)
        left = factor * (0.5 * dp[:-1] * delta - df)
        right = factor * (0.5 * dp[1:] * delta + df)
        main = np.r_[left, -R * beta] - np.r_[0.0, right]
        matrix = diags((-left / volumes[1:], main / volumes, right / volumes[:-1]),
                       offsets=(-1, 0, 1), format='csr')
        return bmat([[matrix, None], [boundary_jac, csr_matrix((1, 1))]], format='csc')

    state = np.r_[np.full(n + 1, initial), 0.0]
    sampled = np.empty((1801, 21))
    sampled[0] = initial
    averages = np.empty(1801)
    averages[0] = initial
    snapshots = {}
    indices = np.arange(21) * (n // 20)
    max_balance_error, evaluations = 0.0, 0
    breaks = np.unique(np.r_[0, environment[(environment[:, 0] > 0) &
                                           (environment[:, 0] < 1800), 0], 1800])
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
        mean = volumes @ sol.y[:-1] / area
        averages[rows] = mean
        max_balance_error = max(max_balance_error,
                                float(np.max(np.abs(mean - initial - sol.y[-1]))))
        for t in REPORT_TIMES[(REPORT_TIMES > start) & (REPORT_TIMES <= stop)]:
            snapshots[int(t)] = sol.y[:-1, np.flatnonzero(rows == t)[0]].copy()
    assert np.isfinite(sampled).all()
    return dict(values=sampled, r=r, profiles=np.array([snapshots[int(t)] for t in REPORT_TIMES]),
                mean=averages, balance_error=max_balance_error, nfev=evaluations)


def make_figures(result_t, result_c, env):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    colors = plt.cm.viridis(np.linspace(0.05, 0.9, 5))
    for idx, color in zip([0, 5, 10, 15, 20], colors):
        axes[0, 0].plot(TIMES / 60, result_t['values'][:, idx], color=color, label=f'{idx / 10:g} cm')
        axes[0, 1].plot(TIMES / 60, result_c['values'][:, idx], color=color, label=f'{idx / 10:g} cm')
    axes[0, 0].plot(TIMES / 60, np.interp(TIMES, env[:, 0], env[:, 1]),
                    color='black', ls='--', lw=1.2, label='烘房温度')
    for row, t in enumerate(REPORT_TIMES):
        axes[1, 0].plot(result_t['r'] * 100, result_t['profiles'][row], label=f'{t} s')
        axes[1, 1].plot(result_c['r'] * 100, result_c['profiles'][row], label=f'{t} s')
    specs = [('温度随时间变化', '时间 / min', '温度 / °C'),
             ('含水率随时间变化', '时间 / min', '干基含水率 / (kg/kg)'),
             ('不同时间的径向温度分布', '距中心距离 / cm', '温度 / °C'),
             ('不同时间的径向含水率分布', '距中心距离 / cm', '干基含水率 / (kg/kg)')]
    for ax, (title, xlabel, ylabel) in zip(axes.flat, specs):
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8, ncol=2)
    fig.savefig(OUT / '第一问结果图.png', dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grids', type=int, nargs='+', default=[800, 1600, 3200, 6400])
    parser.add_argument('--check-time', action='store_true')
    args = parser.parse_args()
    env = read_environment()
    previous = None
    convergence = []
    for n in args.grids:
        start = time.perf_counter()
        rt = solve_field(n, 'T', env)
        rc = solve_field(n, 'C', env)
        record = {'intervals': n, 'dr_m': R / n,
                  'balance_T': rt['balance_error'], 'balance_C': rc['balance_error']}
        if previous is not None:
            for name, cur, prev in [('T', rt, previous[0]), ('C', rc, previous[1])]:
                record[f'max_diff_{name}'] = float(np.max(np.abs(cur['values'] - prev['values'])))
                record[f'table_diff_{name}'] = float(np.max(np.abs(
                    cur['values'][REPORT_TIMES][:, ::5] - prev['values'][REPORT_TIMES][:, ::5])))
        convergence.append(record)
        previous = rt, rc
        print(json.dumps(record), f'elapsed={time.perf_counter() - start:.2f}s', flush=True)

    time_check = {}
    if args.check_time:
        for name, baseline in [('T', rt), ('C', rc)]:
            tight = solve_field(args.grids[-1], name, env, rtol=2e-11, atol=2e-13, max_step=2.0)
            time_check[name] = float(np.max(np.abs(baseline['values'] - tight['values'])))
        print('Time convergence:', time_check, flush=True)
    assert np.min(rt['values']) >= 28 - 1e-8
    assert np.max(rt['values']) <= np.max(env[env[:, 0] <= 1800, 1]) + 1e-8
    assert np.min(rc['values']) > 0 and np.max(rc['values']) <= 2.55 + 1e-8
    assert np.min(np.diff(rt['values'], axis=1)) > -1e-7
    assert np.max(np.diff(rc['values'], axis=1)) < 1e-7

    payload = {'r_cm': np.round(np.linspace(0, 2, 21), 1).tolist(),
               't_s': TIMES[1:].astype(int).tolist(),
               'T': np.round(rt['values'][1:], 4).tolist(),
               'C': np.round(rc['values'][1:], 4).tolist()}
    (OUT / 'result1_data.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    summary = {'model': '1D radial; effective Robin moisture boundary; no latent heat',
               'alpha_m2_s': ALPHA, 'D_initial_m2_s': float(7e-9 * np.exp(-0.89 / 2.55)),
               'grid_intervals': args.grids[-1], 'rtol': 2e-10, 'atol': 2e-12,
               'max_step_s': 5, 'environment_1800': env[env[:, 0] == 1800][0].tolist(),
               'convergence': convergence, 'time_check': time_check,
               'mean_T_1800': float(rt['mean'][-1]), 'mean_C_1800': float(rc['mean'][-1]),
               'table_times': REPORT_TIMES.tolist(), 'table_r_cm': [0, 0.5, 1, 1.5, 2],
               'table_T': rt['values'][REPORT_TIMES][:, ::5].tolist(),
               'table_C': rc['values'][REPORT_TIMES][:, ::5].tolist()}
    (OUT / 'validation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez_compressed(OUT / 'result1_full_precision.npz', t=TIMES, r_cm=payload['r_cm'],
                        T=rt['values'], C=rc['values'], mean_T=rt['mean'], mean_C=rc['mean'])
    lines = []
    for title, field in [('表1：温度 / °C', 'T'), ('表2：干基含水率 / (kg/kg)', 'C')]:
        lines += [f'### {title}', '', '| 时间 / s | 0 cm | 0.5 cm | 1 cm | 1.5 cm | 2 cm |',
                  '|---:|---:|---:|---:|---:|---:|']
        for t, row in zip(REPORT_TIMES, summary[f'table_{field}']):
            lines.append('| ' + str(t) + ' | ' + ' | '.join(f'{v:.4f}' for v in row) + ' |')
        lines += ['']
    (OUT / '结果表.md').write_text('\n'.join(lines), encoding='utf-8')
    make_figures(rt, rc, env)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
