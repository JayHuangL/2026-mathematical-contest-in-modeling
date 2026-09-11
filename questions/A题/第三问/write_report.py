from pathlib import Path
import json
import numpy as np
HERE=Path(__file__).resolve().parent
s=json.loads((HERE/'validation.json').read_text(encoding='utf-8'))
tables=(HERE/'结果表.md').read_text(encoding='utf-8').replace('# 表5：药材烘干过程的水分浓度','### 表5：药材烘干过程的水分浓度')
grids=['| 径向区间数 | 阈值穿越时刻 / h | 与上一网格相差 / s | 60 s输出含水率最大差 |','|---:|---:|---:|---:|']
for r in s['grid_checks']:
    grids.append('| '+str(r['N'])+' | '+f"{r['event_s']/3600:.8f}"+' | '+(f"{r['event_diff_s']:.6f}" if 'event_diff_s' in r else '—')+' | '+(f"{r['max_C_diff_60s']:.3e}" if 'max_C_diff_60s' in r else '—')+' |')
sens_grid=s.get('N', s['grid_checks'][-1]['N'])
sens=[f'| 4 h后边界情景（N={sens_grid}） | 阈值时间 / h | 相对主结果的变化 / h |','|---|---:|---:|']
base=s['grid_checks'][-1]
sens.append(f"| 阶段边界主情景 | {s['event_h']:.6f} | 0 |")
for r in s['tail_sensitivity']:
    label='50°C、0.05' if r['case']=='50C_0.05' else '最后1 h记录均值'
    delta=r.get('delta_h_at_grid')
    if delta is None:
        delta=r.get('delta_h_at_N800')
    if delta is None:
        delta=(r['event_h']-s['event_h'])
    sens.append(f"| {label} | {r['event_h']:.6f} | {delta:.6f} |")
