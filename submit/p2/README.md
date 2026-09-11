# A题第二问独立提交包

正文见 [p2.md](p2.md)，结果工作簿见 [result2.xlsx](result2.xlsx)。本目录从 `questions/` 与 `output/` 中整理第二问所需的输入、计算、验证和图表；不修改原始题面、附件或原第二问目录。

## 内容

- [p2.md](p2.md)：按“问题重述—问题分析—模型假设—符号—模型建立与求解—结果—验证—评价”组织的正文。
- [result2.xlsx](result2.xlsx)：温度、水分浓度两张工作表，10800个时间行、21个径向位置，数值保留四位小数。
- [solve_q2.py](solve_q2.py)：附录3变物性、阶段边界、有限体积和隐式BDF联立求解器。
- [export_result2.py](export_result2.py)：使用 `data/result2_template.xlsx` 导出结果工作簿。
- [verify_result2.py](verify_result2.py)：核对输入哈希、完整工作簿数值、正文表格和格式。
- [validation.json](validation.json)、[结果表.md](结果表.md)：主计算参数、数值验证和正文表格数据。
- [evidence/](evidence/)：边界拟合、阶段检测和第二问敏感性证据；[figures/](figures/)：相关图表。

## 复现

在本目录执行：

```powershell
conda run --no-capture-output -n 2026modeling python solve_q2.py --grids 200 300 400 --check-time
conda run --no-capture-output -n 2026modeling python export_result2.py
conda run --no-capture-output -n 2026modeling python verify_result2.py
```

模型采用附录3物性全程求解，不把第一问的1800 s状态拼接为第二问初值；6330 s之后的稳定尾段均值仅用于边界外推，相关假设已在正文中标明。
