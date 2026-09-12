"""Recompute Q2 parameter sensitivity with the current Kirchhoff-flux model."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "submit" / "all"
Q2_PATH = PACKAGE / "code" / "q2" / "solve_q2.py"
OUT = Path(__file__).resolve().parent / "q2_sensitivity_current.json"


def load_q2():
    spec = importlib.util.spec_from_file_location("q2_current", Q2_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    q2 = load_q2()
    raw = q2.read_environment()
    boundary_t, boundary_c, env, _ = q2.build_boundaries(raw, mode="staged")
    boundary = (boundary_t, boundary_c)
    base_properties = q2.properties
    base_h, base_hm = q2.H, q2.HM

    def run_case(name, parameter=None, factor=1.0):
        q2.H, q2.HM = base_h, base_hm

        def properties(T, C):
            b, k, d, bc, kc, dc, dt = base_properties(T, C)
            if parameter == "capacity":
                b, bc = factor * b, factor * bc
            elif parameter == "conductivity":
                k, kc = factor * k, factor * kc
            elif parameter == "diffusivity":
                d, dc, dt = factor * d, factor * dc, factor * dt
            return b, k, d, bc, kc, dc, dt

        if parameter == "h":
            q2.H = base_h * factor
        elif parameter == "hm":
            q2.HM = base_hm * factor
        q2.properties = properties
        result = q2.solve_model(200, env, boundary=boundary)
        return {
            "case": name,
            "parameter": parameter,
            "factor": factor,
            "T_center_3h": float(result["T"][-1, 0]),
            "T_surface_3h": float(result["T"][-1, -1]),
            "mean_T_3h": float(result["mean_T"][-1]),
            "C_center_3h": float(result["C"][-1, 0]),
            "C_surface_3h": float(result["C"][-1, -1]),
            "mean_C_3h": float(result["mean_C"][-1]),
        }

    try:
        records = [run_case("baseline")]
        for parameter in ("h", "hm", "capacity", "conductivity", "diffusivity"):
            for factor in (0.8, 1.2):
                records.append(run_case(f"{parameter}_{factor:.1f}", parameter, factor))
    finally:
        q2.properties = base_properties
        q2.H, q2.HM = base_h, base_hm

    baseline = records[0]
    metric_names = [key for key in baseline if key.endswith("_3h")]
    for record in records:
        record["delta"] = {
            key: record[key] - baseline[key] for key in metric_names
        }
    elasticities = {}
    for parameter in ("h", "hm", "capacity", "conductivity", "diffusivity"):
        low = next(r for r in records if r["case"] == f"{parameter}_0.8")
        high = next(r for r in records if r["case"] == f"{parameter}_1.2")
        elasticities[parameter] = {
            key: (high[key] - low[key]) / (0.4 * baseline[key])
            for key in metric_names
        }
    payload = {
        "model": "current Q2 Kirchhoff moisture flux",
        "grid_intervals": 200,
        "rtol": 2e-10,
        "atol": 2e-12,
        "max_step_s": 5.0,
        "records": records,
        "central_dimensionless_sensitivity": elasticities,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
