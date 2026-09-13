"""生成论文第六节的三类误差分析表。

脚本读取当前第一至第四问的正式结果记录，只写出结构化表格：数值收敛、
参数敏感性和长期边界系统误差情景。

从 submit 目录运行：

    conda run --no-capture-output -n 2026modeling python code/p6/run_p6.py
"""
from __future__ import annotations

import contextlib
import csv
import gc
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import numpy as np


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
CODE = PACKAGE / "code"
RESULTS = PACKAGE / "results"
OUT = RESULTS / "p6"

Q1_VALIDATION = RESULTS / "q1" / "q1_validation.json"
Q2_VALIDATION = RESULTS / "q2" / "q2_validation.json"
Q2_SENSITIVITY = RESULTS / "q2" / "q2_parameter_sensitivity.json"
Q3_VALIDATION = RESULTS / "q3" / "q3_validation.json"
Q4_VALIDATION = RESULTS / "q4" / "q4_validation.json"

BOUNDARY_SAMPLE_COUNT = 4
BOUNDARY_SEED = 20260913
BOUNDARY_GRID = 200
BOUNDARY_MAX_STEP_S = 300.0
BOUNDARY_BLOCK_POINTS = 10
SOLVER_HORIZON_S = 864000.0


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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_source_links(q2_sensitivity: dict, q3: dict) -> None:
    for relative, expected in q2_sensitivity["source_sha256"].items():
        if sha256(PACKAGE / relative) != expected:
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


def q1_sensitivity_rows(q1: dict) -> list[dict]:
    metric_info = {
        "T_mean_1800_C": ("平均温度", "°C"),
        "C_mean_1800_kg_per_kg": ("平均含水率", "kg/kg"),
    }
    rows = []
    for scenario in q1["sensitivity"]["scenarios"]:
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
    metric_info = {
        "mean_T_3h": ("3 h平均温度", "°C"),
        "mean_C_3h": ("3 h平均含水率", "kg/kg"),
    }
    rows = []
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


