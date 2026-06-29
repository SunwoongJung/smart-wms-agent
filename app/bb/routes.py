"""블랙보드/Auto Mode FastAPI 라우터 — 기존 app에 include_router로 추가."""
from fastapi import APIRouter
from pydantic import BaseModel

from bb import actions, audit, events, reservations, settings

router = APIRouter(prefix="/api", tags=["blackboard"])


class EventIn(BaseModel):
    event_type: str
    target_type: str | None = None
    target_id: str | None = None
    payload_json: dict | None = None
    severity: str = "normal"
    source: str = "manual"


class SettingIn(BaseModel):
    key: str
    value: str


# ---------- Auto Mode ----------
@router.get("/auto-mode")
def auto_mode_get():
    return settings.get_all()


@router.post("/auto-mode/on")
def auto_mode_on():
    settings.set_enabled(True)
    return settings.get_all()


@router.post("/auto-mode/off")
def auto_mode_off():
    settings.set_enabled(False)
    return settings.get_all()


@router.post("/auto-mode/settings")
def auto_mode_set(s: SettingIn):
    settings.set_value(s.key, s.value)
    return settings.get_all()


# ---------- Events ----------
@router.post("/blackboard/events")
def event_add(e: EventIn):
    eid = events.add_event(e.event_type, e.target_type, e.target_id, e.payload_json, e.severity, e.source)
    return {"event_id": eid}


@router.get("/blackboard/events")
def event_list(status: str | None = None, event_type: str | None = None,
               target_id: str | None = None, limit: int = 100):
    return {"events": events.list_events(status, event_type, target_id, limit)}


# ---------- Actions ----------
@router.get("/blackboard/actions")
def action_list(status: str | None = None, action_type: str | None = None,
                target_id: str | None = None, agent_name: str | None = None, limit: int = 200):
    return {"actions": actions.list_actions(status, action_type, target_id, agent_name, limit)}


@router.get("/blackboard/actions/{action_id}")
def action_get(action_id: str):
    return actions.get(action_id) or {"error": "not found"}


# ---------- Audit ----------
@router.get("/blackboard/audit-logs")
def audit_list(action_id: str | None = None, event_id: str | None = None,
               phase: str | None = None, result: str | None = None, limit: int = 200):
    return {"logs": audit.list_logs(action_id, event_id, phase, result, limit)}


# ---------- 가용/예약(검증·디버그용) ----------
@router.get("/blackboard/availability/{sku}")
def availability(sku: str):
    return {"sku": sku, "on_hand": reservations.on_hand(sku), "reserved": reservations.reserved(sku),
            "blocked": reservations.blocked(sku), "available": reservations.available(sku)}
