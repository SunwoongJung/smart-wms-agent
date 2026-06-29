"""Simulation Agent — 의사결정 주기당 1회 배치 What-if(DES)로 KPI를 평가하고
sim-required Action 실행을 게이팅한다.

주기 동안 모인 실시간 데이터(신규 주문/입고는 이미 운영 DB에 반영)를 바탕으로 가까운 미래를
시뮬레이션하여, 팀 가동률이 임계 이상(과부하)이면 추가 자동작업을 보류한다.
Action별로 DES를 돌리면 너무 느리므로 사이클당 1회만 실행한다.
"""
from bb import settings

# 시뮬 결과로 게이팅하는 Action(작업 부하·자원에 영향). 입고/출고확정 등은 게이팅 대상 아님.
SIM_REQUIRED = {"CREATE_PICKING_TASK", "CREATE_PUTAWAY_TASK", "REPRIORITIZE_PICKING_TASK", "ALLOCATE_WORKER"}


def evaluate(horizon_days: int = 7, replications: int = 20) -> dict:
    """현재 상태로 DES 배치 실행 → KPI 산출 → 팀 가동률 임계 초과 시 ok=False."""
    try:
        from sim import des
        r = des.run_des_simulation(horizon_days=horizon_days, replications=replications, persist=False)
    except Exception as e:  # noqa: BLE001 — 시뮬 실패 시 게이트는 통과(자동운영 막지 않음)
        return {"ok": True, "ran": False, "reason": f"시뮬 생략(오류: {e})", "kpis": {}}
    k = {x["kpi_name"]: x for x in r.get("kpis", [])}
    util = (k.get("resource_utilization_team") or {}).get("mean")
    delay = (k.get("shipping_delay_count") or {}).get("mean")
    block = settings.util_block()
    overloaded = util is not None and util >= block
    return {
        "ok": not overloaded,
        "ran": True,
        "reason": (f"팀 가동률 {util*100:.0f}% ≥ 임계 {block*100:.0f}% — 과부하 보류"
                   if overloaded else f"팀 가동률 {util*100:.0f}% — 정상"),
        "team_count": r.get("params", {}).get("team_count"),
        "kpis": {"resource_utilization_team": util, "shipping_delay_count": delay},
    }
