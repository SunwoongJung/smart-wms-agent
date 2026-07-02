"""KPI Dashboard(docs/13) — 실데이터 기반 4대 KPI + 부가정보.

기준일: "오늘"은 실시간 모듈이 계속 데이터를 생성해 값이 흔들리므로 쓰지 않는다.
서버 실제 날짜의 어제(하루 전) 종료 시점을 일별집계·주간 트렌드의 기준으로 삼는다.
"""
import random
from datetime import date, datetime, timedelta

import resmgmt
from db.database import get_connection
from tools.common import q

WORK_MINUTES_PER_DAY = 540  # 09-18 가동 기준(sim/des.py와 동일)
_DT_FMT = "%Y-%m-%d %H:%M:%S"


def reference_date() -> str:
    """일별집계 기준일(어제) — YYYY-MM-DD."""
    return (date.today() - timedelta(days=1)).isoformat()


def _day_range(end_date: str, days: int) -> list[str]:
    end = date.fromisoformat(end_date)
    return [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


# ---------- 1) Zone 점유율 ----------
def zone_occupancy() -> list[dict]:
    # 실제 가용 재고 합 기준(권장). locations.occupied_qty는 피킹 시 감소하지 않아 드리프트가 생기므로 쓰지 않는다.
    return q("""SELECT z.zone_id, ROUND(COALESCE((
                    SELECT SUM(i.qty) FROM inventory i JOIN locations l ON l.location_id=i.location_id
                    WHERE l.zone_id=z.zone_id AND i.status='AVAILABLE'), 0) * 1.0 / z.max_capacity, 3) AS occupancy
                FROM zones z ORDER BY z.zone_id""")


def zone_occupancy_avg() -> float | None:
    zones = zone_occupancy()
    if not zones:
        return None
    return round(sum(z["occupancy"] for z in zones) / len(zones), 3)


def zones_over_target(target: float) -> list[dict]:
    return [z for z in zone_occupancy() if z["occupancy"] > target]


# ---------- 2) 작업팀 가동률 ----------
def _team_count() -> int:
    r = resmgmt.get_resources()
    return max(1, min(r["worker"] // 2, r["forklift"]))


def _stocking_minutes_mean() -> float:
    r = q("SELECT mean_minutes FROM process_time_params WHERE stage='STOCKING'")
    return r[0]["mean_minutes"] if r else 12.0


def _real_utilization(d: str) -> float | None:
    """해당일 완료된 적치 작업 기준 실측 가동률(피킹 완료로그는 아직 없음 — 향후 항목)."""
    n = q("""SELECT COUNT(*) n FROM stocking_tasks
             WHERE completed_at IS NOT NULL AND date(completed_at)=?""", (d,))[0]["n"]
    if n == 0:
        return None
    busy_minutes = n * _stocking_minutes_mean()
    return round(min(1.0, busy_minutes / (_team_count() * WORK_MINUTES_PER_DAY)), 3)


def _ensure_synthetic(metric: str, dates: list[str]) -> None:
    existing = {r["fill_date"] for r in q(
        "SELECT fill_date FROM kpi_synthetic_fill WHERE metric=? AND fill_date IN (%s)"
        % ",".join("?" for _ in dates), tuple([metric, *dates]))}
    missing = [d for d in dates if d not in existing]
    if not missing:
        return
    conn = get_connection()
    try:
        for d in missing:
            rng = random.Random(f"{metric}:{d}")
            v = round(rng.uniform(0.65, 0.95), 3)
            conn.execute(
                "INSERT OR IGNORE INTO kpi_synthetic_fill(metric,fill_date,value) VALUES(?,?,?)",
                (metric, d, v),
            )
        conn.commit()
    finally:
        conn.close()


def _synthetic_utilization(dates: list[str]) -> dict:
    _ensure_synthetic("team_utilization", dates)
    rows = q("SELECT fill_date, value FROM kpi_synthetic_fill WHERE metric='team_utilization' AND fill_date IN (%s)"
              % ",".join("?" for _ in dates), tuple(dates))
    return {r["fill_date"]: r["value"] for r in rows}


def team_utilization_trend(days: int = 7, end_date: str | None = None) -> list[dict]:
    dates = _day_range(end_date or reference_date(), days)
    real = {d: _real_utilization(d) for d in dates}
    need_synth = [d for d in dates if real[d] is None]
    synth = _synthetic_utilization(need_synth) if need_synth else {}
    return [{"date": d, "value": real[d] if real[d] is not None else synth.get(d)} for d in dates]


def team_utilization_current(end_date: str | None = None) -> float | None:
    trend = team_utilization_trend(days=1, end_date=end_date)
    return trend[0]["value"] if trend else None


# ---------- 3) 출고지연 / 4) 적치지연 ----------
def shipping_delay_count(d: str) -> int:
    return q("""SELECT COUNT(*) n FROM outbound_orders
                WHERE due_datetime <= ? AND (shipped_datetime IS NULL OR shipped_datetime > ?)""",
              (f"{d} 23:59:59", f"{d} 23:59:59"))[0]["n"]


def putaway_delay_count(d: str) -> int:
    return q("""SELECT COUNT(*) n FROM inbound_orders io
                WHERE io.received_datetime IS NOT NULL AND io.received_datetime <= ?
                  AND NOT EXISTS (
                    SELECT 1 FROM stocking_tasks st
                    WHERE st.inbound_no = io.inbound_no
                      AND st.completed_at IS NOT NULL AND st.completed_at <= ?
                  )""", (f"{d} 23:59:59", f"{d} 23:59:59"))[0]["n"]


def delay_trend(days: int = 7, end_date: str | None = None) -> list[dict]:
    dates = _day_range(end_date or reference_date(), days)
    return [{"date": d, "shipping_delay_count": shipping_delay_count(d),
             "putaway_delay_count": putaway_delay_count(d)} for d in dates]


# ---------- 피킹 대기시간(실측) ----------
def _wait_seconds(issued_at: str, started_at: str) -> float | None:
    try:
        d = (datetime.strptime(started_at, _DT_FMT) - datetime.strptime(issued_at, _DT_FMT)).total_seconds()
        return d if d >= 0 else None
    except (ValueError, TypeError):
        return None


def picking_wait(days: int = 7, end_date: str | None = None) -> dict:
    """피킹 작업의 실측 대기시간 = started_at(zone 진입) − issued_at(작업 생성).

    자동운영이 실제로 처리한 작업만 started_at이 있으므로 시드 더미(started_at NULL)는 자연 제외된다.
    완료/진행 중이라도 이미 시작된 작업은 실측치를 갖고, 아직 대기 중(TEAM_ASSIGNED)인 작업은
    now−issued_at 로 '현재 대기 경과'를 반영한다.
    """
    start = _day_range(end_date or reference_date(), days)[0]
    waits = []
    for r in q("""SELECT issued_at, started_at FROM picking_tasks
                  WHERE started_at IS NOT NULL AND issued_at IS NOT NULL AND issued_at >= ?""", (f"{start} 00:00:00",)):
        w = _wait_seconds(r["issued_at"], r["started_at"])
        if w is not None:
            waits.append(w)
    ongoing = q("""SELECT COUNT(*) n FROM picking_tasks
                   WHERE status='TEAM_ASSIGNED' AND started_at IS NULL""")[0]["n"]
    avg = round(sum(waits) / len(waits)) if waits else None
    mx = round(max(waits)) if waits else None
    return {"avg_seconds": avg, "max_seconds": mx, "sample": len(waits), "waiting_now": ongoing}


# ---------- 부가정보: 품절 / 1주 내 소진 예상 재고, 재고금액 ----------
def stockout_analysis(limit: int = 5) -> dict:
    """수요가 있는 SKU를 (a) 품절(재고 0)과 (b) 1주 내 소진 예상(재고>0, days_left≤7)으로 분리.

    이미 재고가 0인 SKU는 '소진 예상'이 아니라 '품절'이므로 소진 예상 목록에 넣지 않는다.
    """
    empty = {"within_week_count": 0, "within_week_items": [], "out_of_stock_count": 0, "out_of_stock_items": []}
    anchor = q("SELECT MAX(demand_date) d FROM demand_history")[0]["d"]
    if not anchor:
        return empty
    start = (date.fromisoformat(anchor) - timedelta(days=27)).isoformat()
    demand = q("""SELECT sku, AVG(shipped_qty) avg_qty FROM demand_history
                  WHERE demand_date > ? AND demand_date <= ? GROUP BY sku""", (start, anchor))
    stock = {r["sku"]: r["qty"] for r in
             q("SELECT sku, COALESCE(SUM(qty),0) qty FROM inventory WHERE status='AVAILABLE' GROUP BY sku")}
    within, oos = [], []
    for r in demand:
        avg_qty = r["avg_qty"] or 0
        if avg_qty <= 0:
            continue
        qty = stock.get(r["sku"], 0)
        if qty <= 0:   # 이미 소진됨 = 품절(별도 표기)
            oos.append({"sku": r["sku"], "avg_daily_demand": round(avg_qty, 1)})
            continue
        days_left = qty / avg_qty
        if days_left <= 7:   # 재고는 있으나 1주 내 소진 예상
            within.append({"sku": r["sku"], "qty": qty, "avg_daily_demand": round(avg_qty, 1),
                           "days_left": round(days_left, 1)})
    within.sort(key=lambda x: x["days_left"])
    oos.sort(key=lambda x: -x["avg_daily_demand"])   # 수요 큰 순
    return {"within_week_count": len(within), "within_week_items": within[:limit],
            "out_of_stock_count": len(oos), "out_of_stock_items": oos[:limit]}


def inventory_value() -> float:
    return q("SELECT COALESCE(SUM(i.qty*p.unit_cost),0) v FROM inventory i JOIN products p ON p.sku=i.sku")[0]["v"]


# ---------- 종합 ----------
def dashboard_summary(targets: dict) -> dict:
    ref = reference_date()
    zt = float(targets.get("kpi_target_zone_occupancy", 0.80))
    ut = float(targets.get("kpi_target_utilization", 0.90))
    over = zones_over_target(zt)
    so = stockout_analysis()
    pw = picking_wait()
    return {
        "reference_date": ref,
        "zone_occupancy_avg": zone_occupancy_avg(),
        "zone_occupancy_list": zone_occupancy(),
        "zone_occupancy_target": zt,
        "team_utilization": team_utilization_current(ref),
        "team_utilization_target": ut,
        "shipping_delay_count": shipping_delay_count(ref),
        "putaway_delay_count": putaway_delay_count(ref),
        "picking_wait_seconds": pw["avg_seconds"],
        "picking_wait_sample": pw["sample"],
        "picking_wait_waiting_now": pw["waiting_now"],
        "zone_over_target_count": len(over),
        "zone_over_target_list": [z["zone_id"] for z in over],
        "stockout_within_week_count": so["within_week_count"],
        "stockout_within_week_items": so["within_week_items"],
        "out_of_stock_count": so["out_of_stock_count"],
        "out_of_stock_items": so["out_of_stock_items"],
        "inventory_value": round(inventory_value()),
    }
