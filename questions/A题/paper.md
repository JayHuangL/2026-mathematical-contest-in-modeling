# 药材烘干过程的热湿耦合与移动边界模型

## 1 模型假设与符号说明

为描述圆柱形药材在烘干过程中的温度和含水率变化，将药材视为均匀、各向同性的圆柱体。假设烘干条件沿圆周方向均匀，并忽略轴向传热、轴向传质及端部效应，因而只研究圆柱中段截面上的一维径向变化。固定边界问题的计算区域为 \(0\le r\le R\)，其中 \(r\) 为距圆柱中心的径向距离，\(R\) 为药材半径；考虑收缩时，计算区域变为 \(0\le r\le R(t)\)。此外，模型忽略蒸发潜热、水分迁移携热、内部热源和变形功，将复杂的水分迁移过程等效为扩散过程。

主要符号如下：\(t\) 为时间，单位为 s；\(T(r,t)\) 为药材温度，单位为 ℃；\(C(r,t)\) 为药材干基含水率，单位为 kg/kg；\(\rho\) 为密度，单位为 kg/m³；\(c_p\) 为比热容，单位为 J/(kg·K)；\(k\) 为热传导系数，单位为 W/(m·K)；\(D\) 为有效水分扩散系数，单位为 m²/s；\(h\) 和 \(h_m\) 分别为表面对流换热系数和有效对流传质系数；\(T_a(t)\) 和 \(C_a(t)\) 分别表示烘房空气温度和环境水分参考量。

干基含水率定义为

\[
\boxed{C=\frac{m_w}{m_d}},
\tag{1}
\]

其中，\(m_w\) 为水的质量，\(m_d\) 为干物质质量。因此，\(C\) 并不是单位体积内的水质量，药材体积缩小时也不能直接按体积压缩比例增大 \(C\)。

## 2 固定边界条件下的基础模型

### 2.1 圆柱径向热传导方程

根据傅里叶定律，沿径向向外的导热通量为

\[
q_r=-k\frac{\partial T}{\partial r}.
\tag{2}
\]

取半径为 \(r\)、厚度为 \(\mathrm dr\)、长度为 \(L\) 的微小圆环。其内、外表面积分别近似为 \(2\pi rL\) 和 \(2\pi(r+\mathrm dr)L\)。由能量守恒，控制体内能的增加率等于导热净流入量，即

\[
\rho c_p(2\pi rL\,\mathrm dr)\frac{\partial T}{\partial t}
=-\frac{\partial}{\partial r}(2\pi rLq_r)\,\mathrm dr.
\tag{3}
\]

将式（2）代入式（3），约去公共因子 \(2\pi L\,\mathrm dr\)，得到圆柱径向热传导方程

\[
\boxed{
\rho c_p\frac{\partial T}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left(rk\frac{\partial T}{\partial r}\right)
},\qquad 0<r<R.
\tag{4}
\]

当 \(k\)、\(\rho\)、\(c_p\) 均为常数时，定义热扩散率

\[
\alpha=\frac{k}{\rho c_p},
\tag{5}
\]

式（4）可写为

\[
\boxed{
\frac{\partial T}{\partial t}
=\alpha\left(
\frac{\partial^2T}{\partial r^2}
+\frac1r\frac{\partial T}{\partial r}
\right)
}.
\tag{6}
\]

### 2.2 水分扩散方程

设单位体积干物质质量为 \(\rho_d\)，按照菲克定律定义径向水分质量通量

\[
j_w=-\rho_dD\frac{\partial C}{\partial r}.
\tag{7}
\]

在 \(\rho_d\) 空间均匀且不随水分迁移改变的假设下，对圆环控制体应用水分质量守恒，有

\[
\rho_d\frac{\partial C}{\partial t}
=-\frac1r\frac{\partial}{\partial r}(rj_w).
\tag{8}
\]

代入式（7）并约去 \(\rho_d\)，得到有效水分扩散方程

