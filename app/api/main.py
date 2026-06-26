"""FastAPI 엔드포인트 (docs/08_API_SPEC.md).

실행(앱 디렉토리, venv 활성화):
    uvicorn api.main:app --reload
"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import chat_store
import realtime
import resmgmt
import trace_store
from agent.graph import run as agent_run, stream_run
from config import settings
from sim import des, forecast, versions, whatif
from tools import drafts, lookups, picking, stocking
from tools.common import q

app = FastAPI(title="Smart WMS Agent API", version="0.1")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
UNIT_COST = 1000  # 단위당 명목 재고가치(원) — 총 재고 비용 KPI용(예시값)

DATASETS = {
    "products": {"table": "products", "order": "sku", "search": ["sku", "product_name", "category", "storage_type"],
                 "filters": {"sku": "sku"}},
    "zones": {"table": "zones", "order": "zone_id", "search": ["zone_id", "zone_name", "storage_type"],
              "filters": {"zone_id": "zone_id"}},
    "locations": {"table": "locations", "order": "location_id", "search": ["location_id", "location_name", "zone_id"],
                  "filters": {"zone_id": "zone_id"}},
    "inventory": {"table": "inventory", "order": "inventory_id DESC", "search": ["sku", "lot_no", "location_id", "status"],
                  "filters": {"sku": "sku", "status": "status", "date": "inbound_date"}},
    "inbound_orders": {"table": "inbound_orders", "order": "expected_date DESC, inbound_no", "search": ["inbound_no", "sku", "status", "supplier"],
                       "filters": {"sku": "sku", "status": "status", "date": "expected_date"}},
    "outbound_orders": {"table": "outbound_orders", "order": "due_datetime DESC, order_no", "search": ["order_no", "customer_id", "status"],
                        "filters": {"status": "status", "date": "substr(due_datetime,1,10)"}},
    "outbound_order_lines": {"table": "outbound_order_lines", "order": "line_id DESC", "search": ["order_no", "sku"],
                             "filters": {"sku": "sku"}},
    "shipping_pending": {"table": "shipping_pending", "order": "ready_datetime DESC", "search": ["pending_id", "order_no", "status"],
                         "filters": {"status": "status", "date": "substr(ready_datetime,1,10)"}},
    "stocking_tasks": {"table": "stocking_tasks", "order": "issued_at DESC", "search": ["stocking_task_id", "inbound_no", "location_id", "status"],
                       "filters": {"status": "status"}},
    "picking_tasks": {"table": "picking_tasks", "order": "issued_at DESC", "search": ["picking_task_id", "order_no", "status"],
                      "filters": {"status": "status"}},
    "resources": {"table": "resources", "order": "resource_type", "search": ["resource_id", "resource_type"],
                  "filters": {"status": "active_flag"}},
    "process_time_params": {"table": "process_time_params", "order": "stage", "search": ["stage", "distribution"],
                            "filters": {}},
    "demand_history": {"table": "demand_history", "order": "demand_date DESC", "search": ["sku"],
                       "filters": {"sku": "sku", "date": "demand_date"}},
    "action_drafts": {"table": "action_drafts", "order": "created_at DESC", "search": ["draft_id", "action_type", "target_id", "status"],
                      "filters": {"status": "status"}},
    "simulation_runs": {"table": "simulation_runs", "order": "created_at DESC", "search": ["sim_run_id", "version_name", "run_type"],
                        "filters": {"status": "run_type", "version_name": "version_name"}},
    "simulation_kpis": {"table": "simulation_kpis", "order": "kpi_id DESC", "search": ["sim_run_id", "sku", "kpi_name", "unit"],
                        "filters": {"sku": "sku"}},
    "simulation_events": {"table": "simulation_events", "order": "event_id DESC", "search": ["sim_run_id", "sim_time", "event_type", "detail_json"],
                          "filters": {"status": "event_type"}},
}


# ---------- 요청 모델 ----------
class ChatReq(BaseModel):
    query: str
    user_id: str | None = None
    session_id: str | None = None


class StockingReq(BaseModel):
    inbound_no: str


class PickingReq(BaseModel):
    current_datetime: str | None = None


class ForecastReq(BaseModel):
    sku: str
    forecast_days: int = 30


class RiskScanReq(BaseModel):
    risk_levels: list[str] | None = None


class SimulateReq(BaseModel):
    horizon_days: int = 14
    near_future_days: int | None = None
    replications: int | None = None
    scenario: dict | None = None


class KpiReq(BaseModel):
    kpis: list[str] | None = None
    target_date: str | None = None


class StockingDraftReq(BaseModel):
    inbound_no: str
    location_id: str


class OrderDraftReq(BaseModel):
    order_no: str


class SkuReq(BaseModel):
    sku: str


class ApproveReq(BaseModel):
    draft_id: str
    approved: bool
    user_id: str = "operator01"


# ---------- 엔드포인트 ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/resources")
def resources():
    r = resmgmt.get_resources()
    units = q("SELECT COALESCE(SUM(qty),0) s FROM inventory")[0]["s"]
    value = q("SELECT COALESCE(SUM(i.qty*p.unit_cost),0) v FROM inventory i JOIN products p ON p.sku=i.sku")[0]["v"]
    return {**r, "team_count": max(0, min(r["worker"] // 2, r["forklift"])),
            "base_date": settings.base_date, "inventory_units": units,
            "inventory_value": round(value)}


@app.post("/resources/update")
def resources_update(worker: int, forklift: int):
    return resmgmt.update_resources(worker, forklift)


@app.get("/data/snapshot")
def data_snapshot():
    r = resmgmt.get_resources()
    ops = lookups.query_operation_kpis(
        ["saturated_zone_count", "safety_stock_below_count", "stocking_completion_rate"]
    )["kpis"]
    op = {x["name"]: x.get("value") for x in ops}
    inv = q("SELECT COALESCE(SUM(qty),0) qty, COUNT(*) rows FROM inventory")[0]
    inv_value = q("SELECT COALESCE(SUM(i.qty*p.unit_cost),0) v FROM inventory i JOIN products p ON p.sku=i.sku")[0]["v"]
    latest = q("""SELECT version_name, run_type, created_at FROM simulation_runs
                  WHERE version_name IS NOT NULL ORDER BY created_at DESC LIMIT 1""")
    counts = {
        "products": q("SELECT COUNT(*) n FROM products")[0]["n"],
        "inventory_rows": inv["rows"],
        "inbound_waiting": q("SELECT COUNT(*) n FROM inbound_orders WHERE status IN ('PLANNED','RECEIVED')")[0]["n"],
        "stocking_waiting": q("SELECT COUNT(*) n FROM inbound_orders WHERE status='RECEIVED'")[0]["n"],
        "outbound_planned": q("SELECT COUNT(*) n FROM outbound_orders WHERE status='PLANNED'")[0]["n"],
        "shipping_pending": q("SELECT COUNT(*) n FROM shipping_pending WHERE status='PENDING'")[0]["n"],
        "action_drafts_pending": q("SELECT COUNT(*) n FROM action_drafts WHERE status='PENDING_APPROVAL'")[0]["n"],
    }
    return {
        "base_date": settings.base_date,
        "worker": r["worker"],
        "forklift": r["forklift"],
        "team_count": max(0, min(r["worker"] // 2, r["forklift"])),
        "inventory_units": inv["qty"],
        "inventory_value": round(inv_value),
        "saturated_zone_count": op.get("saturated_zone_count"),
        "safety_stock_below_count": op.get("safety_stock_below_count"),
        "stocking_completion_rate": op.get("stocking_completion_rate"),
        "latest_simulation": latest[0] if latest else None,
        "counts": counts,
    }


@app.get("/data/{dataset}")
def data_rows(dataset: str, limit: int = 100, offset: int = 0, status: str | None = None,
              sku: str | None = None, zone_id: str | None = None, date: str | None = None,
              version_name: str | None = None, qtext: str | None = None):
    spec = DATASETS.get(dataset)
    if not spec:
        raise HTTPException(status_code=404, detail="지원하지 않는 데이터셋입니다.")
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    where, params = [], []
    requested = {"status": status, "sku": sku, "zone_id": zone_id, "date": date, "version_name": version_name}
    for key, value in requested.items():
        col = spec["filters"].get(key)
        if col and value not in (None, ""):
            where.append(f"{col}=?")
            params.append(value)
    if qtext:
        ors = [f"CAST({col} AS TEXT) LIKE ?" for col in spec["search"]]
        where.append("(" + " OR ".join(ors) + ")")
        params.extend([f"%{qtext}%"] * len(ors))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    table, order = spec["table"], spec["order"]
    total = q(f"SELECT COUNT(*) n FROM {table}{clause}", tuple(params))[0]["n"]
    rows = q(f"SELECT * FROM {table}{clause} ORDER BY {order} LIMIT ? OFFSET ?",
             tuple(params + [limit, offset]))
    return {"dataset": dataset, "total": total, "limit": limit, "offset": offset, "rows": rows}


@app.post("/chat")
def chat(r: ChatReq):
    # 세션 보장 + 멀티턴 맥락 주입(계층 B) + 영속화(계층 A)
    session_id = r.session_id or chat_store.create_session(r.user_id)
    history = chat_store.recent_history(session_id)
    s = agent_run(r.query, r.user_id, history=history)
    resp = s.get("final_response")
    sources = s.get("rag_context", [])
    run_id = trace_store.save(s, session_id=session_id, query=r.query)  # 동작 검증용 트레이스
    chat_store.add_message(session_id, "user", r.query)
    if resp:
        chat_store.add_message(session_id, "assistant", resp, intent=s.get("intent"), sources=sources)
    return {"success": s.get("error") is None, "intent": s.get("intent"),
            "session_id": session_id, "run_id": run_id,
            "approval_required": s.get("approval_required", False),
            "response": resp,
            "draft_actions": s.get("draft_actions", []),
            "rag_sources": sources,
            "tool_results": s.get("tool_results", {}), "error": s.get("error")}


@app.post("/chat/stream")
async def chat_stream(r: ChatReq):
    """실시간 동작 스텝핑 — 노드가 끝날 때마다 step 이벤트를 SSE로 흘리고, 마지막에 done."""
    session_id = r.session_id or chat_store.create_session(r.user_id)
    history = chat_store.recent_history(session_id)
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def worker():
        final: dict = {}
        trace_store.set_sink(lambda ev: loop.call_soon_threadsafe(
            queue.put_nowait, {"type": "substep", **ev}))   # 노드 내부 세밀 이벤트
        try:
            for node_id, snap in stream_run(r.query, r.user_id, history):
                final = snap
                st = trace_store.live_step(node_id, snap)
                if st:
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "step", **st})
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "final", "state": final})
        except Exception as e:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
        finally:
            trace_store.clear_sink()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(None, worker)

    async def gen():
        while True:
            ev = await queue.get()
            if ev is None:
                break
            if ev.get("type") == "final":
                s = ev["state"]
                resp, sources = s.get("final_response"), s.get("rag_context", [])
                run_id = trace_store.save(s, session_id=session_id, query=r.query)
                chat_store.add_message(session_id, "user", r.query)
                if resp:
                    chat_store.add_message(session_id, "assistant", resp,
                                           intent=s.get("intent"), sources=sources)
                done = {"type": "done", "session_id": session_id, "run_id": run_id,
                        "intent": s.get("intent"), "approval_required": bool(s.get("approval_required")),
                        "response": resp, "draft_actions": s.get("draft_actions", []),
                        "rag_sources": sources, "tool_results": s.get("tool_results", {}),
                        "error": s.get("error")}
                yield "data: " + json.dumps(done, ensure_ascii=False, default=str) + "\n\n"
            else:
                yield "data: " + json.dumps(ev, ensure_ascii=False, default=str) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/sessions")
def sessions_list(user_id: str | None = None):
    return {"sessions": chat_store.list_sessions(user_id)}


@app.post("/sessions")
def sessions_create(r: ChatReq | None = None):
    return {"session_id": chat_store.create_session(r.user_id if r else None)}


@app.get("/sessions/{session_id}")
def sessions_get(session_id: str):
    return {"session_id": session_id, "messages": chat_store.get_messages(session_id)}


@app.delete("/sessions/{session_id}")
def sessions_delete(session_id: str):
    chat_store.delete_session(session_id)
    return {"deleted": session_id}


@app.get("/inbound")
def inbound(status: str = "PLANNED,RECEIVED", target_date: str | None = None):
    return lookups.lookup_inbound_orders(status.split(","), target_date)


@app.get("/outbound")
def outbound(target_date: str | None = None):
    return lookups.lookup_outbound_orders(["PLANNED", "ALLOCATED"], target_date)


@app.get("/allocation/scan")
def allocation_scan(target_date: str | None = None):
    """예상 결품 분석 — 가용재고 기준 출고 주문 할당 시뮬레이션."""
    from tools import allocation
    return allocation.scan_allocation(target_date)


@app.get("/deadstock/scan")
def deadstock_scan(grades: str | None = None):
    """체화재고 분석 — 저회전/장기 미출고/유통기한 임박."""
    from tools import dead_stock
    return dead_stock.scan_dead_stock(grades.split(",") if grades else None)


@app.get("/replenishment/scan")
def replenishment_scan():
    """재고 보충 추천 — 피킹면 부족 + 보관 보유."""
    from tools import replenishment
    return replenishment.scan_replenishment()


@app.get("/shipping/pending")
def shipping_pending():
    return lookups.lookup_shipping_pending()


@app.post("/recommend/stocking")
def recommend_stocking(r: StockingReq):
    return stocking.recommend_stocking(r.inbound_no)


@app.post("/recommend/picking")
def recommend_picking(r: PickingReq):
    from config import settings
    dt = r.current_datetime or f"{settings.base_date} 10:20"
    return picking.recommend_picking(dt, forecast.risk_level_map())


@app.post("/forecast")
def forecast_ep(r: ForecastReq):
    return {"forecast": forecast.inventory_forecast(r.sku, r.forecast_days),
            "risk": forecast.calculate_inventory_risk(r.sku)}


@app.post("/risk/scan")
def risk_scan(r: RiskScanReq):
    return forecast.scan_inventory_risk(r.risk_levels)


@app.post("/simulate")
def simulate(r: SimulateReq):
    if r.scenario:
        base = des.run_des_simulation(horizon_days=r.horizon_days, near_future_days=r.near_future_days,
                                      replications=r.replications)
        scen = whatif.simulate_operation_what_if(r.scenario, horizon_days=r.horizon_days,
                                                 near_future_days=r.near_future_days, replications=r.replications)
        return {"baseline": base, "scenario": scen,
                "comparison": whatif.compare_simulation_scenarios(base, scen)["comparison"]}
    return des.run_des_simulation(horizon_days=r.horizon_days, near_future_days=r.near_future_days,
                                  replications=r.replications)


@app.get("/simulation/versions")
def simulation_versions():
    """저장된 실행 버전 목록(최신순) + 해석된 작업자/지게차/팀 수."""
    return {"versions": versions.list_versions()}


@app.get("/simulation/versions/{version_name}")
def simulation_version(version_name: str):
    """단일 버전의 전체 결과(kpis·movement·timeseries·events)."""
    v = versions.get_version(version_name)
    if not v:
        raise HTTPException(status_code=404, detail="버전 없음")
    return v


@app.get("/simulation/compare")
def simulation_compare(base: str, target: str):
    """두 버전 비교. base=비교 기준, target=표시 버전 → delta = target - base."""
    b, t = versions.get_version(base), versions.get_version(target)
    if not b or not t:
        raise HTTPException(status_code=404, detail="버전 없음")
    return whatif.compare_simulation_scenarios(b, t)


@app.post("/kpi")
def kpi(r: KpiReq):
    kpis = r.kpis or ["zone_occupancy", "saturated_zone_count", "safety_stock_below_count"]
    return lookups.query_operation_kpis(kpis, r.target_date)


@app.post("/stocking/draft")
def stocking_draft(r: StockingDraftReq):
    return drafts.create_stocking_task_draft(r.inbound_no, r.location_id)


@app.post("/picking/draft")
def picking_draft(r: OrderDraftReq):
    return drafts.create_picking_instruction_draft(r.order_no)


@app.post("/allocation/draft")
def allocation_draft(r: OrderDraftReq):
    return drafts.create_allocation_draft(r.order_no)


@app.post("/replenishment/draft")
def replenishment_draft(r: SkuReq):
    return drafts.create_replenishment_draft(r.sku)


@app.post("/disposal/draft")
def disposal_draft(r: SkuReq):
    return drafts.create_disposal_draft(r.sku)


@app.post("/shipping/draft")
def shipping_draft(r: OrderDraftReq):
    return drafts.create_shipping_confirm_draft(r.order_no)


@app.get("/drafts")
def list_drafts(status: str | None = None, limit: int = 60):
    """승인 Draft 목록(payload·dry-run 파싱 포함) — Approval 탭용."""
    sql = ("SELECT draft_id, action_type, target_id, payload_json, dry_run_result_json, "
           "status, created_at, approved_at, executed_at FROM action_drafts")
    params: tuple = ()
    if status:
        marks = ",".join("?" for _ in status.split(","))
        sql += f" WHERE status IN ({marks})"
        params = tuple(status.split(","))
    sql += " ORDER BY created_at DESC LIMIT ?"
    rows = q(sql, params + (limit,))
    for r in rows:
        r["payload"] = json.loads(r.pop("payload_json")) if r.get("payload_json") else {}
        dr = r.pop("dry_run_result_json")
        r["dry_run"] = json.loads(dr) if dr else None
    return {"drafts": rows}


@app.post("/approve")
def approve(r: ApproveReq):
    return drafts.approve_action(r.draft_id, r.approved, r.user_id)


@app.get("/events")
async def events():
    """SSE — 실시간 수요 발생 이벤트 스트림(Toast 알림용)."""
    async def gen():
        qe = realtime.subscribe()
        try:
            yield ": connected\n\n"
            while True:
                ev = await qe.get()
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            realtime.unsubscribe(qe)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/realtime/start")
async def realtime_start(interval: int | None = None):
    return realtime.start(interval)


@app.post("/realtime/stop")
async def realtime_stop():
    return realtime.stop()


@app.get("/realtime/status")
def realtime_status():
    return realtime.status()


class RealtimeConfigReq(BaseModel):
    interval: int | None = None
    outbound_ratio: float | None = None
    out_qty_min: int | None = None
    out_qty_max: int | None = None
    in_qty_min: int | None = None
    in_qty_max: int | None = None


@app.post("/realtime/config")
def realtime_config(r: RealtimeConfigReq):
    """실시간 수요 생성 설정(주기·출고비율·수량 범위)."""
    return realtime.configure(r.model_dump(exclude_none=True))


@app.post("/realtime/emit")
async def realtime_emit():
    """수동으로 실시간 요청 1건 발생(데모용)."""
    return await realtime.emit_once()


@app.get("/traces")
def traces_list(limit: int = 40, session_id: str | None = None):
    """에이전트 실행 트레이스 목록(최신순) — AI 동작 검증 화면. session_id로 세션별 필터."""
    return {"traces": trace_store.list_traces(limit, session_id)}


@app.get("/traces/{run_id}")
def trace_detail(run_id: str):
    t = trace_store.get_trace(run_id)
    if not t:
        raise HTTPException(status_code=404, detail="트레이스 없음")
    return t


@app.get("/trace/{run_id}")
def trace(run_id: str):
    return {"tool_logs": q("SELECT tool_name,success,executed_at FROM tool_logs WHERE run_id=?", (run_id,)),
            "rag_logs": q("SELECT query,top_k,executed_at FROM rag_logs WHERE run_id=?", (run_id,))}


# --- SPA(커스텀 프론트엔드) 서빙 ---
_NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html", headers=_NO_CACHE)


class _NoCacheStatic(StaticFiles):
    """정적 자산을 항상 재검증(no-cache)해 코드 변경이 새로고침으로 즉시 반영되게 한다."""
    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp


app.mount("/static", _NoCacheStatic(directory=WEB_DIR / "static"), name="static")
