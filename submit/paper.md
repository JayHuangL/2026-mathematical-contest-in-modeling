# 药材烘干过程的热湿耦合与移动边界模型

## 1 本文符号约定与模型假设

为避免固定边界模型、移动边界模型及数值离散中的符号发生混淆，本文将所用符号统一约定如下。除特别注明外，长度、时间和温度分别采用 m、s 和 ℃；扩散系数经验式中的绝对温度以 K 计。

### 1.1 几何、时间与运动学符号

| 符号 | 含义 | 单位或说明 |
|---|---|---|
| \(t\) | 从烘干开始计量的时间 | s |
| \(r\) | 圆柱截面内某点距中心轴的实际径向距离 | m |
| \(R\) | 固定边界模型中的药材半径 | m |
| \(R_0\) | 药材初始半径，即 \(R(0)\) | m；本题为 \(0.02\) |
| \(R(t)\) | 收缩模型中随时间变化的药材实际半径 | m |
| \(\dot R(t)\) | 半径对时间的导数，即表面径向速度 | m/s；收缩时通常小于0 |
| \(L\) | 圆柱形药材长度 | m；本题为 \(0.25\) |
| \(\xi=r/R(t)\) | 移动边界模型中的归一化材料坐标 | 无量纲，\(0\le\xi\le1\) |
| \(v(r,t)\) | 药材内部材料点的径向运动速度 | m/s |
| \(\phi(r,t)\) | 推导材料导数时使用的一般标量场 | 可代表温度或含水率 |
| \(\mathrm D\phi/\mathrm Dt\) | 沿运动材料点轨迹观察到的材料导数 | 单位为 \(\phi\) 的单位每秒 |

### 1.2 温度、含水率与状态符号

| 符号 | 含义 | 单位或说明 |
|---|---|---|
| \(T(r,t)\) | 实际径向坐标下的药材温度场 | ℃ |
| \(C(r,t)\) | 实际径向坐标下的药材干基含水率场 | kg/kg |
| \(\Theta(\xi,t)\) | 材料坐标下的温度场，满足 \(\Theta(\xi,t)=T(\xi R(t),t)\) | ℃ |
| \(U(\xi,t)\) | 材料坐标下的干基含水率场，满足 \(U(\xi,t)=C(\xi R(t),t)\) | kg/kg |
| \(T_0\) | 药材的均匀初始温度，即 \(T(r,0)=T_0\) | ℃；本题为 \(28^\circ\mathrm C\) |
| \(C_0\) | 药材的均匀初始干基含水率，即 \(C(r,0)=C_0\) | kg/kg；本题为 \(2.55\) |
| \(T_a(t)\) | 烘房空气温度，即表面对流换热的环境边界值 | ℃ |
| \(C_a(t)\) | 表面有效传质条件中的环境水分参考量 | kg/kg |
| \(T_s=T(R,t)\) | 固定边界模型中的药材表面温度 | ℃ |
| \(C_s=C(R,t)\) | 固定边界模型中的药材表面干基含水率 | kg/kg |
| \(\Theta_s=\Theta(1,t)\) | 收缩模型中移动表面处的温度 | ℃ |
| \(U_s=U(1,t)\) | 收缩模型中移动表面处的干基含水率 | kg/kg |
| \(\overline U(t)\) | 收缩模型中按干物质质量加权的平均干基含水率 | kg/kg |
| \(C_{\mathrm{cr}}\) | 药材烘干达标的临界干基含水率 | kg/kg；本题为 \(0.15\) |
| \(M(t)\) | 时刻 \(t\) 药材全域内的最大干基含水率 | kg/kg |
| \(g(t)=M(t)-C_{\mathrm{cr}}\) | 用于定位全域达标时刻的事件函数 | kg/kg |
| \(t_*\) | 全域最大含水率首次向下达到临界值的时刻 | s 或 h |

### 1.3 材料物性、通量与交换参数

