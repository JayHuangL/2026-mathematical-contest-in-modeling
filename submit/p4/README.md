# A题问题4提交包

本目录是问题4的独立整理包，正文见 [p4.md](p4.md)，结果工作簿见 [result4.xlsx](result4.xlsx)。主方案与 `submit/p1` 采用同一类环境边界处理：附件1使用初值固定拉伸指数拟合，并在检测到稳定阶段后过渡到尾段均值；问题4再叠加附件2的 PCHIP 半径和附录4物性。

## 主结果

- 未舍入全域达标时刻：51.1866332388 h。
- 按题目格式向上保留四位小数：**51.1867 h**。
- 报告时刻半径：1.2000 cm。
- 报告时刻全域最大干基含水率：0.149999876864 kg/kg。

## 目录内容

- `p4.md`：论文式正文、公式、表6、结果分析和验证。
- `result4.xlsx`：每 60 s、每 0.1 cm 的完整结果；药材外位置为空，末列为药材表面。
- `solve_q4.py`、`boundary_stage.py`：求解器和边界处理代码。
- `build_workbook.py`：从题目模板重建工作簿。
- `verify_result4.py`、`validation_export.json`：工作簿逐单元核验。
- `validation.json`：网格、时间、Jacobian、收支和控制变量检查。
- `result4_data.json`、`result4_full_precision.npz`：舍入数据和未舍入计算状态。
- `第四问结果图.png`、`figures/03_radius_methods.png`：主结果图和半径插值诊断图。

原始题面和附件保留在 `questions/A题/`，本目录不修改它们。默认运行路径为工作区根目录；也可以进入本目录后省略 `--root` 和 `--out`。

## 复现

```powershell
conda run --no-capture-output -n 2026modeling python questions/p4/solve_q4.py --root questions/A题 --out questions/p4 --grids 200 300 --check-time --comparisons --boundary-mode staged --radius-method pchip
conda run --no-capture-output -n 2026modeling python questions/p4/build_workbook.py --root questions/A题
conda run --no-capture-output -n 2026modeling python questions/p4/verify_result4.py --root questions/A题
```

`output/A题深化分析/q4_selected.json` 中的原始边界对照结果不作为本包的主结果；本包只采用与 `p1` 一致的阶段化环境边界，避免混合不同输入协议。
