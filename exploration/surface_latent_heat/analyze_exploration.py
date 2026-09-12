"""Independent diagnostics, comparison figures and Markdown report."""
import sys
sys.dont_write_bytecode=True
import json
from pathlib import Path
import numpy as np
from scipy.integrate import trapezoid
import explore_physics as ep

OUT=ep.OUT


def read(name): return json.loads((OUT/name).read_text(encoding='utf-8'))


def check_models(boundary,radius):
    out={}
    for geom in ('fixed','moving','local'):
        cls=ep.LocalVolumeModel if geom=='local' else ep.Model
        model=cls(ep.Case('test',geom,energy='enthalpy'),24,boundary,radius)
        m=model.m
        t=20000.
        Ta=float(model.bt(t)); ce=model.equilibrium_C()
        equilibrium=np.r_[np.full(m,Ta),np.full(m,ce),np.zeros(4)]
        eq_error=float(np.max(np.abs(model.rhs(t,equilibrium))))
        y=np.r_[30+10*model.x**2,2.4-.6*model.x**2,np.zeros(4)]
        f=model.rhs(t,y)
        mass_rate=float(2*model.w@f[m:2*m]+f[2*m])
        energy_rate=float(2*model.w@((model.cs+model.cw*y[m:2*m])*f[:m]
                                    +model.cw*y[:m]*f[m:2*m]))
        energy_rate-=f[2*m+1]-f[2*m+2]-f[2*m+3]
        # Verify omitted Jacobian dependencies with full finite differences.
        jac=np.column_stack([(model.rhs(t,y+np.eye(len(y))[i]*1e-5)
                              -model.rhs(t,y-np.eye(len(y))[i]*1e-5))/2e-5
                             for i in range(len(y))])
        missing=float(np.max(np.abs(jac)[model.sparsity.toarray()==0]))
        # Boundary allows condensation and corresponding latent-heat release.
        cold=y.copy(); cold[m-1]=float(ep.dewpoint(model.ambient_p(t)))-1
        j,qc,ql,*_=model.flux(t,cold[:m],cold[m:2*m])
        out[geom]={'equilibrium_rhs_max':eq_error,'mass_rate_residual':mass_rate,
                   'enthalpy_rate_residual':energy_rate,'max_omitted_jacobian_entry':missing,
                   'condensation_j':float(j),'condensation_latent_out':float(ql)}
        assert eq_error<1e-6 and abs(mass_rate)<1e-10 and abs(energy_rate)<1e-8
        assert missing<1e-9 and j<0 and ql<0
    return out


def independent_integrals(name,grid):
    s=read(f'series/{name}_n{grid}.json')
    t=np.array(s['time_h'])*3600
    rho0=(650+128*ep.C0)/(1+ep.C0) if name.startswith('fixed') else (760+90*ep.C0)/(1+ep.C0)
    cw=4186. if name.startswith('fixed') else 4000.
    area_mass=2*np.array(s['radius_m'])/(rho0*ep.R0**2)
    j=np.array(s['j_kg_m2_s'])
    mass_integral=trapezoid(area_mass*j,t)
    net=area_mass*(np.array(s['qexternal'])-np.array(s['qlatent'])-cw*np.array(s['Ts'])*j)
    energy_integral=trapezoid(net,t)
    mass_error=s['Cmean'][-1]-ep.C0+mass_integral
    dH=s['stored_sensible_J_kgdry'][-1]-s['stored_sensible_J_kgdry'][0]
    energy_error=dH-energy_integral
    total=trapezoid(area_mass*(np.abs(s['qexternal'])+np.abs(s['qlatent'])
                              +np.abs(cw*np.array(s['Ts'])*j)),t)
    return {'mass_error_trapezoid_kg_kgdry':float(mass_error),
            'energy_error_trapezoid_J_kgdry':float(energy_error),
            'energy_error_trapezoid_relative':float(abs(energy_error)/total)}


