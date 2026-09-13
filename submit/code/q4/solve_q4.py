"""Q4: moving-radius heat/moisture model on material coordinates.
python 第四问/solve_q4.py --check-time --comparisons
"""
from pathlib import Path
import argparse, csv, hashlib, importlib.util, json, sys, time
import numpy as np
import openpyxl
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator, Akima1DInterpolator, CubicSpline, UnivariateSpline
from scipy.sparse import diags,bmat,csr_matrix
from threadpoolctl import threadpool_limits

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parent.parent
DEFAULT_ROOT=PACKAGE/'data'
OUT=PACKAGE/'results'/'q4'
FIGURE_OUT=PACKAGE/'figures'/'q4'
OUT.mkdir(parents=True,exist_ok=True)
FIGURE_OUT.mkdir(parents=True,exist_ok=True)
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0,str(HERE.parent))
from artifact_names import artifact_name, figure_name
from kirchhoff_flux import moisture_face
from boundary_stage import build_boundaries
R0,H,HM,T0,C0=.02,25.,8e-7,28.,2.55
OUTPUT_R=np.arange(20)*.001
PLOT_RADIAL_POINTS=201

def read_xlsx(path):
    w=openpyxl.load_workbook(path,data_only=True,read_only=True)
    rows=list(w.active.values)
    w.close()
    a=np.array(rows[1:],dtype=float)
    assert np.isfinite(a).all() and a[0,0]==0 and np.all(np.diff(a[:,0])>0)
    return a

def _radius_smoothing_factor(values):
    second=np.diff(np.asarray(values,dtype=float),n=2)
    center=np.median(second)
    sigma=1.4826*np.median(np.abs(second-center))/np.sqrt(6.)
    if not np.isfinite(sigma) or sigma<=0:
        sigma=max(float(np.std(values))*1e-4,np.finfo(float).eps)
    return float(len(values)*sigma**2)

def _radius_curve(name,t,r):
    if name=='linear':
        return lambda q: np.interp(q,t,r), {'method':name}
    if name=='pchip':
        return PchipInterpolator(t,r,extrapolate=False), {'method':name}
    if name=='akima':
        return Akima1DInterpolator(t,r,extrapolate=False), {'method':name}
    if name=='cubic_spline':
        return CubicSpline(t,r,bc_type='natural',extrapolate=False), {'method':name}
    if name=='smooth_spline':
        s=_radius_smoothing_factor(r)
        return UnivariateSpline(t,r,s=s,ext=2), {'method':name,'smoothing_factor':s}
    raise ValueError('Unknown radius diagnostic method: '+str(name))

