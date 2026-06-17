"""FastAPI 엔드포인트 (docs/08_API_SPEC.md).

실행(앱 디렉토리, venv 활성화):
    uvicorn api.main:app --reload
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import resmgmt
from agent.graph import run as agent_run
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
    s = agent_run(r.query, r.user_id)
    return {"success": s.get("error") is None, "intent": s.get("intent"),
            "approval_required": s.get("approval_required", False),
            "response": s.get("final_response"),
            "draft_actions": s.get("draft_actions", []),
            "rag_sources": s.get("rag_context", []),
            "tool_results": s.get("tool_results", {}), "error": s.get("error")}


@app.get("/inbound")
def inbound(status: str = "PLANNED,RECEIVED", target_date: str | None = None):
    return lookups.lookup_inbound_orders(status.split(","), target_date)


@app.get("/outbound")
def outbound(target_date: str | None = None):
    return lookups.lookup_outbound_orders(["PLANNED"], target_date)


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


@app.post("/shipping/draft")
def shipping_draft(r: OrderDraftReq):
    return drafts.create_shipping_confirm_draft(r.order_no)


@app.post("/approve")
def approve(r: ApproveReq):
    return drafts.approve_action(r.draft_id, r.approved, r.user_id)


@app.get("/trace/{run_id}")
def trace(run_id: str):
    return {"tool_logs": q("SELECT tool_name,success,executed_at FROM tool_logs WHERE run_id=?", (run_id,)),
            "rag_logs": q("SELECT query,top_k,executed_at FROM rag_logs WHERE run_id=?", (run_id,))}


# --- SPA(커스텀 프론트엔드) 서빙 ---
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
