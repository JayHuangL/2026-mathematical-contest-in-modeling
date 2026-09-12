"""Reproduce the integrated A-problem calculations from one entry point.

Default mode uses the grids and checks reported in the paper.  ``--quick``
keeps the same equations and output formats but uses smaller grids for an
isolated smoke test.  Numerical artifacts stay under ``results/``; the paper
figures are synchronized into ``figures/``.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
CODE = PACKAGE / "code"
RESULTS = PACKAGE / "results"
FIGURES = PACKAGE / "figures"

# Boundary-window contract for the submitted four-question package.
# Q1 is an early-time identification problem.  Q2--Q4 use the complete
# Attachment-1 record to detect independent stability transitions and estimate
# tail means, but fit each stretched-exponential branch only up to its own
# transition point before adding an 1800 s blend and constant tail.
Q1_FIT_ENDPOINT_S = 1800.0


def run(script: Path, *args: str) -> None:
    command = [sys.executable, str(script), *args]
    print("+", " ".join(command), flush=True)
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    subprocess.run(command, cwd=PACKAGE, check=True, env=env)


def run_isolated_quick() -> None:
    """Run the smoke test in a disposable copy so formal results stay intact."""
    with tempfile.TemporaryDirectory(prefix="solo_math_modeling_quick_") as temp:
        quick_package = Path(temp) / PACKAGE.name
        shutil.copytree(
            PACKAGE,
            quick_package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        command = [sys.executable, str(quick_package / "run_all.py"),
                   "--quick", "--_isolated-quick"]
        print("+", " ".join(command), flush=True)
        env = os.environ.copy()
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        subprocess.run(command, cwd=quick_package, check=True, env=env)
    print("Quick smoke test passed in a temporary copy; formal results were not changed.",
          flush=True)


def copy_main_figures() -> None:
    mapping = {
        "q1": ["图05_第一问温度水分场.png", "图01_原始环境边界散点.png",
               "图02_拉伸指数最终拟合.png"],
        "q2": ["图10_第二问温度水分场.png", "图06_边界独立稳定分界.png",
               "图07_分段环境边界拟合.png"],
        "q3": ["图11_第三问干燥结果.png"],
        "q4": ["图14_第四问收缩水分场.png", "图12_半径原始散点.png",
               "图13_半径插值方法比较.png"],
    }
    for question, names in mapping.items():
        for name in names:
            source = RESULTS / question / name
            if source.exists():
                shutil.copy2(source, FIGURES / question / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="run a smaller smoke-test grid")
    parser.add_argument("--_isolated-quick", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.quick and not args._isolated_quick:
        run_isolated_quick()
        return

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
        "--boundary-mode", "staged", *common)
    run(CODE / "q2" / "export_result2.py")
    run(CODE / "q3" / "solve_q3.py", "--grids", *map(str, q3_grids),
        "--boundary-mode", "staged", *common, *q3_extra)
    run(CODE / "q4" / "solve_q4.py", "--grids", *map(str, q4_grids),
        "--boundary-mode", "staged", *common, *q4_extra)
    run(CODE / "build_workbooks.py")
    copy_main_figures()
    run(CODE / "q3" / "verify_result3.py")
    run(CODE / "q4" / "verify_result4.py")
    run(CODE / "verify_all.py")
    print("Integrated reproduction completed under", RESULTS)


if __name__ == "__main__":
    main()