| 符号 | 含义 | 单位或说明 |
|---|---|---|
| \(\rho\) 或 \(\rho(C)\) | 药材密度；变物性模型中由局部含水率决定 | kg/m³ |
| \(\rho_d\) | 单位总体积内的干物质质量 | kg/m³ |
| \(\rho_{d0}\) | 初始单位总体积内的干物质质量 | kg/m³ |
| \(c_p\) 或 \(c_p(C)\) | 药材定压比热容；变物性模型中由局部含水率决定 | J/(kg·K) |
| \(k\) 或 \(k(C)\) | 药材热传导系数；变物性模型中由局部含水率决定 | W/(m·K) |
| \(\alpha=k/(\rho c_p)\) | 常物性条件下的热扩散率 | m²/s |
| \(D\)、\(D(C)\) 或 \(D(C,T)\) | 有效水分扩散系数 | m²/s |
| \(h\) | 药材表面的对流换热系数 | W/(m²·K)；本题为 \(25\) |
| \(h_m\) | 药材表面的有效对流传质系数 | m/s；本题为 \(8\times10^{-7}\) |
| \(q_r\) | 以径向向外为正方向定义的导热通量 | W/m² |
| \(j_w\) | 以径向向外为正方向定义的水分质量通量 | kg/(m²·s) |
| \(m_w\) | 药材所含水分质量 | kg |
| \(m_d\) | 药材干物质质量 | kg |

干基含水率定义为

\[
\boxed{C=\frac{m_w}{m_d}},
\tag{1}
\]

故 \(C\) 表示水质量与干物质质量之比，而不是单位体积内的水质量。对于同一材料微团，单纯的几何压缩不会改变 \(m_w/m_d\)，因而不能按体积压缩比例直接增大 \(C\)。

### 1.4 有限体积离散与时间积分符号

| 符号 | 含义 | 单位或说明 |
|---|---|---|
| \(N\) | 径向计算区间总数 | 正整数 |
| \(i\) | 空间节点或控制体编号 | \(i=0,1,\ldots,N\) |
| \(n\) | 时间层编号 | \(n=0,1,\ldots\) |
| \(\Delta r=R/N\) | 固定半径均匀网格的空间步长 | m |
| \(r_i\) | 第 \(i\) 个实际径向节点 | m |
| \(r_{i+1/2}\) | 节点 \(i\) 与 \(i+1\) 之间的控制体界面位置 | m |
| \(\xi_i\) | 第 \(i\) 个归一化材料坐标节点 | 无量纲 |
| \(\xi_{i+1/2}\) | 相邻材料坐标节点之间的控制体界面位置 | 无量纲 |
| \(a_i,b_i\) | 第 \(i\) 个控制体的左、右边界 | 固定半径模型中为 m；材料坐标模型中无量纲 |
| \(w_i=(b_i^2-a_i^2)/2\) | 去除公共因子 \(2\pi L\) 后的圆柱径向控制体几何权重 | 固定半径模型中为 m²；材料坐标模型中无量纲 |
| \(u_i\) | 统一扩散方程在节点 \(i\) 的离散未知量 | 可代表 \(T_i\) 或 \(C_i\) |
| \(a\) 或 \(a_{i+1/2}\) | 统一扩散方程中的扩散系数及其界面值 | 温度方程中代表 \(\alpha\)，含水率方程中代表 \(D\) |
| \(F_{i+1/2}\) | 统一扩散方程在界面 \(i+1/2\) 的离散通量变量 | 单位随所离散方程而定 |
| \(F^T_{i+1/2}\) | 材料坐标下的界面导热通量变量 | W/m |
| \(F^C_{i+1/2}\) | 材料坐标下的界面水分扩散通量变量 | m²/s |
| \(F_s^T,F_s^C\) | 移动表面处的离散换热、传质通量变量 | 分别与 \(F^T,F^C\) 同单位 |
| \(\boldsymbol y(t)\) | 由全部温度和含水率节点值组成的半离散状态向量 | 混合单位向量 |
| \(\boldsymbol f(t,\boldsymbol y)\) | 半离散常微分方程组的右端函数 | 与对应状态量每秒同单位 |
| \(\boldsymbol J=\partial\boldsymbol f/\partial\boldsymbol y\) | 隐式时间积分所用的稀疏Jacobian矩阵 | 各元素单位由对应变量决定 |
| \(\Delta t\) | 时间积分步长 | s |
| \(\boldsymbol y^n,\boldsymbol y^{n+1}\) | 第 \(n\)、\(n+1\) 个时间层的状态向量 | 与 \(\boldsymbol y\) 相同 |

