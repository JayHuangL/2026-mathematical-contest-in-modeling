"""Shared boundary fitting and stage-detection utilities for A-question solvers.

The module deliberately keeps the physical model out of the data-processing
layer.  It supplies either the original piecewise-linear input or a smooth
initial-value-fixed stretched-exponential input followed by a data-detected
constant-stage blend.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import savgol_filter


def _robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    return float(1.4826 * mad)


def _stretched_value(t, y0, amplitude, tau_s, exponent):
    q = np.maximum(np.asarray(t, dtype=float), 0.0) / tau_s
    return y0 + amplitude * (1.0 - np.exp(-(q ** exponent)))


def fit_stretched(t: np.ndarray, y: np.ndarray, endpoint_s: float | None = None):
    """Fit y0+A(1-exp(-(t/tau)^p)); y0 is fixed to the first record."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if endpoint_s is None:
        endpoint_s = float(t[-1])
    mask = t <= float(endpoint_s) + 1e-9
    if np.count_nonzero(mask) < 4:
        raise ValueError("At least four records are required for the boundary fit.")
    tf, yf = t[mask], y[mask]
    y0 = float(yf[0])
    scale = max(float(yf[-1] - y0), np.finfo(float).eps)

    def residual(x):
        return _stretched_value(tf, y0, *x) - yf

    result = least_squares(
        residual,
        x0=[scale, max(float(tf[-1]) / 2.0, 60.0), 1.1],
        bounds=([1e-12, 1e-3, 0.1], [max(10.0 * max(scale, 1e-12), 1.0), 1e7, 5.0]),
        max_nfev=100000,
        xtol=1e-13,
        ftol=1e-13,
        gtol=1e-13,
    )
    if not result.success:
        raise RuntimeError(result.message)
    amplitude, tau_s, exponent = map(float, result.x)
    curve = lambda q: _stretched_value(q, y0, amplitude, tau_s, exponent)
    fit = curve(tf)
    return curve, {
        "method": "stretched_exp",
        "endpoint_s": float(endpoint_s),
        "initial_value": y0,
        "amplitude": amplitude,
        "tau_s": tau_s,
        "exponent": exponent,
        "rmse": float(np.sqrt(np.mean((fit - yf) ** 2))),
        "max_abs": float(np.max(np.abs(fit - yf))),
    }


