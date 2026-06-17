"""What-if 시뮬레이션 + baseline/scenario 비교 (docs/06 §7.1, docs/07 §9)."""
from sim.des import run_des_simulation


def simulate_operation_what_if(scenario: dict, horizon_days: int = 14,
                               near_future_days: int | None = None,
                               replications: int | None = None) -> dict:
    """운영 조건 변경 시나리오를 시뮬레이션한다.

    scenario 예: {"worker_delta": 1, "forklift_delta": 0,
                  "zone_capa_multiplier": {"ZONE_A": 0.8},
                  "demand_multiplier": 1.3, "inbound_delay_days": 1}
    """
    return run_des_simulation(horizon_days=horizon_days, near_future_days=near_future_days,
                              replications=replications, scenario=scenario, run_type="WHATIF")


def _key(k: dict):
    return (k["kpi_name"], k.get("sku"), k.get("zone_id"))


def compare_simulation_scenarios(baseline: dict, scenario: dict) -> dict:
    """두 run의 KPI 분포 delta를 비교한다."""
    b = {_key(k): k for k in baseline["kpis"]}
    comparison = []
    for k in scenario["kpis"]:
        bk = b.get(_key(k))
        if not bk:
            continue
        row = {"kpi_name": k["kpi_name"]}
        if k.get("sku"):
            row["sku"] = k["sku"]
        if k.get("zone_id"):
            row["zone_id"] = k["zone_id"]
        for fld in ("mean", "p50", "p90", "occurrence_prob"):
            bv, sv = bk.get(fld), k.get(fld)
            if isinstance(bv, (int, float)) and isinstance(sv, (int, float)):
                row[f"baseline_{fld}"] = bv
                row[f"scenario_{fld}"] = sv
                row[f"delta_{fld}"] = round(sv - bv, 3)
        comparison.append(row)
    return {"baseline_sim_run_id": baseline["sim_run_id"],
            "scenario_sim_run_id": scenario["sim_run_id"],
            "comparison": comparison}