def feasibility_bound(boundary,radius):
    bt,bc=boundary
    t=np.linspace(0,10800,10801)
    Ta=np.array([bt(q) for q in t]); Y=np.array([bc(q) for q in t])
    td=ep.dewpoint(ep.pv_air(Y))
    rho0=(760+90*ep.C0)/(1+ep.C0)
    # Generous area bound: actual shrinking area never exceeds initial area.
    qmax=trapezoid(2/(rho0*ep.R0)*ep.H*(Ta-td),t)
    initial_H=(1850+4000*ep.C0)*ep.T0
    lost_upper=(qmax+initial_H)/ep.LV
    r3=float(np.interp(10800,radius[:,0],radius[:,1]))
    v3=(r3/ep.R0)**2/rho0
    # Zero pore volume provides maximum room for remaining water.
    maxC=(v3-1/1500)*1000
    vp=1/rho0-ep.C0/1000-1/1500
    maxC_constpore=(v3-1/1500-vp)*1000
    return {'conditions':['humidity is kg/kg dry air','P=101325 Pa','only surface convection h=25',
                          'no condensation; surface >= ambient dewpoint','T >= 0 C',
                          'fixed length; dry mass from Appendix 4 initial density',
                          'water density 1000; true dry solid density 1500 kg/m3'],
            'R_observed_3h_cm':r3*100,'max_convective_heat_3h_J_kgdry':float(qmax),
            'initial_sensible_heat_J_kgdry':initial_H,
            'max_evaporated_water_3h_kg_kgdry':float(lost_upper),
            'min_water_loss_required_zero_pores_kg_kgdry':float(ep.C0-maxC),
            'water_loss_required_constant_pores_kg_kgdry':float(ep.C0-maxC_constpore),
            'interpretation':'Conditional incompatibility of this assumption bundle; not proof that measurements are wrong.'}


def figures(records,inputs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'font.size':10})
    fig,axs=plt.subplots(2,2,figsize=(13,8),constrained_layout=True)
    names=['fixed_M0','fixed_M1','fixed_M2','fixed_M3']
    for name in names:
        s=read(f'series/{name}_n120.json');t=np.array(s['time_h']);keep=t<=4
        axs[0,0].plot(t[keep],np.array(s['Ts'])[keep],label=name.replace('fixed_',''))
        axs[0,1].plot(t,s['Cmax'],label=name.replace('fixed_',''))
    s=read('series/fixed_M3_n120.json');t=np.array(s['time_h']);keep=t<=4
    axs[0,0].plot(t[keep],np.array(s['dewpoint'])[keep],'k:',label='空气露点（干空气基准）')
    axs[0,0].set(xlabel='时间 / h',ylabel='表面温度 / °C',title='固定半径：修正相平衡后消除异常低温')
    axs[0,1].axhline(.15,color='k',ls=':')
    axs[0,1].set(xlabel='时间 / h',ylabel='最大干基含水率',title='固定半径：相同阈值的干燥过程')
    for name in ['local_M4','local_M4_pore_collapse','local_M4_effective','local_M4_radiation']:
        s=read(f'series/{name}_n120.json');t=np.array(s['time_h'])
        axs[1,0].plot(t,100*np.array(s['radius_m']),label=name.replace('local_',''))
    rad=np.array(inputs['radius_m']);axs[1,0].plot(rad[:,0]/3600,rad[:,1]*100,'k--',label='附件半径（观测）')
    axs[1,0].set(xlabel='时间 / h',ylabel='半径 / cm',title='局部体积模型仍未解释快速收缩')
    for geometry,stem in [('fixed','M3'),('moving','M3'),('local','M4')]:
        selected=[next(r for r in records if r['name']==f'{geometry}_{stem}'+suffix)
                  for suffix in ['_eq0.05','','_eq0.14']]
        axs[1,1].plot([r['ceq'] for r in selected],[r['event_h'] for r in selected],'o-',label=geometry)
    axs[1,1].axvline(.15,color='k',ls=':')
    axs[1,1].set(xlabel='假设的平衡含水率',ylabel='达标时间 / h',title='解吸关系决定能否达标（0.18 情景未达标）')
    for ax in axs.flat: ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.savefig(OUT/'模型逐级对比.png',dpi=180);plt.close(fig)