\[
\boxed{
\frac{\partial C}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left(rD\frac{\partial C}{\partial r}\right)
},\qquad 0<r<R.
\tag{9}
\]

第一问中，扩散系数由局部含水率决定：

\[
\boxed{
D(C)=7\times10^{-9}\exp\left(-\frac{0.89}{C}\right)
}.
\tag{10}
\]

由于 \(D\) 不是常数，利用乘积求导法则展开式（9）可得

\[
\frac{\partial C}{\partial t}
=D(C)\left(
\frac{\partial^2C}{\partial r^2}
+\frac1r\frac{\partial C}{\partial r}
\right)
+D'(C)\left(\frac{\partial C}{\partial r}\right)^2,
\tag{11}
\]

其中

\[
D'(C)=\frac{0.89}{C^2}D(C).
\tag{12}
\]

式（11）表明，若将变系数 \(D(C)\) 简单移到微分算子之外，将遗漏最后一项。因此，后续数值计算保留式（9）的守恒通量形式。

### 2.3 初始条件和边界条件

药材初始温度与含水率均匀，故初始条件为

\[
\boxed{
T(r,0)=T_0,\qquad C(r,0)=C_0
},\qquad 0\le r\le R.
\tag{13}
\]

由于圆柱中心处不存在优先的径向方向，根据轴对称性有

\[
\boxed{
\left.\frac{\partial T}{\partial r}\right|_{r=0}=0,
\qquad
\left.\frac{\partial C}{\partial r}\right|_{r=0}=0
}.
\tag{14}
\]

在药材表面，采用第三类边界条件描述药材与空气之间的有限速率交换：

\[
\boxed{
-k\left.\frac{\partial T}{\partial r}\right|_{r=R}
=h[T(R,t)-T_a(t)]
},
\tag{15}
\]

\[
\boxed{
-D\left.\frac{\partial C}{\partial r}\right|_{r=R}
=h_m[C(R,t)-C_a(t)]
}.
\tag{16}
\]

式（15）由表面导热通量与空气对流换热通量连续得到；式（16）将药材与环境之间的含水状态差作为有效传质驱动力。当环境温度高于药材表面温度时，热量流入药材；当药材表面含水率高于环境参考值时，水分由药材向外迁移。

## 3 变物性热湿耦合模型

第二问和第三问中，材料物性随局部含水率和温度改变：

\[
\rho(C)=650+128C,
\tag{17}
\]

\[
c_p(C)=1450+2736\frac{C}{C+1},
\tag{18}
\]

\[
k(C)=0.21+0.38\frac{C}{C+1},
\tag{19}
\]

\[
\boxed{
D(C,T)=2.4\times10^{-3}
\exp\left(-\frac{0.45}{C}\right)
\exp\left[-\frac{3850}{T+273.15}\right]
}.
\tag{20}
\]

式（20）的绝对温度必须使用 K，故当程序以 ℃ 存储温度时，应采用 \(T+273.15\)。将上述局部物性代入式（4）和式（9），得到

\[
\boxed{
\rho(C)c_p(C)\frac{\partial T}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rk(C)\frac{\partial T}{\partial r}\right]
},
\tag{21}
\]

\[
\boxed{
\frac{\partial C}{\partial t}
=\frac1r\frac{\partial}{\partial r}
\left[rD(C,T)\frac{\partial C}{\partial r}\right]
}.
\tag{22}
\]

式（21）中，含水率通过 \(\rho\)、\(c_p\)、\(k\) 影响温度场；式（22）中，温度和含水率共同决定水分扩散系数。因此，温度场与含水率场形成双向耦合，必须在每个空间位置和每个时间步按当前状态更新物性并联立求解。特别地，当 \(k\) 随位置变化时，存在

\[
\frac1r\frac{\partial}{\partial r}(rkT_r)
=k\left(T_{rr}+\frac1rT_r\right)+k_rT_r,
\tag{23}
\]

故不能将 \(k\) 直接提出空间微分算子。对 \(D(C,T)\) 亦然。

