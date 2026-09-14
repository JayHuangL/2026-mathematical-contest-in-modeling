"""从一个入口复现 A 题的完整计算流程。

默认模式使用论文中报告的网格和核验项。``--quick`` 保持相同的方程和输出格式，
但使用更小的网格执行隔离式冒烟测试。数值产物保存在 ``results/``，论文图像写入
``figures/``。
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
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
from artifact_names import FIGURE_NAMES, figure_name

# 提交包四个问题共用的边界窗口约定。
# 第一问是早期时段的辨识问题。第二至第四问使用附件1的完整记录，分别检测稳定阶段
# 并估计尾段均值；每条拉伸指数分支只拟合到各自的过渡点，再接入 1800 s 过渡段和
# 恒定尾段。
Q1_FIT_ENDPOINT_S = 1800.0


def run(script: Path, *args: str) -> None:
    command = [sys.executable, str(script), *args]
    print("+", " ".join(command), flush=True)
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    subprocess.run(command, cwd=PACKAGE, check=True, env=env)


def run_isolated_quick() -> None:
    """在临时副本中执行冒烟测试，以保持正式结果不变。"""
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
    print("临时副本中的快速冒烟测试通过；正式结果未被修改。",
          flush=True)


def check_main_figures() -> None:
    missing = []
    for question, figure_keys in FIGURE_NAMES.items():
        figure_folder = FIGURES / question
        figure_folder.mkdir(parents=True, exist_ok=True)
        for key in figure_keys:
            name = figure_name(question, key)
            figure_path = figure_folder / name
            if not figure_path.exists():
                missing.append(str(figure_path))
    if missing:
        raise FileNotFoundError(f"Missing generated figures: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="使用较小网格运行冒烟测试")
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
        # 这些是论文核验记录所使用的正式网格。
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
    if args.quick:
        run(CODE / "q2" / "run_sensitivity.py", "--grid", "100")
    else:
        run(CODE / "q2" / "run_sensitivity.py", "--grid", "200")
    run(CODE / "q2" / "export_result2.py")
    run(CODE / "q3" / "solve_q3.py", "--grids", *map(str, q3_grids),
        "--boundary-mode", "staged", *common, *q3_extra)
    run(CODE / "q4" / "solve_q4.py", "--grids", *map(str, q4_grids),
        "--boundary-mode", "staged", *common, *q4_extra)
    run(CODE / "build_workbooks.py")
    check_main_figures()
    run(CODE / "q2" / "verify_result2.py")
    run(CODE / "q3" / "verify_result3.py")
    run(CODE / "q4" / "verify_result4.py")
    run(CODE / "verify_all.py")
    print("Integrated reproduction completed under", RESULTS)


if __name__ == "__main__":
    main()
