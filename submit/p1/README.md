# 第一问独立提交包

本目录是 A 题第一问的独立提交目录。最终正文见 [p1.md](p1.md)；总体论文 [../paper.md](../paper.md) 仅作为背景参考，本次整理没有修改它。原始题面与附件也没有被修改。

## 内容

- [p1.md](p1.md)：第一问的题意、假设、`stretched_exp` 边界拟合、控制方程、数值方法、结果和误差分析。
- [solve_q1.py](solve_q1.py)：读取 `data/附件1.xlsx`，拟合环境边界并求解径向温度和含水率。
- [export_result1.py](export_result1.py)：将 `result1_data.json` 导出为题目要求的 `result1.xlsx`。
- [result1.xlsx](result1.xlsx)：1800 个时间行、21 个径向位置的最终结果工作簿。
- [validation.json](validation.json)、[boundary_cv.csv](boundary_cv.csv)、[boundary_endpoint_comparison.csv](boundary_endpoint_comparison.csv)：拟合、终点选择、网格、时间步长和守恒验证记录。
- `figures/` 与 [第一问结果图.png](第一问结果图.png)：拟合比较和模型结果图。
- `data/附件1.xlsx`：本问使用的边界观测数据；`data/result1_template.xlsx`：结果工作簿模板。

## 复现

在本目录执行：

```powershell
conda run --no-capture-output -n 2026modeling python solve_q1.py --check-time --sensitivity-grid 800
conda run --no-capture-output -n 2026modeling python export_result1.py
```

第一条命令生成数值结果、验证记录和图表；第二条命令使用本目录模板生成 `result1.xlsx`。环境依赖为 `numpy`、`scipy`、`matplotlib` 和 `openpyxl`，已在 `2026modeling` 环境中验证；依赖清单见 [requirements.txt](requirements.txt) 和 [environment.yml](environment.yml)。