report=r"""# 第三问：烘干结束时间与全过程水分分布

采用第二问的控制方程、附录3物性及阶段边界，计算得到阈值穿越时间约为 **{{event_h}} h**。按四位小数小时向上取整后，给出满足严格“低于0.15”的烘干时长：

\[
\boxed{t_{\mathrm{结束}}={{finish_h}}\ \mathrm h}
\]

即约 **2.3994天（57小时35分12秒）**。本结果采用6030 s共同分界、600 s过渡和稳定尾段均值，长期边界敏感性见第7节。

## 1. 文件和问题目标

- [完整结果 result3.xlsx](../outputs/q3/result3.xlsx)：保持原模板Sheet1，时间以秒记录，每60 s输出一次，最后追加非整分钟结束时刻。
- [solve_q3.py](solve_q3.py)：直接导入第二问的CoupledModel，复用控制方程及Jacobian，调整径向网格并增加事件检测。
- [validation.json](validation.json)：网格、时间、环境假设及与第二问重叠区间的验证。
- [result3_full_precision.npz](result3_full_precision.npz)：未舍入的温度、含水率和平均含水率，包含0 s初值。
- [结果表.md](结果表.md)：论文表5。

第三问的新增任务是判断**所有位置**何时达标。不能只检查表面或平均含水率；也不能以问题背景中的2—3天代替实际计算。

## 2. 沿用第二问的数学模型

径向范围为\(0\le r\le R=0.02\ \mathrm m\)，未知量为\(T(r,t),C(r,t)\)。

\[
\rho(C)c_p(C)T_t
=\frac1r\frac{\partial}{\partial r}\left(rk(C)T_r\right),
\]

\[
C_t=\frac1r\frac{\partial}{\partial r}\left(rD(T,C)C_r\right).
\tag{1}
\]

全程统一采用附录3：

\[
\rho=650+128C,\qquad
c_p=1450+2736\frac{C}{C+1},
\]
\[
k=0.21+0.38\frac{C}{C+1},
\]
\[
D=2.4\times10^{-3}
\exp\left(-\frac{0.45}{C}\right)
\exp\left(-\frac{3850}{T+273.15}\right).
\tag{2}
\]

这里程序中的\(T\)以°C存储，指数使用开尔文温度。初始条件与边界条件为：

\[
T(r,0)=28,\qquad C(r,0)=2.55,
\]
\[
T_r(0,t)=C_r(0,t)=0,
\]
\[
-k(C_s)T_r(R,t)=h[T_s-T_a(t)],
\]
\[
-D(T_s,C_s)C_r(R,t)=h_m[C_s-C_a(t)],
\tag{3}
\]

其中\(h=25\ \mathrm{W/(m^2\cdot K)}\)、\(h_m=8\times10^{-7}\ \mathrm{m/s}\)。

假设与第二问一致：忽略轴向和端部影响、尺寸固定、不显式加入蒸发潜热及水分携热，环境水分浓度直接作为有效表面传质驱动力的参考量。空气与固体的kg/kg并不自动具有相同质量基准，因此这是需要声明的有效边界假设，而不是严格气固平衡关系。

### 长期环境条件

环境沿用第二问的阶段边界：

\[
(T_a(t),C_a(t))=
\begin{cases}
\text{拟合曲线与600 s过渡},&0\le t\le6330,\\
(49.934221,\ 0.04971557),&t>6330.
\end{cases}
\tag{4}
\]

6030 s是由温度和水分稳定检测结果取均值得到的阶段点；6330 s后恒定均值是长期外推假设，不是数天的实测数据。其环境参考含水率低于0.15，模型允许最终达到干燥标准。

## 3. 达标判据与时间定位

定义全域最大含水率：

\[
M(t)=\max_{0\le r\le R}C(r,t).
\]

所求阈值时刻为：

\[
t_* = \inf\{t\ge0:M(t)<0.15\}.
\tag{5}
\]

数值求解中，设置向下穿越事件：

\[
g(t,\boldsymbol y)=\max_i C_i(t)-0.15=0.
\tag{6}
\]

事件函数每次检查全部径向计算节点，不预先只检查中心。计算还验证了各接受时间步上含水率沿半径向外不增加，因此本例最湿位置确实是中心。

得到：
\[
t_*={{event_s}}\ \mathrm s={{event_h}}\ \mathrm h.
\]

事件时刻对应最大值等于0.15，是严格达标区间的边界。为了让报告的四位小数时间本身也满足“低于”，采用：

\[
t_{\mathrm{结束},h}
=\frac{\lceil10^4 t_*/3600\rceil}{10^4}
={{finish_h}}.
\tag{7}
\]

随后从事件状态继续积分到该时刻，检查所有节点均小于0.15。最终：

- 结束时刻：{{finish_s}} s。
- 最大含水率：{{final_max}} kg/kg，出现在中心。
- 平均含水率：{{final_mean}} kg/kg。

平均含水率采用圆柱体积权重：
\[
\overline C=\frac{2}{R^2}\int_0^R C(r,t)r\,\mathrm dr.
\tag{8}
\]

四位小数表中，结束时中心仍显示0.1500，结束前某些时刻也可能显示0.1500。这只是舍入结果，达标判定始终使用未舍入数值。

## 4. 数值方法与后期网格处理

继续使用第二问的通量型有限体积离散及隐式BDF积分，温度和水分全程联立求解。没有在温度接近50°C后擅自冻结温度场，也没有重置或拼接第一问状态。

随着表面含水率下降，\(\exp(-0.45/C)\)显著变小。后期表面附近会形成很陡的水分梯度，均匀网格即使含水率误差看起来很小，阈值时间仍可能相差数秒。

为此采用表面加密的平滑非均匀网格：

\[
x_i=\frac{i}{N},\qquad
r_i=R\frac{1-\exp(-4x_i)}{1-\exp(-4)},\quad i=0,\ldots,N.
\tag{9}
\]

相邻节点中点为控制体积界面，\(w_i=(b_i^2-a_i^2)/2\)。界面通量为：
\[
F^T_{i+1/2}=r_{i+1/2}\frac{k_i+k_{i+1}}2
\frac{T_{i+1}-T_i}{r_{i+1}-r_i},
\]
\[
F^C_{i+1/2}=r_{i+1/2}\frac{D_i+D_{i+1}}2
\frac{C_{i+1}-C_i}{r_{i+1}-r_i}.
\tag{10}
\]

节点时间导数仍为：
\[
\dot T_i=\frac{F^T_{i+1/2}-F^T_{i-1/2}}{w_i\rho_i c_{p,i}},
\qquad
\dot C_i=\frac{F^C_{i+1/2}-F^C_{i-1/2}}{w_i}.
\tag{11}
\]

最终采用300个区间。每0.1 cm的输出位置通过保形分段三次插值PCHIP获得。事件判断使用原始计算节点，不依赖输出插值或21个输出位置。

在0—4 h按环境数据节点分段积分，内部最大步长5 s；之后最大步长300 s，并每6 h分段保存。所有分段继承前一段末态。输出间隔60 s与内部积分步长不同，整数分钟数据由积分器连续插值获得。

## 5. 表5与过程解释

{{TABLE}}

![第三问干燥过程与径向分布](第三问结果图.png)

6 h时中心含水率仍约1.0156 kg/kg；到54 h，表面已经接近环境参考值，中心仍高于0.15。因此表面达标不等于整根药材达标。

后期含水率降低导致扩散系数变小，干燥速度减慢。这也是不能用前几小时失水速度线性外推结束时间的原因。

## 6. 数值验证

### 网格加密

{{GRIDS}}

非均匀网格加密后，最后两级的结束时间差为{{grid_last_diff}} s；主结果的阶段边界和物性敏感性见第7节。

### 时间积分与重叠区间

在最终网格上将相对/绝对容差各收紧10倍，后4 h最大步长从300 s减至120 s：
- 阈值时刻差：{{time_diff}} s。
- 全部共同分钟输出的含水率最大差：{{time_cdiff}} kg/kg。

与第二问0—3 h的共同分钟时刻比较：
- 温度最大差：{{overlap_t}}°C。
- 含水率最大差：{{overlap_c}} kg/kg。

差异来自计算网格和空间输出插值，不是更换了物理参数或初始条件。

### 收支与物理检查

另设积分变量记录表面水分交换：
\[
\dot z=\frac{2h_m}{R}(C_a-C_s),\qquad z(0)=0.
\]

检查\(\overline C-C_0-z\)的累计收支残差，最终网格最大残差为{{balance}} kg/kg。还检查了全部接受状态上的含水率正值、上界及径向单调性。此类检查验证的是离散模型一致性，不代替实测验证。

## 7. 长期环境假设的敏感性

用同一主网格对照长期边界外推：

{{SENS}}

长期边界、阶段点和扩散/传质参数造成的变化明显大于数值网格误差，因此应将“约57.59 h”理解为指定模型假设下的预测。四位小数用于题目输出，不意味着实际烘干过程已知到0.36秒。

## 8. 复现

在A题目录执行：

\x60\x60\x60powershell
python 第三问/solve_q3.py --boundary-mode staged --grids 220 300 --check-time --sensitivity
\x60\x60\x60

程序直接导入同目录下第二问的控制方程。依赖NumPy、SciPy、openpyxl、Matplotlib、threadpoolctl；不会改写第一、二问结果或原附件。

配置了\x60@oai/artifact-tool\x60后运行：
\x60\x60\x60powershell
node 第三问/build_workbook.mjs
\x60\x60\x60

结果文件保留原模板Sheet1。共{{rows}}个时间行，包含每60 s记录和最后的非整分钟结束记录；末行时间以秒保存为四位小数。温度仅保留在全精度辅助数据中，result3.xlsx按题意只填写水分浓度。
"""
values={'event_h':f"{s['event_h']:.10f}",'event_s':f"{s['event_s']:.6f}",'finish_h':f"{s['finish_h']:.4f}",'finish_s':f"{s['finish_s']:.4f}",'final_max':f"{s['final_max_C']:.12f}",'final_mean':f"{s['final_mean_C']:.8f}",'TABLE':tables,'GRIDS':'\n'.join(grids),'SENS':'\n'.join(sens),'grid_last_diff':f"{s['grid_checks'][-1]['event_diff_s']:.6f}",'time_diff':f"{s['time_check']['event_diff_s']:.6f}",'time_cdiff':f"{s['time_check']['max_C_diff']:.3e}",'overlap_t':f"{s['q2_overlap_max_diff']['T']:.3e}",'overlap_c':f"{s['q2_overlap_max_diff']['C']:.3e}",'balance':f"{s['grid_checks'][-1]['balance_error']:.3e}",'rows':str(s['output_time_rows'])}
for k,v in values.items():
    report=report.replace('{{'+k+'}}',v)
report=report.replace('\\x60','\x60')
assert '{{' not in report
(HERE/'第三问公式与求解.md').write_text(report,encoding='utf-8')
print('Report written')
