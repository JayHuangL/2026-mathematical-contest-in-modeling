"""Q3: reuse Q2 equations, detect max(C)=0.15, export each 60 s.
python 第三问/solve_q3.py --check-time --sensitivity
"""
from pathlib import Path
import argparse
import importlib.util
import json
import hashlib
import sys
import time
import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator
from threadpoolctl import threadpool_limits

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent.parent
OUT = PACKAGE / 'results' / 'q3'
FIGURE_OUT = PACKAGE / 'figures' / 'q3'
OUT.mkdir(parents=True, exist_ok=True)
FIGURE_OUT.mkdir(parents=True, exist_ok=True)
PLOT_RADIAL_POINTS = 201
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
from artifact_names import artifact_name, figure_name


def load_q2(root=None):
    spec = importlib.util.spec_from_file_location('q2_model', PACKAGE/'code'/'q2'/'solve_q2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integrate(q2, env, n, rtol=2e-10, atol=2e-12, max_step=300., tail=None):
    return _integrate(q2, env, n, rtol=rtol, atol=atol, max_step=max_step, tail=tail,
                      boundary=None)


def _integrate(q2, env, n, rtol=2e-10, atol=2e-12, max_step=300., tail=None,
               boundary=None):
    class Model(q2.CoupledModel):
        def __init__(self,n,env):
            super().__init__(n,env,boundary=boundary)
            x=np.linspace(0,1,n+1)
            self.r=q2.R*(-np.expm1(-4*x))/(-np.expm1(-4))
            self.faces=(self.r[:-1]+self.r[1:])/2
            self.w=np.diff(np.r_[0.,self.faces,q2.R]**2)/2
            self.factor=self.faces/np.diff(self.r)
        def ambient(self, t):
            if boundary is not None:
                return float(boundary[0](t)), float(boundary[1](t))
            if tail is not None and t > env[-1, 0]:
                return tail
            return super().ambient(t)
    model = Model(n, env)
    m = model.m
    state = np.r_[np.full(m, q2.T0), np.full(m, q2.C0), 0.0]
    radii=np.linspace(0,q2.R,21)
    plot_radii=np.linspace(0,q2.R,PLOT_RADIAL_POINTS)
    def sample(y):
        return PchipInterpolator(model.r,y[:m],axis=0)(radii), PchipInterpolator(model.r,y[m:2*m],axis=0)(radii)
    def sample_plot(y):
        return (PchipInterpolator(model.r,y[:m],axis=0)(plot_radii),
                PchipInterpolator(model.r,y[m:2*m],axis=0)(plot_radii))
    times, out_t, out_c, avg_c = [0.], [np.full(21,28.)], [np.full(21,2.55)], [2.55]
    plot_t, plot_c = [np.full(PLOT_RADIAL_POINTS,28.)], [np.full(PLOT_RADIAL_POINTS,2.55)]
    balance, max_radial_increase = 0., 0.
    event_t, event_y = None, None
    snapshots = {}

    def event(t,y):
        return np.max(y[m:2*m])-0.15
    event.terminal, event.direction = True, -1

    breaks = np.unique(np.r_[env[:,0],np.arange(21600,864001,21600)])
    for start, stop in zip(breaks[:-1],breaks[1:]):
        sol = solve_ivp(model.rhs,(start,stop),state,method='BDF',jac=model.jac,
                        rtol=rtol,atol=atol,first_step=.001,
                        max_step=min(max_step,5.) if start < env[-1,0] else max_step,
                        events=event,dense_output=True)
        if not sol.success:
            raise RuntimeError(sol.message)
        end = sol.t[-1]
        # Check all physical nodes at the integrator's accepted states.
        assert np.min(sol.y[m:2*m]) > 0 and np.max(sol.y[m:2*m]) <= 2.55+1e-8
        max_radial_increase = max(max_radial_increase,float(np.max(np.diff(sol.y[m:2*m],axis=0))))
        balance = max(balance,float(np.max(np.abs(model.w@sol.y[m:2*m]/model.area-2.55-sol.y[-1]))))
        wanted = np.arange((int(start)//60+1)*60, end+1e-8,60.)
        if len(wanted):
            y = sol.sol(wanted)
            times.extend(wanted.tolist())
            sampled_t,sampled_c=sample(y)
            out_t.extend(sampled_t.T)
            out_c.extend(sampled_c.T)
            sampled_plot_t,sampled_plot_c=sample_plot(y)
            plot_t.extend(sampled_plot_t.T)
            plot_c.extend(sampled_plot_c.T)
            avg_c.extend((model.w@y[m:2*m]/model.area).tolist())
        state = sol.y[:,-1]
        if stop%21600 == 0:
            print(f'N={n}, t={end/3600:.4f} h, max C={np.max(state[m:2*m]):.8f}',flush=True)
        if len(sol.t_events[0]):
            event_t, event_y = float(sol.t_events[0][0]), sol.y_events[0][0]
            break
    if event_t is None:
        raise RuntimeError('Threshold not reached within 240 h; no time is fabricated.')
    # Round UP to four decimals in hours so the published duration is actually below threshold.
    finish_h = np.ceil(event_t/3600*1e4)/1e4
    finish_s = float(finish_h*3600)
    if finish_s-event_t < 1e-7:
        finish_h += 1e-4
        finish_s = float(finish_h*3600)
    endsol = solve_ivp(model.rhs,(event_t,finish_s),event_y,method='BDF',jac=model.jac,
                      rtol=rtol,atol=atol,first_step=min(.001,(finish_s-event_t)/2))
    assert endsol.success
    final_y = endsol.y[:,-1]
    assert np.max(final_y[m:2*m]) < .15
    times.append(finish_s)
    sampled_t,sampled_c=sample(final_y)
    out_t.append(sampled_t)
    out_c.append(sampled_c)
    sampled_plot_t,sampled_plot_c=sample_plot(final_y)
    plot_t.append(sampled_plot_t)
    plot_c.append(sampled_plot_c)
    avg_c.append(float(model.w@final_y[m:2*m]/model.area))
    times, out_t, out_c = np.array(times),np.array(out_t),np.array(out_c)
    assert np.all(np.diff(times)>0)
    assert max_radial_increase < 1e-8
    table_indices = [i for i,t in enumerate(times) if t>0 and abs(t%21600)<1e-6]
    if len(times)-1 not in table_indices:
        table_indices.append(len(times)-1)
    return dict(t=times,T=out_t,C=out_c,mean_C=np.array(avg_c),
                plot_r_cm=plot_radii*100.0,plot_T=np.array(plot_t),plot_C=np.array(plot_c),
                event_s=event_t,
                finish_h=float(finish_h),finish_s=finish_s,
                final_max_C=float(np.max(final_y[m:2*m])),
                final_max_r_cm=float(model.r[np.argmax(final_y[m:2*m])]*100),
                balance_error=balance,max_radial_increase=max_radial_increase,
                table_t=times[table_indices],table_C=out_c[table_indices][:,::5])


def plot(result,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, PowerNorm
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'font.size':10})
    time_h=result['t']/3600.0
    r_cm=result['plot_r_cm']
    moisture=result['plot_C'].T
    moisture_cmap=LinearSegmentedColormap.from_list(
        'moisture_gray_blue',
        [(0.00,'#f0f0f0'),(0.13,'#d9d9d9'),(0.20,'#bdbdbd'),
         (0.24,'#9ecae1'),(0.50,'#3182bd'),(1.00,'#08519c')])
    # Emphasize the low-concentration range while retaining a monotone
    # gray-to-blue interpretation for the concentration field.
    moisture_cmap.set_bad('#ffffff')
    # A sublinear map places the median concentration near the visual midpoint,
    # keeping gray and blue regions visually comparable.
    # Start the displayed scale at 0.08 kg/kg; lower values are clipped to
    # the light-gray endpoint so 0.08 is the bottom colorbar tick.  The
    # milder sublinear exponent keeps 0.12 and 0.15 close to the bottom.
    moisture_norm=PowerNorm(gamma=0.5,vmin=0.08,
                            vmax=float(np.nanmax(moisture)),clip=True)
    moisture_ticks=np.array([0.08,0.12,0.15,0.30,0.60,1.00,1.50,2.00,2.55])
    fig, ax = plt.subplots(figsize=(9.4,5.6),constrained_layout=True)
    moisture_mesh=ax.pcolormesh(
        time_h,r_cm,moisture,shading='nearest',cmap=moisture_cmap,
        norm=moisture_norm)
    ax.contour(time_h,r_cm,moisture,levels=[0.15],colors=['#4d4d4d'],
               linestyles='--',linewidths=1.0,zorder=6)
    ax.set(title='水分浓度场',xlabel='时间 / h',ylabel='距中心距离 / cm',ylim=(0,2))
    ax.set_xlim(float(time_h[0]),float(time_h[-1]))
    ax.set_yticks(np.arange(0,2.01,.5))
    moisture_bar=fig.colorbar(moisture_mesh,ax=ax,pad=.02,ticks=moisture_ticks)
    moisture_bar.ax.tick_params(labelsize=8,pad=2)
    moisture_bar.set_label('水分浓度 / (kg/kg)')
    fig.savefig(FIGURE_OUT / figure_name('q3', 'drying_result'), dpi=180)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=PACKAGE/'data',
                        help='Kept for command compatibility; the unified package uses its local data directory.')
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--grids',type=int,nargs='+',default=[400,800,1600,3200])
    parser.add_argument('--check-time',action='store_true')
    parser.add_argument('--sensitivity',action='store_true')
    parser.add_argument('--boundary-mode',choices=('staged','raw'),default='staged',
                        help='Use independent detected temperature/moisture stage boundaries (default) or raw 60 s knots.')
    parser.add_argument('--fit-endpoint-s',type=float,default=None,
                        help='Optional common fit endpoint; default is each variable transition point.')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    q2=load_q2(args.root)
    env=q2.read_environment()
    if str(HERE) not in sys.path:
        sys.path.insert(0,str(HERE))
    from boundary_stage import build_boundaries
    boundary_t,boundary_c,solver_env,boundary_info=build_boundaries(
        env,mode=args.boundary_mode,fit_endpoint_s=args.fit_endpoint_s)
    boundary=None if args.boundary_mode=='raw' else (boundary_t,boundary_c)
    records,prev=[],None
    for n in args.grids:
        start=time.perf_counter()
        result=_integrate(q2,solver_env,n,boundary=boundary)
        rec={'N':n,'event_s':result['event_s'],'finish_h':result['finish_h'],
             'balance_error':result['balance_error'],'elapsed_s':time.perf_counter()-start}
        if prev is not None:
            count=min(len(prev['t']),len(result['t']))-1
            rec['event_diff_s']=abs(result['event_s']-prev['event_s'])
            rec['max_C_diff_60s']=float(np.max(abs(result['C'][:count]-prev['C'][:count])))
        records.append(rec)
        prev=result
        print(json.dumps(rec),flush=True)
    checks={}
    if args.check_time:
        tight=_integrate(q2,solver_env,args.grids[-1],rtol=2e-11,atol=2e-13,max_step=120.,
                         boundary=boundary)
        count=min(len(tight['t']),len(result['t']))-1
        checks={'event_diff_s':abs(tight['event_s']-result['event_s']),
                'max_C_diff':float(np.max(abs(tight['C'][:count]-result['C'][:count])))}
    sensitivity=[]
    if args.sensitivity:
        for name,tail in [('50C_0.05',(50.,.05)),('last_hour_mean',tuple(env[env[:,0]>=10800,1:].mean(axis=0)))]:
            sensitivity_grid=args.grids[-1]
            test=_integrate(q2,solver_env,sensitivity_grid,tail=tail)
            baseline=next((r['event_s'] for r in records if r['N']==sensitivity_grid),None)
            sensitivity.append({'case':name,'T_tail':float(tail[0]),'C_tail':float(tail[1]),
                                'sensitivity_grid':sensitivity_grid,
                                'event_h':test['event_s']/3600,
                                'delta_h_at_grid':None if baseline is None else (test['event_s']-baseline)/3600})
    q2_diff={}
    q2data=PACKAGE/'results'/'q2'/artifact_name('q2', 'full_precision')
    if q2data.exists():
        with np.load(q2data) as reference:
            match=result['t']<=10800
            for field in ['T','C']:
                q2_diff[field]=float(np.max(abs(result[field][match]-reference[field][result['t'][match].astype(int)])))
    summary={'model':'same equations as Q2; Kirchhoff moisture flux; graded radial finite volumes',
             'moisture_face_flux':'inherited from Q2: 8-point Gauss-Legendre Kirchhoff average in C at arithmetic face temperature',
             'grid_mapping':'r=R*(1-exp(-4*x))/(1-exp(-4)), x=i/N',
             'output_interpolation':'PCHIP',
             'input_sha256':hashlib.sha256((PACKAGE/'data'/'附件1.xlsx').read_bytes()).hexdigest(),
             'q2_code_sha256':hashlib.sha256((PACKAGE/'code'/'q2'/'solve_q2.py').read_bytes()).hexdigest(),
             'N':args.grids[-1],'rtol':2e-10,'atol':2e-12,'max_step_after_4h_s':300.,
             'tail_T':float(solver_env[-1,1]),'tail_C':float(solver_env[-1,2]),
             'boundary_mode':args.boundary_mode,'boundary_metadata':boundary_info,
             'event_s':result['event_s'],'event_h':result['event_s']/3600,
             'finish_s':result['finish_s'],'finish_h':result['finish_h'],
             'final_max_C':result['final_max_C'],'final_max_r_cm':result['final_max_r_cm'],
             'final_mean_C':float(result['mean_C'][-1]),
             'max_radial_increase':result['max_radial_increase'],
             'grid_checks':records,'time_check':checks,'tail_sensitivity':sensitivity,
             'q2_overlap_max_diff':q2_diff,
             'table_t_s':result['table_t'].tolist(),'table_C':result['table_C'].tolist(),
             'output_time_rows':len(result['t'])-1}
    (args.out / artifact_name('q3', 'validation')).write_text(
        json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    payload={'r_cm':np.round(np.linspace(0,2,21),1).tolist(),
             't_s':np.round(result['t'][1:],4).tolist(),'C':np.round(result['C'][1:],4).tolist()}
    (args.out / artifact_name('q3', 'result_data')).write_text(
        json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    np.savez_compressed(
        args.out / artifact_name('q3', 'full_precision'), t=result['t'], T=result['T'], C=result['C'], mean_C=result['mean_C'],
    )
    plot(result,args.out)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()
