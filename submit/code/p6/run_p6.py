"""Build the error and sensitivity-analysis package for Section 6.

The script consumes the current, hash-checked q1--q4 validation records.  It
does not rerun the four forward solvers; ``submit/run_all.py`` remains the
single entry point for regenerating those numerical results.

Run from ``submit`` or from any directory:

    conda run --no-capture-output -n 2026modeling python code/p6/run_p6.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
RESULTS = PACKAGE / "results"
OUT = RESULTS / "p6"
FIGURES = PACKAGE / "figures" / "p6"

Q1_VALIDATION = RESULTS / "q1" / "q1_validation.json"
Q2_VALIDATION = RESULTS / "q2" / "q2_validation.json"
Q2_SENSITIVITY = RESULTS / "q2" / "q2_parameter_sensitivity.json"
Q3_VALIDATION = RESULTS / "q3" / "q3_validation.json"
Q4_VALIDATION = RESULTS / "q4" / "q4_validation.json"

PARAMETER_LABELS = {
    "h": r"$h$",
    "hm": r"$h_m$",
    "D": r"$D$",
    "capacity": r"$\rho c_p$",
    "conductivity": r"$k$",
    "diffusivity": r"$D$",
}
Q2_PARAMETERS = ("h", "hm", "capacity", "conductivity", "diffusivity")
Q1_PARAMETERS = ("h", "hm", "D")
BLUE = "#4c78a8"
RED = "#e45756"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate_source_links(q2_sensitivity: dict, q3: dict) -> None:
    """Reject old diagnostics whose recorded solver hashes no longer match."""
    for relative, expected in q2_sensitivity["source_sha256"].items():
        actual = sha256(PACKAGE / relative)
        if actual != expected:
            raise RuntimeError(f"stale Q2 sensitivity source hash: {relative}")
    q2_relative = "code/q2/solve_q2.py"
    if sha256(PACKAGE / q2_relative) != q3["q2_code_sha256"]:
        raise RuntimeError("stale Q3 diagnostic: q2 solver hash does not match")


def convergence_rows(q1: dict, q2: dict, q3: dict, q4: dict) -> list[dict]:
    rows: list[dict] = []

    def add(question: str, check: str, metric: str, value: float,
            unit: str, comparison: str, interpretation: str) -> None:
        rows.append({
            "question": question,
            "check": check,
            "metric": metric,
            "value": float(value),
            "unit": unit,
            "comparison": comparison,
            "interpretation": interpretation,
        })

    q1_last = q1["convergence"][-1]
    add("问题1", "空间加密", "全场温度最大差", q1_last["max_diff_T"], "°C",
        "N=3200→6400", "网格差已远小于温度结果的有效显示尺度")
    add("问题1", "空间加密", "全场含水率最大差", q1_last["max_diff_C"], "kg/kg",
        "N=3200→6400", "表面附近梯度是主要空间离散误差来源")
    add("问题1", "时间收紧", "全场温度最大差", q1["time_check"]["T"], "°C",
        "容差各收紧10倍", "时间积分误差很小")
    add("问题1", "时间收紧", "全场含水率最大差", q1["time_check"]["C"], "kg/kg",
        "容差各收紧10倍", "时间积分误差很小")

    q2_last = q2["convergence"][-1]
    add("问题2", "空间加密", "全场温度最大差", q2_last["max_diff_T"], "°C",
        "N=300→400", "网格差已收敛")
    add("问题2", "空间加密", "全场含水率最大差", q2_last["max_diff_C"], "kg/kg",
        "N=300→400", "初始表面梯度使全场最大差偏大")
    add("问题2", "空间加密", "题目表格点含水率最大差", q2_last["table_diff_C"], "kg/kg",
        "N=300→400", "题目要求的展示位置稳定")
    add("问题2", "时间收紧", "全场温度最大差", q2["time_check"]["T"], "°C",
        "容差各收紧10倍", "时间积分误差很小")
    add("问题2", "时间收紧", "全场含水率最大差", q2["time_check"]["C"], "kg/kg",
        "容差各收紧10倍", "时间积分误差很小")

    q3_grid = q3["grid_checks"][-1]
    add("问题3", "空间加密", "达标事件时间差", q3_grid["event_diff_s"], "s",
        "N=220→300", "事件定位稳定")
    add("问题3", "空间加密", "60 s输出含水率最大差", q3_grid["max_C_diff_60s"], "kg/kg",
        "N=220→300", "输出场的空间差异仍远小于小时级终点")
    add("问题3", "时间收紧", "达标事件时间差", q3["time_check"]["event_diff_s"], "s",
        "容差各收紧10倍", "事件定位的时间误差很小")
    add("问题3", "时间收紧", "全场含水率最大差", q3["time_check"]["max_C_diff"], "kg/kg",
        "容差各收紧10倍", "时间积分误差很小")

    q4_grid = q4["grid_checks"][-1]
    add("问题4", "空间加密", "达标事件时间差", q4_grid["event_diff_s"], "s",
        "N=200→300", "移动边界事件定位稳定")
    add("问题4", "空间加密", "实际位置输出含水率最大差", q4_grid["max_output_C_diff"], "kg/kg",
        "N=200→300", "输出场差异远小于小时级终点")
    add("问题4", "时间收紧", "达标事件时间差", q4["time_check"]["event_diff_s"], "s",
        "容差各收紧10倍", "事件定位的时间误差很小")
    add("问题4", "时间收紧", "实际位置输出含水率最大差", q4["time_check"]["max_output_C_diff"], "kg/kg",
        "容差各收紧10倍", "时间积分误差很小")
    return rows


def balance_rows(q1: dict, q2: dict, q3: dict, q4: dict) -> list[dict]:
    values = {
        "问题1": max(float(row["balance_C"]) for row in q1["convergence"]),
        "问题2": max(float(row["moisture_balance_error"]) for row in q2["convergence"]),
        "问题3": max(float(row["balance_error"]) for row in q3["grid_checks"]),
        "问题4": max(float(row["balance_error"]) for row in q4["grid_checks"]),
    }
    return [
        {
            "question": question,
            "max_absolute_water_balance_residual": residual,
            "unit": "kg/kg",
            "scope": "formal grid records",
        }
        for question, residual in values.items()
    ]


def physical_rows(q3: dict, q4: dict) -> list[dict]:
    rows = []
    validation_radial_increase = {
        "q3": float(q3["max_radial_increase"]),
        "q4": float(q4["max_radial_increase"]),
    }
    for question in ("q1", "q2", "q3", "q4"):
        path = RESULTS / question / f"{question}_result_full_precision.npz"
        with np.load(path, mmap_mode="r") as data:
            temperature = np.asarray(data["T"])
            moisture = np.asarray(data["C"])
            radial_increase = (
                validation_radial_increase[question]
                if question in validation_radial_increase
                else float(np.nanmax(np.diff(moisture, axis=1)))
            )
            rows.append({
                "question": f"问题{question[1:]}",
                "min_temperature_C": float(np.nanmin(temperature)),
                "max_temperature_C": float(np.nanmax(temperature)),
                "min_moisture_kg_per_kg": float(np.nanmin(moisture)),
                "max_moisture_kg_per_kg": float(np.nanmax(moisture)),
                "max_radial_increase_kg_per_kg": radial_increase,
                "center_is_wettest": bool(np.all(np.nanargmax(moisture, axis=1) == 0)),
            })
    return rows


def q1_sensitivity_rows(q1: dict) -> list[dict]:
    sensitivity = q1["sensitivity"]
    rows = []
    metric_info = {
        "T_mean_1800_C": ("平均温度", "°C"),
        "C_mean_1800_kg_per_kg": ("平均含水率", "kg/kg"),
    }
    for scenario in sensitivity["scenarios"]:
        name = scenario["name"]
        if name.startswith("h_factor_"):
            parameter, factor = "h", float(name.rsplit("_", 1)[-1])
        elif name.startswith("hm_factor_"):
            parameter, factor = "hm", float(name.rsplit("_", 1)[-1])
        elif name.startswith("D_factor_"):
            parameter, factor = "D", float(name.rsplit("_", 1)[-1])
        elif name.startswith("fit_window_"):
            parameter, factor = "拟合窗口", float(name.split("_")[-1].replace("s", ""))
        elif name == "linear_input":
            parameter, factor = "边界表示", "分段线性"
        else:
            parameter, factor = name, ""
        for metric, (label, unit) in metric_info.items():
            rows.append({
                "analysis": "问题1",
                "scenario": name,
                "parameter": parameter,
                "factor": factor,
                "metric": label,
                "value": float(scenario["metrics"][metric]),
                "delta": float(scenario["delta_from_reference"][metric]),
                "unit": unit,
                "dimensionless_sensitivity": "",
            })
    return rows


def q2_sensitivity_rows(q2_sensitivity: dict) -> list[dict]:
    rows = []
    metric_info = {
        "mean_T_3h": ("3 h平均温度", "°C"),
        "mean_C_3h": ("3 h平均含水率", "kg/kg"),
    }
    for record in q2_sensitivity["records"]:
        if record["case"] == "baseline":
            continue
        for metric, (label, unit) in metric_info.items():
            rows.append({
                "analysis": "问题2",
                "scenario": record["case"],
                "parameter": record["parameter"],
                "factor": record["factor"],
                "metric": label,
                "value": float(record[metric]),
                "delta": float(record["delta"][metric]),
                "unit": unit,
                "dimensionless_sensitivity": float(
                    q2_sensitivity["central_dimensionless_sensitivity"]
                    [record["parameter"]][metric]
                ),
            })
    return rows


def scenario_rows(q3: dict, q4: dict) -> list[dict]:
    rows = []
    q3_reference = float(q3["event_h"])
    q4_reference = float(q4["event_h"])
    q3_descriptions = {
        "50C_0.05": "尾段固定为50 °C、0.05 kg/kg",
        "last_hour_mean": "尾段采用附件最后1 h均值",
    }
    q4_descriptions = {
        "appendix4_fixed_radius": "附录4物性、固定半径",
        "appendix3_shrinking": "附录3物性、保持收缩半径",
        "linear_radius": "附录4物性、分段线性半径",
        "tail_50C_0.05": "附录4物性、尾段固定为50 °C、0.05 kg/kg",
    }
    for record in q3["tail_sensitivity"]:
        event_h = float(record["event_h"])
        rows.append({
            "question": "问题3",
            "scenario": record["case"],
            "description": q3_descriptions.get(record["case"], record["case"]),
            "event_h": event_h,
            "delta_h": event_h - q3_reference,
            "reference_event_h": q3_reference,
        })
    for record in q4["comparisons"]:
        event_h = float(record["event_h"])
        rows.append({
            "question": "问题4",
            "scenario": record["case"],
            "description": q4_descriptions.get(record["case"], record["case"]),
            "event_h": event_h,
            "delta_h": event_h - q4_reference,
            "reference_event_h": q4_reference,
        })
    return rows


def configure_plot() -> None:
    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": 10,
    })


def signed_colors(values) -> list[str]:
    return [BLUE if value >= 0 else RED for value in values]


def make_convergence_figure(rows: list[dict]) -> str:
    space_c = []
    time_c = []
    event_space = []
    event_time = []
    labels = ["问题1", "问题2", "问题3", "问题4"]
    for question in labels:
        space = [r["value"] for r in rows if r["question"] == question
                 and r["check"] == "空间加密" and r["unit"] == "kg/kg"]
        time = [r["value"] for r in rows if r["question"] == question
                and r["check"] == "时间收紧" and r["unit"] == "kg/kg"]
        space_c.append(max(space))
        time_c.append(max(time))
    for question in ("问题3", "问题4"):
        event_space.append(next(r["value"] for r in rows if r["question"] == question
                                and r["check"] == "空间加密" and r["unit"] == "s"))
        event_time.append(next(r["value"] for r in rows if r["question"] == question
                               and r["check"] == "时间收紧" and r["unit"] == "s"))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    x = np.arange(len(labels))
    width = 0.36
    axes[0].bar(x - width / 2, space_c, width, color=BLUE, label="空间加密")
    axes[0].bar(x + width / 2, time_c, width, color=RED, label="时间收紧")
    axes[0].set_yscale("log")
    axes[0].set_xticks(x, labels)
    axes[0].set_title("含水率数值差异的数量级")
    axes[0].set_xlabel("问题")
    axes[0].set_ylabel("最大差异 / (kg/kg)")
    axes[0].grid(axis="y", alpha=0.22)
    axes[0].legend(frameon=False)

    x_event = np.arange(2)
    axes[1].bar(x_event - width / 2, event_space, width, color=BLUE, label="空间加密")
    axes[1].bar(x_event + width / 2, event_time, width, color=RED, label="时间收紧")
    axes[1].set_yscale("log")
    axes[1].set_xticks(x_event, ["问题3", "问题4"])
    axes[1].set_title("干燥终点事件时间差")
    axes[1].set_xlabel("问题")
    axes[1].set_ylabel("事件时间差 / s")
    axes[1].grid(axis="y", alpha=0.22)
    axes[1].legend(frameon=False)

    path = FIGURES / "p6_fig_01_numerical_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path.relative_to(PACKAGE).as_posix()


def make_parameter_figure(q1: dict, q2_sensitivity: dict) -> str:
    q1_scenarios = {row["name"]: row for row in q1["sensitivity"]["scenarios"]}
    q1_t = []
    q1_c = []
    for parameter in Q1_PARAMETERS:
        low = q1_scenarios[f"{parameter}_factor_0.8"]
        high = q1_scenarios[f"{parameter}_factor_1.2"]
        q1_t.append([low["delta_from_reference"]["T_mean_1800_C"],
                     high["delta_from_reference"]["T_mean_1800_C"]])
        q1_c.append([low["delta_from_reference"]["C_mean_1800_kg_per_kg"],
                     high["delta_from_reference"]["C_mean_1800_kg_per_kg"]])

    central = q2_sensitivity["central_dimensionless_sensitivity"]
    q2_t = [central[p]["mean_T_3h"] for p in Q2_PARAMETERS]
    q2_c = [central[p]["mean_C_3h"] for p in Q2_PARAMETERS]
    labels_q1 = [PARAMETER_LABELS[p] for p in Q1_PARAMETERS]
    labels_q2 = [PARAMETER_LABELS[p] for p in Q2_PARAMETERS]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), constrained_layout=True)
    x1 = np.arange(len(Q1_PARAMETERS))
    width = 0.34
    low_t = [pair[0] for pair in q1_t]
    high_t = [pair[1] for pair in q1_t]
    low_c = [pair[0] for pair in q1_c]
    high_c = [pair[1] for pair in q1_c]
    axes[0, 0].bar(x1 - width / 2, low_t, width, color=BLUE, label="×0.8")
    axes[0, 0].bar(x1 + width / 2, high_t, width, color=RED, label="×1.2")
    axes[0, 0].set_xticks(x1, labels_q1)
    axes[0, 0].set_title("问题1：1800 s平均温度变化")
    axes[0, 0].set_ylabel("变化 / °C")
    axes[0, 0].legend(frameon=False)

    axes[0, 1].bar(x1 - width / 2, low_c, width, color=BLUE, label="×0.8")
    axes[0, 1].bar(x1 + width / 2, high_c, width, color=RED, label="×1.2")
    axes[0, 1].set_xticks(x1, labels_q1)
    axes[0, 1].set_title("问题1：1800 s平均含水率变化")
    axes[0, 1].set_ylabel("变化 / (kg/kg)")
    axes[0, 1].legend(frameon=False)

    x2 = np.arange(len(Q2_PARAMETERS))
    axes[1, 0].bar(x2, q2_t, color=signed_colors(q2_t))
    axes[1, 0].set_xticks(x2, labels_q2)
    axes[1, 0].set_title("问题2：3 h平均温度无量纲敏感度")
    axes[1, 0].set_ylabel("中心差分灵敏度")

    axes[1, 1].bar(x2, q2_c, color=signed_colors(q2_c))
    axes[1, 1].set_xticks(x2, labels_q2)
    axes[1, 1].set_title("问题2：3 h平均含水率无量纲敏感度")
    axes[1, 1].set_ylabel("中心差分灵敏度")

    for ax in axes.flat:
        ax.axhline(0.0, color="black", lw=0.8)
        ax.grid(axis="y", alpha=0.22)

    path = FIGURES / "p6_fig_02_parameter_sensitivity.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path.relative_to(PACKAGE).as_posix()


def make_scenario_figure(scenarios: list[dict]) -> str:
    by_question = {"问题3": [], "问题4": []}
    for row in scenarios:
        by_question[row["question"]].append(row)
    q3 = by_question["问题3"]
    q4 = by_question["问题4"]
    q4_structural_names = {"appendix4_fixed_radius", "appendix3_shrinking"}
    q4_local = [row for row in q4 if row["scenario"] not in q4_structural_names]
    q4_structural = [row for row in q4 if row["scenario"] in q4_structural_names]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), constrained_layout=True)
    figure_labels = {
        "50C_0.05": "固定尾段",
        "last_hour_mean": "末1 h均值",
        "appendix4_fixed_radius": "附录4固定半径",
        "appendix3_shrinking": "附录3收缩",
        "linear_radius": "分段线性半径",
        "tail_50C_0.05": "固定尾段",
    }
    panels = [
        (axes[0], q3, "问题3：长期边界情景"),
        (axes[1], q4_structural, "问题4：结构情景"),
        (axes[2], q4_local, "问题4：局部输入情景"),
    ]
    for ax, rows, title in panels:
        values = [row["delta_h"] for row in rows]
        labels = [figure_labels.get(row["scenario"], row["scenario"]) for row in rows]
        y = np.arange(len(rows))
        ax.barh(y, values, color=signed_colors(values))
        ax.axvline(0.0, color="black", lw=0.8)
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.set_title(title)
        ax.set_xlabel("达标时间相对变化 / h")
        ax.grid(axis="x", alpha=0.22)

    path = FIGURES / "p6_fig_03_scenario_sensitivity.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path.relative_to(PACKAGE).as_posix()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    q1 = read_json(Q1_VALIDATION)
    q2 = read_json(Q2_VALIDATION)
    q2_sensitivity = read_json(Q2_SENSITIVITY)
    q3 = read_json(Q3_VALIDATION)
    q4 = read_json(Q4_VALIDATION)
    validate_source_links(q2_sensitivity, q3)

    convergence = convergence_rows(q1, q2, q3, q4)
    balances = balance_rows(q1, q2, q3, q4)
    physical = physical_rows(q3, q4)
    sensitivity = q1_sensitivity_rows(q1) + q2_sensitivity_rows(q2_sensitivity)
    scenarios = scenario_rows(q3, q4)

    write_csv(
        OUT / "p6_convergence.csv",
        convergence,
        ["question", "check", "metric", "value", "unit", "comparison", "interpretation"],
    )
    write_csv(
        OUT / "p6_balance.csv",
        balances,
        ["question", "max_absolute_water_balance_residual", "unit", "scope"],
    )
    write_csv(
        OUT / "p6_physical_checks.csv",
        physical,
        ["question", "min_temperature_C", "max_temperature_C",
         "min_moisture_kg_per_kg", "max_moisture_kg_per_kg",
         "max_radial_increase_kg_per_kg", "center_is_wettest"],
    )
    write_csv(
        OUT / "p6_sensitivity.csv",
        sensitivity,
        ["analysis", "scenario", "parameter", "factor", "metric", "value",
         "delta", "unit", "dimensionless_sensitivity"],
    )
    write_csv(
        OUT / "p6_scenarios.csv",
        scenarios,
        ["question", "scenario", "description", "event_h", "delta_h", "reference_event_h"],
    )

    configure_plot()
    figure_paths = [
        make_convergence_figure(convergence),
        make_parameter_figure(q1, q2_sensitivity),
        make_scenario_figure(scenarios),
    ]

    source_paths = [
        HERE / "run_p6.py",
        PACKAGE / "code" / "q1" / "solve_q1.py",
        PACKAGE / "code" / "q2" / "solve_q2.py",
        PACKAGE / "code" / "q2" / "run_sensitivity.py",
        PACKAGE / "code" / "q2" / "boundary_stage.py",
        PACKAGE / "code" / "q3" / "solve_q3.py",
        PACKAGE / "code" / "q4" / "solve_q4.py",
        PACKAGE / "code" / "kirchhoff_flux.py",
    ]
    input_paths = [
        PACKAGE / "data" / "附件1.xlsx",
        PACKAGE / "data" / "附件2.xlsx",
        Q1_VALIDATION,
        Q2_VALIDATION,
        Q2_SENSITIVITY,
        Q3_VALIDATION,
        Q4_VALIDATION,
    ]
    summary = {
        "section": "6 误差与敏感性分析",
        "model_version": "current submit q1-q4 formal results",
        "source_hashes": {
            path.relative_to(PACKAGE).as_posix(): sha256(path) for path in source_paths
        },
        "input_hashes": {
            path.relative_to(PACKAGE).as_posix(): sha256(path) for path in input_paths
        },
        "main_results": {
            "q1_mean_T_1800_C": float(q1["mean_T_1800"]),
            "q1_mean_C_1800_kg_per_kg": float(q1["mean_C_1800"]),
            "q2_mean_T_3h_C": float(q2["mean_T_10800"]),
            "q2_mean_C_3h_kg_per_kg": float(q2["mean_C_10800"]),
            "q3_event_h": float(q3["event_h"]),
            "q4_event_h": float(q4["event_h"]),
        },
        "convergence": convergence,
        "water_balance": balances,
        "jacobian_and_limit_checks": {
            "q2_jacobian_relative_error": float(q2["jacobian_relative_error"]),
            "q4_jacobian_relative_error": float(q4["model_checks"]["jacobian_relative_error"]),
            "q4_fixed_radius_q2_rhs_max_difference": float(
                q4["model_checks"]["fixed_radius_q2_rhs_max_difference"]
            ),
            "q4_uniform_no_exchange_derivative": float(
                q4["model_checks"]["uniform_no_exchange_derivative"]
            ),
        },
        "physical_checks": physical,
        "sensitivity": {
            "q1_reference": q1["sensitivity"]["reference"],
            "q1_scenarios": q1["sensitivity"]["scenarios"],
            "q2_reference": q2_sensitivity["records"][0],
            "q2_scenarios": q2_sensitivity["records"][1:],
            "q2_central_dimensionless": q2_sensitivity["central_dimensionless_sensitivity"],
        },
        "scenario_sensitivity": scenarios,
        "generated_files": {
            "convergence_csv": "results/p6/p6_convergence.csv",
            "balance_csv": "results/p6/p6_balance.csv",
            "physical_checks_csv": "results/p6/p6_physical_checks.csv",
            "sensitivity_csv": "results/p6/p6_sensitivity.csv",
            "scenarios_csv": "results/p6/p6_scenarios.csv",
            "figures": figure_paths,
        },
    }
    write_json(OUT / "p6_summary.json", summary)
    print(json.dumps({
        "summary": "results/p6/p6_summary.json",
        "convergence_rows": len(convergence),
        "sensitivity_rows": len(sensitivity),
        "scenario_rows": len(scenarios),
        "figures": figure_paths,
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