def make_boundary_ensemble(raw_env: np.ndarray, build_boundaries, q2_model,
                           sample_count: int, seed: int) -> tuple[list[dict], dict]:
    """将稳定尾段的中心残差块传播到第三、第四问。"""
    q3_model = load_module("p6_q3_model", CODE / "q3" / "solve_q3.py")
    q4_model = load_module("p6_q4_model", CODE / "q4" / "solve_q4.py")

    base_t, base_c, staged_env, boundary_info = build_boundaries(
        raw_env, mode="staged"
    )
    stable_start = max(
        float(boundary_info["transition_temperature"]["right_s"]),
        float(boundary_info["transition_moisture"]["right_s"]),
    )
    stable_mask = raw_env[:, 0] >= stable_start
    residual_pool = raw_env[stable_mask, 1:] - staged_env[stable_mask, 1:]
    residual_pool = residual_pool - residual_pool.mean(axis=0)
    if len(residual_pool) < BOUNDARY_BLOCK_POINTS:
        raise RuntimeError("stable tail is too short for block resampling")
    dt_s = float(np.median(np.diff(raw_env[:, 0])))
    if not np.allclose(np.diff(raw_env[:, 0]), dt_s):
        raise RuntimeError("environment sampling is not uniform")

    plateau = np.array([
        float(boundary_info["plateau_temperature"]),
        float(boundary_info["plateau_moisture"]),
    ])
    end_s = float(raw_env[-1, 0])
    horizon_s = SOLVER_HORIZON_S - end_s
    if horizon_s <= 0:
        raise RuntimeError("solver horizon must exceed environment data")

    radius = q4_model.read_xlsx(PACKAGE / "data" / "附件2.xlsx")
    radius[:, 1] /= 100.0
    q3_reference = float(read_json(Q3_VALIDATION)["event_h"])
    q4_reference = float(read_json(Q4_VALIDATION)["event_h"])

    def make_realization(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        block_length_s = BOUNDARY_BLOCK_POINTS * dt_s
        count = int(np.ceil(horizon_s / block_length_s))
        values = []
        while len(values) < count:
            start = int(rng.integers(0, len(residual_pool)))
            block = (start + np.arange(BOUNDARY_BLOCK_POINTS)) % len(residual_pool)
            values.append(residual_pool[block].mean(axis=0))
        values = np.asarray(values[:count], dtype=float)
        relative_times = np.arange(count + 1, dtype=float) * block_length_s
        residuals = np.vstack([np.zeros((1, 2)), values])
        return relative_times, residuals

    def make_boundary(relative_times: np.ndarray, residuals: np.ndarray):
        def temperature(t):
            q = float(t)
            if q <= end_s:
                return float(base_t(q))
            return float(plateau[0] + np.interp(
                q - end_s, relative_times, residuals[:, 0]
            ))

        def moisture(t):
            q = float(t)
            if q <= end_s:
                return float(base_c(q))
            return float(plateau[1] + np.interp(
                q - end_s, relative_times, residuals[:, 1]
            ))

        return temperature, moisture

    rows = []
    common = {
        "method": "均值平台+稳定尾段残差成块重采样",
        "N": BOUNDARY_GRID,
        "block_points": BOUNDARY_BLOCK_POINTS,
        "block_length_s": BOUNDARY_BLOCK_POINTS * dt_s,
        "stable_start_s": stable_start,
    }
    for question, event_h in (("问题3", q3_reference), ("问题4", q4_reference)):
        rows.append({
            **common,
            "question": question,
            "sample": "mean_baseline",
            "seed": "",
            "residual_std_T_C": float(np.std(residual_pool[:, 0], ddof=1)),
            "residual_std_C_kg_per_kg": float(np.std(residual_pool[:, 1], ddof=1)),
            "event_h": event_h,
            "delta_h": 0.0,
            "baseline_event_h": event_h,
        })

    for sample in range(1, sample_count + 1):
        sample_seed = seed + sample
        relative_times, residuals = make_realization(
            np.random.default_rng(sample_seed)
        )
        boundary = make_boundary(relative_times, residuals)
        with contextlib.redirect_stdout(io.StringIO()):
            q3_result = q3_model._integrate(
                q2_model,
                staged_env,
                BOUNDARY_GRID,
                max_step=BOUNDARY_MAX_STEP_S,
                boundary=boundary,
            )
            q4_result = q4_model.simulate(
                staged_env,
                radius,
                BOUNDARY_GRID,
                max_step=BOUNDARY_MAX_STEP_S,
                boundary=boundary,
                radius_method="pchip",
            )
        events = {
            "问题3": float(q3_result["event_s"]) / 3600.0,
            "问题4": float(q4_result["event_s"]) / 3600.0,
        }
        del q3_result, q4_result
        gc.collect()
        print(f"systematic boundary sample {sample}/{sample_count} finished", flush=True)
        for question, event_h in events.items():
            baseline = q3_reference if question == "问题3" else q4_reference
            rows.append({
                **common,
                "question": question,
                "sample": f"bootstrap_{sample:02d}",
                "seed": sample_seed,
                "residual_std_T_C": float(np.std(residual_pool[:, 0], ddof=1)),
                "residual_std_C_kg_per_kg": float(np.std(residual_pool[:, 1], ddof=1)),
                "event_h": event_h,
                "delta_h": event_h - baseline,
                "baseline_event_h": baseline,
            })

    metadata = {
        "method": common["method"],
        "seed": seed,
        "sample_count": sample_count,
        "N": BOUNDARY_GRID,
        "max_step_s": BOUNDARY_MAX_STEP_S,
        "block_points": BOUNDARY_BLOCK_POINTS,
        "block_length_s": BOUNDARY_BLOCK_POINTS * dt_s,
        "environment_end_s": end_s,
        "stable_start_s": stable_start,
        "stable_sample_count": int(len(residual_pool)),
        "plateau_temperature_C": float(plateau[0]),
        "plateau_moisture_kg_per_kg": float(plateau[1]),
        "residual_std_T_C": float(np.std(residual_pool[:, 0], ddof=1)),
        "residual_std_C_kg_per_kg": float(np.std(residual_pool[:, 1], ddof=1)),
        "boundary_formula": "future boundary = detected plateau mean + centered stable-tail residual blocks",
    }
    return rows, metadata


def systematic_summary(rows: list[dict]) -> list[dict]:
    summaries = []
    for question in ("问题3", "问题4"):
        selected = [
            float(row["event_h"]) for row in rows
            if row["question"] == question and row["sample"] != "mean_baseline"
        ]
        baseline = next(
            float(row["baseline_event_h"]) for row in rows
            if row["question"] == question and row["sample"] == "mean_baseline"
        )
        deltas = np.asarray(selected) - baseline
        summaries.append({
            "question": question,
            "baseline_event_h": baseline,
            "fluctuation_mean_event_h": float(np.mean(selected)),
            "fluctuation_std_h": float(np.std(selected, ddof=1)),
            "fluctuation_min_event_h": float(np.min(selected)),
            "fluctuation_max_event_h": float(np.max(selected)),
            "mean_delta_h": float(np.mean(deltas)),
            "min_delta_h": float(np.min(deltas)),
            "max_delta_h": float(np.max(deltas)),
            "sample_count": len(selected),
        })
    return summaries


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q1 = read_json(Q1_VALIDATION)
    q2 = read_json(Q2_VALIDATION)
    q2_sensitivity = read_json(Q2_SENSITIVITY)
    q3 = read_json(Q3_VALIDATION)
    q4 = read_json(Q4_VALIDATION)
    validate_source_links(q2_sensitivity, q3)

    q2_model_for_data = load_module("p6_q2_data_model", CODE / "q2" / "solve_q2.py")
    raw_env = q2_model_for_data.read_environment()
    boundary_module = load_module(
        "p6_boundary_stage", CODE / "q3" / "boundary_stage.py"
    )

    convergence = convergence_rows(q1, q2, q3, q4)
    sensitivity = q1_sensitivity_rows(q1) + q2_sensitivity_rows(q2_sensitivity)
    systematic, systematic_metadata = make_boundary_ensemble(
        raw_env,
        boundary_module.build_boundaries,
        q2_model_for_data,
        BOUNDARY_SAMPLE_COUNT,
        BOUNDARY_SEED,
    )
    systematic_stats = systematic_summary(systematic)

    write_csv(
        OUT / "p6_convergence.csv",
        convergence,
        ["question", "check", "metric", "value", "unit", "comparison", "interpretation"],
    )
    write_csv(
        OUT / "p6_sensitivity.csv",
        sensitivity,
        ["analysis", "scenario", "parameter", "factor", "metric", "value",
         "delta", "unit", "dimensionless_sensitivity"],
    )
    write_csv(
        OUT / "p6_systematic_boundary.csv",
        systematic,
        ["method", "question", "sample", "seed", "N", "block_points",
         "block_length_s", "stable_start_s", "residual_std_T_C",
         "residual_std_C_kg_per_kg", "event_h", "delta_h", "baseline_event_h"],
    )

    source_paths = [
        HERE / "run_p6.py",
        CODE / "q1" / "solve_q1.py",
        CODE / "q2" / "solve_q2.py",
        CODE / "q2" / "run_sensitivity.py",
        CODE / "q2" / "boundary_stage.py",
        CODE / "q3" / "boundary_stage.py",
        CODE / "q3" / "solve_q3.py",
        CODE / "q4" / "boundary_stage.py",
        CODE / "q4" / "solve_q4.py",
        CODE / "kirchhoff_flux.py",
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
        "error_categories": [
            "数值收敛性误差",
            "参数敏感性误差",
            "系统误差：长期边界扰动",
        ],
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
        "numerical_convergence": convergence,
        "parameter_sensitivity": {
            "q1_reference": q1["sensitivity"]["reference"],
            "q1_scenarios": q1["sensitivity"]["scenarios"],
            "q2_reference": q2_sensitivity["records"][0],
            "q2_scenarios": q2_sensitivity["records"][1:],
            "q2_central_dimensionless": q2_sensitivity["central_dimensionless_sensitivity"],
        },
        "systematic_boundary": {
            **systematic_metadata,
            "summary": systematic_stats,
        },
        "generated_files": {
            "convergence_csv": "results/p6/p6_convergence.csv",
            "sensitivity_csv": "results/p6/p6_sensitivity.csv",
            "systematic_boundary_csv": "results/p6/p6_systematic_boundary.csv",
        },
    }
    write_json(OUT / "p6_summary.json", summary)
    print(json.dumps({
        "summary": "results/p6/p6_summary.json",
        "convergence_rows": len(convergence),
        "sensitivity_rows": len(sensitivity),
        "systematic_boundary_rows": len(systematic),
        "systematic_summary": systematic_stats,
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
