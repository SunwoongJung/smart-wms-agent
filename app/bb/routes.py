"""블랙보드/Auto Mode FastAPI 라우터 — 기존 app에 include_router로 추가."""
from fastapi import APIRouter
from pydantic import BaseModel

from bb import actions, audit, control_loop, events, reservations, settings

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


@router.get("/blackboard/actions/{action_id}/explanation")
def action_explanation(action_id: str, regenerate: bool = False, use_llm: bool = True):
    """운영자용 한국어 설명(LLM, 폴백 템플릿). 최초 생성 후 캐시."""
    from bb import explanation
    return explanation.explain(action_id, regenerate=regenerate, use_llm=use_llm)


# ---------- Audit ----------
@router.get("/blackboard/audit-logs")
def audit_list(action_id: str | None = None, event_id: str | None = None,
               phase: str | None = None, result: str | None = None, limit: int = 200):
    return {"logs": audit.list_logs(action_id, event_id, phase, result, limit)}


# ---------- Control Loop ----------
@router.post("/blackboard/run-once")
def run_once(force: bool = False):
    """1 사이클 실행(이벤트→에이전트→Action→실행). force=true면 Auto Mode OFF여도 실행."""
    return control_loop.run_once(force=force)


@router.post("/auto-mode/loop/start")
def loop_start():
    return control_loop.start()


@router.post("/auto-mode/loop/stop")
def loop_stop():
    return control_loop.stop()


@router.get("/auto-mode/loop/status")
def loop_status():
    return control_loop.status()


@router.get("/blackboard/simulation")
def simulation_gate():
    """배치 What-if(DES) 게이트 결과(캐시, 논블로킹). 오래되면 백그라운드 갱신."""
    from bb import simulation_agent
    return simulation_agent.gate()


@router.post("/blackboard/simulation/run")
def simulation_run():
    """지금 즉시 시뮬레이션 1회 실행(블로킹, 자동운영 OFF여도 강제). 결과 반환."""
    from bb import simulation_agent
    return simulation_agent.evaluate()


# ---------- 가용/예약(검증·디버그용) ----------
@router.get("/blackboard/availability/{sku}")
def availability(sku: str):
    return {"sku": sku, "on_hand": reservations.on_hand(sku), "reserved": reservations.reserved(sku),
            "blocked": reservations.blocked(sku), "available": reservations.available(sku)}