下标 \(0\) 表示初始状态或中心节点，下标 \(a\) 表示环境边界，下标 \(s\) 表示药材表面，下标 \(d\) 表示干物质；下标 \(i\) 表示空间节点，\(i+1/2\) 表示相邻节点之间的控制体界面。上标 \(n\) 表示离散时间层，上横线表示空间平均，变量上方的点表示对时间求导。偏导记号 \(T_t,T_r,T_{rr}\) 分别是 \(\partial T/\partial t\)、\(\partial T/\partial r\)、\(\partial^2T/\partial r^2\) 的简写，其他场变量采用相同约定。

### 1.5 模型假设

1. 药材为均匀、各向同性的圆柱体，初始温度和含水率均匀。
2. 烘干条件沿圆周方向均匀；忽略轴向传热、轴向传质和端部效应，只研究圆柱中段截面的一维径向状态。
3. 固定边界问题中药材半径保持不变；移动边界问题中长度保持不变，药材沿径向均匀收缩，材料点的相对坐标 \(\xi=r/R(t)\) 保持不变。
4. 忽略蒸发潜热、水分迁移携热、内部热源和变形功，将药材内部水分迁移等效为扩散过程。
5. 表面采用有限速率的对流换热边界和有效传质边界；\(C_a(t)\) 作为有效传质驱动力的环境参考量，不额外建立严格的气固相平衡关系。

## 2 问题1模型建立与求解

### 2.1 问题1模型建立

问题1研究固定半径药材在预热阶段的温度与含水率分布。根据傅里叶定律，沿径向向外的导热通量为

\[
q_r=-k\frac{\partial T}{\partial r}.
\]

取半径为 \(r\)、厚度为 \(\mathrm dr\)、长度为 \(L\) 的微小圆环。由能量守恒，控制体内能的增加率等于导热净流入量：

\[
\rho c_p(2\pi rL\,\mathrm dr)\frac{\partial T}{\partial t}
=-\frac{\partial}{\partial r}(2\pi rLq_r)\,\mathrm dr.
\]

代入傅里叶定律并约去公共因子，得到圆柱径向热传导方程

\[
\boxed{
\rho c_p\frac{\partial T}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left(rk\frac{\partial T}{\partial r}\right)
},\qquad 0<r<R.
\tag{2}
\]

问题1中 \(\rho\)、\(c_p\)、\(k\) 均为常数。令热扩散率 \(\alpha=k/(\rho c_p)\)，式（2）也可写为

\[
\frac{\partial T}{\partial t}
=\alpha\left(
\frac{\partial^2T}{\partial r^2}
+\frac1r\frac{\partial T}{\partial r}
\right).
\]

对于水分迁移，设单位体积干物质质量为 \(\rho_d\)，根据菲克定律定义径向水分质量通量

\[
j_w=-\rho_dD(C)\frac{\partial C}{\partial r}.
\]

对同一圆环应用水分质量守恒，并假设 \(\rho_d\) 在空间上均匀，可得

\[
\boxed{
\frac{\partial C}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rD(C)\frac{\partial C}{\partial r}\right]
},\qquad 0<r<R,
\tag{3}
\]

其中问题1的有效水分扩散系数为

\[
D(C)=7\times10^{-9}\exp\left(-\frac{0.89}{C}\right).
\]

由于 \(D\) 随含水率变化，式（3）展开后为

\[
\frac{\partial C}{\partial t}
=D(C)\left(
\frac{\partial^2C}{\partial r^2}
+\frac1r\frac{\partial C}{\partial r}
\right)
+D'(C)\left(\frac{\partial C}{\partial r}\right)^2,
\qquad
D'(C)=\frac{0.89}{C^2}D(C).
\]

因此，不能简单地把 \(D(C)\) 提到微分算子之外；数值求解应保留式（3）的守恒通量形式。

药材初始状态均匀，初始条件为

\[
T(r,0)=T_0,\qquad C(r,0)=C_0.
\]

圆柱中心满足轴对称条件

\[
\left.\frac{\partial T}{\partial r}\right|_{r=0}=0,
\qquad
\left.\frac{\partial C}{\partial r}\right|_{r=0}=0.
\]

