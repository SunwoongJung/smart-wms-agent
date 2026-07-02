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


@router.get("/blackboard/capacity")
def capacity():
    """실시간 작업팀 가용/백로그(미처리 대기: 적치·피킹 별도)."""
    from bb import capacity as cap
    return cap.snapshot()


@router.post("/blackboard/simulation/run")
def simulation_run():
    """지금 즉시 시뮬레이션 1회 실행(블로킹, 자동운영 OFF여도 강제). 결과 반환."""
    from bb import simulation_agent
    return simulation_agent.evaluate()


# ---------- 요청 생애주기(실시간 입/출고 한 건 추적) ----------
@router.get("/blackboard/requests")
def request_list(kind: str | None = None, limit: int = 40):
    """실시간 생성(RT-*) 입/출고 요청 목록(최신순, 현재 상태 포함)."""
    from bb import lifecycle
    return {"requests": lifecycle.list_requests(kind, limit)}


@router.get("/blackboard/requests/{kind}/{request_id}/trace")
def request_trace(kind: str, request_id: str):
    """요청 한 건의 업무 마일스톤 타임라인(파생 뷰)."""
    from bb import lifecycle
    return lifecycle.request_trace(kind, request_id)


@router.post("/blackboard/requests/{order_no}/replenish-now")
def replenish_now(order_no: str):
    """'바로 보충' — 발주 대기 주문의 발주분을 가상 즉시 입고·재고 반영 후 주문 재개.

    자동운영 OFF면 재개(피킹)를 태울 컨트롤 루프가 없어 주문이 어중간하게 멈추므로 거부한다.
    """
    from bb import backorder
    if not settings.enabled():
        return {"error": "자동운영이 꺼져 있어 보충할 수 없습니다. 자동운영을 먼저 켜주세요."}
    return backorder.replenish_now(order_no)


@router.get("/blackboard/awaiting-orders")
def awaiting_orders():
    """자동발주 배지 숫자의 세부 — 발주 대기(AWAITING_STOCK) 출고주문 목록 + 발주분 상세."""
    from bb import backorder
    return {"orders": backorder.awaiting_orders()}


# ---------- 가용/예약(검증·디버그용) ----------
@router.get("/blackboard/availability/{sku}")
def availability(sku: str):
    return {"sku": sku, "on_hand": reservations.on_hand(sku), "reserved": reservations.reserved(sku),
            "blocked": reservations.blocked(sku), "available": reservations.available(sku)}
