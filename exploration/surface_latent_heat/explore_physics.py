"""Progressive, conditional latent-heat models; every write stays in this folder.

Run: python -X utf8 -B explore_physics.py
No imports of the formal solvers (some have import-time output side effects).
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import argparse
from dataclasses import dataclass, asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq, minimize_scalar
from scipy.sparse import lil_matrix
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
OUT = HERE / 'physical_exploration'
os.environ['MPLCONFIGDIR'] = str(OUT / 'mplconfig')
R0, C0, T0, H, HM, LV = .02, 2.55, 28., 25., 8e-7, 2.4e6
P, R_AIR, R_VAPOR, CP_AIR = 101325., 287.05, 461.5, 1006.
# Lewis-number-one approximation at a reference dry-air density.
BETA0 = H * R_AIR / (CP_AIR * R_VAPOR * P)


def dump(path, data):
    path = path.resolve()
    if not path.is_relative_to(HERE):
        raise ValueError('All outputs must stay inside surface_latent_heat')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def psat(T):
    """NOAA Tetens formula, Pa, T in Celsius; 0-50 C exploration range."""
    return 611. * 10. ** (7.5 * T / (237.3 + T))


def dewpoint(p):
    a = np.log10(p / 611.)
    return 237.3 * a / (7.5 - a)


def pv_air(Y):
    return P * Y / (.62197 + Y)


def read_xlsx(path):
    import openpyxl
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(book.active.values)
    book.close()
    return np.asarray(rows[1:], dtype=float), list(rows[0])


def load_inputs(package):
    # Boundary module has no output side effects; bytecode writing is disabled.
    path = package / 'code/q2/boundary_stage.py'
    spec = importlib.util.spec_from_file_location('physics_boundary', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env, headers = read_xlsx(package / 'data/附件1.xlsx')
    rad, rheaders = read_xlsx(package / 'data/附件2.xlsx')
    bt, bc, _, metadata = module.build_boundaries(env, mode='staged', fit_endpoint_s=14400.)
    rad[:, 1] /= 100.
    dump(OUT / 'inputs.json', {'environment': env.tolist(), 'environment_headers': headers,
                             'radius_m': rad.tolist(), 'radius_headers': rheaders,
                             'boundary_metadata': metadata})
    return (bt, bc), rad, metadata


@dataclass
class Case:
    name: str
    geometry: str = 'fixed'
    boundary: str = 'vapor'  # empirical, vapor, wet
    energy: str = 'empirical'  # empirical, capacity_only, enthalpy
    latent: float = 1.
    ceq: float = .10  # assumed asymptotic equilibrium moisture at plateau
    beta_factor: float = 1.
    humidity_basis: str = 'dry_air'  # dry_air, moist_air, effective_material
    radius_time_factor: float = 1.
    pore_collapse: float = 0.
    aw_exponent: float = 1.
    emissivity: float = 0.
    max_h: float = 240.


class Model:
    def __init__(self, case, n, boundary, radius):
        self.case, self.n, self.m = case, n, n + 1
        self.bt, self.bc = boundary
        self.rad = PchipInterpolator(radius[:, 0], radius[:, 1], extrapolate=False)
        self.rad_end = radius[-1, 0]
        z = np.linspace(0., 1., n + 1)
        self.x = -np.expm1(-4 * z) / -np.expm1(-4.)
        f = (self.x[:-1] + self.x[1:]) / 2.
        self.w = np.diff(np.r_[0., f, 1.] ** 2) / 2.
        self.factor = f / np.diff(self.x)
        if case.geometry == 'fixed':
            self.rho0 = (650 + 128 * C0) / (1 + C0)
            self.cs, self.cw = 1450., 4186.
        else:
            self.rho0 = (760 + 90 * C0) / (1 + C0)
            self.cs, self.cw = 1850., 4000.
        rh = float(pv_air(self.bc(1e8)) / psat(self.bt(1e8)))
        self.b = case.ceq**case.aw_exponent * (1 - rh) / rh
        self.sparsity = lil_matrix((2*self.m+4, 2*self.m+4), dtype=int)
        for i in range(self.m):
            for j in range(max(0, i-1), min(self.m, i+2)):
                for a in (0, self.m):
                    for b in (0, self.m):
                        self.sparsity[a+i, b+j] = 1
        self.sparsity[2*self.m:, self.m-1] = 1
        self.sparsity[2*self.m:, 2*self.m-1] = 1
        self.sparsity = self.sparsity.tocsc()

    def radius(self, t):
        if self.case.geometry == 'fixed':
            return R0
        return float(self.rad(min(t / self.case.radius_time_factor, self.rad_end)))

    def aw(self, C):
        # A scenario family, NOT a measured sorption isotherm.
        power = C**self.case.aw_exponent
        return power / (power + self.b)

    def external_heat(self,t,Ts):
        Ta = float(self.bt(t))
        return H*(Ta-Ts)+self.case.emissivity*5.670374419e-8*((Ta+273.15)**4-(Ts+273.15)**4)

    def ambient_p(self, t):
        Y = float(self.bc(t))
        if self.case.humidity_basis == 'effective_material':
            return float(self.aw(Y) * psat(self.bt(t)))
        if self.case.humidity_basis == 'moist_air':
            Y = Y / (1. - Y)
        return pv_air(Y)

    def flux(self, t, T, C):
        R = self.radius(t)
        rd = self.rho0 * (R0 / R)**2
        qc = self.external_heat(t,T[-1])
        a = 1. if self.case.boundary == 'wet' else self.aw(C[-1])
        dp = a * psat(T[-1]) - self.ambient_p(t)
        j = rd * HM * (C[-1] - float(self.bc(t))) if self.case.boundary == 'empirical' \
            else BETA0 * self.case.beta_factor * dp
        return j, qc, self.case.latent * LV * j, dp, R, rd

    def material(self, T, C):
        if np.min(C) <= 0 or np.min(T) < -50 or np.max(T) > 100:
            raise ValueError('Outside positive-moisture / temperature validity domain')
        if self.case.geometry == 'fixed':
            rho = 650. + 128. * C
            k = .21 + .38 * C/(1+C)
            D = 2.4e-3*np.exp(-.45/C - 3850/(T+273.15))
        else:
            rho = 760. + 90. * C
            k = .12 + .20 * C/(1+C)
            D = 4.2e-4*np.exp(-.30/C - 3850/(T+273.15))
        cp = (self.cs + self.cw*C)/(1+C)
        return rho*cp, k, D

    def rhs(self, t, y):
        m = self.m
        T, C = y[:m], y[m:2*m]
        b, k, D = self.material(T, C)
        j, qc, ql, _, R, rd = self.flux(t, T, C)
        fc, ft = np.zeros(m+1), np.zeros(m+1)
        fc[1:-1] = self.factor * .5*(D[:-1]+D[1:])*np.diff(C)
        fc[-1] = -R*j/rd
        ct = np.diff(fc)/(R*R*self.w)
        ft[1:-1] = self.factor * .5*(k[:-1]+k[1:])*np.diff(T)
        if self.case.energy == 'enthalpy':
            ft[1:-1] += rd * self.cw * .5*(T[:-1]+T[1:]) * fc[1:-1]
            ft[-1] = R*(qc - ql - self.cw*T[-1]*j)
            et = np.diff(ft)/(rd*R*R*self.w)
            tt = (et - self.cw*T*ct)/(self.cs+self.cw*C)
        else:
            ft[-1] = R*(qc-ql)
            if self.case.energy == 'capacity_only':
                b = rd*(self.cs+self.cw*C)
            tt = np.diff(ft)/(R*R*self.w*b)
        scale = 2/(rd*R)
        return np.r_[tt, ct, scale*j, scale*qc, scale*ql, scale*self.cw*T[-1]*j]

    def equilibrium_C(self):
        if self.case.boundary == 'empirical':
            return float(self.bc(1e8))
        if self.case.boundary == 'wet':
            return None
        rh = self.ambient_p(1e8)/psat(self.bt(1e8))
        return float((self.b*rh/(1-rh))**(1/self.case.aw_exponent))


class LocalVolumeModel(Model):
    """Dry-mass Lagrangian shells; nonuniform deformation from local water loss.

    v(C) = 1/rho_s + C/rho_l + vp0*(1-a+a*C/C0), per kg dry solid.
    a=0 holds pore volume per kg dry solid constant; a=1 collapses it linearly.
    The initial bulk density is exactly preserved for either choice.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.rho_s = 1500.  # assumption, only affects a != 0
        self.vp0 = 1/self.rho0 - C0/1000. - 1/self.rho_s
        assert self.vp0 > 0
        self.mass = self.rho0*R0*R0*self.w  # per radian per unit length
        ref_faces = np.r_[0., (self.x[:-1]+self.x[1:])/2, 1.]
        self.location = (self.x**2-ref_faces[:-1]**2)/np.diff(ref_faces**2)
        # Geometry depends on every C cell. A local Jacobian pattern would be wrong.
        self.sparsity = self.sparsity.tolil()
        self.sparsity[:,self.m:2*self.m] = 1
        self.sparsity = self.sparsity.tocsc()

    def volume(self,C):
        a = self.case.pore_collapse
        return 1/self.rho_s+C/1000.+self.vp0*(1-a+a*C/C0)

    def mesh(self,C):
        v = self.volume(C)
        f2 = np.r_[0.,2*np.cumsum(self.mass*v)]
        nodes = np.sqrt(f2[:-1]+self.location*np.diff(f2))
        faces = np.sqrt(f2)
        return nodes, faces, 1/v

    def flux(self,t,T,C):
        _,faces,rd = self.mesh(C)
        R = faces[-1]
        a = self.aw(C[-1])
        dp = a*psat(T[-1])-self.ambient_p(t)
        j = BETA0*self.case.beta_factor*dp
        qc = self.external_heat(t,T[-1])
        return j,qc,self.case.latent*LV*j,dp,R,self.rho0*(R0/R)**2

    def rhs(self,t,y):
        m=self.m
        T,C=y[:m],y[m:2*m]
        _,k,D=self.material(T,C)
        nodes,faces,rd=self.mesh(C)
        factor=faces[1:-1]/np.diff(nodes)
        j,qc,ql,_,R,_=self.flux(t,T,C)
        fm,ft=np.zeros(m+1),np.zeros(m+1)
        fm[1:-1]=factor*.5*(rd[:-1]*D[:-1]+rd[1:]*D[1:])*np.diff(C)
        fm[-1]=-R*j
        ct=np.diff(fm)/self.mass
        ft[1:-1]=factor*.5*(k[:-1]+k[1:])*np.diff(T) \
            + self.cw*.5*(T[:-1]+T[1:])*fm[1:-1]
        ft[-1]=R*(qc-ql-self.cw*T[-1]*j)
        et=np.diff(ft)/self.mass
        tt=(et-self.cw*T*ct)/(self.cs+self.cw*C)
        scale=R/np.sum(self.mass)
        return np.r_[tt,ct,scale*j,scale*qc,scale*ql,scale*self.cw*T[-1]*j]


