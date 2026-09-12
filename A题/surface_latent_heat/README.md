# 表面潜热与物理建模探索

最新结论见 [相变潜热渐进建模：结果比较与可行性](physical_exploration/探索结果与可行性.md)。

- [建模方法、公式与假设](physical_exploration/建模方法与假设.md)：湿度解释、相平衡边界、混合物焓与局部体积收缩。
- [对比图](physical_exploration/模型逐级对比.png)：温度、干燥过程、半径与解吸关系敏感性。
- [验证结果](physical_exploration/validation.json)：守恒、网格、容差、独立求积及早期供热/收缩相容性。
- [计算脚本](explore_physics.py)、[分析脚本](analyze_exploration.py)：运行方式见方法说明。

原始 `run_surface_latent.py` 与 `results/` 是早先“保持原水分边界、仅扣表面潜热”的模型形式敏感性对照，本轮未修改。

新探索消除了部分物理矛盾，但尚未获得足以替换正式答案的实验验证。具体时长都是带有新增假设的情景值。
