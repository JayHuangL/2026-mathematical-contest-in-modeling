"""Lightweight independent checks for the integrated submission package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import openpyxl


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
DATA = PACKAGE / "data"
RESULTS = PACKAGE / "results"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_check(question: str, expected_rows: int, keys: tuple[str, ...]) -> dict:
    folder = RESULTS / question
    payload = json.loads((folder / f"result{question[1:]}_data.json").read_text(encoding="utf-8"))
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
    payload = json.loads((folder / f"result{question[1:]}_data.json").read_text(encoding="utf-8"))
    book = openpyxl.load_workbook(folder / f"result{question[1:]}.xlsx", data_only=True, read_only=True)
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
        "q1_workbook": _workbook_shape(RESULTS / "q1" / "result1.xlsx", ["温度", "水分浓度"], 1800, 22),
        "q2_workbook": _workbook_shape(RESULTS / "q2" / "result2.xlsx", ["温度", "水分浓度"], 10800, 22),
        "q3_workbook": _workbook_shape(RESULTS / "q3" / "result3.xlsx", ["Sheet1"], 3461, 22),
        "q4_workbook": _workbook_shape(RESULTS / "q4" / "result4.xlsx", ["Sheet1"], 3077, 22),
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
        validation = json.loads((RESULTS / question / "validation.json").read_text(encoding="utf-8"))
        if validation_key not in validation:
            raise AssertionError(f"{question}: missing validation field {validation_key}")
    q4 = json.loads((RESULTS / "q4" / "validation.json").read_text(encoding="utf-8"))
    if q4.get("radius_extrapolation_used"):
        raise AssertionError("q4: radius extrapolation unexpectedly used")
    with np.load(RESULTS / "q3" / "result3_full_precision.npz") as q3_full:
        if not float(np.max(q3_full["C"][-1])) < 0.15:
            raise AssertionError("q3: final state is not strictly below the threshold")
    with np.load(RESULTS / "q4" / "result4_full_precision.npz") as q4_full:
        if not float(np.nanmax(q4_full["C"][-1])) < 0.15:
            raise AssertionError("q4: final state is not strictly below the threshold")
    checks["input_sha256"] = {
        "附件1.xlsx": _hash(DATA / "附件1.xlsx"),
        "附件2.xlsx": _hash(DATA / "附件2.xlsx"),
    }
    output = RESULTS / "reproducibility_check.json"
    output.write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