def simulate(case, n, boundary, radius, *, rtol=2e-7, step=600.):
    started = time.perf_counter()
    model = (LocalVolumeModel if case.geometry=='local' else Model)(case, n, boundary, radius)
    m = model.m
    y0 = np.r_[np.full(m, T0), np.full(m, C0), np.zeros(4)]
    def target(t, y): return np.max(y[m:2*m]) - .15
    target.terminal, target.direction = True, -1
    def dry_surface(t, y): return np.min(y[m:2*m]) - 1e-5
    dry_surface.terminal, dry_surface.direction = True, -1
    sol = solve_ivp(model.rhs, (0., case.max_h*3600), y0, method='BDF',
                    jac_sparsity=model.sparsity, rtol=rtol, atol=rtol*1e-2,
                    first_step=.001, max_step=step, dense_output=True,
                    events=[target, dry_surface])
    if not sol.success:
        raise RuntimeError(f'{case.name}: {sol.message}')
    stop = float(sol.t[-1])
    reached = bool(len(sol.t_events[0]))
    status = 'target' if reached else ('wet_surface_depleted' if len(sol.t_events[1]) else 'time_limit')
    # Dense early sampling and local minimization avoid missing the initial cold dip.
    sample = np.unique(np.r_[np.linspace(0, min(stop, 4*3600), 1441),
                             np.linspace(0, stop, 1441), sol.t,
                             [10800.] if stop >= 10800 else []])
    y = sol.sol(sample)
    T, C = y[:m], y[m:2*m]
    meanC, meanT = 2*model.w@C, 2*model.w@T
    if case.geometry == 'local':
        volumes = model.w[:,None]*model.volume(C)
        meanT = np.sum(volumes*T,axis=0)/np.sum(volumes,axis=0)
    fluxes = np.asarray([model.flux(t, yy[:m], yy[m:2*m]) for t, yy in zip(sample, y.T)])
    j, qc, ql, dp, radii, rd = fluxes.T
    ambientp = np.array([model.ambient_p(t) for t in sample])
    td = dewpoint(ambientp)
    stored = 2*model.w@((model.cs+model.cw*C)*T)
    H0 = (model.cs+model.cw*C0)*T0
    h_res = stored-H0-y[2*m+1]+y[2*m+2]+y[2*m+3]
    scale = max(float(np.max(np.abs(y[2*m+1])+np.abs(y[2*m+2])+np.abs(y[2*m+3]))), 1.)
    idx = int(np.argmin(T[-1]))
    optimum = minimize_scalar(lambda t: float(sol.sol(t)[m-1]),
                              bounds=(sample[max(0,idx-1)], sample[min(len(sample)-1,idx+1)]),
                              method='bounded')
    minT = min(float(T[-1,idx]), float(optimum.fun))
    tmin = float(sample[idx] if T[-1,idx] <= optimum.fun else optimum.x)
    violation = (j > 1e-10) & (dp < -1.)
    liquid_fraction = C/model.volume(C)/1000. if case.geometry=='local' else rd[None,:]*C/1000.
    obs = radius[radius[:,0]<=stop]
    radius_rmse = np.sqrt(np.mean((np.interp(obs[:,0],sample,radii)-obs[:,1])**2))
    def at3(array):
        return float(np.interp(10800.,sample,array)) if stop >= 10800 else None
    result = {
        **asdict(case), 'grid': n, 'status': status, 'stop_h': stop/3600,
        'event_h': stop/3600 if reached else None,
        'predicted_equilibrium_C': model.equilibrium_C(),
        'beta_kg_m2_s_Pa': BETA0*case.beta_factor,
        'isotherm_b': model.b,
        'Tmean_3h': at3(meanT), 'Ts_3h': at3(T[-1]), 'Cmean_3h': at3(meanC),
        'min_Ts': minT, 'min_Ts_time_h': tmin/3600,
        'min_Ts_minus_dewpoint': float(np.min(T[-1]-td)),
        'evaporation_against_vapor_gradient': bool(np.any(violation)),
        'max_wrong_way_j': float(np.max(np.where(violation,j,0.))),
        'mass_balance_abs_kg_kg': float(np.max(np.abs(meanC-C0+y[2*m]))),
        'mixture_enthalpy_residual_J_kgdry': float(np.max(np.abs(h_res))),
        'mixture_enthalpy_residual_relative': float(np.max(np.abs(h_res))/scale),
        'max_liquid_volume_fraction': float(np.max(liquid_fraction)),
        'final_radius_cm': float(radii[-1]*100),
        'radius_observation_rmse_cm': float(radius_rmse*100),
        'final_Cmax': float(np.max(C[:,-1])),
        'final_Cmean': float(meanC[-1]),
        'min_C': float(np.min(C)),
        'cpu_wall_s': time.perf_counter()-started,
        'nfev': sol.nfev, 'njev': sol.njev,
    }
    series = {'time_h': (sample/3600).tolist(), 'Ts': T[-1].tolist(), 'Tc': T[0].tolist(),
              'Cmean': meanC.tolist(), 'Cmax': np.max(C,axis=0).tolist(),
              'Cs': C[-1].tolist(), 'Tmean': meanT.tolist(),
              'dewpoint': td.tolist(), 'j_kg_m2_s': j.tolist(),
              'qexternal': qc.tolist(), 'qlatent': ql.tolist(), 'radius_m': radii.tolist(),
              'stored_sensible_J_kgdry': stored.tolist(),
              'integrated_water_out_kg_kgdry': y[2*m].tolist(),
              'integrated_external_J_kgdry': y[2*m+1].tolist(),
              'integrated_latent_J_kgdry': y[2*m+2].tolist(),
              'integrated_liquid_sensible_J_kgdry': y[2*m+3].tolist()}
    dump(OUT / 'series' / f'{case.name}_n{n}.json', series)
    return result


