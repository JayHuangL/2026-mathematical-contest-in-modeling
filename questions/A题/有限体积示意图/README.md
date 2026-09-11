# 径向有限体积离散示意图

本目录用于生成 A 题热湿耦合模型中的径向有限体积离散示意图。脚本不依赖题目数据，运行后直接将高清 PNG 和矢量 PDF 写入提交包的 `submit/all/figures/`。

在仓库根目录执行：

```powershell
conda run --no-capture-output -n 2026modeling python "questions/A题/有限体积示意图/plot_fvm_schematic.py"
```

也可以指定其他输出目录：

```powershell
conda run --no-capture-output -n 2026modeling python "questions/A题/有限体积示意图/plot_fvm_schematic.py" --output-dir "path/to/output"
```

脚本输出两张图：`圆柱体与dr示意图.png/.pdf` 单独展示圆柱体及顶部径向层厚 `dr`；`有限体积离散示意图.png/.pdf` 将环形控制体、`dr_i`、界面通量和相邻控制体的守恒平衡合并展示。
