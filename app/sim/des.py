"""SimPy DES 엔진 (docs/07_FORECAST_AND_SIMULATION.md) — 제품 메인 기능.

전체 4단계 모델: 입고처리 → 적치 → 피킹 → 패킹/출고. 각 단계는 작업자/지게차 자원을 경쟁하며,
Zone 용량 제약과 재고 소진을 추적한다. 처리시간은 분포에서 샘플링하고 Monte Carlo 반복으로
KPI를 확률 분포(P50/P90/발생확률)로 산출한다.

Hybrid: 근거리(near_future_days 이내)는 확정 출고/입고 이벤트, 원거리는 Regression 수요예측을
Poisson 샘플링해 가상 출고 이벤트로 투입.
"""
import json
import math
import statistics
import uuid
from datetime import date, datetime, timedelta

import numpy as np
import simpy

from config import settings
from db.database import get_connection
from resmgmt import ensure_resource_rows_schema
from sim.forecast import fit_demand, scan_inventory_risk
from tools.common import q

MIN_PER_DAY = 24 * 60
WORK_START_H = 9   # 업무 시작 09시 (가용 업무시간 09-18)


def _base_date() -> date:
    return date.fromisoformat(settings.base_date)


def _sim_label(minute: float) -> str:
    d = int(minute // MIN_PER_DAY) + 1
    rem = int(minute % MIN_PER_DAY)
    return f"D{d} {rem // 60:02d}:{rem % 60:02d}"


def _sample_time(p: dict, rng) -> float:
    dist, m, s = p["distribution"], p["mean_minutes"], p["std_minutes"]
    if dist == "TRIANGULAR":
        lo = p["min_minutes"] if p["min_minutes"] is not None else max(0.5, m - 2 * s)
        hi = p["max_minutes"] if p["max_minutes"] is not None else m + 2 * s
        mode = min(max(m, lo), hi)
        return float(rng.triangular(lo, mode, hi))
    if dist == "LOGNORMAL":
        sigma = math.sqrt(math.log(1 + (s / m) ** 2))
        mu = math.log(m) - sigma ** 2 / 2
        return float(rng.lognormal(mu, sigma))
    return max(0.5, float(rng.normal(m, s)))  # WEIBULL 등 fallback


def _load_static():
    ensure_resource_rows_schema()
    products = {r["sku"]: r for r in q("SELECT * FROM products")}
    zones = {r["zone_id"]: dict(r) for r in q("SELECT * FROM zones")}
    sku_qty, sku_zone, zone_occ = {}, {}, {z: 0 for z in zones}
    best = {}
    for r in q("""SELECT i.sku, l.zone_id, SUM(i.qty) qty FROM inventory i
                  JOIN locations l ON l.location_id=i.location_id GROUP BY i.sku, l.zone_id"""):
        sku_qty[r["sku"]] = sku_qty.get(r["sku"], 0) + r["qty"]
        zone_occ[r["zone_id"]] += r["qty"]
        if r["sku"] not in best or r["qty"] > best[r["sku"]]:
            best[r["sku"]] = r["qty"]
            sku_zone[r["sku"]] = r["zone_id"]
    resources = {r["resource_type"]: r["count"] for r in q("""SELECT resource_type, COUNT(*) count
                                                              FROM resources WHERE active_flag=1
                                                              GROUP BY resource_type""")}
    ptp = {r["stage"]: dict(r) for r in q("SELECT * FROM process_time_params")}
    return products, zones, sku_qty, sku_zone, zone_occ, resources, ptp


def _target_zone(products, zones, sku):
    """입고 적치 대상 Zone: 제품 보관조건과 일치하는 Zone 중 첫 번째."""
    st = products[sku]["storage_type"] if sku in products else "NORMAL"
    for zid, z in zones.items():
        if z["storage_type"] == st:
            return zid
    return next(iter(zones))


def _run_once(rep, horizon_days, near_days, scenario, record=False):
    """단일 replication. record=True면 대표 run용 시계열/이벤트도 수집."""
    rng = np.random.default_rng(settings.des_random_seed + rep)
    products, zones, sku_qty, sku_zone, zone_occ, resources, ptp = _load_static()

    # --- 시나리오 적용 (What-if) ---
    sc = scenario or {}
    worker_n = max(0, resources.get("WORKER", 3) + sc.get("worker_delta", 0))
    forklift_n = max(0, resources.get("FORKLIFT", 2) + sc.get("forklift_delta", 0))
    capa_mult = sc.get("zone_capa_multiplier", {})
    for zid in zones:
        zones[zid]["max_capacity"] = int(zones[zid]["max_capacity"] * capa_mult.get(zid, 1.0))
    demand_mult = sc.get("demand_multiplier", 1.0)
    inbound_delay = sc.get("inbound_delay_days", 0)

    # 3인1조(지게차 1 + 작업자 2) = 1팀. 남는 작업자/지게차는 조를 만들 수 없다.
    team_n = min(worker_n // 2, forklift_n)
    horizon_min = horizon_days * MIN_PER_DAY
    base = _base_date()

    if team_n <= 0:
        zone_max_occ = {
            z: (zone_occ[z] / zones[z]["max_capacity"] if zones[z]["max_capacity"] else 0)
            for z in zones
        }
        out = {
            "shipping_delays": len(q("SELECT order_no FROM outbound_orders WHERE status IN ('PLANNED','ALLOCATED')")),
            "picking_wait_avg": 0.0,
            "zone_max_occ": zone_max_occ,
            "stockout_day": {},
            "util_team": 0.0,
        }
        if record:
            out["_events"] = [{"sim_time": "D1 09:00", "event_type": "NO_AVAILABLE_TEAM",
                               "detail": {"worker_count": worker_n, "forklift_count": forklift_n}}]
            out["_ts"] = [{"sim_time": "D1 00:00",
                           "occupancy": {z: round(zone_max_occ[z], 3) for z in zones}}]
            out["_inv"] = []
        return out

    env = simpy.Environment()
    teams = simpy.Resource(env, capacity=team_n)

    metrics = {"picking_waits": [], "shipping_delays": 0, "orders": 0,
               "stockout_min": {}, "zone_max_occ": {z: 0.0 for z in zones},
               "team_busy": 0.0}
    events, ts, inv_proj = [], [], []

    def touch_zone_peak():
        for zid, z in zones.items():
            ratio = zone_occ[zid] / z["max_capacity"] if z["max_capacity"] else 0
            metrics["zone_max_occ"][zid] = max(metrics["zone_max_occ"][zid], ratio)

    def inbound_proc(sku, qty, arrive):
        yield env.timeout(arrive)
        # 한 팀이 입고처리 + 적치를 수행(이동 포함)
        req = teams.request()
        yield req
        t = _sample_time(ptp["INBOUND"], rng) + _sample_time(ptp["STOCKING"], rng)
        yield env.timeout(t)
        metrics["team_busy"] += t
        teams.release(req)
        zid = sku_zone.get(sku) or _target_zone(products, zones, sku)
        cap = zones[zid]["max_capacity"]
        free = max(0, cap - zone_occ[zid]) if cap else qty
        place = min(qty, free)
        overflow = qty - place
        zone_occ[zid] += place              # 용량 한도까지만 적치 (heatmap ≤ 100%)
        sku_qty[sku] = sku_qty.get(sku, 0) + place
        if overflow > 0 and record:         # 초과분 = 적치 실패(도크 대기)
            events.append({"sim_time": _sim_label(env.now), "event_type": "STOCKING_FAILED",
                           "detail": {"zone_id": zid, "overflow": overflow}})
        touch_zone_peak()

    def outbound_proc(lines, arrive, due_min, order_no):
        """다중 SKU 라인 주문: 한 번의 피킹 트립(라인 수에 비례) + 1회 패킹."""
        yield env.timeout(arrive)
        t0 = env.now
        # 한 팀이 피킹(라인 수 비례) + 패킹을 수행
        req = teams.request()
        yield req
        metrics["picking_waits"].append(env.now - t0)
        pick_t = _sample_time(ptp["PICKING"], rng) * (1 + 0.3 * (len(lines) - 1))
        pack_t = _sample_time(ptp["PACKING_SHIP"], rng)
        yield env.timeout(pick_t)
        metrics["team_busy"] += pick_t
        for sku, qty in lines:  # 재고 소진
            avail = sku_qty.get(sku, 0)
            taken = min(avail, qty)
            sku_qty[sku] = avail - taken
            zid = sku_zone.get(sku)
            if zid:
                zone_occ[zid] = max(0, zone_occ[zid] - taken)
            if taken < qty and sku not in metrics["stockout_min"]:
                metrics["stockout_min"][sku] = env.now
                if record:
                    events.append({"sim_time": _sim_label(env.now), "event_type": "STOCKOUT",
                                   "detail": {"sku": sku, "short": qty - taken}})
        yield env.timeout(pack_t)
        metrics["team_busy"] += pack_t
        teams.release(req)
        metrics["orders"] += 1
        if env.now > due_min:
            metrics["shipping_delays"] += 1
            if record:
                events.append({"sim_time": _sim_label(env.now), "event_type": "SHIPPING_DELAY",
                               "detail": {"order_no": order_no, "due": _sim_label(due_min)}})
        touch_zone_peak()

    def monitor():
        focal = [r["sku"] for r in scan_inventory_risk(["HIGH", "MEDIUM"])["risks"]]
        while env.now <= horizon_min:
            if record:
                ts.append({"sim_time": _sim_label(env.now),
                           "occupancy": {z: round(zone_occ[z] / zones[z]["max_capacity"], 3)
                                         if zones[z]["max_capacity"] else 0 for z in zones}})
                day = int(env.now // MIN_PER_DAY) + 1
                for s in focal[:8]:
                    inv_proj.append({"sim_time": f"D{day}", "sku": s, "qty": max(0, sku_qty.get(s, 0))})
            yield env.timeout(MIN_PER_DAY)

    # --- 이벤트 스케줄 ---
    # 입고 (확정): horizon 내 RECEIVED(t0) / PLANNED(expected_date)
    for r in q("SELECT sku, qty, expected_date, status FROM inbound_orders WHERE status IN ('PLANNED','RECEIVED')"):
        try:
            offset_days = (date.fromisoformat(r["expected_date"]) - base).days + (inbound_delay if r["status"] == "PLANNED" else 0)
        except Exception:
            continue
        if offset_days > horizon_days:
            continue
        arrive = max(0, offset_days) * MIN_PER_DAY + WORK_START_H * 60 if r["status"] == "PLANNED" else 0
        env.process(inbound_proc(r["sku"], r["qty"], arrive))

    # 출고 근거리(확정): due day 1..near_days
    near_cut = base + timedelta(days=near_days)
    for o in q("SELECT order_no, due_datetime FROM outbound_orders WHERE status IN ('PLANNED','ALLOCATED')"):
        due_dt = datetime.strptime(o["due_datetime"], "%Y-%m-%d %H:%M")
        day_off = (due_dt.date() - base).days
        if day_off < 1 or day_off > near_days:
            continue
        due_min = day_off * MIN_PER_DAY + due_dt.hour * 60 + due_dt.minute
        # due 2시간 전 도착(개장 시각 이후). 동시 도착 burst 방지하되 마감 압박은 유지.
        arrive = max(day_off * MIN_PER_DAY + WORK_START_H * 60, due_min - 120)
        lines = [(ln["sku"], int(ln["qty"] * demand_mult))
                 for ln in q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (o["order_no"],))]
        if lines:
            env.process(outbound_proc(lines, arrive, due_min, o["order_no"]))

    # 출고 원거리(예측): day near+1..horizon. SKU별 Poisson 수요를 하루 ORDERS_PER_DAY개
    # 주문으로 통합하고 마감시간을 11~17시로 분산(현실적 부하·가동률).
    ORDERS_PER_DAY = 10
    fcache = {s: fit_demand(s)[0] for s in products}
    for k in range(near_days + 1, horizon_days + 1):
        day_demand = {}
        for sku, f in fcache.items():
            if f is None:
                continue
            lam = f(k) * demand_mult
            if lam <= 0:
                continue
            d = int(rng.poisson(lam))
            if d > 0:
                day_demand[sku] = d
        skus = list(day_demand.keys())
        if not skus:
            continue
        rng.shuffle(skus)
        n = min(len(skus), ORDERS_PER_DAY)
        for gi in range(n):
            group = skus[gi::n]  # 라운드로빈 분배
            lines = [(s, day_demand[s]) for s in group]
            due_min = (k - 1) * MIN_PER_DAY + 11 * 60 + int(gi * (6 * 60) / n)  # 11:00~17:00 분산
            arrive = max((k - 1) * MIN_PER_DAY + WORK_START_H * 60, due_min - 120)
            env.process(outbound_proc(lines, arrive, due_min, f"FAR-D{k}-{gi}"))

    if record:
        env.process(monitor())
    env.run(until=horizon_min)

    util_team = metrics["team_busy"] / (team_n * horizon_min)
    out = {
        "shipping_delays": metrics["shipping_delays"],
        "picking_wait_avg": statistics.mean(metrics["picking_waits"]) if metrics["picking_waits"] else 0.0,
        "zone_max_occ": metrics["zone_max_occ"],
        "stockout_day": {s: int(m // MIN_PER_DAY) + 1 for s, m in metrics["stockout_min"].items()},
        "util_team": util_team,
    }
    if record:
        out["_events"], out["_ts"], out["_inv"] = events, ts, inv_proj
    return out


def _pctl(vals, p):
    return float(np.percentile(vals, p)) if vals else None


def _resolved_counts(scenario):
    """시나리오 적용 후 실제 작업자/지게차/팀 수."""
    ensure_resource_rows_schema()
    res = {r["resource_type"]: r["count"] for r in q("""SELECT resource_type, COUNT(*) count
                                                       FROM resources WHERE active_flag=1
                                                       GROUP BY resource_type""")}
    sc = scenario or {}
    w = max(0, res.get("WORKER", 3) + sc.get("worker_delta", 0))
    f = max(0, res.get("FORKLIFT", 2) + sc.get("forklift_delta", 0))
    return w, f, min(w // 2, f)


def run_des_simulation(horizon_days: int = 14, near_future_days: int | None = None,
                       replications: int | None = None, random_seed: int | None = None,
                       scenario: dict | None = None, run_type: str = "BASELINE",
                       persist: bool = True) -> dict:
    near = near_future_days if near_future_days is not None else settings.des_near_future_days
    reps = replications if replications is not None else settings.des_replications
    if random_seed is not None:
        settings.des_random_seed = random_seed

    runs = [_run_once(0, horizon_days, near, scenario, record=True)]
    runs += [_run_once(i, horizon_days, near, scenario, record=False) for i in range(1, reps)]
    rep0 = runs[0]
    base = _base_date()

    delays = [r["shipping_delays"] for r in runs]
    waits = [r["picking_wait_avg"] for r in runs]
    util_t = [r["util_team"] for r in runs]
    zones = list(rep0["zone_max_occ"].keys())

    kpis = [
        {"kpi_name": "shipping_delay_count", "mean": round(statistics.mean(delays), 2),
         "p90": _pctl(delays, 90), "occurrence_prob": round(sum(1 for d in delays if d > 0) / len(delays), 3),
         "unit": "count"},
        {"kpi_name": "picking_wait_minutes", "p50": round(_pctl(waits, 50), 1),
         "p90": round(_pctl(waits, 90), 1), "unit": "minutes"},
        {"kpi_name": "resource_utilization_team", "mean": round(statistics.mean(util_t), 3), "unit": "percent"},
    ]
    for z in zones:
        vals = [r["zone_max_occ"][z] for r in runs]
        kpis.append({"kpi_name": "zone_max_occupancy", "sku": None, "p90": round(_pctl(vals, 90), 3),
                     "mean": round(statistics.mean(vals), 3), "unit": "percent", "zone_id": z})

    # SKU별 예상소진일 (HIGH/MEDIUM 위험 SKU)
    focal = [r["sku"] for r in scan_inventory_risk(["HIGH", "MEDIUM"])["risks"]]
    for s in focal:
        days = [r["stockout_day"][s] for r in runs if s in r["stockout_day"]]
        if len(days) >= max(1, reps * 0.1):  # 10%+ run에서 소진 시에만 보고
            p50d = _pctl(days, 50)
            p90d = _pctl(days, 10)  # 보수적(이른 소진) = 하위 10퍼센타일
            kpis.append({"kpi_name": "expected_stockout_date", "sku": s,
                         "p50": (base + timedelta(days=int(p50d))).isoformat(),
                         "p90": (base + timedelta(days=int(p90d))).isoformat(),
                         "occurrence_prob": round(len(days) / reps, 3), "unit": "date"})

    import datetime as _dt
    from sim.animation import generate_movement
    sim_run_id = f"SIM-{uuid.uuid4().hex[:6]}"
    version_name = _dt.datetime.now().strftime("V%Y%m%d-%H%M%S")
    w, f, t = _resolved_counts(scenario)
    sc = scenario or {}
    params = {"worker_count": w, "forklift_count": f, "team_count": t,
              "worker_delta": sc.get("worker_delta", 0), "forklift_delta": sc.get("forklift_delta", 0),
              "zone_capa_multiplier": sc.get("zone_capa_multiplier", {})}
    result = {"sim_run_id": sim_run_id, "version_name": version_name, "run_type": run_type,
              "scenario": scenario, "params": params, "kpis": kpis,
              "zone_occupancy_timeseries": rep0["_ts"],
              "inventory_projection": rep0["_inv"],
              "bottleneck_events": rep0["_events"],
              "movement": generate_movement(w, f, horizon_days=horizon_days)}
    if persist:
        _persist(sim_run_id, version_name, run_type, scenario, horizon_days, near, reps, result)
    return result


def _persist(sim_run_id, version_name, run_type, scenario, horizon_days, near, reps, result):
    from sim.versions import ensure_version_columns
    ensure_version_columns()  # 기존 DB에 자원 수 컬럼 보장
    p = result.get("params", {}) or {}
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO simulation_runs(sim_run_id,version_name,run_type,scenario_json,horizon_days,
                        near_future_days,replications,random_seed,result_json,worker_count,forklift_count,team_count)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (sim_run_id, version_name, run_type,
                      json.dumps(scenario, ensure_ascii=False) if scenario else None,
                      horizon_days, near, reps, settings.des_random_seed,
                      json.dumps(result, ensure_ascii=False, default=str),
                      p.get("worker_count"), p.get("forklift_count"), p.get("team_count")))
        for k in result["kpis"]:
            conn.execute("""INSERT INTO simulation_kpis(sim_run_id,sku,kpi_name,p50,p90,mean,occurrence_prob,unit)
                            VALUES(?,?,?,?,?,?,?,?)""",
                         (sim_run_id, k.get("sku"), k["kpi_name"],
                          k.get("p50") if isinstance(k.get("p50"), (int, float)) else None,
                          k.get("p90") if isinstance(k.get("p90"), (int, float)) else None,
                          k.get("mean"), k.get("occurrence_prob"), k.get("unit")))
        for e in result["bottleneck_events"]:
            conn.execute("INSERT INTO simulation_events(sim_run_id,sim_time,event_type,detail_json) VALUES(?,?,?,?)",
                         (sim_run_id, e["sim_time"], e["event_type"], json.dumps(e["detail"], ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    r = run_des_simulation(horizon_days=7, replications=n, persist=True)
    print(f"sim_run_id={r['sim_run_id']} | KPIs={len(r['kpis'])} | events={len(r['bottleneck_events'])}")
