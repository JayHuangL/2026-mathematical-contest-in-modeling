"""Surface latent-heat model-form sensitivity for the integrated A problem.

This script reads submit/all without modifying its code or formal results.  It
compares the existing model with a surface energy balance that subtracts the
latent heat associated with the effective dry-basis moisture flux.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse import bmat, csr_matrix, diags
from threadpoolctl import threadpool_limits


HERE = Path(__file__).resolve().parent
H = 25.0
HM = 8e-7
R0 = 0.02
T0 = 28.0
C0 = 2.55


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def find_package(explicit: Path | None) -> Path:
    if explicit is not None:
        package = explicit.resolve()
    else:
        candidates = [HERE, *HERE.parents]
        package = next((p for p in candidates if (p / "code/q2/solve_q2.py").exists()), None)
        if package is None:
            raise FileNotFoundError("Use --package to point to submit/all.")
    required = [package / "code/q2/solve_q2.py", package / "code/q4/solve_q4.py",
                package / "data/附件1.xlsx", package / "data/附件2.xlsx"]
    if not all(p.exists() for p in required):
        raise FileNotFoundError(f"Incomplete integrated package: {package}")
    return package


def build_boundary(package: Path, q2):
    boundary_stage = load_module("latent_boundary", package / "code/q2/boundary_stage.py")
    raw = q2.read_environment()
    bt, bc, env, metadata = boundary_stage.build_boundaries(
        raw, mode="staged", fit_endpoint_s=14400.0
    )
    return env, (bt, bc), metadata


def rho_d0_for(geometry: str) -> float:
    rho_wet_initial = (650.0 + 128.0 * C0) if geometry == "fixed" else (760.0 + 90.0 * C0)
    return rho_wet_initial / (1.0 + C0)


class FixedSurfaceLatent:
    def __init__(self, q2, n, env, boundary, lv, latent_factor, rho_d_factor):
        self.q2 = q2
        self.n = n
        self.m = n + 1
        self.env = env
        self.boundary = boundary
        self.lv = lv
        self.latent_factor = latent_factor
        self.rho_d = rho_d0_for("fixed") * rho_d_factor
        z = np.linspace(0.0, 1.0, n + 1)
        self.r = R0 * (-np.expm1(-4.0 * z)) / (-np.expm1(-4.0))
        self.faces = (self.r[:-1] + self.r[1:]) / 2.0
        self.w = np.diff(np.r_[0.0, self.faces, R0] ** 2) / 2.0
        self.area = R0**2 / 2.0
        self.factor = self.faces / np.diff(self.r)
        self.zero = csr_matrix((1, self.m))

    def ambient(self, t):
        return float(self.boundary[0](t)), float(self.boundary[1](t))

    def surface_fluxes(self, t, state):
        ta, ca = self.ambient(t)
        ts, cs = state[self.m - 1], state[2 * self.m - 1]
        conv = H * (ta - ts)
        latent = self.latent_factor * self.rho_d * self.lv * HM * (cs - ca)
        return float(conv), float(latent), float(conv - latent)

    def rhs(self, t, state):
        m = self.m
        T, C = state[:m], state[m:2 * m]
        b, k, d, *_ = self.q2.properties(T, C)
        ta, ca = self.ambient(t)
        ft = np.empty(m + 1, dtype=state.dtype)
        fc = np.empty_like(ft)
        ft[0] = fc[0] = 0.0
        ft[1:-1] = self.factor * (k[:-1] + k[1:]) / 2.0 * np.diff(T)
        fc[1:-1] = self.factor * (d[:-1] + d[1:]) / 2.0 * np.diff(C)
        latent = self.latent_factor * self.rho_d * self.lv * HM * (C[-1] - ca)
        ft[-1] = R0 * (H * (ta - T[-1]) - latent)
        fc[-1] = R0 * HM * (ca - C[-1])
        return np.r_[np.diff(ft) / (self.w * b), np.diff(fc) / self.w,
                        fc[-1] / self.area]

    @staticmethod
    def block(left, right, boundary, denominator):
        main = np.r_[left, boundary] - np.r_[0.0, right]
        return diags((-left / denominator[1:], main / denominator,
                      right / denominator[:-1]), (-1, 0, 1), format="csr")

    def jac(self, t, state):
        m = self.m
        T, C = state[:m], state[m:2 * m]
        b, k, d, bc, kc, dc, dt = self.q2.properties(T, C)
        f = self.factor
        dT, dC = np.diff(T), np.diff(C)
        kf, df = (k[:-1] + k[1:]) / 2.0, (d[:-1] + d[1:]) / 2.0
        jtt = self.block(-f * kf, f * kf, -R0 * H, self.w * b)
        latent_c = -R0 * self.latent_factor * self.rho_d * self.lv * HM
        jtc = self.block(0.5 * f * kc[:-1] * dT, 0.5 * f * kc[1:] * dT,
                         latent_c, self.w * b)
        jtc -= diags(self.rhs(t, state)[:m] * bc / b, format="csr")
        jcc = self.block(f * (0.5 * dc[:-1] * dC - df),
                         f * (0.5 * dc[1:] * dC + df), -R0 * HM, self.w)
        jct = self.block(0.5 * f * dt[:-1] * dC, 0.5 * f * dt[1:] * dC,
                         0.0, self.w)
        balance_c = csr_matrix(([-2.0 * HM / R0], ([0], [m - 1])), shape=(1, m))
        return bmat([[jtt, jtc, None], [jct, jcc, None],
                     [self.zero, balance_c, csr_matrix((1, 1))]], format="csc")


class MovingSurfaceLatent:
    def __init__(self, q4, n, env, radius, boundary, lv, latent_factor, rho_d_factor):
        self.q4 = q4
        self.base = q4.Model(n, env, radius, boundary=boundary, radius_method="pchip")
        self.__dict__.update(self.base.__dict__)
        self.lv = lv
        self.latent_factor = latent_factor
        self.rho_d_initial = rho_d0_for("moving") * rho_d_factor

    def R(self, t):
        return self.base.R(t)

    def ambient(self, t):
        return self.base.ambient(t)

    def block(self, left, right, boundary, denominator):
        return self.base.block(left, right, boundary, denominator)

    def dry_density(self, t):
        radius = float(self.R(t))
        return self.rho_d_initial * (R0 / radius) ** 2

    def surface_fluxes(self, t, state):
        ta, ca = self.ambient(t)
        ts, cs = state[self.m - 1], state[2 * self.m - 1]
        conv = H * (ta - ts)
        latent = self.latent_factor * self.dry_density(t) * self.lv * HM * (cs - ca)
        return float(conv), float(latent), float(conv - latent)

    def rhs(self, t, state):
        m = self.m
        T, C = state[:m], state[m:2 * m]
        b, k, d, *_ = self.material(T, C)
        radius = float(self.R(t))
        ta, ca = self.ambient(t)
        ft = np.empty(m + 1, dtype=state.dtype)
        fc = np.empty_like(ft)
        ft[0] = fc[0] = 0.0
        ft[1:-1] = self.factor * (k[:-1] + k[1:]) / 2.0 * np.diff(T)
        fc[1:-1] = self.factor * (d[:-1] + d[1:]) / 2.0 * np.diff(C)
        latent = self.latent_factor * self.dry_density(t) * self.lv * HM * (C[-1] - ca)
        ft[-1] = radius * (H * (ta - T[-1]) - latent)
        fc[-1] = radius * HM * (ca - C[-1])
        return np.r_[np.diff(ft) / (radius**2 * self.w * b),
                        np.diff(fc) / (radius**2 * self.w),
                        2.0 * HM / radius * (ca - C[-1])]

    def jac(self, t, state):
        m = self.m
        T, C = state[:m], state[m:2 * m]
        b, k, d, bc, kc, dc, dt = self.material(T, C)
        radius = float(self.R(t))
        f = self.factor
        dT, dC = np.diff(T), np.diff(C)
        kf, df = (k[:-1] + k[1:]) / 2.0, (d[:-1] + d[1:]) / 2.0
        jtt = self.block(-f * kf, f * kf, -radius * H, radius**2 * self.w * b)
        latent_c = -radius * self.latent_factor * self.dry_density(t) * self.lv * HM
        jtc = self.block(0.5 * f * kc[:-1] * dT, 0.5 * f * kc[1:] * dT,
                         latent_c, radius**2 * self.w * b)
        jtc -= diags(self.rhs(t, state)[:m] * bc / b, format="csr")
        jcc = self.block(f * (0.5 * dc[:-1] * dC - df),
                         f * (0.5 * dc[1:] * dC + df), -radius * HM,
                         radius**2 * self.w)
        jct = self.block(0.5 * f * dt[:-1] * dC, 0.5 * f * dt[1:] * dC,
                         0.0, radius**2 * self.w)
        fluxrow = csr_matrix(([-2.0 * HM / radius], ([0], [m - 1])), shape=(1, m))
        return bmat([[jtt, jtc, None], [jct, jcc, None],
                     [self.zero, fluxrow, csr_matrix((1, 1))]], format="csc")


def check_jacobian(model):
    rng = np.random.default_rng(20260911)
    x = model.r / R0 if hasattr(model, "r") else model.x
    state = np.r_[28.0 + 5.0 * x**2, C0 - 0.7 * x**2, 0.0]
    errors = []
    for t in (600.0, 7200.0, 72000.0):
        jac = model.jac(t, state)
        direction = rng.normal(size=state.size)
        exact = np.imag(model.rhs(t, state + 1e-25j * direction)) / 1e-25
        errors.append(float(np.max(np.abs(jac @ direction - exact)) /
                            max(np.max(np.abs(exact)), 1e-30)))
    return max(errors)


def simulate(model, q2, end_limit=864000.0):
    m = model.m
    initial = np.r_[np.full(m, T0), np.full(m, C0), 0.0]

    def event(t, state):
        return float(np.max(state[m:2 * m]) - 0.15)

    event.terminal = True
    event.direction = -1
    sol = solve_ivp(model.rhs, (0.0, end_limit), initial, method="BDF", jac=model.jac,
                    rtol=2e-9, atol=2e-11, max_step=300.0, first_step=0.001,
                    events=event, dense_output=True)
    if not sol.success:
        raise RuntimeError(sol.message)
    event_s = float(sol.t_events[0][0]) if len(sol.t_events[0]) else np.nan
    stop = event_s if np.isfinite(event_s) else float(sol.t[-1])
    sample = np.unique(np.r_[np.linspace(0.0, stop, 401), [1800.0, 3600.0, 7200.0, 10800.0]])
    sample = sample[sample <= stop]
    states = sol.sol(sample)
    T, C = states[:m], states[m:2 * m]
    mean_T = np.sum(model.w[:, None] * T, axis=0) / np.sum(model.w)
    mean_C = np.sum(model.w[:, None] * C, axis=0) / np.sum(model.w)
    conv, latent, net, residual = [], [], [], []
    for t, state in zip(sample, states.T):
        qc, ql, qn = model.surface_fluxes(float(t), state)
        conv.append(qc); latent.append(ql); net.append(qn)
        rhs = model.rhs(float(t), state)
        b = q2.properties(state[:m], state[m:2*m])[0] if isinstance(model, FixedSurfaceLatent) \
            else model.material(state[:m], state[m:2*m])[0]
        radius = R0 if isinstance(model, FixedSurfaceLatent) else float(model.R(t))
        scale = 1.0 if isinstance(model, FixedSurfaceLatent) else radius**2
        lhs = np.sum(scale * model.w * b * rhs[:m])
        residual.append(abs(lhs - radius * qn))

    def at(seconds, array):
        return float(np.interp(seconds, sample, array)) if seconds <= sample[-1] else np.nan

    surface_T = T[-1]
    surface_C = C[-1]
    result = {
        "event_h": event_s / 3600.0 if np.isfinite(event_s) else None,
        "event_reached": bool(np.isfinite(event_s)),
        "T_center_3h": at(10800.0, T[0]),
        "T_surface_3h": at(10800.0, surface_T),
        "T_mean_3h": at(10800.0, mean_T),
        "C_center_3h": at(10800.0, C[0]),
        "C_surface_3h": at(10800.0, surface_C),
        "C_mean_3h": at(10800.0, mean_C),
        "min_surface_T_C": float(np.min(surface_T)),
        "time_min_surface_T_h": float(sample[np.argmin(surface_T)] / 3600.0),
        "peak_latent_flux_W_m2": float(np.max(latent)),
        "min_net_heat_flux_W_m2": float(np.min(net)),
        "max_heat_rate_balance_error": float(np.max(residual)),
        "moisture_balance_error": float(np.max(np.abs(mean_C - C0 - states[-1]))),
        "t_h": (sample / 3600.0).tolist(),
        "T_center": T[0].tolist(),
        "T_surface": surface_T.tolist(),
        "C_center": C[0].tolist(),
        "C_surface": surface_C.tolist(),
        "convective_flux": np.asarray(conv).tolist(),
        "latent_flux": np.asarray(latent).tolist(),
        "net_heat_flux": np.asarray(net).tolist(),
    }
    return result


def make_figure(records, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "font.size": 10})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for geometry, marker in (("fixed", "o"), ("moving", "s")):
        rows = [r for r in records if r["geometry"] == geometry]
        axes[0, 0].plot([r["latent_factor"] for r in rows], [r["event_h"] for r in rows],
                        marker=marker, label="固定半径" if geometry == "fixed" else "收缩半径")
    axes[0, 0].set(xlabel="潜热系数倍率", ylabel="达标时间 / h", title="潜热对干燥终点的影响")
    for geometry, color in (("fixed", "tab:blue"), ("moving", "tab:orange")):
        for factor, style in ((0.0, "--"), (1.0, "-")):
            r = next(x for x in records if x["geometry"] == geometry and x["latent_factor"] == factor)
            t = np.array(r["series"]["t_h"]); mask = t <= 4.0
            axes[0, 1].plot(t[mask], np.array(r["series"]["T_surface"])[mask], color=color, ls=style,
                            label=f"{'固定' if geometry=='fixed' else '收缩'}，倍率{factor:g}")
            axes[1, 0].plot(t, r["series"]["C_center"], color=color, ls=style,
                            label=f"{'固定' if geometry=='fixed' else '收缩'}，倍率{factor:g}")
    full = next(x for x in records if x["geometry"] == "fixed" and x["latent_factor"] == 1.0)
    t = np.array(full["series"]["t_h"]); mask = t <= 4.0
    axes[1, 1].plot(t[mask], np.array(full["series"]["convective_flux"])[mask], label="对流供热")
    axes[1, 1].plot(t[mask], np.array(full["series"]["latent_flux"])[mask], label="潜热消耗")
    axes[1, 1].plot(t[mask], np.array(full["series"]["net_heat_flux"])[mask], label="进入药材净热流")
    axes[0, 1].set(xlabel="时间 / h", ylabel="表面温度 / °C", title="表面蒸发冷却")
    axes[1, 0].set(xlabel="时间 / h", ylabel="中心干基含水率 / (kg/kg)", title="中心干燥过程")
    axes[1, 1].set(xlabel="时间 / h", ylabel="热流密度 / (W/m²)", title="固定半径全潜热情景")
    for ax in axes.flat:
        ax.grid(alpha=0.25); ax.legend(fontsize=8)
    fig.savefig(out / "表面潜热敏感性.png", dpi=180)
    plt.close(fig)


def write_report(records, metadata, validation, out, lv, rho_factor, n):
    def row(geometry, factor):
        return next(r for r in records if r["geometry"] == geometry and r["latent_factor"] == factor)
    fb, fl, mb, ml = row("fixed", 0.0), row("fixed", 1.0), row("moving", 0.0), row("moving", 1.0)
    lines = [
        "# 表面相变潜热的模型形式敏感性分析", "",
        "本分析为独立对照，不修改四问主模型及正式结果。附录经验密度仍按局部含水率用于有效热容量；潜热通量使用空间均匀的干物质体积密度。固定半径时该密度为常数，收缩模型中按 $R_0^2/R(t)^2$ 更新。", "",
        "## 模型", "",
        "表面水质量通量和净入射热流取", "",
        "$$j_w=\\rho_dh_m(C_s-C_a),$$", "",
        "$$q_{\\mathrm{in}}=h(T_a-T_s)-\\lambda L_vj_w,$$", "",
        "其中 $\\lambda$ 为潜热倍率。$\\lambda=0$ 复现原模型，$\\lambda=1$ 为完整表面潜热情景。这里并未把整个区域的 $C_t$ 当作汽化速率。", "",
        f"计算采用 $L_v={lv:.3g}$ J/kg、干物质密度倍率 {rho_factor:g}、每个模型 {n} 个径向区间。阶段化拉伸指数环境边界与正式模型一致。", "",
        "## 结果", "",
        "| 几何 | 潜热倍率 | 达标时间 / h | 3 h平均温度 / °C | 3 h平均含水率 | 最低表面温度 / °C | 峰值潜热通量 / (W/m²) |", "|---|---:|---:|---:|---:|---:|---:|"
    ]
    for r in records:
        event = "未在240 h内达到" if r["event_h"] is None else f'{r["event_h"]:.6f}'
        lines.append(f'| {"固定半径" if r["geometry"]=="fixed" else "收缩半径"} | {r["latent_factor"]:.2f} | {event} | {r["T_mean_3h"]:.4f} | {r["C_mean_3h"]:.4f} | {r["min_surface_T_C"]:.4f} | {r["peak_latent_flux_W_m2"]:.2f} |')
    lines += ["", "全潜热相对无潜热的终点变化：", "",
              f'- 固定半径：{fb["event_h"]:.6f} h → {fl["event_h"]:.6f} h，延长 {fl["event_h"]-fb["event_h"]:.6f} h（约 {(fl["event_h"]/fb["event_h"]-1)*100:.2f}%）；',
              f'- 收缩半径：{mb["event_h"]:.6f} h → {ml["event_h"]:.6f} h，延长 {ml["event_h"]-mb["event_h"]:.6f} h（约 {(ml["event_h"]/mb["event_h"]-1)*100:.2f}%）。', "",
              f'全潜热情景从 $N={validation["grid_check"]}$ 加密到 $N={validation["grid_main"]}$ 后，固定半径终点变化约 {validation["fixed_event_difference_s"]:.2f} s，收缩半径终点变化约 {validation["moving_event_difference_s"]:.2f} s；该网格差明显小于潜热造成的小时级变化。', "",
              "## 合理性解释", "",
              "若加入潜热后出现明显蒸发冷却或终点大幅推迟，这首先说明潜热项对结果重要；同时也说明现有 $h_m$ 与 $C_a$ 作为有效干基边界时，未必能直接解释为真实水质量通量。尤其当潜热需求超过对流供热时，模型会通过降低表面温度取得能量平衡。该结果应作为模型形式敏感性，而不直接替换正式答案。", "",
              "代码同时检查了解析 Jacobian、含水率累计收支和瞬时热量收支。详细数值见 sensitivity_results.csv 与 sensitivity_results.json，曲线见表面潜热敏感性.png。", "",
              "## 边界拟合记录", "",
              f'阶段共同分界时刻：{metadata["phase_common_s"]:.1f} s；稳定温度：{metadata["plateau_temperature"]:.8f} °C；稳定环境水分：{metadata["plateau_moisture"]:.8f} kg/kg。', ""]
    (out / "表面潜热模型与结果.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=None, help="Path to submit/all")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--grid", type=int, default=300)
    parser.add_argument("--grid-check", type=int, default=150)
    parser.add_argument("--lv", type=float, default=2.4e6)
    parser.add_argument("--rho-d-factor", type=float, default=1.0)
    parser.add_argument("--factors", type=float, nargs="+", default=[0.0, 0.25, 0.5, 0.75, 1.0])
    args = parser.parse_args()
    package = find_package(args.package)
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    q2 = load_module("latent_q2", package / "code/q2/solve_q2.py")
    q4 = load_module("latent_q4", package / "code/q4/solve_q4.py")
    env, boundary, metadata = build_boundary(package, q2)
    radius = q4.read_xlsx(package / "data/附件2.xlsx"); radius[:, 1] /= 100.0
    records = []
    for geometry in ("fixed", "moving"):
        for factor in args.factors:
            if geometry == "fixed":
                model = FixedSurfaceLatent(q2, args.grid, env, boundary, args.lv, factor, args.rho_d_factor)
            else:
                model = MovingSurfaceLatent(q4, args.grid, env, radius, boundary, args.lv, factor, args.rho_d_factor)
            jac_error = check_jacobian(model)
            if jac_error > 2e-10:
                raise AssertionError(f"Jacobian check failed: {jac_error}")
            result = simulate(model, q2)
            series = {k: result.pop(k) for k in ("t_h", "T_center", "T_surface", "C_center",
                                                   "C_surface", "convective_flux", "latent_flux",
                                                   "net_heat_flux")}
            record = {"geometry": geometry, "latent_factor": factor, "L_v_J_kg": args.lv,
                      "rho_d_factor": args.rho_d_factor,
                      "rho_d_initial_kg_m3": rho_d0_for(geometry) * args.rho_d_factor,
                      "jacobian_relative_error": jac_error, **result, "series": series}
            records.append(record)
            print(json.dumps({k: v for k, v in record.items() if k != "series"}, ensure_ascii=False), flush=True)
    serial = {"model": "surface latent heat as model-form sensitivity",
              "formal_results_modified": False, "boundary_metadata": metadata, "cases": records}
    (out / "sensitivity_results.json").write_text(json.dumps(serial, ensure_ascii=False, indent=2), encoding="utf-8")
    scalar_keys = [k for k in records[0] if k != "series"]
    with (out / "sensitivity_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=scalar_keys); writer.writeheader()
        for record in records: writer.writerow({k: record[k] for k in scalar_keys})
    grid_events = {}
    for geometry in ("fixed", "moving"):
        if geometry == "fixed":
            model = FixedSurfaceLatent(q2, args.grid_check, env, boundary, args.lv, 1.0, args.rho_d_factor)
        else:
            model = MovingSurfaceLatent(q4, args.grid_check, env, radius, boundary, args.lv, 1.0, args.rho_d_factor)
        grid_events[geometry] = simulate(model, q2)["event_h"]
    full_fixed = next(r for r in records if r["geometry"] == "fixed" and r["latent_factor"] == 1.0)
    full_moving = next(r for r in records if r["geometry"] == "moving" and r["latent_factor"] == 1.0)
    validation = {
        "model": "surface latent heat used only as model-form sensitivity",
        "formal_results_modified": False,
        "grid_main": args.grid,
        "grid_check": args.grid_check,
        "fixed_full_latent_event_h_grid_check": grid_events["fixed"],
        "fixed_full_latent_event_h_grid_main": full_fixed["event_h"],
        "fixed_event_difference_s": abs(full_fixed["event_h"] - grid_events["fixed"]) * 3600.0,
        "moving_full_latent_event_h_grid_check": grid_events["moving"],
        "moving_full_latent_event_h_grid_main": full_moving["event_h"],
        "moving_event_difference_s": abs(full_moving["event_h"] - grid_events["moving"]) * 3600.0,
        "max_jacobian_relative_error": max(r["jacobian_relative_error"] for r in records),
        "max_heat_rate_balance_error": max(r["max_heat_rate_balance_error"] for r in records),
        "max_moisture_balance_error": max(r["moisture_balance_error"] for r in records),
    }
    (out / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    make_figure(records, out)
    write_report(records, metadata, validation, out, args.lv, args.rho_d_factor, args.grid)
    print(f"Wrote independent latent-heat sensitivity results to {out}")


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        main()