def detect_stable_phase(t: np.ndarray, y: np.ndarray, window_s: float = 1800.0,
                       persist_windows: int = 3) -> dict:
    """Return first persistent low-slope/low-range window after 1800 s."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    dt = float(np.median(np.diff(t)))
    points = max(3, int(round(window_s / dt)))
    if points % 2 == 0:
        points += 1
    smooth_window = min(max(points // 6 * 2 + 1, 7), len(y) - (1 - len(y) % 2))
    if smooth_window % 2 == 0:
        smooth_window -= 1
    smoothed = savgol_filter(y, smooth_window, 2, mode="interp")
    tail = t >= 0.75 * t[-1]
    sigma = _robust_sigma(y[tail] - smoothed[tail])
    resolution = float(np.median(np.abs(np.diff(y))))
    range_tol = max(2.0 * sigma, 4.0 * resolution)
    slope_tol = range_tol / window_s

    def stats(start_index):
        stop = min(start_index + points, len(y))
        tx, sy = t[start_index:stop], smoothed[start_index:stop]
        slope = float(np.polyfit(tx, sy, 1)[0])
        return float(np.ptp(sy)), slope

    phase_index = None
    for i in np.where(t >= 1800.0 - 1e-9)[0]:
        windows = []
        valid = True
        for j in range(persist_windows):
            k = i + j * points
            if k + points > len(y):
                valid = False
                break
            value_range, slope = stats(k)
            windows.append({"start_s": float(t[k]), "range": value_range, "slope": slope})
            valid &= value_range <= range_tol and abs(slope) <= slope_tol
        if valid:
            phase_index = int(i)
            break
    if phase_index is None:
        raise RuntimeError("No persistent stable phase was found in the attachment.")
    phase_s = float(t[phase_index])
    tail_values = y[t >= phase_s]
    return {
        "phase_s": phase_s,
        "window_s": float(window_s),
        "persist_windows": int(persist_windows),
        "range_tol": float(range_tol),
        "slope_tol": float(slope_tol),
        "plateau_mean": float(np.mean(tail_values)),
        "plateau_std": float(np.std(tail_values, ddof=1)),
        "smoothing_window_points": int(smooth_window),
        "sigma_residual": float(sigma),
        "resolution_scale": resolution,
        "windows": windows,
    }


def build_boundaries(environment: np.ndarray, mode: str = "staged",
                     fit_endpoint_s: float | None = None,
                     transition_s: float = 600.0):
    """Build temperature/moisture callables and a knot table for the solvers.

    ``mode='raw'`` reproduces the original piecewise-linear input.  The
    default ``staged`` mode selects the stretched-exponential family, detects
    temperature and moisture stable times independently, and gives each
    boundary its own transition interval and measured tail mean.  The two
    stages are therefore not replaced by their arithmetic mean.
    """
    env = np.asarray(environment, dtype=float)
    t = env[:, 0]
    if mode == "raw":
        bt = lambda q: np.interp(q, t, env[:, 1])
        bc = lambda q: np.interp(q, t, env[:, 2])
        return bt, bc, env.copy(), {"mode": "raw_piecewise_linear"}
    if mode != "staged":
        raise ValueError("mode must be 'raw' or 'staged'")
    phase_t = detect_stable_phase(t, env[:, 1])
    phase_c = detect_stable_phase(t, env[:, 2])
    center_t, center_c = phase_t["phase_s"], phase_c["phase_s"]
    left_t, right_t = center_t - transition_s / 2.0, center_t + transition_s / 2.0
    left_c, right_c = center_c - transition_s / 2.0, center_c + transition_s / 2.0
    if fit_endpoint_s is None:
        endpoint_t, endpoint_c = left_t, left_c
        fit_endpoint_policy = "before_each_transition"
    else:
        endpoint_t = endpoint_c = float(fit_endpoint_s)
        fit_endpoint_policy = "explicit_common_endpoint"
    curve_t, fit_t = fit_stretched(t, env[:, 1], endpoint_t)
    curve_c, fit_c = fit_stretched(t, env[:, 2], endpoint_c)
    plateau_t = float(np.mean(env[t >= center_t, 1]))
    plateau_c = float(np.mean(env[t >= center_c, 2]))

    def stage(curve, plateau, left, right, query):
        scalar = np.ndim(query) == 0
        q = np.asarray(query, dtype=float)
        result = np.asarray(curve(np.clip(q, t[0], t[-1])), dtype=float)
        result = np.array(result, copy=True)
        result[q >= right] = plateau
        blend = (q > left) & (q < right)
        alpha = (q[blend] - left) / (right - left)
        result[blend] = (1.0 - alpha) * result[blend] + alpha * plateau
        return float(result) if scalar else result

    bt = lambda q: stage(curve_t, plateau_t, left_t, right_t, q)
    bc = lambda q: stage(curve_c, plateau_c, left_c, right_c, q)
    staged_env = np.c_[t, bt(t), bc(t)]
    metadata = {
        "mode": "stretched_exp_plus_independent_constant_stages",
        "fit_endpoint_policy": fit_endpoint_policy,
        "fit_endpoint_temperature_s": float(endpoint_t),
        "fit_endpoint_moisture_s": float(endpoint_c),
        "transition_s": float(transition_s),
        "phase_temperature": phase_t,
        "phase_moisture": phase_c,
        "phase_gap_s": float(center_c - center_t),
        "transition_temperature": {
            "center_s": float(center_t), "left_s": float(left_t),
            "right_s": float(right_t), "width_s": float(transition_s)
        },
        "transition_moisture": {
            "center_s": float(center_c), "left_s": float(left_c),
            "right_s": float(right_c), "width_s": float(transition_s)
        },
        "plateau_temperature": plateau_t,
        "plateau_moisture": plateau_c,
        "fit_temperature": fit_t,
        "fit_moisture": fit_c,
    }
    return bt, bc, staged_env, metadata
