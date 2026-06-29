"""Auto Mode 컨트롤 루프 — 의사결정 주기마다 이벤트 수집→에이전트 제안→정책/실행.

run_once(): 1 사이클(테스트 가능). run_forever(): 별도 스레드에서 주기 반복(블로킹 작업이 async 루프를
막지 않도록 스레드로 동작). 빌드 6~8은 Picking 흐름만 — 도메인 6종·배치 시뮬은 빌드 9~10.
"""
import threading
import time

from bb import actions, audit, events, executor, settings
from bb.agents import REGISTRY
from bb.store import ensure_schema


def run_once(force: bool = False) -> dict:
    """1 사이클: NEW 이벤트 → 에이전트 propose → Action 생성·실행. 실행 중 발생한 체인 이벤트
    (NEED_PUTAWAY·TASK_CREATED)도 같은 사이클에서 소진(budget·pass 상한)."""
    ensure_schema()
    if not force and not settings.enabled():
        return {"enabled": False, "events": 0, "created": [], "executed": []}
    budget = settings.max_actions_per_cycle()
    out = {"enabled": True, "events": 0, "created": [], "executed": []}
    passes = 0
    while budget > 0 and passes < 100:
        passes += 1
        evs = events.new_events(limit=budget)
        if not evs:
            break
        for ev in evs:
            if budget <= 0:
                break
            events.set_status(ev["event_id"], "PROCESSING")
            audit.log("EVENT_RECEIVED", "OK", event_id=ev["event_id"], message=ev["event_type"])
            for agent in REGISTRY:
                if not agent.handles(ev["event_type"]):
                    continue
                for spec in agent.propose(ev):
                    res = actions.create(**spec)
                    out["created"].append({"action_id": res.get("action_id"), "status": res["status"],
                                           "agent": spec["agent_name"], "type": spec["action_type"]})
                    if res["status"] == "PENDING":
                        audit.log("ACTION_CREATED", "OK", action_id=res["action_id"], event_id=ev["event_id"],
                                  agent_name=spec["agent_name"], action_type=spec["action_type"],
                                  message=spec.get("reason"))
                        r = executor.execute(res["action_id"])
                        out["executed"].append({"action_id": res["action_id"], "agent": spec["agent_name"],
                                                "type": spec["action_type"], "status": r.get("status"),
                                                "reason": r.get("reason")})
                        budget -= 1
            events.set_status(ev["event_id"], "PROCESSED")
            out["events"] += 1
    return out


# ---------- 백그라운드 주기 실행 ----------
_thread: threading.Thread | None = None
_running = False


def _loop():
    global _running
    while _running:
        try:
            if settings.enabled():
                run_once()
        except Exception as e:  # noqa: BLE001
            audit.log("FINISHED", "FAIL", message=f"control loop 오류: {e}")
        time.sleep(settings.cycle_seconds())


def start() -> dict:
    global _thread, _running
    if not _running:
        _running = True
        _thread = threading.Thread(target=_loop, name="bb-control-loop", daemon=True)
        _thread.start()
    return {"running": _running, "cycle_seconds": settings.cycle_seconds()}


def stop() -> dict:
    global _running
    _running = False
    return {"running": _running}


def status() -> dict:
    return {"running": _running, "enabled": settings.enabled(), "cycle_seconds": settings.cycle_seconds()}