def _radius_metrics(curve,t_train,r_train,t_test,r_test):
    prediction=np.asarray(curve(t_test),dtype=float)
    if not np.isfinite(prediction).all():
        raise ValueError('Radius candidate returned a non-finite value.')
    dense=np.linspace(float(t_test[0]),float(t_test[-1]),721)
    values=np.asarray(curve(dense),dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Radius candidate returned a non-finite dense value.')
    lo,hi=float(np.min(r_train)),float(np.max(r_train))
    overshoot=np.maximum(lo-values,0.)+np.maximum(values-hi,0.)
    return {
        'cv_rmse_cm':float(np.sqrt(np.mean((prediction-r_test)**2))*100.),
        'cv_mae_cm':float(np.mean(np.abs(prediction-r_test))*100.),
        'cv_max_abs_cm':float(np.max(np.abs(prediction-r_test))*100.),
        'overshoot_max_cm':float(np.max(overshoot)*100.),
        'roughness':float(np.mean(np.abs(np.diff(values,n=2)/(dense[1]-dense[0])**2))),
    }

def radius_diagnostics(radius,out):
    """Validate radius candidates and render the final PCHIP representation."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    methods=['linear','pchip','akima','cubic_spline','smooth_spline']
    labels={'linear':'分段线性','pchip':'PCHIP','akima':'Akima',
            'cubic_spline':'自然三次样条','smooth_spline':'平滑样条'}
    colors={'linear':'#1f77b4','pchip':'#d62728','akima':'#2ca02c',
            'cubic_spline':'#9467bd','smooth_spline':'#ff7f0e'}
    t,r=radius[:,0],radius[:,1]
    hold=np.zeros(len(t),dtype=bool)
    hold[1:-1:5]=True
    rows=[]
    for name in methods:
        try:
            curve,metadata=_radius_curve(name,t[~hold],r[~hold])
            metrics=_radius_metrics(curve,t[~hold],r[~hold],t[hold],r[hold])
            dense=np.linspace(t[0],t[-1],5000)
            values=np.asarray(curve(dense),dtype=float)
            row={'method':name,**metrics,
                 'increasing_segments':int(np.sum(np.diff(values)>1e-9)),
                 'min_radius_cm':float(np.min(values)*100.),
                 'max_radius_cm':float(np.max(values)*100.),
                 'fit_metadata':repr(metadata)}
        except Exception as exc:
            row={'method':name,'error':str(exc)}
        rows.append(row)

    fieldnames=['cv_mae_cm','cv_max_abs_cm','cv_rmse_cm','fit_metadata',
                'increasing_segments','max_radius_cm','method','min_radius_cm',
                'overshoot_max_cm','roughness']
    with (out / artifact_name('q4', 'radius_method_comparison')).open(
            'w',encoding='utf-8',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key:row.get(key,'') for key in fieldnames})

    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'font.size':10})
    fig,ax=plt.subplots(figsize=(9,4.8),constrained_layout=True)
    ax.scatter(t/3600.,r*100.,s=12,color='#4d4d4d',alpha=.65,label='附件2原始观测')
    ax.set(xlabel='时间 / h',ylabel='半径 / cm',title='附件2：药材半径原始观测')
    ax.grid(alpha=.2)
    ax.legend(fontsize=9)
    fig.savefig(FIGURE_OUT / figure_name('q4', 'radius_raw'), dpi=180)
    plt.close(fig)

    grid=np.linspace(t[0],t[-1],1800)
    pchip_curve,_=_radius_curve('pchip',t,r)
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),constrained_layout=True)
    for ax,xmax,title in [(axes[0],72.,'全观测区间'),(axes[1],24.,'前 24 h 放大')]:
        ax.scatter(t/3600.,r*100.,s=8,color='#555555',alpha=.45,label='附件2观测')
        ax.plot(grid/3600.,np.asarray(pchip_curve(grid))*100.,color='#d62728',lw=2.4,
                label='PCHIP（最终选定）')
        ax.set(xlabel='时间 / h',ylabel='半径 / cm',xlim=(0.,xmax),title=title)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('半径数据与最终选定的 PCHIP 插值')
    fig.savefig(FIGURE_OUT / figure_name('q4', 'radius_pchip_fit'), dpi=180)
    plt.close(fig)
    return rows

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
        Df,*_=moisture_face(T[:-1],T[1:],C[:-1],C[1:],self.material)
        fc[1:-1]=self.factor*Df*np.diff(C)
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
        kf=(k[:-1]+k[1:])/2
        Df,Dcl,Dcr,Dtl,Dtr=moisture_face(T[:-1],T[1:],C[:-1],C[1:],self.material)
        tt=self.block(-f*kf,f*kf,-R*H,R*R*self.w*b)
        tc=self.block(.5*f*kc[:-1]*dT,.5*f*kc[1:]*dT,0.,R*R*self.w*b)
        tc-=diags(self.rhs(t,y)[:m]*bc/b,format='csr')
        cc=self.block(f*(Dcl*dC-Df),f*(Dcr*dC+Df),-R*HM,R*R*self.w)
        ct=self.block(f*Dtl*dC,f*Dtr*dC,0.,R*R*self.w)
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
    plot_r_cm=np.linspace(0.,R0*100.,PLOT_RADIAL_POINTS)
    plot_t=[]; plot_c=[]
    table_profiles=[]
    fixed_profile_x=np.linspace(0,1,401)
    def append(t,y):
        R=float(model.R(t))
        valid=OUTPUT_R<=R
        targets=np.r_[OUTPUT_R[valid]/R,1.]
        interp_t=PchipInterpolator(model.x,y[:m])
        interp_c=PchipInterpolator(model.x,y[m:2*m])
        vt=interp_t(targets)
        vc=interp_c(targets)
        trow,crow=np.full(21,np.nan),np.full(21,np.nan)
        trow[:20][valid],crow[:20][valid]=vt[:-1],vc[:-1]
        trow[-1],crow[-1]=vt[-1],vc[-1]
        tc.append(trow);cc.append(crow);radii.append(R);mean.append(float(2*model.w@y[m:2*m]))
        plot_valid=plot_r_cm<=R*100.+1e-12
        plot_t_row=np.full(PLOT_RADIAL_POINTS,np.nan)
        plot_c_row=np.full(PLOT_RADIAL_POINTS,np.nan)
        plot_x=plot_r_cm[plot_valid]/(R*100.)
        plot_t_row[plot_valid]=interp_t(plot_x)
        plot_c_row[plot_valid]=interp_c(plot_x)
        plot_t.append(plot_t_row);plot_c.append(plot_c_row)
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
            'plot_r_cm':plot_r_cm,'plot_T':np.array(plot_t),'plot_C':np.array(plot_c),
            'event_s':event_s,'finish_s':finish_s,'finish_h':finish_h,
            'final_max_C':float(np.max(last.y[m:2*m,-1])),'max_radial_increase':radial_increase,
            'balance_error':balance,'table_indices':table_indices,
            'profile_x':fixed_profile_x,'profiles_C':np.array(table_profiles)}

def graph(result,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, PowerNorm
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10})
    time_h=result['t']/3600.
    r_cm=result['plot_r_cm']
    moisture=result['plot_C'].T
    moisture_cmap=LinearSegmentedColormap.from_list(
        'moisture_gray_blue',
        [(0.00,'#f0f0f0'),(0.13,'#d9d9d9'),(0.20,'#bdbdbd'),
         (0.24,'#9ecae1'),(0.50,'#3182bd'),(1.00,'#08519c')])
    moisture_cmap.set_bad('#ffffff')
    # Emphasize the low-concentration range while retaining a monotone
    # gray-to-blue interpretation for the concentration field.
    # A sublinear map places the median concentration near the visual midpoint,
    # keeping gray and blue regions visually comparable.
    # Start the displayed scale at 0.08 kg/kg; lower values are clipped to
    # the light-gray endpoint so 0.08 is the bottom colorbar tick.  The
    # milder sublinear exponent keeps 0.12 and 0.15 close to the bottom.
    moisture_norm=PowerNorm(gamma=0.5,vmin=0.08,
                            vmax=float(np.nanmax(moisture)),clip=True)
    moisture_ticks=np.array([0.08,0.12,0.15,0.30,0.60,1.00,1.50,2.00,2.55])
    fig,moisture_ax=plt.subplots(figsize=(9.4,5.4),constrained_layout=True)
    moisture_mesh=moisture_ax.pcolormesh(
        time_h,r_cm,moisture,shading='nearest',cmap=moisture_cmap,
        norm=moisture_norm)
    moisture_ax.contour(time_h,r_cm,moisture,levels=[0.15],colors=['#4d4d4d'],
                        linestyles='--',linewidths=1.0,zorder=6)
    moisture_ax.set(xlabel='时间 / h',ylabel='距中心距离 / cm',
                    ylim=(0,R0*100.),title='水分浓度场')
    moisture_ax.set_xlim(float(time_h[0]),float(time_h[-1]))
    moisture_ax.set_yticks(np.arange(0,R0*100.+.01,.5))
    moisture_ax.fill_between(time_h,result['R']*100.,R0*100.,facecolor='none',
                             edgecolor='black',linewidth=0.,hatch='///',zorder=5)
    moisture_ax.plot(time_h,result['R']*100.,color='black',lw=1.5,zorder=7,
                     label='当前药材表面')
    moisture_bar=fig.colorbar(moisture_mesh,ax=moisture_ax,pad=.02,
                              ticks=moisture_ticks)
    moisture_bar.ax.tick_params(labelsize=8,pad=2)
    moisture_bar.set_label('水分浓度 / (kg/kg)')
    fig.savefig(FIGURE_OUT / figure_name('q4', 'shrinkage_moisture_field'), dpi=180)
    plt.close(fig)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--out',type=Path,default=OUT)
    p.add_argument('--grids',type=int,nargs='+',default=[400,800,1600,3200])
    p.add_argument('--check-time',action='store_true')
    p.add_argument('--comparisons',action='store_true')
    p.add_argument('--boundary-mode',choices=('staged','raw'),default='staged',
                   help='Use independent detected temperature/moisture stage boundaries (default) or raw 60 s knots.')
    p.add_argument('--fit-endpoint-s',type=float,default=None,
                   help='Optional common fit endpoint; default is each variable transition point.')
    p.add_argument('--radius-method',choices=('pchip','linear','akima','cubic_spline'),default='pchip')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    raw_env=read_xlsx(PACKAGE/'data'/'附件1.xlsx')
    boundary_t,boundary_c,env,boundary_info=build_boundaries(
        raw_env,mode=a.boundary_mode,fit_endpoint_s=a.fit_endpoint_s)
    boundary=None if a.boundary_mode=='raw' else (boundary_t,boundary_c)
    radius=read_xlsx(PACKAGE/'data'/'附件2.xlsx');radius[:,1]/=100
    assert radius[0,1]==R0 and np.all(np.diff(radius[:,1])<=0)
    radius_diagnostics(radius,a.out)
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
    summary={'model':'homogeneous radial shrinkage; Appendix 4; material coordinates; Kirchhoff moisture flux',
             'moisture_face_flux':'8-point Gauss-Legendre Kirchhoff average in C at arithmetic face temperature',
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
    q3path=PACKAGE/'results'/'q3'/artifact_name('q3', 'validation')
    if q3path.exists():
        q3s=json.loads(q3path.read_text(encoding='utf-8'))
        summary['q3_finish_h']=q3s['finish_h']
        q3_n800=next((v['event_s']/3600 for v in q3s['grid_checks'] if v['N']==800),None)
        summary['q3_event_h_N800']=q3_n800
    (a.out / artifact_name('q4', 'validation')).write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    payload={'fixed_r_cm':np.round(OUTPUT_R*100,1).tolist(),'t_s':np.round(r['t'][1:],4).tolist(),
             'R_cm':(r['R'][1:]*100).tolist(),
             'C':[[None if np.isnan(v) else round(float(v),4) for v in row] for row in r['C'][1:]]}
    (a.out / artifact_name('q4', 'result_data')).write_text(
        json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    np.savez_compressed(a.out / artifact_name('q4', 'full_precision'), t=r['t'], T=r['T'], C=r['C'], R=r['R'], mean_C=r['mean_C'],
                        profile_x=r['profile_x'],profiles_C=r['profiles_C'],table_indices=table_i)
    graph(r,a.out)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
