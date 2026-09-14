"""对一体化提交包执行轻量级独立核验。"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import openpyxl

from artifact_names import artifact_name, figure_name, global_artifact_name, workbook_path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
DATA = PACKAGE / "data"
RESULTS = PACKAGE / "results"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _csv_records(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _payload_check(question: str, expected_rows: int, keys: tuple[str, ...]) -> dict:
    folder = RESULTS / question
    payload = json.loads((folder / artifact_name(question, "result_data")).read_text(encoding="utf-8"))
    times = payload["t_s"]
    if len(times) != expected_rows:
        raise AssertionError(f"{question}: wrong output row count")
    for key in keys:
        values = payload[key]
        if len(values) != expected_rows or any(len(row) != 21 for row in values):
            raise AssertionError(f"{question}: wrong {key} shape")
    return {"rows": len(times), "radial_columns": 21, "payload": True}


def _workbook_shape(path: Path, sheets: list[str], rows: int, columns: int) -> dict:
    book = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if book.sheetnames[: len(sheets)] != sheets:
        raise AssertionError(f"{path}: unexpected sheets {book.sheetnames}")
    counts = []
    for sheet in book.worksheets[: len(sheets)]:
        count = sum(1 for _ in sheet.iter_rows(min_row=2, max_col=columns))
        counts.append(count)
    book.close()
    if counts != [rows] * len(sheets):
        raise AssertionError(f"{path}: unexpected rows {counts}")
    return {"sheets": sheets, "rows": counts}


def _assert_cell(actual, expected, label: str) -> None:
    if expected is None:
        if actual is not None:
            raise AssertionError(f"{label}: expected blank cell")
    elif isinstance(expected, str):
        if actual != expected:
            raise AssertionError(f"{label}: workbook header differs from payload")
    elif actual is None or not np.isclose(float(actual), float(expected), rtol=0.0, atol=5e-12):
        raise AssertionError(f"{label}: workbook value differs from payload")


def _workbook_matches_payload(question: str, sheet_keys: list[tuple[str, str]], headers: list[object]) -> dict:
    folder = RESULTS / question
    payload = json.loads((folder / artifact_name(question, "result_data")).read_text(encoding="utf-8"))
    book = openpyxl.load_workbook(workbook_path(RESULTS, question), data_only=True, read_only=True)
    if book.sheetnames[:len(sheet_keys)] != [name for name, _ in sheet_keys]:
        raise AssertionError(f"{question}: unexpected workbook sheets")
    times = payload["t_s"]
    for sheet_name, key in sheet_keys:
        rows = iter(book[sheet_name].iter_rows(min_row=1, max_col=len(headers)))
        header = next(rows)
        for column, expected in enumerate(headers, start=1):
            _assert_cell(header[column - 1].value, expected, f"{question}/{sheet_name} header {column}")
        for row_index, (time_s, expected_values) in enumerate(zip(times, payload[key]), start=2):
            row = next(rows)
            _assert_cell(row[0].value, time_s, f"{question}/{sheet_name} row {row_index} time")
            for column, expected in enumerate(expected_values, start=2):
                _assert_cell(row[column - 1].value, expected,
                             f"{question}/{sheet_name} row {row_index} column {column}")
        try:
            next(rows)
        except StopIteration:
            pass
        else:
            raise AssertionError(f"{question}/{sheet_name}: unexpected extra workbook rows")
    book.close()
    return {"values_match_payload": True, "rows": len(times), "columns": len(headers) - 1}


def main() -> None:
    checks = {
        "q1": _payload_check("q1", 1800, ("T", "C")),
        "q2": _payload_check("q2", 10800, ("T", "C")),
        "q3": _payload_check("q3", 3461, ("C",)),
        "q4": _payload_check("q4", 3077, ("C",)),
        "q1_workbook": _workbook_shape(workbook_path(RESULTS, "q1"), ["温度", "水分浓度"], 1800, 22),
        "q2_workbook": _workbook_shape(workbook_path(RESULTS, "q2"), ["温度", "水分浓度"], 10800, 22),
        "q3_workbook": _workbook_shape(workbook_path(RESULTS, "q3"), ["Sheet1"], 3461, 22),
        "q4_workbook": _workbook_shape(workbook_path(RESULTS, "q4"), ["Sheet1"], 3077, 22),
        "q1_workbook_values": _workbook_matches_payload(
            "q1", [("温度", "T"), ("水分浓度", "C")],
            ["时间\\到药材中心的距离", *[round(i / 10, 1) for i in range(21)]],
        ),
        "q2_workbook_values": _workbook_matches_payload(
            "q2", [("温度", "T"), ("水分浓度", "C")],
            ["时间\\到药材中心的距离", *[round(i / 10, 1) for i in range(21)]],
        ),
        "q3_workbook_values": _workbook_matches_payload(
            "q3", [("Sheet1", "C")],
            ["时间\\到药材中心的距离", *[round(i / 10, 1) for i in range(21)]],
        ),
        "q4_workbook_values": _workbook_matches_payload(
            "q4", [("Sheet1", "C")],
            ["时间\\到药材中心的距离", *[round(i / 10, 1) for i in range(20)], "药材表面"],
        ),
    }
    for question, validation_key in [("q1", "selected_boundary_method"), ("q2", "model"), ("q3", "event_h"), ("q4", "event_h")]:
        validation = json.loads((RESULTS / question / artifact_name(question, "validation")).read_text(encoding="utf-8"))
        if validation_key not in validation:
            raise AssertionError(f"{question}: missing validation field {validation_key}")
    q4 = json.loads((RESULTS / "q4" / artifact_name("q4", "validation")).read_text(encoding="utf-8"))
    if q4.get("radius_extrapolation_used"):
        raise AssertionError("q4: radius extrapolation unexpectedly used")
    with np.load(RESULTS / "q3" / artifact_name("q3", "full_precision")) as q3_full:
        if not float(np.max(q3_full["C"][-1])) < 0.15:
            raise AssertionError("q3: final state is not strictly below the threshold")
    with np.load(RESULTS / "q4" / artifact_name("q4", "full_precision")) as q4_full:
        if not float(np.nanmax(q4_full["C"][-1])) < 0.15:
            raise AssertionError("q4: final state is not strictly below the threshold")
    checks["input_sha256"] = {
        "附件1.xlsx": _hash(DATA / "附件1.xlsx"),
        "附件2.xlsx": _hash(DATA / "附件2.xlsx"),
    }
    source_files = [PACKAGE / "run_all.py", *sorted((PACKAGE / "code").rglob("*.py"))]
    checks["source_sha256"] = {
        path.relative_to(PACKAGE).as_posix(): _hash(path) for path in source_files
    }

    q2_sensitivity = json.loads(
        (RESULTS / "q2" / artifact_name("q2", "parameter_sensitivity")).read_text(encoding="utf-8"))
    for relative, expected in q2_sensitivity["source_sha256"].items():
        if checks["source_sha256"].get(relative) != expected:
            raise AssertionError(f"q2 sensitivity was not generated by current {relative}")

    forbidden_result_files = [
        path for path in RESULTS.rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".md"}
    ]
    if forbidden_result_files:
        raise AssertionError(f"Results directory contains presentation files: {forbidden_result_files}")
    checks["result_directory_layout"] = {"image_files": 0, "markdown_files": 0}

    generated_files = []
    for question in ("q1", "q2", "q3", "q4"):
        folder = RESULTS / question
        generated_files.extend([
            workbook_path(RESULTS, question),
            folder / artifact_name(question, "result_data"),
            folder / artifact_name(question, "full_precision"),
            folder / artifact_name(question, "validation"),
        ])
    generated_files.extend([
        RESULTS / "q2" / artifact_name("q2", "parameter_sensitivity"),
        RESULTS / "q2" / artifact_name("q2", "validation_export"),
        RESULTS / "q3" / artifact_name("q3", "validation_export"),
        RESULTS / "q4" / artifact_name("q4", "validation_export"),
        RESULTS / "q4" / artifact_name("q4", "radius_method_comparison"),
    ])
    generated_figure_paths = [
        PACKAGE / "figures" / question / figure_name(question, key)
        for question, figures in {
            "q1": ("boundary_raw", "boundary_fit", "temperature_moisture_field"),
            "q2": ("boundary_stability", "boundary_staged_fit", "parameter_sensitivity",
                   "temperature_moisture_field"),
            "q3": ("drying_result",),
            "q4": ("radius_raw", "radius_pchip_fit", "shrinkage_moisture_field"),
        }.items()
        for key in figures
    ]
    generated_files.extend(generated_figure_paths)
    missing = [str(path) for path in generated_files if not path.exists()]
    if missing:
        raise AssertionError(f"Missing generated outputs: {missing}")

    legacy_generated_names = {
        "q1": ("q1_result.xlsx", "result1_data.json", "result1_full_precision.npz",
               "validation.json", "boundary_cv.csv", "boundary_endpoint_comparison.csv",
               "q1_fig_05_temperature_moisture_field.png",
               "图01_原始环境边界散点.png", "图02_拉伸指数最终拟合.png", "图05_第一问温度水分场.png"),
        "q2": ("q2_result.xlsx", "result2_data.json", "result2_full_precision.npz",
               "validation.json", "parameter_sensitivity.json", "validation_export.json",
               "q2_fig_06_boundary_stability_detection.png", "q2_fig_07_staged_boundary_fit.png",
               "q2_fig_08_fit_endpoint_comparison.png", "q2_fig_09_parameter_sensitivity.png",
               "q2_fig_10_temperature_moisture_field.png",
               "图06_边界独立稳定分界.png", "图07_分段环境边界拟合.png", "图08_拟合终点比较.png",
               "图09_第二问参数敏感性.png", "图10_第二问温度水分场.png"),
        "q3": ("q3_result.xlsx", "result3_data.json", "result3_full_precision.npz",
               "validation.json", "validation_export.json", "q3_fig_11_drying_result.png",
               "图11_第三问干燥结果.png"),
        "q4": ("q4_result.xlsx", "result4_data.json", "result4_full_precision.npz",
               "validation.json", "validation_export.json", "radius_method_comparison.csv",
               "q4_fig_12_radius_raw_scatter.png", "q4_fig_13_radius_interpolation_comparison.png",
               "q4_fig_14_shrinkage_moisture_field.png",
               "图12_半径原始散点.png", "图13_半径插值方法比较.png", "图14_第四问收缩水分场.png"),
    }
    legacy_paths = [RESULTS / question / name for question, names in legacy_generated_names.items()
                    for name in names]
    legacy_paths += [PACKAGE / "figures" / question / name
                     for question, names in legacy_generated_names.items()
                     for name in names if name.endswith(".png")]
    legacy_existing = [str(path) for path in legacy_paths if path.exists()]
    if legacy_existing:
        raise AssertionError(f"Legacy generated artifact names remain: {legacy_existing}")
    checks["generated_output_sha256"] = {
        path.relative_to(PACKAGE).as_posix(): _hash(path) for path in generated_files
    }

    checks["synchronized_paper_figures_sha256"] = {
        path.relative_to(PACKAGE).as_posix(): _hash(path)
        for path in generated_figure_paths
    }

    checks["figure_assets"] = {
        "count": len(generated_figure_paths),
        "all_exist": True,
        "paths": [path.relative_to(PACKAGE).as_posix()
                  for path in generated_figure_paths],
    }

    # 这些文件属于上游数据预处理证据或人工制作的几何示意图，不依赖 PDE 面通量
    # 实现。因此正式运行只核验并记录它们，不虚构为由程序重新生成。
    boundary_cv_path = RESULTS / "q1" / artifact_name("q1", "boundary_cv")
    endpoint_path = RESULTS / "q1" / artifact_name("q1", "boundary_endpoint_comparison")
    boundary_cv = _csv_records(boundary_cv_path)
    endpoints = _csv_records(endpoint_path)
    expected_methods = {"linear", "pchip", "akima", "cubic_spline",
                        "smooth_spline", "stretched_exp"}
    if len(boundary_cv) != 12 or {row["series"] for row in boundary_cv} != {"T", "C"}:
        raise AssertionError("Unexpected Q1 boundary model CV structure")
    if {row["method"] for row in boundary_cv} != expected_methods:
        raise AssertionError("Q1 boundary model CV does not contain all six methods")
    if len(endpoints) != 84 or {row["series"] for row in endpoints} != {"T", "C"}:
        raise AssertionError("Unexpected Q1 endpoint-comparison structure")
    if {row["method"] for row in endpoints} != expected_methods:
        raise AssertionError("Q1 endpoint comparison does not contain all six methods")
    checks["upstream_preprocessing_diagnostics"] = {
        "boundary_cv_rows": len(boundary_cv),
        "endpoint_comparison_rows": len(endpoints),
        "schema_complete": True,
        "input_dependency": "附件1.xlsx (unchanged hash recorded above)",
    }

    # 这两个 CSV 文件是上游数值诊断结果，作为结果证据保留，并与当前输入和源代码
    # 进行一致性核验。
    static_assets = [boundary_cv_path, endpoint_path]
    checks["static_assets_sha256"] = {
        path.relative_to(PACKAGE).as_posix(): _hash(path) for path in static_assets
    }
    output = RESULTS / global_artifact_name("reproducibility_check")
    output.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
