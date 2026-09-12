"""Reproduce the integrated A-problem calculations from one entry point.

Default mode uses the grids and checks reported in the paper.  ``--quick``
keeps the same equations and output formats but uses smaller grids for a
smoke test.  All generated artifacts stay under ``results/``.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
CODE = PACKAGE / "code"
RESULTS = PACKAGE / "results"
FIGURES = PACKAGE / "figures"

# Boundary-window contract for the submitted four-question package.
# Q1 is an early-time identification problem; Q2--Q4 share the full
# Attachment-1 fit and replace temperature/moisture with their own constant
# tails after independently detected stability transitions.
Q1_FIT_ENDPOINT_S = 1800.0
FULL_ATTACHMENT_FIT_ENDPOINT_S = 14400.0


def run(script: Path, *args: str) -> None:
    command = [sys.executable, str(script), *args]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=PACKAGE, check=True)


def copy_main_figures() -> None:
    mapping = {
        "q1": ["第一问结果图.png", "01_raw_environment_scatter.png",
               "02_selected_stretched_exp_fit.png"],
        "q2": ["第二问结果图.png", "边界独立分界图.png"],
        "q3": ["第三问结果图.png"],
        "q4": ["第四问结果图.png"],
    }
    for question, names in mapping.items():
        for name in names:
            source = RESULTS / question / name
            if source.exists():
                shutil.copy2(source, FIGURES / question / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="run a smaller smoke-test grid")
    args = parser.parse_args()

    if args.quick:
        q1_grids, q2_grids, q3_grids, q4_grids = [200, 400], [100, 200], [100, 200], [100, 200]
        common = []
        q1_extra = ["--skip-sensitivity"]
        q3_extra = []
        q4_extra = []
    else:
        # These are the formal grids used by the reported validation records.
        q1_grids, q2_grids = [800, 1600, 3200, 6400], [200, 300, 400]
        q3_grids, q4_grids = [220, 300], [200, 300]
        common = ["--check-time"]
        q1_extra = ["--sensitivity-grid", "800"]
        q3_extra = ["--sensitivity"]
        q4_extra = ["--comparisons"]

    run(CODE / "q1" / "solve_q1.py", "--grids", *map(str, q1_grids),
        "--fit-window-s", str(int(Q1_FIT_ENDPOINT_S)), *common, *q1_extra)
    run(CODE / "q1" / "export_result1.py")
    run(CODE / "q2" / "solve_q2.py", "--grids", *map(str, q2_grids),
        "--boundary-mode", "staged",
        "--fit-endpoint-s", str(int(FULL_ATTACHMENT_FIT_ENDPOINT_S)), *common)
    run(CODE / "q2" / "export_result2.py")
    run(CODE / "q3" / "solve_q3.py", "--grids", *map(str, q3_grids),
        "--boundary-mode", "staged",
        "--fit-endpoint-s", str(int(FULL_ATTACHMENT_FIT_ENDPOINT_S)), *common, *q3_extra)
    run(CODE / "q4" / "solve_q4.py", "--grids", *map(str, q4_grids),
        "--boundary-mode", "staged",
        "--fit-endpoint-s", str(int(FULL_ATTACHMENT_FIT_ENDPOINT_S)), *common, *q4_extra)
    run(CODE / "build_workbooks.py")
    copy_main_figures()
    run(CODE / "verify_all.py")
    print("Integrated reproduction completed under", RESULTS)


if __name__ == "__main__":
    main()