表面采用有限速率的对流换热和有效传质边界：

\[
\boxed{
-k\left.\frac{\partial T}{\partial r}\right|_{r=R}
=h[T(R,t)-T_a(t)],
\qquad
-D(C_s)\left.\frac{\partial C}{\partial r}\right|_{r=R}
=h_m[C(R,t)-C_a(t)]
}.
\tag{4}
\]

当空气温度高于药材表面温度时，热量由环境传入药材；当药材表面含水率高于环境参考值时，水分由药材向外迁移。问题1中温度方程的系数不依赖含水率，水分扩散系数也不依赖温度，因此两个场可分别求解。

### 2.2 问题1数值求解

采用径向有限体积法离散空间。将区间 \([0,R]\) 划分为 \(N\) 个小区间：

\[
r_i=i\Delta r,\qquad \Delta r=\frac RN,\qquad i=0,1,\ldots,N.
\]

节点 \(r_i\) 对应一个环状控制体，左右边界分别记为 \(a_i,b_i\)。约去圆柱体积中的公共因子 \(2\pi L\) 后，控制体几何权重为

\[
w_i=\int_{a_i}^{b_i}r\,\mathrm dr
=\frac{b_i^2-a_i^2}{2}.
\]

对统一形式

\[
u_t=\frac1r\frac{\partial}{\partial r}(ra u_r)
\]

乘以 \(r\)，并在第 \(i\) 个控制体上积分，得到

\[
w_i\frac{\mathrm du_i}{\mathrm dt}
=F_{i+1/2}-F_{i-1/2},
\]

其中内部界面通量变量采用中心差分：

\[
F_{i+1/2}
=r_{i+1/2}a_{i+1/2}
\frac{u_{i+1}-u_i}{\Delta r}.
\]

对于温度方程，\(u=T\)、\(a=\alpha\)；对于水分方程，\(u=C\)、\(a=D(C)\)，界面扩散系数取相邻节点值的平均。中心通量取 \(F_{-1/2}=0\)，表面交换条件直接作为最外侧控制体的边界通量。于是半离散方程为

\[
\boxed{
\frac{\mathrm du_i}{\mathrm dt}
=\frac{F_{i+1/2}-F_{i-1/2}}{w_i}
}.
\tag{5}
\]

这种写法无需在 \(r=0\) 处直接计算 \(1/r\)，并且相邻控制体共享同一界面通量，内部通量求和时两两抵消，保证离散收支一致。

空间离散后，偏微分方程转化为常微分方程组

\[
\frac{\mathrm d\boldsymbol y}{\mathrm dt}
=\boldsymbol f(t,\boldsymbol y).
\]

由于细网格扩散系统具有刚性，时间方向采用自适应隐式BDF方法。以一阶BDF为例，

\[
\frac{\boldsymbol y^{n+1}-\boldsymbol y^n}{\Delta t}
=\boldsymbol f(t_{n+1},\boldsymbol y^{n+1}).
\]

右端含有新时刻未知量，因此每个时间步通过隐式迭代求解。计算中提供稀疏Jacobian矩阵，以提高迭代效率。

## 3 问题2模型建立与求解

### 3.1 问题2模型建立

问题2仍采用固定半径的一维圆柱径向模型，但材料物性随局部状态变化。各物性关系为

\[
\rho(C)=650+128C,
\]

\[
c_p(C)=1450+2736\frac{C}{C+1},
\qquad
k(C)=0.21+0.38\frac{C}{C+1},
\]

\[
D(C,T)=2.4\times10^{-3}
\exp\left(-\frac{0.45}{C}\right)
\exp\left[-\frac{3850}{T+273.15}\right].
\]

扩散系数经验式中的温度必须使用绝对温度，因此当 \(T\) 以 ℃ 表示时应代入 \(T+273.15\)。

将上述物性代入问题1的守恒型控制方程，得到问题2的非线性热湿耦合模型：

\[
\boxed{
\rho(C)c_p(C)\frac{\partial T}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rk(C)\frac{\partial T}{\partial r}\right]
},
\tag{6}
\]

\[
\boxed{
\frac{\partial C}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rD(C,T)\frac{\partial C}{\partial r}\right]
}.
\tag{7}
\]

