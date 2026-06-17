"""FastAPI 엔드포인트 (docs/08_API_SPEC.md).

실행(앱 디렉토리, venv 활성화):
    uvicorn api.main:app --reload
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import resmgmt
from agent.graph import run as agent_run
from config import settings
from sim import des, forecast, whatif
from tools import drafts, lookups, picking, stocking
from tools.common import q

app = FastAPI(title="Smart WMS Agent API", version="0.1")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
UNIT_COST = 1000  # 단위당 명목 재고가치(원) — 총 재고 비용 KPI용(예시값)


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
    return {**r, "team_count": max(0, min(r["worker"] // 2, r["forklift"])),
            "base_date": settings.base_date, "inventory_units": units,
            "inventory_value": units * UNIT_COST}


@app.post("/resources/update")
def resources_update(worker: int, forklift: int):
    return resmgmt.update_resources(worker, forklift)


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
