"""Resource Agent — TASK_CREATED → ALLOCATE_WORKER(가용 작업자 1명 자동 배정).

가용 작업자 = active WORKER 중 진행중(ISSUED) 작업에 배정되지 않은 자. 없으면 다음 사이클 대기.
"""
import json

from tools.common import q

NAME = "ResourceAgent"
EVENTS = {"TASK_CREATED"}


def handles(event_type: str) -> bool:
    return event_type in EVENTS


def _free_worker() -> str | None:
    rows = q("""SELECT resource_id FROM resources
                WHERE resource_type='WORKER' AND active_flag=1 AND resource_id NOT IN (
                    SELECT worker_id FROM picking_tasks WHERE worker_id IS NOT NULL AND status='ISSUED'
                    UNION SELECT worker_id FROM stocking_tasks WHERE worker_id IS NOT NULL AND status='ISSUED')
                ORDER BY resource_id LIMIT 1""")
    return rows[0]["resource_id"] if rows else None


def propose(event: dict) -> list[dict]:
    tid = event.get("target_id")
    if not tid:
        return []
    kind = json.loads(event.get("payload_json") or "{}").get("kind") or ("picking" if tid.startswith("PCK") else "stocking")
    tbl = "picking_tasks" if kind == "picking" else "stocking_tasks"
    idcol = "picking_task_id" if kind == "picking" else "stocking_task_id"
    t = q(f"SELECT worker_id, status FROM {tbl} WHERE {idcol}=?", (tid,))
    if not t or t[0]["worker_id"] or t[0]["status"] != "ISSUED":
        return []
    w = _free_worker()
    if not w:
        return []
    return [dict(agent_name=NAME, action_type="ALLOCATE_WORKER",
                 idempotency_key=f"ALLOCATE_WORKER:{tid}", event_id=event["event_id"],
                 target_type="task", target_id=tid,
                 payload={"task_id": tid, "kind": kind, "resource_id": w},
                 priority_score=30.0, auto_executable=True,
                 reason=f"작업 {tid}에 작업자 {w} 자동 배정")]