def main():
    inputs=read('inputs.json');records=read('results_n120.json');fine=read('results_n240.json')
    package=ep.HERE.parents[1]/'submit/all'
    boundary,radius,_=ep.load_inputs(package)
    check=check_models(boundary,radius)
    coarse={r['name']:r for r in records};fine_by={r['name']:r for r in fine}
    grids={k:{'event_difference_s':abs(v['event_h']-coarse[k]['event_h'])*3600,
              'min_Ts_difference_C':abs(v['min_Ts']-coarse[k]['min_Ts'])}
           for k,v in fine_by.items() if v['event_h'] is not None}
    tolerance=read('tolerance_n120.json')
    tol={g:abs(v['event_h']-coarse[g+('_M4' if g=='local' else '_M3')]['event_h'])*3600
         for g,v in tolerance.items()}
    integrals={name:independent_integrals(name,240) for name in ['fixed_M3','moving_M3','local_M4']}
    bound=feasibility_bound(boundary,radius)
    radobs=np.array(inputs['radius_m'])
    window=radobs[:,0]<=48*3600
    radius_comparison={}
    for name in ['local_M4','local_M4_pore_collapse','local_M4_effective','local_M4_radiation']:
        s=read(f'series/{name}_n120.json');t=np.array(s['time_h'])*3600
        pred=np.interp(radobs[window,0],t,s['radius_m'])
        radius_comparison[name]={'rmse_0_48h_cm':float(np.sqrt(np.mean((pred-radobs[window,1])**2))*100),
                                 'radius_3h_cm':float(np.interp(10800,t,s['radius_m'])*100)}
    val={'model_checks':check,'grid_120_to_240':grids,'tight_tolerance_event_difference_s':tol,
         'independent_sample_quadrature':integrals,'conditional_energy_volume_bound':bound,
         'radius_observation_common_window':radius_comparison}
    assert max(x['event_difference_s'] for x in grids.values())<12
    assert max(tol.values())<1
    assert max(abs(x['mass_error_trapezoid_kg_kgdry']) for x in integrals.values())<1e-4
    assert max(x['energy_error_trapezoid_relative'] for x in integrals.values())<1e-5
    ep.dump(OUT/'validation.json',val)
    figures(records,inputs)
    lines=['# 相变潜热渐进建模：结果比较与可行性','',
      '本轮只在 `surface_latent_heat` 内新增文件。既有潜热对照、正式求解代码和正式结果均保留。', '',
      '**结论：气侧相平衡边界值得采用；完整焓收支可以实现；局部体积收缩能消除体积矛盾。但现有数据不足以验证唯一的新干燥时长，新的体积模型也未重现实测快速收缩，不能直接替换正式模型。**','',
      '公式、变量、来源与各级假设见 [建模方法与假设](建模方法与假设.md)。下述数值是条件情景计算，不是拟合得到的材料参数，也不是对真实误差的估计。','',
      '## 1. 逐级比较','',
      '主情景：空气数据按 kg 水/kg 干空气解释，标准大气压，传质系数用 Lewis 数为 1 的近似量级；假设解吸曲线使恒温阶段平衡含水率为 0.10。潜热固定 2.4 MJ/kg。', '',
      '本表采用 240 个径向区间；完整参数扫描采用 120 个区间。固定半径采用附录3物性，收缩采用附录4物性，两列差异不能单独归因于收缩。','',
      '| 方案 | 几何与能量处理 | 达标时间 / h | 3 h平均温度 / °C | 最低表面温度 / °C | 最大局部水体积分数 |',
      '|---|---|---:|---:|---:|---:|']
    desc={'fixed_M0':'固定；原经验边界、无潜热','fixed_M1':'固定；原表面潜热',
          'fixed_M2':'固定；相平衡边界、经验热容量','fixed_M3':'固定；相平衡与完整焓',
          'moving_M0':'指定半径；原经验边界、无潜热','moving_M1':'指定半径；原表面潜热',
          'moving_M2':'指定半径；相平衡边界','moving_M3':'指定半径；相平衡与完整焓',
          'local_M4':'局部含水率决定体积；完整焓',
          'local_M4_pore_collapse':'M4；孔隙体积随水分减少','local_M4_radiation':'M4；另加壁面辐射'}
    for name,description in desc.items():
        r=fine_by[name]
        lines.append(f"| {name} | {description} | {r['event_h']:.3f} | {r['Tmean_3h']:.3f} | {r['min_Ts']:.3f} | {r['max_liquid_volume_fraction']:.3f} |")
    lines += ['', '“最大局部水体积分数”按水密度 1000 kg/m³、守恒干物质密度计算；大于 1 表示在该物理解释下连水都装不下，不是允许存在的孔隙状态。M0/M1 原本为经验模型，此检查是新增物理解读的兼容性检查。','',
      '### M0 → M1：仅扣潜热不能保证合理','',
      'M1 再现了既有对照的小时级延长，同时在低于空气露点时持续向外失水。与潜热是否大于瞬时对流供热不同，逆蒸气压梯度蒸发才是这里的关键问题。早期输出加密并定位极小值后，最低温度与旧表的稀疏采样最低值略有不同。','',
      '### M1 → M2：相平衡约束有效，但耗时可能更长','',
      'M2 使用有符号蒸气压差，同时让蒸发降温反过来抑制失水。没有设置温度下限，没有强行截断为“供热允许的最大通量”。主情景最低温度回到约 27°C；所有已算蒸气压边界情景均未出现逆蒸气压梯度蒸发。','',
      '这并不意味着干燥更快：真实气侧交换与后期平衡含水率约束也改变了失水过程。M1 与 M2 的耗时差异混合了边界定义和系数转换，不能全部记为潜热误差。','',
      '充分湿润表面 `M2wet` 仅计算前 12 h，固定/收缩的 3 h平均温度都约 41.68°C；它没有后期解吸机制，不作为全程预测模型。','',
      '### M2 → M3：累计焓闭合改善，预测变化相对小','',
      f"固定半径主情景由 {fine_by['fixed_M2']['event_h']:.3f} h 变为 {fine_by['fixed_M3']['event_h']:.3f} h；指定半径由 {fine_by['moving_M2']['event_h']:.3f} h 变为 {fine_by['moving_M3']['event_h']:.3f} h。",
      '另有 `M3capacity` 只替换质量一致的热容量、暂不补全液态水焓通量，作为拆分对照。它与 M3 耗时接近，但并不严格满足采用的混合物焓守恒。该结果说明当前主情景的首要问题是边界与收缩，而不是遗漏的内部显热输运。','',
      '### M3 → M4：修正局部体积，仍未解释观测','',
      '指定实测半径并假设均匀收缩，使主情景最大水体积分数约 1.46；即使把半径变化整体放慢两倍，仍超过 1。M4 改用干物质质量坐标，局部体积随含水率变化，干物质密度也随位置变化。它保持质量、焓守恒且满足体积约束。','',
      f"M4 主情景在 {fine_by['local_M4']['event_h']:.3f} h 达标，终点半径 {fine_by['local_M4']['final_radius_cm']:.3f} cm。与积分区间内附件半径观测比较的 RMSE 为 {fine_by['local_M4']['radius_observation_rmse_cm']:.3f} cm；这不是校准误差，而是未拟合预测与观测的失配。",
      'M4 早期收缩明显慢于附件。允许孔隙塌缩虽然缩短干燥时间，却把终点半径压得更小，并未自然解决全过程拟合问题。新增辐射能提高供热，但其辐射率和壁温属于附加假设。','',
      f"为公平比较，统一采用0—48 h观测窗口时，M4、孔隙塌缩、等效含水率解释、辐射情景的半径 RMSE 分别为 "+
      '、'.join(f"{v['rmse_0_48h_cm']:.3f}" for v in radius_comparison.values())+' cm。'+
      f"M4 主情景在3 h的半径为 {radius_comparison['local_M4']['radius_3h_cm']:.3f} cm，而观测为 {bound['R_observed_3h_cm']:.3f} cm。",'',
      '![模型逐级对比](模型逐级对比.png)','',
      '## 2. 缺失假设会造成多大差异','',
      '以下均为 120 区间结果。每一行仅改变列出的假设，其余沿用相应主情景。未达标情景积分到 240 h。','',
      '| 改变的假设 | 固定 M3 / h | 指定半径 M3 / h | 局部体积 M4 / h |',
      '|---|---:|---:|---:|']
    for suffix,label in [('_eq0.05','平衡含水率 0.05'),('','平衡含水率 0.10（主情景）'),
                         ('_eq0.14','平衡含水率 0.14'),('_eq0.18','平衡含水率 0.18'),
                         ('_beta0.5','气侧系数 × 0.5'),('_beta2','气侧系数 × 2'),
                         ('_effective','附件值解释为材料等效含水率'),('_moistair','附件值解释为湿空气水质量分数')]:
        vals=[]
        for g,s in [('fixed','M3'),('moving','M3'),('local','M4')]:
            r=coarse[f'{g}_{s}{suffix}'];vals.append(f"{r['event_h']:.3f}" if r['event_h'] else '240 h内未达标')
        lines.append('| '+label+' | '+' | '.join(vals)+' |')
    lines += ['', '平衡含水率 0.18 情景的最大含水率在 240 h时接近 0.18。其长期平衡高于目标，延长计算时间不能使稳态低于 0.15。0.05、0.10、0.14、0.18 是刻意覆盖可达与不可达区间的假设，不是实验测得的药材性质。','',
      '即使固定恒温阶段平衡含水率，解吸曲线的中间形状也有影响：M4 的指数 0.7、1、1.5 分别得到 '+
      '、'.join(f"{coarse[k]['event_h']:.3f} h" for k in ['local_M4_aw0.7','local_M4','local_M4_aw1.5'])+'。因此一个终点平衡含水率不能唯一决定全过程。','',
      '“有效材料含水率”分支只是检验另一种题意解释，并不证明该解释正确。不同分支对应的真实空气湿度不同，不能把低温高低直接用于判断哪个分支更好。','',
      '## 3. 早期收缩与供热的条件相容性检查','',
      f"附件在 3 h给出半径 {bound['R_observed_3h_cm']:.3f} cm。取水密度 1000、干物质真密度 1500 kg/m³，即便孔隙全部消失，达到该体积也至少需要失水 {bound['min_water_loss_required_zero_pores_kg_kgdry']:.3f} kg/kg干物质。",
      '在“干空气湿度基准、无凝结且表面不低于空气露点、仅有给定对流供热”的情景下，采用初始最大表面积积分供热，并把初始全部显热也用于汽化，可得一个宽松的失水上界：','',
      r'\[\Delta C_{\max}\leq\frac{\int_0^{3h}\frac{2h}{\rho_{d0}R_0}(T_a-T_{\mathrm{dew}})\,dt+(c_s+c_wC_0)T_0}{L_v}.\]','',
      f"该上界仅为 {bound['max_evaporated_water_3h_kg_kgdry']:.3f} kg/kg干物质，低于上面的最低体积需求。该估计还忽略最终剩余显热和逸出水的显热，已偏向允许更多汽化。",
      '**这否定的是这组假设同时成立，而不是否定附件数据。**可疑之处包括湿度解释、初始密度的体积基准、固定长度、仅汽化失水（是否有液态排水）、遗漏的供热路径，以及半径记录是否对应同一工况。真密度 1500 是假设；露点下界也不能推广到存在凝结或额外制冷的任意过程。','',
      '该检查解释了为什么不能仅通过调整扩散系数去追上附件的早期收缩。应先核实物理量定义与实验工况，再进行参数反演。','',
      '## 4. 数值检验与物理检验','',
      f"120 → 240 区间的已核验主方案中，最大达标时间差 {max(x['event_difference_s'] for x in grids.values()):.3f} s；最大最低温度差 {max(x['min_Ts_difference_C'] for x in grids.values()):.6f}°C。",
      f"将相对容差从 2×10⁻⁷ 收紧为 2×10⁻⁹，同时最大时间步从 600 s降至300 s，三个主方案最大达标时间差 {max(tol.values()):.3f} s。",
      '验证项还包括均匀平衡态、离散质量/焓守恒、Jacobian 稀疏结构完整性，以及低于露点时凝结释放潜热。新局部体积模型使用全局几何依赖，未错误套用局部三对角依赖。','',
      '独立用保存的时间序列做梯形积分，而非仅检查 RHS 的望远镜求和：','',
      '| 方案 | 累计质量残差 / kg·kg⁻¹ | 累计焓残差 / J·kg干⁻¹ | 相对总能量交换 |',
      '|---|---:|---:|---:|']
    for name,x in integrals.items():
        lines.append(f"| {name} | {x['mass_error_trapezoid_kg_kgdry']:.3e} | {x['energy_error_trapezoid_J_kgdry']:.3e} | {x['energy_error_trapezoid_relative']:.3e} |")
    lines += ['', '累计 ODE 积分器中的守恒残差更小，但独立采样积分保留了额外求积误差。详细值见 `validation.json`。这些是数值误差检验，不是与真实温度、含水率观测之间的预测误差；后两类观测目前缺失。','',
      '## 5. 最终可行性判断','',
      '| 层面 | 结论 |', '|---|---|',
      '| 数值可解性 | M2、M3、M4 均可稳定求解；网格和时间精度检查通过。 |',
      '| 固定几何下的物理一致性 | M3 在所列简化假设下可行，推荐作为下一步校准的最小模型。 |',
      '| 给定半径 + 均匀干物质密度 | 本次物理解释下出现局部水体积超限，不能当作完整真实材料模型。 |',
      '| 可预测的收缩耦合 | M4 结构上可行，但半径预测失配显著，需要更合理的孔隙/变形关系和工况信息。 |',
      '| 直接替换正式时长 | 不可：参数与湿度解释未确认，温度和失水数据不足以验证准确性。 |',
      '| 增加内部汽液两相 | 理论上可行，但目前不优先；不能用更多自由参数掩盖边界与体积不相容。 |','',
      '优先补充：空气湿度定义与气压、至少一条失重曲线、表面/中心温度、干物质质量与体积定义、相同工况下的半径及长度变化、材料解吸关系。随后联合校准温度、质量和尺寸，并保留未参与校准的工况进行检验。','',
      '如果数据证实内部蒸发不可忽略，再将水拆成液态/结合态与蒸气，引入孔隙率、液相饱和度、蒸气分压和相变速率；热源使用真实相变速率，而不是直接使用总含水率的时间导数。','']
    (OUT/'探索结果与可行性.md').write_text('\n'.join(lines),encoding='utf-8')
    ep.dump(OUT/'comparison_summary.json',{'cases_main':fine,'cases_scenarios':records})
    import scipy
    import matplotlib
    ep.dump(OUT/'run_manifest.json',{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
             'matplotlib':matplotlib.__version__,'scenario_count_n120':len(records),
             'fine_case_count_n240':len(fine),
             'script_sha256':{p.name:ep.hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [ep.HERE/'explore_physics.py',ep.HERE/'analyze_exploration.py']},
             'input_boundary_source_sha256':ep.hashlib.sha256((package/'code/q2/boundary_stage.py').read_bytes()).hexdigest(),
             'scope_audits':{g:{k:v for k,v in read(f'scope_audit_n{g}.json').items() if k!='before_sha256'}
                              for g in [120,240]}})
    print(json.dumps({'grid':grids,'tolerance':tol,'bound':bound,'integrals':integrals},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
