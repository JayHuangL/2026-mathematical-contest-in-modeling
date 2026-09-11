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


def _payload_check(question: str, expected_rows: int, key: str = "C") -> dict:
    folder = RESULTS / question
    payload = json.loads((folder / f"result{question[1:]}_data.json").read_text(encoding="utf-8"))
    times = payload["t_s"]
    values = payload[key]
    if len(times) != expected_rows or len(values) != expected_rows:
        raise AssertionError(f"{question}: wrong output row count")
    if any(len(row) != 21 for row in values):
        raise AssertionError(f"{question}: wrong radial column count")
    return {"rows": len(times), "radial_columns": len(values[0]), "payload": True}


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


def main() -> None:
    checks = {
        "q1": _payload_check("q1", 1800, "T"),
        "q2": _payload_check("q2", 10800, "T"),
        "q3": _payload_check("q3", 3461),
        "q4": _payload_check("q4", 3077),
        "q1_workbook": _workbook_shape(RESULTS / "q1" / "result1.xlsx", ["温度", "水分浓度"], 1800, 22),
        "q2_workbook": _workbook_shape(RESULTS / "q2" / "result2.xlsx", ["温度", "水分浓度"], 10800, 22),
        "q3_workbook": _workbook_shape(RESULTS / "q3" / "result3.xlsx", ["Sheet1"], 3461, 22),
        "q4_workbook": _workbook_shape(RESULTS / "q4" / "result4.xlsx", ["Sheet1"], 3077, 22),
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