## 4 全域干燥达标时间

第三问沿用式（17）—（22）的固定半径耦合模型。题目要求药材所有位置的含水率均低于阈值 \(C_{\mathrm{cr}}=0.15\)，因此定义全域最大含水率

\[
M(t)=\max_{0\le r\le R}C(r,t).
\tag{24}
\]

进入达标状态的临界时刻定义为

\[
\boxed{
t_*=\inf\left\{t\ge0:M(t)<C_{\mathrm{cr}}\right\}
}.
\tag{25}
\]

数值求解时构造事件函数

\[
g(t)=M(t)-C_{\mathrm{cr}}.
\tag{26}
\]

当 \(g(t)\) 从正值向下穿越零点时，说明全域最大含水率达到阈值。求解器在相邻时间步之间定位 \(g(t)=0\) 的根，而不是将固定输出间隔直接作为时间定位精度。严格判断“低于”阈值时，应使用未舍入结果，并取零点之后的时刻作为最终结束时刻。

## 5 收缩条件下的移动边界模型

### 5.1 材料速度和材料导数

第四问中药材半径随时间变化，物理区域为

\[
0\le r\le R(t).
\tag{27}
\]

假设药材沿径向均匀收缩、长度不变，并且材料点的相对径向位置保持不变。对于相对位置为 \(\xi\) 的材料点，有

\[
r(t)=\xi R(t).
\tag{28}
\]

对时间求导得到该材料点的径向速度

\[
\boxed{
v(r,t)=\frac{\mathrm dr}{\mathrm dt}
=\xi\dot R(t)
=\frac{\dot R(t)}{R(t)}r
}.
\tag{29}
\]

对于同时依赖空间和时间的场量 \(\phi(r,t)\)，沿运动材料点轨迹的变化率由多元复合函数链式法则给出：

\[
\frac{\mathrm d}{\mathrm dt}\phi(r(t),t)
=\frac{\partial\phi}{\partial t}
+\frac{\mathrm dr}{\mathrm dt}\frac{\partial\phi}{\partial r}.
\tag{30}
\]

定义材料导数

\[
\boxed{
\frac{\mathrm D\phi}{\mathrm Dt}
=\frac{\partial\phi}{\partial t}
+v\frac{\partial\phi}{\partial r}
}.
\tag{31}
\]

其中，\(\partial\phi/\partial t\) 表示固定空间位置处的局部变化率，\(v\partial\phi/\partial r\) 表示材料点运动到不同空间位置造成的变化率，二者之和才是同一材料颗粒实际经历的时间变化率。

用材料导数代替静止介质中的局部时间导数，移动区域上的控制方程为

\[
\boxed{
\rho c_p\left(T_t+vT_r\right)
=\frac1r\frac{\partial}{\partial r}(rkT_r)
},
\tag{32}
\]

\[
\boxed{
C_t+vC_r
=\frac1r\frac{\partial}{\partial r}(rDC_r)
}.
\tag{33}
\]

这里的速度项描述药材收缩所引起的材料运动。如果仅在固定边界方程中将常数 \(R\) 改为 \(R(t)\)，却不处理材料运动，则模型与均匀收缩假设不一致。

### 5.2 移动区域到固定区域的坐标变换

为避免计算网格随半径不断移动，引入归一化材料坐标

\[
\boxed{
\xi=\frac r{R(t)},\qquad 0\le\xi\le1
}.
\tag{34}
\]

并定义

\[
\Theta(\xi,t)=T(\xi R(t),t),
\qquad
U(\xi,t)=C(\xi R(t),t).
\tag{35}
\]

其中，\(\xi=0\) 始终对应圆柱中心，\(\xi=1\) 始终对应移动表面。由于固定实际位置 \(r\) 时 \(\xi=r/R(t)\)，有

\[
\left.\frac{\partial\xi}{\partial t}\right|_r
=-\frac{r\dot R}{R^2}
=-\frac{\xi\dot R}{R}.
\tag{36}
\]

