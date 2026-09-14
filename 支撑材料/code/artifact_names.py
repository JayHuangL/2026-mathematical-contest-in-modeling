"""一体化提交代码生成的结果文件统一命名。

题目附件和结果工作簿模板保留原始名称。本模块只统一命名数值结果、诊断数据
和图像，确保所有求解器与核验器遵循同一套文件约定。
"""
from __future__ import annotations

from pathlib import Path


ARTIFACT_NAMES = {
    "q1": {
        "workbook": "result1.xlsx",
        "result_data": "q1_result_data.json",
        "full_precision": "q1_result_full_precision.npz",
        "validation": "q1_validation.json",
        "boundary_cv": "q1_boundary_model_cv.csv",
        "boundary_endpoint_comparison": "q1_boundary_endpoint_comparison.csv",
    },
    "q2": {
        "workbook": "result2.xlsx",
        "result_data": "q2_result_data.json",
        "full_precision": "q2_result_full_precision.npz",
        "validation": "q2_validation.json",
        "parameter_sensitivity": "q2_parameter_sensitivity.json",
        "validation_export": "q2_validation_export.json",
    },
    "q3": {
        "workbook": "result3.xlsx",
        "result_data": "q3_result_data.json",
        "full_precision": "q3_result_full_precision.npz",
        "validation": "q3_validation.json",
        "validation_export": "q3_validation_export.json",
    },
    "q4": {
        "workbook": "result4.xlsx",
        "result_data": "q4_result_data.json",
        "full_precision": "q4_result_full_precision.npz",
        "validation": "q4_validation.json",
        "validation_export": "q4_validation_export.json",
        "radius_method_comparison": "q4_radius_method_comparison.csv",
    },
}


FIGURE_NAMES = {
    "q1": {
        "boundary_raw": "q1_fig_01_boundary_raw_scatter.png",
        "boundary_fit": "q1_fig_02_boundary_stretched_exp_fit.png",
        "temperature_moisture_field": "q1_fig_03_temperature_moisture_field.png",
    },
    "q2": {
        "boundary_stability": "q2_fig_01_boundary_stability_detection.png",
        "boundary_staged_fit": "q2_fig_02_staged_boundary_fit.png",
        "parameter_sensitivity": "q2_fig_03_parameter_sensitivity.png",
        "temperature_moisture_field": "q2_fig_04_temperature_moisture_field.png",
    },
    "q3": {
        "drying_result": "q3_fig_01_drying_result.png",
    },
    "q4": {
        "radius_raw": "q4_fig_01_radius_raw_scatter.png",
        "radius_pchip_fit": "q4_fig_02_radius_pchip_fit.png",
        "shrinkage_moisture_field": "q4_fig_03_shrinkage_moisture_field.png",
    },
}


GLOBAL_ARTIFACT_NAMES = {
    "reproducibility_check": "reproducibility_check.json",
}


def artifact_name(question: str, key: str) -> str:
    """返回指定问题产物的统一文件名。"""
    try:
        return ARTIFACT_NAMES[question][key]
    except KeyError as exc:
        raise KeyError(f"Unknown artifact name: {question}/{key}") from exc


def workbook_path(results_root: Path, question: str) -> Path:
    """返回结果工作簿在提交包顶层的路径。"""
    return results_root / artifact_name(question, "workbook")


def figure_name(question: str, key: str) -> str:
    """返回生成图像的统一文件名。"""
    try:
        return FIGURE_NAMES[question][key]
    except KeyError as exc:
        raise KeyError(f"Unknown figure name: {question}/{key}") from exc


def global_artifact_name(key: str) -> str:
    """返回提交包级产物的统一文件名。"""
    try:
        return GLOBAL_ARTIFACT_NAMES[key]
    except KeyError as exc:
        raise KeyError(f"Unknown global artifact name: {key}") from exc