含水率通过 \(\rho(C)\)、\(c_p(C)\)、\(k(C)\) 影响温度场，温度和含水率又共同决定 \(D(C,T)\)，因此二者形成双向耦合。变系数必须保留在散度算子内部。例如

\[
\frac1r\frac{\partial}{\partial r}(rkT_r)
=k\left(T_{rr}+\frac1rT_r\right)+k_rT_r,
\]

若直接把 \(k\) 提到算子外，将遗漏 \(k_rT_r\) 项。问题2采用与问题1相同的初始条件、中心对称条件及表面交换条件，但其中局部物性均按当前状态更新。

### 3.2 问题2数值求解

问题2继续采用式（5）的有限体积框架。在界面 \(i+1/2\) 处分别计算

\[
F^T_{i+1/2}
=r_{i+1/2}k_{i+1/2}
\frac{T_{i+1}-T_i}{\Delta r},
\]

\[
F^C_{i+1/2}
=r_{i+1/2}D_{i+1/2}
\frac{C_{i+1}-C_i}{\Delta r},
\]

其中 \(k_{i+1/2}\) 和 \(D_{i+1/2}\) 由相邻节点当前物性确定。温度方程和含水率方程的半离散形式为

\[
\rho_i c_{p,i}w_i\frac{\mathrm dT_i}{\mathrm dt}
=F^T_{i+1/2}-F^T_{i-1/2},
\]

\[
w_i\frac{\mathrm dC_i}{\mathrm dt}
=F^C_{i+1/2}-F^C_{i-1/2}.
\]

将全部节点温度和含水率组成统一状态向量

\[
\boldsymbol y=
\begin{bmatrix}
\boldsymbol T\\
\boldsymbol C
\end{bmatrix},
\]

再用隐式BDF方法联立推进。每次计算方程右端时，均使用当前 \(T_i,C_i\) 重新计算 \(\rho_i,c_{p,i},k_i,D_i\)，而不是用全域平均状态代替局部物性。Jacobian矩阵同时包含温度内部、水分内部以及热湿交叉导数，因此能够反映耦合关系。

## 4 问题3模型建立与求解

### 4.1 问题3模型建立

问题3不再建立新的传热传质方程，而是沿用问题2的固定半径耦合模型，并将积分时间延长至药材全部位置达到干燥标准。定义时刻 \(t\) 的全域最大含水率

\[
M(t)=\max_{0\le r\le R}C(r,t).
\]

题目要求所有位置的干基含水率均低于临界值 \(C_{\mathrm{cr}}=0.15\)，故达标时间定义为

\[
\boxed{
t_*=\inf\left\{t\ge0:
\max_{0\le r\le R}C(r,t)<C_{\mathrm{cr}}
\right\}.
}
\tag{8}
\]

该判据使用全域最大值，而不是表面含水率或体积平均含水率。中心通常是最湿位置，但数值计算仍检查全部空间节点，避免在未经验证时直接把达标条件简化为中心条件。

### 4.2 问题3数值求解

在问题2的BDF积分过程中构造事件函数

\[
g(t)=\max_i C_i(t)-C_{\mathrm{cr}}.
\]

只检测 \(g(t)\) 从正值向负值的穿越。当一次时间步的两端出现符号变化时，求解器利用连续插值在该时间步内部定位 \(g(t)=0\) 的根，从而得到临界时刻 \(t_*\)。因此，达标时间的定位精度由时间积分误差控制决定，而不受结果文件固定输出间隔限制。

题目使用“低于”临界值。为避免阈值相等和数值显示舍入造成歧义，计算中使用未舍入含水率判定，并在临界根之后继续推进至最终报告时刻，确认所有节点均满足 \(C_i<C_{\mathrm{cr}}\)。

## 5 问题4模型建立与求解

### 5.1 移动边界与材料运动

问题4考虑药材收缩，物理区域变为

\[
0\le r\le R(t).
\]

假设药材长度不变并沿径向均匀收缩，材料点的相对径向位置保持不变。对相对位置为 \(\xi\) 的材料点，有

\[
r(t)=\xi R(t).
\]

对时间求导，得到内部材料速度