def scope_snapshot(package):
    paths = list((package/'code').rglob('*'))+list((package/'results').rglob('*'))
    paths += list((package/'data').rglob('*'))
    paths += list((HERE/'results').rglob('*'))+[HERE/'run_surface_latent.py']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def cases():
    out = []
    for geom in ('fixed','moving'):
        out += [Case(f'{geom}_M0', geom, boundary='empirical', latent=0),
                Case(f'{geom}_M1', geom, boundary='empirical'),
                Case(f'{geom}_M2wet', geom, boundary='wet', max_h=12),
                Case(f'{geom}_M2', geom),
                Case(f'{geom}_M3capacity', geom, energy='capacity_only'),
                Case(f'{geom}_M3', geom, energy='enthalpy')]
        for eq in (.05, .14, .18):
            out.append(Case(f'{geom}_M3_eq{eq:.2f}', geom, energy='enthalpy', ceq=eq))
        for beta in (.5,2.):
            out.append(Case(f'{geom}_M3_beta{beta:g}',geom,energy='enthalpy',beta_factor=beta))
        out.append(Case(f'{geom}_M3_effective',geom,energy='enthalpy',humidity_basis='effective_material'))
        out.append(Case(f'{geom}_M3_moistair',geom,energy='enthalpy',humidity_basis='moist_air'))
    out.append(Case('moving_M3_radius_slow', 'moving', energy='enthalpy', radius_time_factor=2.))
    out.append(Case('local_M4', 'local', energy='enthalpy'))
    for eq in (.05,.14,.18):
        out.append(Case(f'local_M4_eq{eq:.2f}','local',energy='enthalpy',ceq=eq))
    for beta in (.5,2.):
        out.append(Case(f'local_M4_beta{beta:g}','local',energy='enthalpy',beta_factor=beta))
    out.append(Case('local_M4_pore_collapse','local',energy='enthalpy',pore_collapse=1.))
    out.append(Case('local_M4_effective','local',energy='enthalpy',humidity_basis='effective_material'))
    out.append(Case('local_M4_moistair','local',energy='enthalpy',humidity_basis='moist_air'))
    for exponent in (.7,1.5):
        out.append(Case(f'local_M4_aw{exponent:g}','local',energy='enthalpy',aw_exponent=exponent))
    out.append(Case('local_M4_radiation','local',energy='enthalpy',emissivity=.9))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package',type=Path,default=HERE.parents[1]/'submit/all')
    parser.add_argument('--grid',type=int,default=120)
    parser.add_argument('--only',nargs='*')
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    before = scope_snapshot(args.package)
    boundary, radius, metadata = load_inputs(args.package)
    selected = [c for c in cases() if not args.only or c.name in args.only]
    filename=OUT/f'results_n{args.grid}.json'
    records=json.loads(filename.read_text(encoding='utf-8')) if filename.exists() else []
    for c in selected:
        result=simulate(c,args.grid,boundary,radius)
        records=[r for r in records if r['name']!=c.name]+[result]
        dump(filename,records)
        print(json.dumps(result,ensure_ascii=False),flush=True)
    after=scope_snapshot(args.package)
    dump(OUT/f'scope_audit_n{args.grid}.json',{'unchanged':before==after,'files_checked':len(before),
         'changed':[p for p in before if before[p]!=after.get(p)],'before_sha256':before})
    assert before==after,'Formal inputs, code, results or original comparison were changed'
    if args.verify:
        checks = {}
        for g in ('fixed','moving','local'):
            c=Case(g+('_M4_tight' if g=='local' else '_M3_tight'),g,energy='enthalpy')
            checks[g]=simulate(c,args.grid,boundary,radius,rtol=2e-9,step=300.)
        dump(OUT/f'tolerance_n{args.grid}.json',checks)


if __name__=='__main__':
    with threadpool_limits(limits=1):
        main()