根据链式法则，含水率的局部时间导数和空间导数分别为

\[
\left.C_t\right|_r
=U_t-\frac{\xi\dot R}{R}U_\xi,
\qquad
C_r=\frac1R U_\xi.
\tag{37}
\]

由式（29）可得

\[
vC_r
=\xi\dot R\frac1R U_\xi
=\frac{\xi\dot R}{R}U_\xi.
\tag{38}
\]

因此，式（37）中的坐标运动项与式（38）中的材料运动项相互抵消：

\[
\boxed{
C_t+vC_r=U_t
}.
\tag{39}
\]

同理可得

\[
\boxed{
T_t+vT_r=\Theta_t
}.
\tag{40}
\]

变换后的方程没有显式的 \(\dot R\) 项，并非忽略了收缩速度，而是因为坐标 \(\xi\) 跟随均匀收缩的材料运动。

再由

\[
\frac{\partial}{\partial r}
=\frac1R\frac{\partial}{\partial\xi}
\tag{41}
\]

可得

\[
\frac1r\frac{\partial}{\partial r}
\left(rkT_r\right)
=\frac1{R^2\xi}\frac{\partial}{\partial\xi}
\left(\xi k\Theta_\xi\right),
\tag{42}
\]

\[
\frac1r\frac{\partial}{\partial r}
\left(rDC_r\right)
=\frac1{R^2\xi}\frac{\partial}{\partial\xi}
\left(\xi DU_\xi\right).
\tag{43}
\]

最终得到固定计算区域 \(0\le\xi\le1\) 上的移动边界模型：

\[
\boxed{
\rho(U)c_p(U)\Theta_t
=\frac1{R(t)^2\xi}\frac{\partial}{\partial\xi}
\left[\xi k(U)\Theta_\xi\right]
},
\tag{44}
\]

\[
\boxed{
U_t
=\frac1{R(t)^2\xi}\frac{\partial}{\partial\xi}
\left[\xi D(\Theta,U)U_\xi\right]
}.
\tag{45}
\]

式（44）和式（45）中的 \(1/R(t)^2\) 反映实际扩散距离随收缩而缩短。

### 5.3 第四问物性及边界条件

第四问采用的局部物性为

\[
\rho(U)=760+90U,
\tag{46}
\]

\[
c_p(U)=1850+2150\frac{U}{U+1},
\qquad
k(U)=0.12+0.20\frac{U}{U+1},
\tag{47}
\]

\[
\boxed{
D(\Theta,U)=4.2\times10^{-4}
\exp\left(-\frac{0.30}{U}\right)
\exp\left[-\frac{3850}{\Theta+273.15}\right]
}.
\tag{48}
\]

固定材料坐标下的初始条件和中心对称条件为

\[
\boxed{
\Theta(\xi,0)=T_0,
\qquad U(\xi,0)=C_0
},
\tag{49}
\]

\[
\boxed{
\Theta_\xi(0,t)=0,
\qquad U_\xi(0,t)=0
}.
\tag{50}
\]

将 \(T_r=\Theta_\xi/R\) 和 \(C_r=U_\xi/R\) 代入实际表面的交换条件，得到 \(\xi=1\) 处

\[
\boxed{
-\frac{k(U_s)}{R(t)}\Theta_\xi(1,t)
=h[\Theta_s-T_a(t)]
},
\tag{51}
\]

\[
\boxed{
-\frac{D(\Theta_s,U_s)}{R(t)}U_\xi(1,t)
=h_m[U_s-C_a(t)]
},
\tag{52}
\]

其中，\(\Theta_s=\Theta(1,t)\)、\(U_s=U(1,t)\) 分别为移动表面处的温度和含水率。内部方程中的 \(1/R^2\) 与边界梯度中的 \(1/R\) 来自同一坐标变换，必须同时保留。

### 5.4 收缩条件下的含水率守恒

均匀径向收缩且长度不变时，干物质总质量守恒。若初始单位体积干物质质量为 \(\rho_{d0}\)，则

