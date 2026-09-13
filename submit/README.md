# A题可复现提交附件

本目录是 A 题的代码、输入数据、结果数据、图片和环境配置附件，不包含论文 DOCX。所有脚本均以本目录为根目录解析路径，可以脱离 `questions\A题\` 和根目录论文单独运行。

## 数据和结果边界

`data\` 中只有两份原始数据：

- `附件1.xlsx`：烘房温度和环境水分浓度记录。
- `附件2.xlsx`：药材半径记录。

`data\result1_template.xlsx` 至 `data\result4_template.xlsx` 是题目要求的结果模板，不是原始观测数据。求解产生的 JSON、NPZ、CSV 和验证记录按问题写入 `results\q1` 至 `results\q4`，四个结果工作簿写入 `results\` 顶层，模型图片统一写入 `figures\`。

## 环境

推荐使用本机已有的 Conda 环境 `2026modeling`：

```powershell
conda run --no-capture-output -n 2026modeling python --version
```

`environment.yml` 记录了该环境所需的 Python、NumPy、SciPy、Matplotlib、OpenPyXL 和 Threadpoolctl 版本约束。若本机尚未创建该环境，可执行：

```powershell
conda env create -f environment.yml
```

## 复现命令

以下命令均在 `submit\` 目录执行。

### 快速链路检查

```powershell
conda run --no-capture-output -n 2026modeling python run_all.py --quick
```

`--quick` 会将提交包复制到系统临时目录，用较小网格检查四问求解、工作簿导出、图片生成和验证链路；正式 `results\` 和 `figures\` 不会被覆盖，临时副本由程序自动清理。

### 正式四问复现

```powershell
conda run --no-capture-output -n 2026modeling python run_all.py
```

正式运行使用论文对应的网格和时间精度设置，重建 `results\q1` 至 `results\q4` 的数值文件、`results\result1.xlsx` 至 `results\result4.xlsx` 四个结果工作簿、验证记录和代码生成图片。运行时间取决于机器性能。

第六节的数值收敛、参数敏感性和长期边界扰动表依赖四问正式结果，正式四问运行完成后再执行：

```powershell
conda run --no-capture-output -n 2026modeling python code\p6\run_p6.py
conda run --no-capture-output -n 2026modeling python code\p6\verify_p6.py
```

### 单独导出和核验

```powershell
conda run --no-capture-output -n 2026modeling python code\build_workbooks.py
conda run --no-capture-output -n 2026modeling python code\verify_all.py
```

`build_workbooks.py` 从 `results\q1` 至 `results\q4` 的 JSON 结果重建顶层的 `results\result1.xlsx` 至 `results\result4.xlsx`。`verify_all.py` 检查输入哈希、数组形状、工作簿表头和行数、工作簿与 JSON 数值一致性、终止阈值、图片和旧文件名残留。

## 目录结构

```text
submit/
├─ README.md
├─ environment.yml
├─ run_all.py
├─ data/
│  ├─ 附件1.xlsx
│  ├─ 附件2.xlsx
│  └─ result1_template.xlsx ... result4_template.xlsx
├─ code/
│  ├─ q1/ ... q4/       四问求解器、导出器和专项核验器
│  ├─ p6/               第六节三类误差表的生成与核验
│  ├─ build_workbooks.py
│  ├─ kirchhoff_flux.py
│  └─ verify_all.py
├─ results/
│  ├─ result1.xlsx ... result4.xlsx  四问结果工作簿（顶层）
│  ├─ q1/ ... q4/       四问 JSON、NPZ、CSV 和验证记录
│  └─ p6/               第六节 CSV 表和摘要 JSON
└─ figures/
   ├─ q1/ ... q4/       四问结果图和诊断图
```

`results\` 不放 Markdown、PNG 等展示文件；展示图片只放在 `figures\`。运行产生的 Python 缓存目录不属于提交内容。