\[
\boxed{
v(r,t)=\frac{\mathrm dr}{\mathrm dt}
=\xi\dot R(t)
=\frac{\dot R(t)}{R(t)}r.
}
\tag{9}
\]

对于同时依赖空间和时间的一般场量 \(\phi(r,t)\)，沿材料点轨迹使用多元复合函数的链式法则：

\[
\frac{\mathrm d}{\mathrm dt}\phi(r(t),t)
=\frac{\partial\phi}{\partial t}
+\frac{\mathrm dr}{\mathrm dt}\frac{\partial\phi}{\partial r}.
\]

由此定义材料导数

\[
\frac{\mathrm D\phi}{\mathrm Dt}
=\frac{\partial\phi}{\partial t}
+v\frac{\partial\phi}{\partial r}.
\]

其中，第一项表示固定空间位置处的局部变化，第二项表示材料运动到不同位置造成的变化。用材料导数描述收缩材料内部状态，实际空间中的控制方程为

\[
\rho c_p(T_t+vT_r)
=\frac1r\frac{\partial}{\partial r}(rkT_r),
\]

\[
C_t+vC_r
=\frac1r\frac{\partial}{\partial r}(rDC_r).
\]

因此，只把固定边界模型中的常数 \(R\) 改成 \(R(t)\) 并不充分，还必须处理内部材料运动。

### 5.2 移动区域到固定区域的映射

为避免不断移动计算网格，引入归一化材料坐标

\[
\boxed{
\xi=\frac r{R(t)},\qquad 0\le\xi\le1,
}
\tag{10}
\]

并定义

\[
\Theta(\xi,t)=T(\xi R(t),t),
\qquad
U(\xi,t)=C(\xi R(t),t).
\]

固定实际位置 \(r\) 时，

\[
\left.\frac{\partial\xi}{\partial t}\right|_r
=-\frac{\xi\dot R}{R}.
\]

由链式法则，

\[
\left.C_t\right|_r
=U_t-\frac{\xi\dot R}{R}U_\xi,
\qquad
C_r=\frac1R U_\xi.
\]

结合 \(v=\xi\dot R\)，有

\[
vC_r=\frac{\xi\dot R}{R}U_\xi,
\]

所以坐标运动项和材料运动项恰好抵消：

\[
C_t+vC_r=U_t.
\]

同理，

\[
T_t+vT_r=\Theta_t.
\]

变换后不再显式出现 \(\dot R\)，是因为坐标 \(\xi\) 跟随均匀收缩的材料运动，并非忽略了收缩速度。

又因为

\[
\frac{\partial}{\partial r}
=\frac1R\frac{\partial}{\partial\xi},
\]

扩散算子可变换为

\[
\frac1r\frac{\partial}{\partial r}(rkT_r)
=\frac1{R^2\xi}\frac{\partial}{\partial\xi}
(\xi k\Theta_\xi),
\]

\[
\frac1r\frac{\partial}{\partial r}(rDC_r)
=\frac1{R^2\xi}\frac{\partial}{\partial\xi}
(\xi DU_\xi).
\]

因此，固定材料坐标区域上的移动边界模型为

\[
\boxed{
\rho(U)c_p(U)\Theta_t
=\frac1{R(t)^2\xi}
\frac{\partial}{\partial\xi}
\left[\xi k(U)\Theta_\xi\right],
}
\tag{11}
\]

\[
\boxed{
U_t
=\frac1{R(t)^2\xi}
\frac{\partial}{\partial\xi}
\left[\xi D(\Theta,U)U_\xi\right].
}
\tag{12}
\]

其中 \(1/R(t)^2\) 反映了药材收缩后实际扩散距离缩短。

### 5.3 第四问物性、初始条件与边界条件

第四问采用新的局部物性关系：

\[
\rho(U)=760+90U,
\]

\[
c_p(U)=1850+2150\frac{U}{U+1},
\qquad
k(U)=0.12+0.20\frac{U}{U+1},
\]

\[
D(\Theta,U)=4.2\times10^{-4}
\exp\left(-\frac{0.30}{U}\right)
\exp\left[-\frac{3850}{\Theta+273.15}\right].
\]

初始条件与中心对称条件为

\[
\Theta(\xi,0)=T_0,\qquad U(\xi,0)=C_0,
\]