\[
\rho_d(t)\pi R(t)^2L
=\rho_{d0}\pi R_0^2L,
\tag{53}
\]

从而

\[
\rho_d(t)=\rho_{d0}\frac{R_0^2}{R(t)^2}.
\tag{54}
\]

由于 \(U=m_w/m_d\)，纯几何压缩不会自动改变 \(U\)。归一化坐标下的干基平均含水率为

\[
\boxed{
\overline U(t)=2\int_0^1U(\xi,t)\xi\,\mathrm d\xi
}.
\tag{55}
\]

对式（45）乘以 \(2\xi\) 并在 \([0,1]\) 上积分，结合中心零通量条件和式（52），得到

\[
\frac{\mathrm d\overline U}{\mathrm dt}
=\frac{2}{R^2}
\left[\xi DU_\xi\right]_{0}^{1}
=\boxed{
\frac{2h_m}{R(t)}[C_a(t)-U_s]
}.
\tag{56}
\]

式（56）说明，药材平均含水率的变化完全由表面传质通量决定，也为数值计算提供了整体收支检验。

## 6 有限体积离散与时间积分

### 6.1 固定半径问题的空间离散

对固定半径问题，将 \([0,R]\) 划分为 \(N\) 个区间，节点为

\[
r_i=i\Delta r,qquad \Delta r=\frac RN,qquad i=0,1,\ldots,N.
\tag{57}
\]

节点 \(r_i\) 对应的环状控制体积左右边界分别为 \(a_i\) 和 \(b_i\)，去掉公共因子 \(2\pi L\) 后的体积权重为

\[
\boxed{
w_i=\int_{a_i}^{b_i}r\,\mathrm dr
=\frac{b_i^2-a_i^2}{2}
}.
\tag{58}
\]

对统一扩散方程

\[
u_t=\frac1r\frac{\partial}{\partial r}(ra u_r)
\tag{59}
\]

乘以 \(r\)，并在第 \(i\) 个控制体积上积分：

\[
w_i\frac{\mathrm du_i}{\mathrm dt}
=\left.ra u_r\right|_{b_i}
-\left.ra u_r\right|_{a_i}.
\tag{60}
\]

在相邻节点中点定义界面通量变量

\[
\boxed{
F_{i+1/2}
=r_{i+1/2}a_{i+1/2}
\frac{u_{i+1}-u_i}{\Delta r}
},
\tag{61}
\]

其中，变系数情形采用相邻节点系数的界面平均值。于是半离散方程为

\[
\boxed{
\frac{\mathrm du_i}{\mathrm dt}
=\frac{F_{i+1/2}-F_{i-1/2}}{w_i}
}.
\tag{62}
\]

中心边界通量取 \(F_{-1/2}=0\)，从而自动避免在 \(r=0\) 处除以零。表面换热和传质条件直接作为最外侧控制体积的边界通量。有限体积法使相邻控制体积共享同一界面通量，将全部离散方程求和时内部通量两两抵消，因此具有明确的离散守恒性。

### 6.2 移动边界问题的空间离散

对第四问，在固定区间 \([0,1]\) 上建立 \(\xi\) 网格。为提高表面梯度的分辨能力，可采用表面加密网格

\[
\boxed{
\xi_i=
\frac{1-\exp(-4i/N)}{1-\exp(-4)},
\qquad i=0,1,\ldots,N
}.
\tag{63}
\]

控制体积权重仍为

\[
w_i=\frac{b_i^2-a_i^2}{2},
\tag{64}
\]

温度和含水率的内部界面通量分别离散为

\[
F^T_{i+1/2}
=\xi_{i+1/2}\frac{k_i+k_{i+1}}2
\frac{\Theta_{i+1}-\Theta_i}{\xi_{i+1}-\xi_i},
\tag{65}
\]

\[
F^C_{i+1/2}
=\xi_{i+1/2}\frac{D_i+D_{i+1}}2
\frac{U_{i+1}-U_i}{\xi_{i+1}-\xi_i}.
\tag{66}
\]

