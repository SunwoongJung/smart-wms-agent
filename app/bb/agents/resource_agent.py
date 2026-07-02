"""Resource Agent — TASK_CREATED → ALLOCATE_TEAM(가용 team=worker 2 + forklift 1 자동 배정).

가용 = active인 자원 중, 진행중(TEAM_ASSIGNED·IN_PROGRESS) 작업에 배정되지 않은 자.
2명의 작업자 + 지게차 1대를 모두 구할 수 있을 때만 제안(부분 배정 없음). 없으면 다음 사이클 대기.
"""
import json

from tools.common import q

NAME = "ResourceAgent"
EVENTS = {"TASK_CREATED"}
_BUSY_STATUSES = ("TEAM_ASSIGNED", "IN_PROGRESS")


def handles(event_type: str) -> bool:
    return event_type in EVENTS


def _busy_ids() -> set:
    marks = ",".join("?" for _ in _BUSY_STATUSES)
    rows = q(f"""SELECT worker_id id FROM picking_tasks WHERE worker_id IS NOT NULL AND status IN ({marks})
                 UNION SELECT worker_id_2 FROM picking_tasks WHERE worker_id_2 IS NOT NULL AND status IN ({marks})
                 UNION SELECT forklift_id FROM picking_tasks WHERE forklift_id IS NOT NULL AND status IN ({marks})
                 UNION SELECT worker_id FROM stocking_tasks WHERE worker_id IS NOT NULL AND status IN ({marks})
                 UNION SELECT worker_id_2 FROM stocking_tasks WHERE worker_id_2 IS NOT NULL AND status IN ({marks})
                 UNION SELECT forklift_id FROM stocking_tasks WHERE forklift_id IS NOT NULL AND status IN ({marks})""",
             tuple(_BUSY_STATUSES) * 6)
    return {r["id"] for r in rows}


def _free_team() -> dict | None:
    busy = _busy_ids()
    workers = [r["resource_id"] for r in q(
        "SELECT resource_id FROM resources WHERE resource_type='WORKER' AND active_flag=1 ORDER BY resource_id")
        if r["resource_id"] not in busy]
    forklifts = [r["resource_id"] for r in q(
        "SELECT resource_id FROM resources WHERE resource_type='FORKLIFT' AND active_flag=1 ORDER BY resource_id")
        if r["resource_id"] not in busy]
    if len(workers) < 2 or not forklifts:
        return None
    return {"worker_id": workers[0], "worker_id_2": workers[1], "forklift_id": forklifts[0]}


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
    team = _free_team()
    if not team:
        return []
    return [dict(agent_name=NAME, action_type="ALLOCATE_TEAM",
                 idempotency_key=f"ALLOCATE_TEAM:{tid}", event_id=event["event_id"],
                 target_type="task", target_id=tid,
                 payload={"task_id": tid, "kind": kind, **team},
                 priority_score=30.0, auto_executable=True,
                 reason=f"작업 {tid}에 team(작업자 {team['worker_id']}/{team['worker_id_2']}, "
                        f"지게차 {team['forklift_id']}) 자동 배정")]