\[
\Theta_\xi(0,t)=0,\qquad U_\xi(0,t)=0.
\]

由于 \(T_r=\Theta_\xi/R\)、\(C_r=U_\xi/R\)，移动表面 \(\xi=1\) 处的交换条件为

\[
\boxed{
-\frac{k(U_s)}{R(t)}\Theta_\xi(1,t)
=h[\Theta_s-T_a(t)],
\qquad
-\frac{D(\Theta_s,U_s)}{R(t)}U_\xi(1,t)
=h_m[U_s-C_a(t)].
}
\tag{13}
\]

内部方程中的 \(1/R^2\) 和边界梯度中的 \(1/R\) 均由同一坐标变换产生，必须同时保留。

### 5.4 干基含水率的移动区域守恒

含水率定义为 \(U=m_w/m_d\)，纯粹缩小材料体积不会自动改变水质量与干物质质量之比。长度不变且干物质总质量守恒时，

\[
\rho_d(t)\pi R(t)^2L
=\rho_{d0}\pi R_0^2L,
\]

从而

\[
\rho_d(t)=\rho_{d0}\frac{R_0^2}{R(t)^2}.
\]

材料坐标下的平均干基含水率为

\[
\overline U(t)=2\int_0^1U(\xi,t)\xi\,\mathrm d\xi.
\]

对式（12）乘以 \(2\xi\) 并在 \([0,1]\) 上积分，再利用中心零通量和表面传质条件，得到整体收支关系

\[
\boxed{
\frac{\mathrm d\overline U}{\mathrm dt}
=\frac{2h_m}{R(t)}[C_a(t)-U_s].
}
\tag{14}
\]

该式表明平均含水率的变化完全由表面传质通量决定，可用于检查移动边界离散的守恒一致性。

### 5.5 问题4数值求解与实际位置输出

在固定区间 \([0,1]\) 上建立表面加密网格：

\[
\xi_i=
\frac{1-\exp(-4i/N)}{1-\exp(-4)},
\qquad i=0,1,\ldots,N.
\]

控制体几何权重仍为

\[
w_i=\frac{b_i^2-a_i^2}{2}.
\]

内部界面通量变量分别取

\[
F^T_{i+1/2}
=\xi_{i+1/2}\frac{k_i+k_{i+1}}2
\frac{\Theta_{i+1}-\Theta_i}{\xi_{i+1}-\xi_i},
\]

\[
F^C_{i+1/2}
=\xi_{i+1/2}\frac{D_i+D_{i+1}}2
\frac{U_{i+1}-U_i}{\xi_{i+1}-\xi_i}.
\]

由式（13），表面通量变量为

\[
F_s^T=R(t)h[T_a(t)-\Theta_s],
\qquad
F_s^C=R(t)h_m[C_a(t)-U_s].
\]

最终的半离散方程为

\[
\boxed{
\frac{\mathrm d\Theta_i}{\mathrm dt}
=\frac{F^T_{i+1/2}-F^T_{i-1/2}}
{R(t)^2w_i\rho_i c_{p,i}},
\qquad
\frac{\mathrm dU_i}{\mathrm dt}
=\frac{F^C_{i+1/2}-F^C_{i-1/2}}
{R(t)^2w_i}.
}
\tag{15}
\]

温度和含水率仍采用隐式BDF法联立推进。每次计算方程右端时，根据当前时间更新 \(R(t)\)，并根据当前节点状态更新全部局部物性。达标时间仍通过

\[
\max_iU_i(t)-C_{\mathrm{cr}}=0
\]

的向下穿越事件确定。

计算结果位于材料坐标 \(\xi_i\) 上，而题目要求给出固定实际距离 \(r_j\) 处的状态。时刻 \(t\) 的对应关系为

\[
\xi_j(t)=\frac{r_j}{R(t)}.
\]

仅当 \(r_j\le R(t)\) 时，该位置仍位于药材内部，可计算

\[
C(r_j,t)=U\left(\frac{r_j}{R(t)},t\right).
\]

若 \(r_j>R(t)\)，该位置已位于药材外部，结果应留空，不能填零或向区域外插。移动表面值始终由 \(U(1,t)\) 给出。