根据式（51）和式（52），表面通量变量为

\[
F_s^T=R(t)h[T_a(t)-\Theta_s],
\qquad
F_s^C=R(t)h_m[C_a(t)-U_s].
\tag{67}
\]

因此，移动边界模型的半离散方程为

\[
\boxed{
\frac{\mathrm d\Theta_i}{\mathrm dt}
=\frac{F^T_{i+1/2}-F^T_{i-1/2}}
{R(t)^2w_i\rho_i c_{p,i}}
},
\tag{68}
\]

\[
\boxed{
\frac{\mathrm dU_i}{\mathrm dt}
=\frac{F^C_{i+1/2}-F^C_{i-1/2}}
{R(t)^2w_i}
}.
\tag{69}
\]

### 6.3 隐式BDF时间积分

空间离散后，温度和含水率组成状态向量

\[
\boldsymbol y(t)=
\begin{bmatrix}
\boldsymbol T(t)\\
\boldsymbol C(t)
\end{bmatrix}
\quad\text{或}\quad
\boldsymbol y(t)=
\begin{bmatrix}
\boldsymbol\Theta(t)\\
\boldsymbol U(t)
\end{bmatrix},
\tag{70}
\]

偏微分方程由此转化为常微分方程组

\[
\boxed{
\frac{\mathrm d\boldsymbol y}{\mathrm dt}
=\boldsymbol f(t,\boldsymbol y)
}.
\tag{71}
\]

由于空间网格较细、扩散时间尺度差异较大，半离散系统具有刚性；同时，物性依赖当前温度和含水率，使方程组具有非线性。为此采用隐式后向差分公式（BDF）进行自适应时间积分。以一阶BDF为例，其时间离散形式为

\[
\frac{\boldsymbol y^{n+1}-\boldsymbol y^n}{\Delta t}
=\boldsymbol f(t_{n+1},\boldsymbol y^{n+1}).
\tag{72}
\]

右端含有未知的新时刻状态 \(\boldsymbol y^{n+1}\)，故每个时间步需迭代求解非线性代数方程。实际计算采用可变步长、可变阶BDF方法，并提供稀疏Jacobian矩阵

\[
\boldsymbol J=\frac{\partial\boldsymbol f}{\partial\boldsymbol y},
\tag{73}
\]

以提高隐式迭代效率。由于每个节点主要与自身及相邻节点发生通量交换，Jacobian具有稀疏带状结构。

## 7 移动边界下的实际位置输出

第四问的计算结果位于固定材料坐标 \(\xi_i\) 上，而题目要求给出固定实际距离 \(r_j\) 处的含水率。对任意时刻 \(t\)，将实际位置转换为

\[
\boxed{
\xi_j(t)=\frac{r_j}{R(t)}
}.
\tag{74}
\]

仅当 \(r_j\le R(t)\) 时，该位置位于药材内部，可由 \(U(\xi,t)\) 插值得到

\[
C(r_j,t)=U\left(\frac{r_j}{R(t)},t\right).
\tag{75}
\]

当 \(r_j>R(t)\) 时，该位置已处于药材外部，对应结果应留空，而不能填为零或进行区域外推。移动表面值则始终由

\[
C_s(t)=U(1,t)
\tag{76}
\]

给出。第四问的达标事件仍按式（24）—（26）判断，只需将固定半径场 \(C(r,t)\) 替换为材料坐标场 \(U(\xi,t)\)。

## 8 模型求解流程

第一问在固定半径下采用常数热物性和含水率相关扩散系数，分别求解温度方程与水分方程；第二问采用变物性关系，使温度和含水率形成双向耦合，并联立推进；第三问延续第二问模型，通过全域最大含水率事件确定烘干结束时刻；第四问在均匀径向收缩假设下引入材料导数和归一化材料坐标，将移动区域映射到固定区域，随后采用有限体积法和隐式BDF法求解，并将材料坐标结果转换回题目要求的实际径向位置。
