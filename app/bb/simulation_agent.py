"""Simulation Agent — 배치 What-if(DES) KPI 게이트 (노동/공간 2차원).

DES는 수 초가 걸리므로 사이클을 막지 않도록 결과를 캐시한다.
- gate(): 캐시를 '즉시' 반환(논블로킹). 오래됐으면 백그라운드 갱신만 트리거.
- evaluate(): DES를 실제로 돌려 캐시 갱신(백그라운드/명시 호출용).
게이트는 두 병목을 구분한다:
  · 노동(팀 가동률, 09-18 기준)  → 피킹·우선순위·작업자배정
  · 공간(존별 예측 점유율 피크)  → 적치·입고 (적치는 목표 존 기준)
"""
import threading
import time

from bb import settings

# 노동/공간 게이트 대상 Action
LABOR_GATED = {"CREATE_PICKING_TASK", "REPRIORITIZE_PICKING_TASK", "ALLOCATE_WORKER"}
SPACE_GATED = {"CREATE_PUTAWAY_TASK", "CREATE_INBOUND_TASK"}
SIM_REQUIRED = LABOR_GATED | SPACE_GATED   # 하위호환

# 캐시에는 '원시 KPI'만 저장(임계값은 굽지 않는다) — 임계 비교는 gate() 읽기 시점에 최신 설정으로.
_CACHE = {"ran": False, "kpis": {}, "zone_peak": {}, "team_count": None, "ts": None}
_lock = threading.Lock()
_refreshing = False


def _run_des() -> dict:
    from sim import des
    r = des.run_des_simulation(horizon_days=settings.sim_horizon_days(),
                               replications=settings.sim_replications(), persist=False)
    k = {x["kpi_name"]: x for x in r.get("kpis", [])}
    util = (k.get("resource_utilization_team") or {}).get("mean")
    delay = (k.get("shipping_delay_count") or {}).get("mean")
    # 존별 예측 점유율 피크(시뮬 타임시리즈에서 존별 최댓값)
    zone_peak: dict = {}
    for snap in (r.get("zone_occupancy_timeseries") or []):
        for z, occ in (snap.get("occupancy") or {}).items():
            if occ > zone_peak.get(z, 0):
                zone_peak[z] = occ
    return {"ran": True, "zone_peak": zone_peak, "team_count": r.get("params", {}).get("team_count"),
            "kpis": {"resource_utilization_team": util, "shipping_delay_count": delay}, "ts": time.time()}


def evaluate() -> dict:
    """DES 실행(블로킹) → 원시 KPI 캐시 갱신. 반환은 gate()와 동일 형식."""
    global _CACHE
    try:
        res = _run_des()
    except Exception as e:  # noqa: BLE001 — 실패 시 게이트 통과(자동운영 막지 않음)
        res = {"ran": False, "kpis": {}, "zone_peak": {}, "team_count": None,
               "error": str(e), "ts": time.time()}
    with _lock:
        _CACHE = res
    return _decorate(dict(res))


def _decorate(c: dict) -> dict:
    """원시 캐시에 '현재 임계값' 기준의 판정(labor_ok·space_ok·ok·reason)을 입힌다."""
    ub, zb = settings.util_block(), settings.zone_block()
    util = (c.get("kpis") or {}).get("resource_utilization_team")
    zp = c.get("zone_peak") or {}
    worst = max(zp.items(), key=lambda kv: kv[1], default=(None, 0))
    c["labor_ok"] = (util is None) or (util <= ub)
    c["space_ok"] = worst[1] <= zb
    c["ok"] = c["labor_ok"] and c["space_ok"]
    c["util_block"], c["zone_block"] = ub, zb
    c["worst_zone"], c["worst_zone_occ"] = worst
    c["refresh_seconds"] = settings.sim_refresh_seconds()   # 다음 갱신 카운트다운용
    if not c.get("ran"):
        c["reason"] = c.get("error") and f"시뮬 생략(오류: {c['error']})" or "시뮬 준비 중"
    else:
        us = f"{util*100:.0f}%" if util is not None else "—"
        c["reason"] = f"가동률 {us}(임계 {ub*100:.0f}%) · 최대존점유 {worst[1]*100:.0f}%(임계 {zb*100:.0f}%)"
    return c


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
    """캐시 즉시 반환(논블로킹) + 현재 임계값 기준 판정 부여. 오래됐으면 백그라운드 갱신 트리거."""
    with _lock:
        c = dict(_CACHE)
    age = (time.time() - c["ts"]) if c.get("ts") else None
    if c["ts"] is None or (age is not None and age > settings.sim_refresh_seconds()):
        _async_refresh()
    return _decorate(c)


def kick() -> None:
    """자동운영 시작 시 첫 DES를 백그라운드로 띄워 KPI를 채운다."""
    _async_refresh()
