"""Zone 스케줄러 — 매 컨트롤 루프 사이클마다 zone 점유·team 배정 진행을 앞당긴다(폴링, 이벤트 1회성 아님).

team 배정 단계: ISSUED(팀 미배정)인 작업 중 team이 비면 FIFO로 ALLOCATE_TEAM — TASK_CREATED
이벤트는 1회만 발동되므로(ResourceAgent가 그 순간 team이 없으면 영영 재시도 안 됨), 여기서 폴링으로
보강한다. 완료 단계: IN_PROGRESS이고 작업시간이 다 된 작업 → FINISH_ZONE_LEG(적치는 즉시 완료,
피킹은 남은 zone이 있으면 zone_index만 전진). 시작 단계: team은 배정됐지만(TEAM_ASSIGNED) 목표
zone이 사용중이라 대기하던 작업 중, zone이 빈 것부터 FIFO로 START_ZONE_WORK. Zone 동시용량은
1(단일 점유).
"""
from bb import actions, executor
from bb.agents.resource_agent import _free_team
from bb.store import now
from bb.zone_work import current_zone, zone_busy
from tools.common import q

NAME = "ZoneScheduler"
_KINDS = (("stocking_tasks", "stocking_task_id", "stocking"), ("picking_tasks", "picking_task_id", "picking"))


def _pending_team_requests() -> list[dict]:
    out = []
    for tbl, idcol, kind in _KINDS:
        rows = q(f"""SELECT {idcol} AS task_id, issued_at FROM {tbl}
                     WHERE status='ISSUED' AND worker_id IS NULL ORDER BY issued_at ASC""")
        out.extend({"task_id": r["task_id"], "kind": kind, "issued_at": r["issued_at"]} for r in rows)
    out.sort(key=lambda t: t["issued_at"] or "")   # stocking·picking 병합 후 발행시각 순 FIFO
    return out


def _due_in_progress() -> list[dict]:
    out = []
    for tbl, idcol, kind in _KINDS:
        zone_idx_col = "zone_index" if kind == "picking" else "0 AS zone_index"
        rows = q(f"""SELECT {idcol} AS task_id, {zone_idx_col} FROM {tbl}
                     WHERE status='IN_PROGRESS' AND expected_complete_at IS NOT NULL
                       AND expected_complete_at<=?""", (now(),))
        for r in rows:
            out.append({"task_id": r["task_id"], "kind": kind, "zone_index": r.get("zone_index") or 0})
    return out


def _waiting_for_zone() -> list[dict]:
    out = []
    for tbl, idcol, kind in _KINDS:
        rows = q(f"SELECT * FROM {tbl} WHERE status='TEAM_ASSIGNED' ORDER BY issued_at ASC")
        for r in rows:
            out.append({"task_id": r[idcol], "kind": kind, "zone_index": r.get("zone_index") or 0,
                        "zone_id": current_zone(kind, r)})
    return out


def advance() -> dict:
    finished, started, allocated = [], [], []

    for t in _pending_team_requests():
        team = _free_team()
        if not team:
            break   # team 풀 소진 — 나머지는 다음 사이클
        aid = actions.create(
            agent_name=NAME, action_type="ALLOCATE_TEAM",
            idempotency_key=f"ALLOCATE_TEAM:{t['task_id']}",
            target_type="task", target_id=t["task_id"], payload={"task_id": t["task_id"], "kind": t["kind"], **team},
            priority_score=30.0, auto_executable=True,
            reason=f"{t['task_id']} team({team['worker_id']}/{team['worker_id_2']}, {team['forklift_id']}) 배정")
        if aid["status"] == "PENDING":
            r = executor.execute(aid["action_id"])
            if r.get("status") == "SUCCESS":
                allocated.append({"task_id": t["task_id"]})

    for t in _due_in_progress():
        aid = actions.create(
            agent_name=NAME, action_type="FINISH_ZONE_LEG",
            idempotency_key=f"FINISH_ZONE_LEG:{t['task_id']}:{t['zone_index']}",
            target_type="task", target_id=t["task_id"], payload={"task_id": t["task_id"], "kind": t["kind"]},
            priority_score=50.0, auto_executable=True, reason=f"{t['task_id']} zone 작업시간 종료 — 완료 처리")
        if aid["status"] == "PENDING":
            r = executor.execute(aid["action_id"])
            finished.append({"task_id": t["task_id"], "status": r.get("status")})

    for t in _waiting_for_zone():
        if t["zone_id"] and zone_busy(t["zone_id"], exclude_task_id=t["task_id"]):
            continue   # zone 사용중 — 대기 유지, 다음 사이클 재시도
        aid = actions.create(
            agent_name=NAME, action_type="START_ZONE_WORK",
            idempotency_key=f"START_ZONE_WORK:{t['task_id']}:{t['zone_index']}",
            target_type="task", target_id=t["task_id"], payload={"task_id": t["task_id"], "kind": t["kind"]},
            priority_score=45.0, auto_executable=True,
            reason=f"{t['task_id']} zone({t['zone_id'] or '-'}) 확보 — 작업 시작")
        if aid["status"] == "PENDING":
            r = executor.execute(aid["action_id"])
            if r.get("status") == "SUCCESS":
                started.append({"task_id": t["task_id"], "zone_id": t["zone_id"]})

    return {"allocated": allocated, "finished": finished, "started": started}
