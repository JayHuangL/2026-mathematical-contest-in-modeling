"""Rebuild the Q2 boundary-endpoint and parameter-sensitivity diagnostics.

The endpoint comparison is a data-preprocessing diagnostic read from the
validated Q1 CSV.  The parameter sensitivity is recomputed with the current
Q2 solver, so it automatically uses the same staged boundary and Kirchhoff
moisture flux as the formal result.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

import solve_q2 as q2


PACKAGE = Path(__file__).resolve().parents[2]
OUT = PACKAGE / "results" / "q2"
Q1_ENDPOINTS = PACKAGE / "results" / "q1" / "boundary_endpoint_comparison.csv"
METHODS = ("linear", "pchip", "akima", "cubic_spline", "smooth_spline", "stretched_exp")
PARAMETERS = ("h", "hm", "capacity", "conductivity", "diffusivity")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_endpoint_figure() -> None:
    rows = list(csv.DictReader(Q1_ENDPOINTS.open(encoding="utf-8-sig", newline="")))
    if not rows:
        raise RuntimeError(f"No endpoint diagnostics in {Q1_ENDPOINTS}")
    expected = {(series, method) for series in ("T", "C") for method in METHODS}
    actual = {(row["series"], row["method"]) for row in rows}
    if not expected.issubset(actual):
        raise AssertionError("The endpoint diagnostic CSV is incomplete.")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    titles = {"T": "温度：拟合终点对 0–1800 s 误差的影响",
              "C": "环境水分：拟合终点对 0–1800 s 误差的影响"}
    for ax, series in zip(axes, ("T", "C")):
        for method in METHODS:
            selected = sorted((row for row in rows
                               if row["series"] == series and row["method"] == method),
                              key=lambda row: float(row["endpoint_s"]))
            x = [float(row["endpoint_s"]) / 3600.0 for row in selected]
            y = [float(row["q1_rmse"]) for row in selected]
            ax.plot(x, y, marker="o", ms=4, lw=1.4, label=method)
        ax.set(title=titles[series], xlabel="拟合终点 / h", ylabel="RMSE")
        ax.grid(alpha=0.22)
        ax.legend(fontsize=8, ncol=2, loc="best")
    fig.savefig(OUT / "图08_拟合终点比较.png", dpi=180)
    plt.close(fig)


def run_case(boundary, environment, base_properties, base_h, base_hm,
             parameter: str | None, factor: float, grid: int) -> dict:
    q2.H, q2.HM = base_h, base_hm

    def properties(temperature, moisture):
        b, k, d, b_c, k_c, d_c, d_t = base_properties(temperature, moisture)
        if parameter == "capacity":
            b, b_c = factor * b, factor * b_c
        elif parameter == "conductivity":
            k, k_c = factor * k, factor * k_c
        elif parameter == "diffusivity":
            d, d_c, d_t = factor * d, factor * d_c, factor * d_t
        return b, k, d, b_c, k_c, d_c, d_t

    if parameter == "h":
        q2.H = base_h * factor
    elif parameter == "hm":
        q2.HM = base_hm * factor
    q2.properties = properties
    result = q2.solve_model(grid, environment, boundary=boundary)
    return {
        "case": "baseline" if parameter is None else f"{parameter}_{factor:.1f}",
        "parameter": parameter,
        "factor": factor,
        "T_center_3h": float(result["T"][-1, 0]),
        "T_surface_3h": float(result["T"][-1, -1]),
        "mean_T_3h": float(result["mean_T"][-1]),
        "C_center_3h": float(result["C"][-1, 0]),
        "C_surface_3h": float(result["C"][-1, -1]),
        "mean_C_3h": float(result["mean_C"][-1]),
    }


def run_parameter_sensitivity(grid: int) -> dict:
    raw = q2.read_environment()
    boundary_t, boundary_c, environment, boundary_info = q2.build_boundaries(raw, mode="staged")
    boundary = (boundary_t, boundary_c)
    base_properties, base_h, base_hm = q2.properties, q2.H, q2.HM
    try:
        records = [run_case(boundary, environment, base_properties, base_h, base_hm,
                            None, 1.0, grid)]
        for parameter in PARAMETERS:
            for factor in (0.8, 1.2):
                records.append(run_case(boundary, environment, base_properties, base_h, base_hm,
                                        parameter, factor, grid))
    finally:
        q2.properties, q2.H, q2.HM = base_properties, base_h, base_hm

    baseline = records[0]
    metrics = [key for key in baseline if key.endswith("_3h")]
    for record in records:
        record["delta"] = {key: record[key] - baseline[key] for key in metrics}
    elasticities = {}
    for parameter in PARAMETERS:
        low = next(row for row in records if row["case"] == f"{parameter}_0.8")
        high = next(row for row in records if row["case"] == f"{parameter}_1.2")
        elasticities[parameter] = {
            key: (high[key] - low[key]) / (0.4 * baseline[key]) for key in metrics
        }
    payload = {
        "model": "current Q2 staged-boundary model with Kirchhoff moisture flux",
        "definition": "central dimensionless sensitivity [Y(1.2p)-Y(0.8p)]/(0.4Y(p))",
        "grid_intervals": grid,
        "rtol": 2e-10,
        "atol": 2e-12,
        "max_step_s": 5.0,
        "boundary_metadata": boundary_info,
        "source_sha256": {
            "code/q2/solve_q2.py": _sha256(Path(q2.__file__)),
            "code/q2/run_sensitivity.py": _sha256(Path(__file__)),
            "code/q2/boundary_stage.py": _sha256(Path(q2.__file__).with_name("boundary_stage.py")),
            "code/kirchhoff_flux.py": _sha256(PACKAGE / "code" / "kirchhoff_flux.py"),
        },
        "records": records,
        "central_dimensionless_sensitivity": elasticities,
    }
    (OUT / "parameter_sensitivity.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def make_sensitivity_figure(payload: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "font.size": 10})
    labels = [r"$h$", r"$h_m$", r"$\rho c_p$", r"$k$", r"$D$"]
    elasticities = payload["central_dimensionless_sensitivity"]
    values_t = [elasticities[p]["mean_T_3h"] for p in PARAMETERS]
    values_c = [elasticities[p]["mean_C_3h"] for p in PARAMETERS]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    colors = ["#4c78a8" if value >= 0 else "#e45756" for value in values_t]
    axes[0].bar(labels, values_t, color=colors)
    colors = ["#4c78a8" if value >= 0 else "#e45756" for value in values_c]
    axes[1].bar(labels, values_c, color=colors)
    axes[0].set_title("3 h 平均温度的无量纲敏感度")
    axes[1].set_title("3 h 平均含水率的无量纲敏感度")
    for ax in axes:
        ax.axhline(0.0, color="black", lw=0.8)
        ax.set_xlabel("扰动参数（±20% 中心差分）")
        ax.set_ylabel("无量纲敏感度")
        ax.grid(axis="y", alpha=0.22)
    fig.savefig(OUT / "图09_第二问参数敏感性.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid", type=int, default=200)
    parser.add_argument("--endpoint-only", action="store_true")
    args = parser.parse_args()
    make_endpoint_figure()
    if not args.endpoint_only:
        payload = run_parameter_sensitivity(args.grid)
        make_sensitivity_figure(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()
