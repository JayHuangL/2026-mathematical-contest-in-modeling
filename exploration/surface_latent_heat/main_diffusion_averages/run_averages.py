"""Read-only formal inputs; no latent heat; interface-diffusivity exploration."""
import sys
sys.dont_write_bytecode=True
import ast, argparse, hashlib, json, time, os
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
from scipy.interpolate import PchipInterpolator
from scipy.sparse import lil_matrix
from numpy.polynomial.legendre import leggauss
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
PKG=HERE.parents[2]/'submit/all'
OUT=HERE/'results'
os.environ['MPLCONFIGDIR']=str(HERE/'mplconfig')

def save(path,obj):
    assert path.resolve().is_relative_to(HERE)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

def selected_functions(path,names):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.Import,ast.ImportFrom))]
    # Only requested functions, no imports with potential side effects.
    nodes=[n for n in nodes if isinstance(n,ast.FunctionDef) and n.name in names]
    ns={'np':np,'least_squares':least_squares}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns

def xlsx(path):
    import openpyxl
    book=openpyxl.load_workbook(path,data_only=True,read_only=True)
    a=np.array(list(book.active.values)[1:],dtype=float);book.close()
    return a

def setup():
    import importlib.util
    path=PKG/'code/q2/boundary_stage.py'
    spec=importlib.util.spec_from_file_location('avg_boundary',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    env=xlsx(PKG/'data/附件1.xlsx')
    bt,bc,_,meta=mod.build_boundaries(env)
    q1=selected_functions(PKG/'code/q1/solve_q1.py',
        ['stretched_exponential','fit_environment','make_fitted_boundary'])
    _,fit=q1['fit_environment'](env,1800.)
    fun=q1['make_fitted_boundary'](fit)
    q2=selected_functions(PKG/'code/q2/solve_q2.py',['properties'])['properties']
    q4=selected_functions(PKG/'code/q4/solve_q4.py',['props4'])['props4']
    radius=xlsx(PKG/'data/附件2.xlsx');radius[:,1]/=100
    save(OUT/'input_metadata.json',{'q1':fit,'q2_q4':meta,
         'formal_property_functions':'AST-extracted directly; no formal solver module imported'})
    return ((lambda t:fun(t,1),lambda t:fun(t,2)),(bt,bc)),q2,q4,radius

class Model:
    def __init__(self,q,n,method,inputs,order=8):
        self.q,self.n,self.m,self.method=q,n,n+1,method
        boundaries,self.q2,self.q4,rad=inputs
        self.bt,self.bc=boundaries[0 if q==1 else 1]
        self.rad=PchipInterpolator(rad[:,0],rad[:,1])
        self.rad_end=rad[-1,0]
        z=np.linspace(0,1,n+1)
        self.x=z if q<=2 else -np.expm1(-4*z)/-np.expm1(-4.)
        f=.5*(self.x[:-1]+self.x[1:])
        self.w=.5*np.diff(np.r_[0.,f,1.]**2)
        self.factor=f/np.diff(self.x)
        z,w=leggauss(order);self.gz=(z+1)/2;self.gw=w/2
        m=self.m
        s=lil_matrix((2*m+1,2*m+1),dtype=int)
        for i in range(m):
            for j in range(max(0,i-1),min(m,i+2)):
                for a in (0,m):
                    for b in (0,m):s[a+i,b+j]=1
        s[-1,2*m-1]=1
        self.sp=s.tocsc()

    def R(self,t):
        return .02 if self.q<4 else float(self.rad(min(t,self.rad_end)))

    def props(self,T,C):
        if self.q==1:
            if np.min(C)<=0:raise ValueError('Nonpositive C')
            return np.full_like(C,820*2600.),np.full_like(C,.36),7e-9*np.exp(-.89/C)
        return (self.q4 if self.q==4 else self.q2)(T,C)[:3]

    def mean(self,T,C,D,order=None):
        if self.method=='arithmetic':return .5*(D[:-1]+D[1:])
        if self.method=='harmonic':return 2*D[:-1]*D[1:]/(D[:-1]+D[1:])
        tf=.5*(T[:-1]+T[1:])
        if self.method=='midpoint':
            return self.props(tf,.5*(C[:-1]+C[1:]))[2]
        gz,gw=self.gz,self.gw
        if order is not None:
            z,w=leggauss(order);gz,gw=(z+1)/2,w/2
        c=C[:-1,None]+np.diff(C)[:,None]*gz
        a=.89 if self.q==1 else (.30 if self.q==4 else .45)
        pref=7e-9 if self.q==1 else (4.2e-4 if self.q==4 else 2.4e-3)*np.exp(-3850/(tf+273.15))
        return pref*(np.exp(-a/c)@gw)

    def rhs(self,t,y):
        m=self.m;T,C=y[:m],y[m:2*m]
        b,k,D=self.props(T,C);R=self.R(t)
        ft,fc=np.zeros(m+1),np.zeros(m+1)
        ft[1:-1]=self.factor*.5*(k[:-1]+k[1:])*np.diff(T)
        fc[1:-1]=self.factor*self.mean(T,C,D)*np.diff(C)
        ft[-1]=R*25*(self.bt(t)-T[-1])
        fc[-1]=R*8e-7*(self.bc(t)-C[-1])
        return np.r_[np.diff(ft)/(R*R*self.w*b),np.diff(fc)/(R*R*self.w),
                      2*8e-7/R*(self.bc(t)-C[-1])]

def solve(q,n,method,inputs,tight=False,order=8):
    start=time.perf_counter();model=Model(q,n,method,inputs,order)
    m=model.m
    def event(t,y):return np.max(y[m:2*m])-.15
    event.terminal=True;event.direction=-1
    end=1800 if q==1 else (10800 if q==2 else 240*3600)
    step=(10 if q==1 else 30) if q<=2 else 300
    tol=2e-11 if tight else 2e-9
    sol=solve_ivp(model.rhs,(0,end),np.r_[np.full(m,28.),np.full(m,2.55),0.],
        method='BDF',jac_sparsity=model.sp,rtol=tol,atol=tol*.01,first_step=.001,
        max_step=step/2 if tight else step,dense_output=True,events=event if q>=3 else None)
    if not sol.success:raise RuntimeError(sol.message)
    if q>=3 and not len(sol.t_events[0]):raise RuntimeError('No event')
    # Compare solutions at fixed common times, not each method's own event.
    times=np.array([100,300,600,900,1200,1500,1800]) if q==1 else (
        np.arange(1800,10801,1800) if q==2 else np.r_[1800,10800,np.arange(6,49,6)*3600])
    states=sol.sol(times)
    grid=np.linspace(0,1,101)
    tf=np.array([PchipInterpolator(model.x,col[:m])(grid) for col in states.T])
    cf=np.array([PchipInterpolator(model.x,col[m:2*m])(grid) for col in states.T])
    ratios=[];max_gap=0.;where=None;quaderr=0
    for i in np.linspace(0,len(sol.t)-1,min(401,len(sol.t))).astype(int):
        y=sol.y[:,i];T,C=y[:m],y[m:2*m];D=model.props(T,C)[2]
        ratio=np.maximum(D[1:]/D[:-1],D[:-1]/D[1:]);ratios.append(ratio)
        if np.max(ratio)>max_gap:
            k=int(np.argmax(ratio));max_gap=float(ratio[k])
            where={'time_s':float(sol.t[i]),'x':float(model.x[k]),
                   'C_pair':C[k:k+2].tolist(),'T_pair':T[k:k+2].tolist()}
        if method=='kirchhoff':
            d8=model.mean(T,C,D);d16=model.mean(T,C,D,16)
            quaderr=max(quaderr,float(np.max(np.abs(d8-d16)/d16)))
    avg=2*model.w@sol.y[m:2*m]
    name=f'q{q}_{method}_n{n}'+('_tight' if tight else '')+('_g16' if order==16 else '')
    result={'name':name,'q':q,'N':n,'method':method,'tight':tight,'gauss_order':order,
        'event_h':float(sol.t[-1]/3600) if q>=3 else None,
        'T_center_end':float(sol.y[0,-1]),'T_surface_end':float(sol.y[m-1,-1]),
        'C_center_end':float(sol.y[m,-1]),'C_surface_end':float(sol.y[2*m-1,-1]),
        'mass_balance_error':float(np.max(np.abs(avg-2.55-sol.y[-1]))),
        'min_C':float(np.min(sol.y[m:2*m])),'max_adjacent_D_ratio_sampled':max_gap,
        'ratio_location':where,'gauss8_vs16_max_relative':quaderr,
        'wall_s':time.perf_counter()-start,'nfev':sol.nfev,'njev':sol.njev,
        'sample_times_s':times.tolist(),'sample_x':grid.tolist(),'T':tf.tolist(),'C':cf.tolist()}
    save(OUT/(name+'.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('T','C','sample_times_s','sample_x')},ensure_ascii=False),flush=True)
    return result

def snapshot():
    return {str(p.relative_to(PKG)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in PKG.rglob('*') if p.is_file()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--grids',type=int,nargs='+',default=[100,200,400,800])
    p.add_argument('--qs',type=int,nargs='+',default=[1,2,3,4])
    p.add_argument('--methods',nargs='+',default=['arithmetic','harmonic','midpoint','kirchhoff'])
    p.add_argument('--tight',action='store_true')
    p.add_argument('--order',type=int,default=8)
    args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    before=snapshot();inputs=setup()
    for q in args.qs:
        for n in args.grids:
            for method in args.methods:solve(q,n,method,inputs,args.tight,args.order)
    after=snapshot()
    assert before==after,'Formal package changed during run'
    save(OUT/'scope_audit.json',{'unchanged':before==after,'files_checked':len(before),'sha256':before})

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
