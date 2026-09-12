# 参考文献资料索引

本目录收集与 `submit/paper.md` 建模及数值求解直接相关的参考资料。PDF 文件均已检查为有效 PDF。引用时应以原论文题名、期刊和 DOI 为准。

## 建议优先引用

| 文件 | 主要内容 | 适合支撑的论文内容 |
|---|---|---|
| `05_Shampine_Reichelt_1997_MATLAB_ODE_Suite.pdf` | 刚性常微分方程、BDF/NDF、变阶与步长调整、误差控制、Jacobian | 空间离散后形成刚性常微分方程组；采用自适应隐式 BDF；利用 Jacobian 提高隐式迭代效率 |
| `01_SUNDIALS_CVODES_2005.pdf` | 变步长、变阶 BDF，局部误差控制，Newton 迭代及 Jacobian | 对“自适应隐式 BDF”的算法机制作补充说明 |
| `02_Eymard_Gallouet_Herbin_2000_Finite_Volume_Methods.pdf` | 有限体积法、控制体积分、界面通量与局部守恒 | 径向有限体积离散、共享界面通量和离散守恒 |
| `03_Fritsch_Butland_1984_PCHIP.pdf` | 局部单调、保形分段三次 Hermite 插值 | 半径序列与非均匀网格输出采用 PCHIP，避免普通三次样条过冲 |
| `04_Tuly_et_al_2023_Jackfruit_Drying_Shrinkage.pdf` | 考虑收缩的热质传递干燥模型及数值模拟 | 热湿耦合、含水率扩散、对流边界以及收缩对干燥过程的影响 |

## 与本文写法的关系

1. Shampine 和 Reichelt 的论文最接近本文实际使用的 SciPy BDF 实现基础。SciPy 的 BDF 求解器采用 1—5 阶变阶方法、准恒定步长策略，并含 NDF 精度修正。因此正文宜写“自适应隐式 BDF 方法”，不宜声称程序始终采用固定阶数或固定时间步长。
2. Serban 和 Hindmarsh 给出了变步长、变阶 BDF 的误差控制与非线性方程求解结构，可用于解释每个隐式时间步为什么需要 Newton 类迭代和 Jacobian。
3. Eymard 等人的综述强调有限体积法从控制体守恒出发，通过界面通量连接相邻控制体。这与本文圆柱径向权重和共享通量的写法一致。
4. Fritsch–Butland 方法是 SciPy `PchipInterpolator` 内部导数选择的重要理论来源，适合支撑“保形、避免非物理过冲”的表述。
5. Tuly 等人的开放获取论文可作为干燥收缩模型的应用文献。本文的模型更简化，因此引用时宜表述为“已有研究常通过耦合热质传递方程分析收缩对干燥过程的影响”，不应写成本文完整复现了其多物理模型。

## 在线来源

- Shampine & Reichelt: <https://doi.org/10.1137/S1064827594276424>
- Serban & Hindmarsh: <https://computing.llnl.gov/sites/default/files/asme_cvodes.pdf>
- Eymard, Gallouët & Herbin: <https://doi.org/10.1016/S1570-8659(00)07005-8>
- Fritsch & Butland: <https://doi.org/10.1137/0905021>
- Tuly et al.: <https://doi.org/10.3390/en16114461>
- SciPy BDF 官方说明（网页，未下载）：<https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html>

完整 BibTeX 见 `references.bib`。
