# A题四问整合提交包

`paper.md` 是四问合并后的论文初稿；`data/` 保存题目附件和结果模板，`code/` 保存统一求解、导出与核验程序，`results/` 保存当前已核验的数值结果，`figures/` 保存正文引用的图片（包括根目录下分开的圆柱体与 `dr` 示意图、控制体守恒示意图）。`run_all.py` 是提交包的唯一总入口，负责四问的执行顺序、边界拟合窗口、结果重建和统一核验；`code/q1`--`code/q4` 仅作为其内部的可追溯实现单元。

## 复现

在 `submit/all/` 目录执行：

```powershell
conda env create -f environment.yml       # 已有 2026modeling 环境时跳过
conda run --no-capture-output -n 2026modeling python run_all.py --quick
```

`--quick` 用较小空间网格检查程序链路。提交结果对应的完整网格、时间收紧、事件和敏感性核验使用：

```powershell
conda run --no-capture-output -n 2026modeling python run_all.py
```

完整运行会重建 `results/q1`--`results/q4` 下的 JSON、NPZ、Excel 和验证记录；预计耗时取决于机器性能。若只需重建工作簿，可运行 `python code/build_workbooks.py`；若只需检查现有结果，可运行 `python code/verify_all.py`。

完整模式使用报告对应的收敛网格：第一问 N=800、1600、3200、6400，第二问 N=200、300、400，第三、四问分别 N=220、300；边界窗口由 `run_all.py` 固定为第一问 0--1800 s、第二至第四问 0--14400 s。第二至第四问由程序分别识别温度 5280 s、水分 6780 s 的稳定点，并在各自 600 s 区间内平滑接入尾段均值，不再取共同分界点。`--quick` 仅用于快速检查链路，不替代正式结果。

## 目录约定

```text
all/
├─ paper.md                 合并论文初稿
├─ run_all.py               统一复现入口
├─ data/                    附件1、附件2及四个结果模板
├─ code/q1...q4/            四问求解器及各问专用边界工具
├─ code/build_workbooks.py  从 JSON 重建四个工作簿
├─ code/verify_all.py       独立结构、行数、哈希和事件检查
├─ results/q1...q4/         数值输出与验证记录
└─ figures/                 论文引用的结果图和有限体积示意图
```

所有脚本只读本目录下的 `data/` 以及前序步骤在 `results/` 中生成的统一中间结果，新的输出仍写入 `results/`；不依赖 `questions/A题/` 或 `submit/p1`--`submit/p4` 的外部文件。
