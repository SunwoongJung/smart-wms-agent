"""Auto Mode 컨트롤 루프 — 의사결정 주기마다 이벤트 수집→에이전트 제안→정책/실행.

run_once(): 1 사이클(테스트 가능). run_forever(): 별도 스레드에서 주기 반복(블로킹 작업이 async 루프를
막지 않도록 스레드로 동작). 빌드 6~8은 Picking 흐름만 — 도메인 6종·배치 시뮬은 빌드 9~10.
"""
import threading
import time

from bb import actions, audit, events, executor, settings, simulation_agent
from bb.agents import REGISTRY
from bb.store import ensure_schema, now


def run_once(force: bool = False, step_delay: float | None = None) -> dict:
    """1 사이클: NEW 이벤트 → 에이전트 propose → Action 생성·실행. 실행 중 발생한 체인 이벤트
    (NEED_PUTAWAY·TASK_CREATED)도 같은 사이클에서 소진(budget·pass 상한).
    step_delay: Action 1건 처리 후 지연(초) — 한 건씩 흘러가는 모습을 눈으로 보이게 함."""
    ensure_schema()
    if not force and not settings.enabled():
        return {"enabled": False, "events": 0, "created": [], "executed": []}
    if step_delay is None:
        step_delay = settings.step_delay()
    budget = settings.max_actions_per_cycle()
    out = {"enabled": True, "events": 0, "created": [], "executed": []}

    # 배치 What-if 게이트 — 캐시(논블로킹). DES는 백그라운드에서 갱신되어 흐름을 막지 않음.
    sim_gate = {"ok": True, "ran": False, "reason": "시뮬 미사용", "kpis": {}}
    if settings.simulation_required() and events.new_events(limit=1):
        sim_gate = simulation_agent.gate()
        if sim_gate.get("ran"):
            audit.log("PRECHECK", "OK" if sim_gate["ok"] else "BLOCKED",
                      agent_name="SimulationAgent", action_type="BATCH_SIMULATION", message=sim_gate["reason"])
    out["simulation"] = sim_gate

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
                        if spec["action_type"] in simulation_agent.SIM_REQUIRED and not sim_gate["ok"]:
                            actions.update(res["action_id"], status="POLICY_BLOCKED",
                                           reason=f"배치 시뮬 차단: {sim_gate['reason']}", finished_at=now())
                            audit.log("POLICY_CHECK", "BLOCKED", action_id=res["action_id"], event_id=ev["event_id"],
                                      agent_name=spec["agent_name"], action_type=spec["action_type"],
                                      message=f"시뮬 KPI: {sim_gate['reason']}")
                            out["executed"].append({"action_id": res["action_id"], "agent": spec["agent_name"],
                                                    "type": spec["action_type"], "status": "POLICY_BLOCKED",
                                                    "reason": sim_gate["reason"]})
                        else:
                            r = executor.execute(res["action_id"])
                            out["executed"].append({"action_id": res["action_id"], "agent": spec["agent_name"],
                                                    "type": spec["action_type"], "status": r.get("status"),
                                                    "reason": r.get("reason")})
                        budget -= 1
                        if step_delay > 0:
                            time.sleep(step_delay)   # 한 건씩 가시화(사람이 흐름을 볼 수 있게)
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
        simulation_agent.kick()   # 첫 배치 시뮬을 백그라운드로 띄움
        _thread = threading.Thread(target=_loop, name="bb-control-loop", daemon=True)
        _thread.start()
    return {"running": _running, "cycle_seconds": settings.cycle_seconds()}


def stop() -> dict:
    global _running
    _running = False
    return {"running": _running}


def status() -> dict:
    return {"running": _running, "enabled": settings.enabled(), "cycle_seconds": settings.cycle_seconds()}
