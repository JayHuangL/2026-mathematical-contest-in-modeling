# A题第三问提交包

本目录是第三问的提交材料。正文按当前 submit/p1/p1.md 的论文写法组织，并吸收 docs/25B优秀论文.pdf 的“摘要—问题分析—模型假设—符号—模型建立与求解—结果—可靠性分析”结构。优秀论文仅作为结构参考，不借用其题面数据或物理模型。

## 主结论

在附录3变物性、固定半径、阶段边界和有效 Robin 传质边界下：

- 原始阈值事件：57.5865978968 h；
- 按四位小数小时向上取整的提交时间：57.5866 h；
- 报告时刻未舍入最大含水率：0.1499999978 kg/kg，位置为中心；
- 报告时刻体积平均含水率：0.12430315 kg/kg。

## 文件

- p3.md：第三问正文，含模型、求解、表5、图和验证结论。
- result3.xlsx：题目要求的结果工作簿，保留 Sheet1，每 60 s、每 0.1 cm 输出。
- 结果表.md：表5摘要。
- 第三问结果图.png：干燥过程和径向分布图。
- validation.json：本目录主结果的边界、网格、时间和收支验证。
- result3_data.json、result3_full_precision.npz：四位小数和未舍入结果。
- solve_q3.py、verify_result3.py、build_workbook.mjs：复现、导出和校验脚本。
- source/：随包保存的当前第二问求解器、边界处理程序、附件1和结果模板。

## 源文件口径

主表来自 questions/A题/第三问 的表面加密有限体积实现，并在本目录使用当前 questions/A题/第二问/solve_q2.py 重新运行，避免旧结果验证哈希失效。output/A题深化分析/q3_selected.json 是全题深度分析中的均匀网格辅助诊断，事件时刻不同于本目录主网格结果；它被整理为补充敏感性_均匀网格诊断.csv，不参与主表生成。

## 复现

在项目根目录执行：

~~~powershell
conda run --no-capture-output -n 2026modeling python submit\p3\solve_q3.py --grids 220 300 --check-time --sensitivity --boundary-mode staged
node submit\p3\build_workbook.mjs
conda run --no-capture-output -n 2026modeling python submit\p3\verify_result3.py
~~~

第一条命令只更新本目录的计算结果；第二条命令根据本目录的 JSON 和 source/附件/附件3/result3.xlsx 重建工作簿；第三条命令检查输入哈希、结果数组、表格时间轴、数值格式和严格低于阈值条件。

result3.xlsx 已在本目录完成重建和校验。build_workbook.mjs 使用当前工作区提供的 Artifact Tool 运行环境；若在没有该运行环境的机器上复现，只需保留已生成的 result3.xlsx，或先配置相应的 Node 依赖。
