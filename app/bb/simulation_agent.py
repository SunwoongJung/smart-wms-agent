"""Simulation Agent — 배치 What-if(DES) KPI 게이트.

DES는 수 초가 걸리므로 의사결정 사이클을 블로킹하지 않도록 결과를 캐시한다.
- gate(): 캐시를 '즉시' 반환(논블로킹). 오래됐으면 백그라운드 스레드로 갱신만 트리거.
- evaluate(): DES를 실제로 돌려 캐시를 갱신(백그라운드 작업·명시 호출용).
컨트롤 루프는 gate()만 사용하므로 한 건씩 흐르는 흐름이 시뮬레이션에 막히지 않는다.
"""
import threading
import time

from bb import settings

# 시뮬 결과로 게이팅하는 Action(작업 부하·자원에 영향). 입고/출고확정 등은 게이팅 대상 아님.
SIM_REQUIRED = {"CREATE_PICKING_TASK", "CREATE_PUTAWAY_TASK", "REPRIORITIZE_PICKING_TASK", "ALLOCATE_WORKER"}

_CACHE = {"ok": True, "ran": False, "reason": "시뮬 준비 중", "kpis": {}, "ts": None}
_lock = threading.Lock()
_refreshing = False


def _run_des(horizon_days: int, replications: int) -> dict:
    from sim import des
    r = des.run_des_simulation(horizon_days=horizon_days, replications=replications, persist=False)
    k = {x["kpi_name"]: x for x in r.get("kpis", [])}
    util = (k.get("resource_utilization_team") or {}).get("mean")
    delay = (k.get("shipping_delay_count") or {}).get("mean")
    block = settings.util_block()
    overloaded = util is not None and util >= block
    return {
        "ok": not overloaded, "ran": True,
        "reason": (f"팀 가동률 {util*100:.0f}% ≥ 임계 {block*100:.0f}% — 과부하 보류"
                   if overloaded else f"팀 가동률 {util*100:.0f}% — 정상"),
        "team_count": r.get("params", {}).get("team_count"),
        "kpis": {"resource_utilization_team": util, "shipping_delay_count": delay},
        "ts": time.time(),
    }


def evaluate(horizon_days: int = 3, replications: int = 5) -> dict:
    """DES 실행(블로킹) → 캐시 갱신·반환. 게이트용이라 가벼운 파라미터(과부하 신호만 필요)."""
    global _CACHE
    try:
        res = _run_des(horizon_days, replications)
    except Exception as e:  # noqa: BLE001 — 실패 시 게이트 통과(자동운영 막지 않음)
        res = {"ok": True, "ran": False, "reason": f"시뮬 생략(오류: {e})", "kpis": {}, "ts": time.time()}
    with _lock:
        _CACHE = res
    return dict(res)


def _async_refresh() -> None:
    global _refreshing
    with _lock:
        if _refreshing:
            return
        _refreshing = True

    def job():
        global _refreshing
        try:
            evaluate()
        finally:
            with _lock:
                _refreshing = False

    threading.Thread(target=job, name="bb-sim-refresh", daemon=True).start()


def gate() -> dict:
    """캐시 즉시 반환(논블로킹). 캐시가 없거나 오래됐으면 백그라운드 갱신을 트리거."""
    with _lock:
        c = dict(_CACHE)
    age = (time.time() - c["ts"]) if c.get("ts") else None
    if c["ts"] is None or (age is not None and age > settings.sim_refresh_seconds()):
        _async_refresh()
    return c


def kick() -> None:
    """자동운영 시작 시 첫 DES를 백그라운드로 띄워 KPI를 채운다."""
    _async_refresh()
