"""Q4: moving-radius heat/moisture model on material coordinates.
python 第四问/solve_q4.py --check-time --comparisons
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys, time
import numpy as np
import openpyxl
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator, Akima1DInterpolator, CubicSpline
from scipy.sparse import diags,bmat,csr_matrix
from threadpoolctl import threadpool_limits

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent.parent
DEFAULT_ROOT=PACKAGE/'data'
OUT=PACKAGE/'results'/'q4'
OUT.mkdir(parents=True,exist_ok=True)
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))
from boundary_stage import build_boundaries
R0,H,HM,T0,C0=.02,25.,8e-7,28.,2.55
OUTPUT_R=np.arange(20)*.001

def read_xlsx(path):
    w=openpyxl.load_workbook(path,data_only=True,read_only=True)
    rows=list(w.active.values)
    w.close()
    a=np.array(rows[1:],dtype=float)
    assert np.isfinite(a).all() and a[0,0]==0 and np.all(np.diff(a[:,0])>0)
    return a

def load_q2(root=None):
    spec=importlib.util.spec_from_file_location('q2_model',PACKAGE/'code'/'q2'/'solve_q2.py')
    q2=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q2)
    return q2

def props4(T,C):
    K=T+273.15
    if np.min(C.real)<=0 or np.min(K.real)<=0:
        raise ValueError('Nonphysical state; no silent clipping.')
    rho=760+90*C
    cp=1850+2150*C/(C+1)
    k=.12+.20*C/(C+1)
    D=4.2e-4*np.exp(-.30/C-3850/K)
    return rho*cp,k,D,90*cp+rho*2150/(C+1)**2,.20/(C+1)**2,D*.30/C**2,D*3850/K**2

class Model:
    def __init__(self,n,env,radius,material=props4,fixed_radius=None,linear_radius=False,tail=None,
                 graded=True,boundary=None,radius_method=None):
        self.n,self.m=n,n+1
        self.env,self.radius_data,self.material=env,radius,material
        self.fixed_radius,self.linear_radius,self.tail=fixed_radius,linear_radius,tail
        self.boundary=boundary
        self.radius_method='linear' if linear_radius and radius_method is None else (radius_method or 'pchip')
        z=np.linspace(0,1,n+1)
        self.x=-np.expm1(-4*z)/(-np.expm1(-4)) if graded else z
        self.faces=(self.x[:-1]+self.x[1:])/2
        self.w=np.diff(np.r_[0.,self.faces,1.]**2)/2
        self.factor=self.faces/np.diff(self.x)
        if self.radius_method == 'pchip':
            self.curve=PchipInterpolator(radius[:,0],radius[:,1],extrapolate=False)
        elif self.radius_method == 'akima':
            self.curve=Akima1DInterpolator(radius[:,0],radius[:,1],extrapolate=False)
        elif self.radius_method == 'cubic_spline':
            self.curve=CubicSpline(radius[:,0],radius[:,1],bc_type='natural',extrapolate=False)
        elif self.radius_method == 'linear':
            self.curve=None
        else:
            raise ValueError('Unknown radius_method: '+str(self.radius_method))
        self.zero=csr_matrix((1,self.m))
    def R(self,t):
        if self.fixed_radius is not None:
            return np.full_like(np.asarray(t,dtype=float),self.fixed_radius)
        t=np.clip(t,self.radius_data[0,0],self.radius_data[-1,0])
        return np.interp(t,self.radius_data[:,0],self.radius_data[:,1]) if self.radius_method=='linear' else self.curve(t)
    def ambient(self,t):
        if self.boundary is not None:
            return float(self.boundary[0](t)),float(self.boundary[1](t))
        if self.tail is not None and t>self.env[-1,0]:
            return self.tail
        return np.interp(t,self.env[:,0],self.env[:,1]),np.interp(t,self.env[:,0],self.env[:,2])
    def rhs(self,t,y):
        m=self.m
        T,C=y[:m],y[m:2*m]
        b,k,D,*_=self.material(T,C)
        R=self.R(t)
        ta,ca=self.ambient(t)
        ft=np.empty(m+1,dtype=y.dtype)
        fc=np.empty_like(ft)
        ft[0]=fc[0]=0
        ft[1:-1]=self.factor*(k[:-1]+k[1:])/2*np.diff(T)
        fc[1:-1]=self.factor*(D[:-1]+D[1:])/2*np.diff(C)
        ft[-1]=R*H*(ta-T[-1])
        fc[-1]=R*HM*(ca-C[-1])
        return np.r_[np.diff(ft)/(R*R*self.w*b),np.diff(fc)/(R*R*self.w),2*HM/R*(ca-C[-1])]
    def block(self,l,r,boundary,den):
        main=np.r_[l,boundary]-np.r_[0.,r]
        return diags((-l/den[1:],main/den,r/den[:-1]),(-1,0,1),format='csr')
    def jac(self,t,y):
        m=self.m
        T,C=y[:m],y[m:2*m]
        b,k,D,bc,kc,Dc,Dt=self.material(T,C)
        R=self.R(t)
        f=self.factor
        dT,dC=np.diff(T),np.diff(C)
        kf,Df=(k[:-1]+k[1:])/2,(D[:-1]+D[1:])/2
        tt=self.block(-f*kf,f*kf,-R*H,R*R*self.w*b)
        tc=self.block(.5*f*kc[:-1]*dT,.5*f*kc[1:]*dT,0.,R*R*self.w*b)
        tc-=diags(self.rhs(t,y)[:m]*bc/b,format='csr')
        cc=self.block(f*(.5*Dc[:-1]*dC-Df),f*(.5*Dc[1:]*dC+Df),-R*HM,R*R*self.w)
        ct=self.block(.5*f*Dt[:-1]*dC,.5*f*Dt[1:]*dC,0.,R*R*self.w)
        fluxrow=csr_matrix(([-2*HM/R],([0],[m-1])),shape=(1,m))
        return bmat([[tt,tc,None],[ct,cc,None],[self.zero,fluxrow,csr_matrix((1,1))]],format='csc')

def unit_checks(q2,env,radius):
    rng=np.random.default_rng(2026)
    model=Model(40,env,radius)
    y=np.r_[28+7*model.x**2,2.55-.8*model.x**2,0.]
    errors=[]
    for t in [600.,21600.,100000.]:
        j=model.jac(t,y)
        for _ in range(2):
            v=rng.normal(size=len(y))
            exact=np.imag(model.rhs(t,y+1e-25j*v))/1e-25
            errors.append(float(np.max(abs(j@v-exact))/np.max(abs(exact))))
    assert max(errors)<1e-11
    fixed=Model(40,env,radius,material=q2.properties,fixed_radius=R0,graded=False)
    original=q2.CoupledModel(40,env)
    y=np.r_[28+7*fixed.x**2,2.55-.8*fixed.x**2,0.]
    delta=float(np.max(abs(fixed.rhs(1200,y)-original.rhs(1200,y))))
    assert delta<1e-10
    # No environmental driving force: uniform fields remain uniform under shrinkage.
    closed=Model(40,np.array([[0.,T0,C0],[259200.,T0,C0]]),radius)
    initial=np.r_[np.full(41,T0),np.full(41,C0),0.]
    invariant=max(float(np.max(abs(closed.rhs(t,initial)))) for t in [0.,1800.,21600.,259200.])
    assert invariant==0.
    return {'jacobian_relative_error':max(errors),'fixed_radius_q2_rhs_max_difference':delta,'uniform_no_exchange_derivative':invariant}

def simulate(env,radius,n,rtol=2e-10,atol=2e-12,max_step=300.,**options):
    model=Model(n,env,radius,**options)
    m=model.m
    state=np.r_[np.full(m,T0),np.full(m,C0),0.]
    times=[0.]; tc=[]; cc=[]; mean=[]; radii=[]
    table_profiles=[]
    fixed_profile_x=np.linspace(0,1,401)
    def append(t,y):
        R=float(model.R(t))
        valid=OUTPUT_R<=R
        targets=np.r_[OUTPUT_R[valid]/R,1.]
        vt=PchipInterpolator(model.x,y[:m])(targets)
        vc=PchipInterpolator(model.x,y[m:2*m])(targets)
        trow,crow=np.full(21,np.nan),np.full(21,np.nan)
        trow[:20][valid],crow[:20][valid]=vt[:-1],vc[:-1]
        trow[-1],crow[-1]=vt[-1],vc[-1]
        tc.append(trow);cc.append(crow);radii.append(R);mean.append(float(2*model.w@y[m:2*m]))
    append(0.,state)
    def event(t,y):return float(np.max(y[m:2*m])-.15)
    event.terminal,event.direction=True,-1
    breaks=np.unique(np.r_[env[:,0],radius[:,0],np.arange(21600,864001,21600)])
    balance,radial_increase=0.,0.
    event_s,event_y=None,None
    for start,stop in zip(breaks[:-1],breaks[1:]):
        sol=solve_ivp(model.rhs,(start,stop),state,method='BDF',jac=model.jac,
                      rtol=rtol,atol=atol,first_step=.001,
                      max_step=min(5.,max_step) if start<env[-1,0] else max_step,
                      events=event,dense_output=True)
        if not sol.success:raise RuntimeError(sol.message)
        end=sol.t[-1]
        C=sol.y[m:2*m]
        assert C.min()>0 and C.max()<=C0+1e-8
        radial_increase=max(radial_increase,float(np.max(np.diff(C,axis=0))))
        balance=max(balance,float(np.max(abs(2*model.w@C-C0-sol.y[-1]))))
        wanted=np.arange((int(start)//60+1)*60,end+1e-8,60.)
        if len(wanted):
            ys=sol.sol(wanted)
            for i,t in enumerate(wanted):
                times.append(float(t));append(t,ys[:,i])
                if t%21600==0:
                    table_profiles.append(PchipInterpolator(model.x,ys[m:2*m,i])(fixed_profile_x))
        state=sol.y[:,-1]
        if stop%21600==0 or len(sol.t_events[0]):
            print(f'N={n}, t={end/3600:.5f} h, R={float(model.R(end))*100:.6f} cm, Cmax={np.max(state[m:2*m]):.8f}',flush=True)
        if len(sol.t_events[0]):
            event_s,event_y=float(sol.t_events[0][0]),sol.y_events[0][0]
            break
    if event_s is None:raise RuntimeError('No drying event within 240 h.')
    finish_h=float(np.ceil(event_s/3600*1e4)/1e4)
    finish_s=finish_h*3600
    if finish_s-event_s<1e-7:
        finish_h+=1e-4;finish_s=finish_h*3600
    last=solve_ivp(model.rhs,(event_s,finish_s),event_y,method='BDF',jac=model.jac,
                   rtol=rtol,atol=atol,first_step=min(.001,(finish_s-event_s)/2))
    assert last.success and np.max(last.y[m:2*m,-1])<.15
    times.append(finish_s);append(finish_s,last.y[:,-1])
    table_profiles.append(PchipInterpolator(model.x,last.y[m:2*m,-1])(fixed_profile_x))
    assert radial_increase<1e-8
    a=np.array(times)
    table_indices=[i for i,t in enumerate(a) if t>0 and abs(t%21600)<1e-7]
    if len(a)-1 not in table_indices:table_indices.append(len(a)-1)
    return {'t':a,'T':np.array(tc),'C':np.array(cc),'R':np.array(radii),'mean_C':np.array(mean),
            'event_s':event_s,'finish_s':finish_s,'finish_h':finish_h,
            'final_max_C':float(np.max(last.y[m:2*m,-1])),'max_radial_increase':radial_increase,
            'balance_error':balance,'table_indices':table_indices,
            'profile_x':fixed_profile_x,'profiles_C':np.array(table_profiles)}

def graph(result,radius,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(15,4.5),constrained_layout=True)
    axes[0].plot(result['t']/3600,result['R']*100,label='PCHIP半径')
    within=radius[:,0]<=result['finish_s']
    axes[0].scatter(radius[within,0]/3600,radius[within,1]*100,s=8,color='black',label='附件2')
    axes[0].set(xlabel='时间 / h',ylabel='半径 / cm',title='药材收缩')
    for idx,label in [(0,'中心'),(5,'0.5 cm'),(10,'1 cm'),(20,'表面（位置随时间变化）')]:
        axes[1].plot(result['t']/3600,result['C'][:,idx],label=label)
    axes[1].axhline(.15,color='black',ls='--',lw=1,label='阈值0.15')
    axes[1].set(xlabel='时间 / h',ylabel='干基含水率 / (kg/kg)',title='含水率随时间变化')
    for j,i in enumerate(result['table_indices']):
        axes[2].plot(result['profile_x']*result['R'][i]*100,result['profiles_C'][j],label=f"{result['t'][i]/3600:.2f} h")
    axes[2].axhline(.15,color='black',ls='--',lw=1)
    axes[2].set(xlabel='实际距中心距离 / cm',ylabel='干基含水率 / (kg/kg)',title='收缩区域内的径向分布')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(out/'第四问结果图.png',dpi=180)
    plt.close(fig)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--out',type=Path,default=OUT)
    p.add_argument('--grids',type=int,nargs='+',default=[400,800,1600,3200])
    p.add_argument('--check-time',action='store_true')
    p.add_argument('--comparisons',action='store_true')
    p.add_argument('--boundary-mode',choices=('staged','raw'),default='staged',
                   help='Use the common detected stage boundary (default) or raw 60 s knots.')
    p.add_argument('--fit-endpoint-s',type=float,default=None)
    p.add_argument('--radius-method',choices=('pchip','linear','akima','cubic_spline'),default='pchip')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    raw_env=read_xlsx(PACKAGE/'data'/'附件1.xlsx')
    boundary_t,boundary_c,env,boundary_info=build_boundaries(
        raw_env,mode=a.boundary_mode,fit_endpoint_s=a.fit_endpoint_s)
    boundary=None if a.boundary_mode=='raw' else (boundary_t,boundary_c)
    radius=read_xlsx(PACKAGE/'data'/'附件2.xlsx');radius[:,1]/=100
    assert radius[0,1]==R0 and np.all(np.diff(radius[:,1])<=0)
    q2=load_q2()
    checks=unit_checks(q2,env,radius)
    print('Model checks:',checks,flush=True)
    records=[];prev=None
    for n in a.grids:
        tick=time.perf_counter();r=simulate(env,radius,n,boundary=boundary,radius_method=a.radius_method)
        row={'N':n,'event_s':r['event_s'],'finish_h':r['finish_h'],'balance_error':r['balance_error'],'elapsed_s':time.perf_counter()-tick}
        if prev is not None:
            count=min(len(prev['t']),len(r['t']))-1
            row['event_diff_s']=abs(r['event_s']-prev['event_s'])
            assert np.array_equal(np.isnan(r['C'][:count]),np.isnan(prev['C'][:count]))
            row['max_output_C_diff']=float(np.nanmax(abs(r['C'][:count]-prev['C'][:count])))
        records.append(row);prev=r;print(json.dumps(row),flush=True)
    timecheck={}
    if a.check_time:
        tight=simulate(env,radius,a.grids[-1],rtol=2e-11,atol=2e-13,max_step=120.,boundary=boundary,
                       radius_method=a.radius_method)
        count=min(len(tight['t']),len(r['t']))-1
        timecheck={'event_diff_s':abs(r['event_s']-tight['event_s']),
                   'max_output_C_diff':float(np.nanmax(abs(r['C'][:count]-tight['C'][:count])))}
    comparisons=[]
    if a.comparisons:
        for label,opts in [
            ('appendix4_fixed_radius',{'fixed_radius':R0}),
            ('appendix3_shrinking',{'material':q2.properties}),
            ('linear_radius',{'linear_radius':True}),
            ('tail_50C_0.05',{'tail':(50.,.05)})]:
             comparison_boundary=None if 'tail' in opts else boundary
             c=simulate(env,radius,800,boundary=comparison_boundary,**opts)
             comparisons.append({'case':label,'N':800,'event_h':c['event_s']/3600})
    table_i=r['table_indices']
    table_C=r['C'][table_i][:,[0,5,10,20]]
    summary={'model':'homogeneous radial shrinkage; Appendix 4; material coordinates',
              'environment_sha256':hashlib.sha256((PACKAGE/'data'/'附件1.xlsx').read_bytes()).hexdigest(),
              'radius_sha256':hashlib.sha256((PACKAGE/'data'/'附件2.xlsx').read_bytes()).hexdigest(),
              'R_interpolation':a.radius_method+'; hold last after 72 h','tail_T':float(env[-1,1]),'tail_C':float(env[-1,2]),
              'boundary_mode':a.boundary_mode,'boundary_metadata':boundary_info,
              'N':a.grids[-1],'grid':'xi=(1-exp(-4*i/N))/(1-exp(-4))','rtol':2e-10,'atol':2e-12,
              'model_checks':checks,'grid_checks':records,'time_check':timecheck,'comparisons':comparisons,
              'event_s':r['event_s'],'event_h':r['event_s']/3600,'finish_h':r['finish_h'],'finish_s':r['finish_s'],
              'final_max_C':r['final_max_C'],'final_R_cm':float(r['R'][-1]*100),'final_mean_C':float(r['mean_C'][-1]),
              'max_radial_increase':r['max_radial_increase'],'radius_extrapolation_used':bool(r['finish_s']>radius[-1,0]),
              'table_t_s':r['t'][table_i].tolist(),'table_R_cm':(r['R'][table_i]*100).tolist(),'table_C':table_C.tolist(),
              'output_rows':len(r['t'])-1,'outside_blank_count':int(np.isnan(r['C'][1:]).sum())}
    q3path=PACKAGE/'results'/'q3'/'validation.json'
    if q3path.exists():
        q3s=json.loads(q3path.read_text(encoding='utf-8'))
        summary['q3_finish_h']=q3s['finish_h']
        q3_n800=next((v['event_s']/3600 for v in q3s['grid_checks'] if v['N']==800),None)
        summary['q3_event_h_N800']=q3_n800
    (a.out/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    payload={'fixed_r_cm':np.round(OUTPUT_R*100,1).tolist(),'t_s':np.round(r['t'][1:],4).tolist(),
             'R_cm':(r['R'][1:]*100).tolist(),
             'C':[[None if np.isnan(v) else round(float(v),4) for v in row] for row in r['C'][1:]]}
    (a.out/'result4_data.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    np.savez_compressed(a.out/'result4_full_precision.npz',t=r['t'],T=r['T'],C=r['C'],R=r['R'],mean_C=r['mean_C'],
                        profile_x=r['profile_x'],profiles_C=r['profiles_C'],table_indices=table_i)
    lines=['# 表6：收缩药材烘干过程的水分浓度','',
            '| 时间 / h | 0 cm | 0.5 cm | 1 cm | 药材表面 |','|---:|---:|---:|---:|---:|']
    for t,c in zip(summary['table_t_s'],table_C):
        label=f'{t/3600:.4f}' if t==r['finish_s'] else f'{t/3600:g}'
        lines.append('| '+label+' | '+' | '.join(f'{v:.4f}' for v in c)+' |')
    lines+=['','表面列对应的实际位置：','',
             '| 时间 / h | 半径 / cm |','|---:|---:|']
    for t,R in zip(summary['table_t_s'],summary['table_R_cm']):
        label=f'{t/3600:.4f}' if t==r['finish_s'] else f'{t/3600:g}'
        lines.append(f'| {label} | {R:.4f} |')
    (a.out/'结果表.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    graph(r,radius,a.out)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
