"""요청 생애주기(파생 뷰) — 입/출고 한 건이 블랙보드에서 거친 업무 마일스톤을 correlation으로 재구성.

스키마 변경 없음. 기존 blackboard_events/blackboard_actions만 요청ID + 파생 작업ID로 묶어 읽는다.
한 요청의 target은 두 갈래로 나뉜다:
  · 입고 INB: 접수·입고처리·적치지시(target=inbound) → 적치작업 STK 생성 후(target=task)
  · 출고 ORD: 접수·피킹지시(target=order) → 피킹작업 PCK(target=task) → 완료 시 다시 target=order
연결: stocking_tasks.inbound_no / picking_tasks.order_no.
"""
import json

from tools.common import q

# 업무 마일스톤 정의(간결) — (key, 라벨, 소스종류, 매칭 event_type/action_type, finalized 여부)
_INBOUND_MS = [
    ("received", "요청 접수", "event", "NEW_INBOUND_ARRIVAL", False),
    ("inbound", "입고 처리", "action", "CREATE_INBOUND_TASK", False),
    ("putaway", "적치 지시", "action", "CREATE_PUTAWAY_TASK", False),
    ("team", "자원 배정(작업팀)", "action", "ALLOCATE_TEAM", False),
    ("start", "적치 작업 시작", "action", "START_ZONE_WORK", False),
    ("done", "적치 완료", "action", "FINISH_ZONE_LEG", True),
]
_OUTBOUND_MS = [
    ("received", "요청 접수", "event", "NEW_OUTBOUND_ORDER", False),
    ("picking", "피킹 지시", "action", "CREATE_PICKING_TASK", False),
    ("team", "자원 배정(작업팀)", "action", "ALLOCATE_TEAM", False),
    ("start", "피킹 작업 시작", "action", "START_ZONE_WORK", False),
    ("pick_done", "피킹 완료", "action", "FINISH_ZONE_LEG", True),
    ("shipping", "출고 준비", "action", "CREATE_SHIPPING_TASK", False),
]
_STATUS_LABEL = {
    # 입고
    "PLANNED": "접수", "RECEIVED": "입고완료", "STOCKING_RECOMMENDED": "적치 진행",
    "STOCKING_TASK_CREATED": "적치 진행", "STOCKED": "적치완료",
    # 출고
    "ALLOCATED": "할당", "PICKING_ISSUED": "피킹 진행", "SHIPPING_PENDING": "출고대기", "SHIPPED": "출고완료",
    "AWAITING_STOCK": "발주 대기",
}
_DONE_STATUS = {"SUCCESS"}
_FAIL_STATUS = {"FAILED"}
_BLOCK_STATUS = {"POLICY_BLOCKED"}


def _kind_of(rid: str) -> str | None:
    if rid.startswith("RT-I-"):
        return "inbound"
    if rid.startswith("RT-O-"):
        return "outbound"
    return None


def list_requests(kind: str | None = None, limit: int = 40) -> list[dict]:
    """실시간 생성(RT-*) 입/출고 요청을 최신순으로. 현재 상태·요약 포함(목록용, 경량)."""
    out = []
    if kind in (None, "inbound"):
        for r in q("""SELECT inbound_no id, sku, qty, status, created_at
                      FROM inbound_orders WHERE inbound_no LIKE 'RT-I-%'
                      ORDER BY created_at DESC, rowid DESC LIMIT ?""", (limit,)):
            out.append({"kind": "inbound", "id": r["id"], "sku": r["sku"], "qty": r["qty"],
                        "status": r["status"], "status_label": _STATUS_LABEL.get(r["status"], r["status"]),
                        "created_at": r["created_at"]})
    if kind in (None, "outbound"):
        for r in q("""SELECT o.order_no id, o.status, o.created_at,
                        (SELECT sku FROM outbound_order_lines WHERE order_no=o.order_no LIMIT 1) sku,
                        (SELECT SUM(qty) FROM outbound_order_lines WHERE order_no=o.order_no) qty
                      FROM outbound_orders o WHERE o.order_no LIKE 'RT-O-%'
                      ORDER BY o.created_at DESC, o.rowid DESC LIMIT ?""", (limit,)):
            out.append({"kind": "outbound", "id": r["id"], "sku": r["sku"], "qty": r["qty"],
                        "status": r["status"], "status_label": _STATUS_LABEL.get(r["status"], r["status"]),
                        "created_at": r["created_at"]})
    out.sort(key=lambda x: (x["created_at"] or ""), reverse=True)
    return out[:limit]


def _targets(kind: str, rid: str) -> list[str]:
    ids = [rid]
    if kind == "inbound":
        ids += [r["stocking_task_id"] for r in
                q("SELECT stocking_task_id FROM stocking_tasks WHERE inbound_no=?", (rid,))]
    else:
        ids += [r["picking_task_id"] for r in
                q("SELECT picking_task_id FROM picking_tasks WHERE order_no=?", (rid,))]
    return ids


def _is_finalized(a: dict) -> bool:
    try:
        return bool(json.loads(a.get("execution_result_json") or "{}").get("finalized"))
    except (ValueError, TypeError):
        return False


def _pick_action(actions: list[dict], action_type: str, finalized: bool) -> dict | None:
    cands = [a for a in actions if a["action_type"] == action_type]
    if finalized:
        fin = [a for a in cands if _is_finalized(a)]
        cands = fin or cands
    if not cands:
        return None
    done = [a for a in cands if a["status"] in _DONE_STATUS]
    pool = done or cands
    return sorted(pool, key=lambda a: (a.get("finished_at") or a.get("created_at") or ""))[-1]


def _ms_status(raw: str | None) -> str:
    if raw in _DONE_STATUS:
        return "done"
    if raw in _FAIL_STATUS:
        return "failed"
    if raw in _BLOCK_STATUS:
        return "blocked"
    if raw is None:
        return "pending"
    return "in_progress"


def request_trace(kind: str, rid: str) -> dict:
    kind = kind or _kind_of(rid)
    if kind not in ("inbound", "outbound"):
        return {"error": "지원하지 않는 요청 종류"}
    tset = _targets(kind, rid)
    marks = ",".join("?" for _ in tset)
    actions = q(f"SELECT * FROM blackboard_actions WHERE target_id IN ({marks}) ORDER BY created_at", tuple(tset))
    ev = q("""SELECT * FROM blackboard_events WHERE target_id=? AND event_type IN
              ('NEW_INBOUND_ARRIVAL','NEW_OUTBOUND_ORDER') ORDER BY created_at LIMIT 1""", (rid,))

    specs = _INBOUND_MS if kind == "inbound" else _OUTBOUND_MS
    milestones = []
    for key, label, src, match, finalized in specs:
        if src == "event":
            e = ev[0] if ev else None
            milestones.append({
                "key": key, "label": label,
                "status": "done" if e else "pending",
                "agent": "실시간 수요",
                "ts": e["created_at"] if e else None,
                "detail": (f"{e['event_type']}" if e else "미발생"),
                "action_id": None,
            })
        else:
            a = _pick_action(actions, match, finalized)
            milestones.append({
                "key": key, "label": label,
                "status": _ms_status(a["status"]) if a else "pending",
                "agent": a["agent_name"] if a else None,
                "ts": (a.get("finished_at") or a.get("started_at") or a.get("created_at")) if a else None,
                "detail": (a.get("reason") or a.get("error_message") or a["action_type"]) if a else "미발생",
                "action_id": a["action_id"] if a else None,
            })

    # 출고 결품 발주 마일스톤 — PLACE_REPLENISHMENT_ORDER가 있으면 '요청 접수' 뒤에 끼워넣는다.
    awaiting = False
    if kind == "outbound":
        repl = _pick_action(actions, "PLACE_REPLENISHMENT_ORDER", False)
        if repl:
            repl_inbs = q("SELECT inbound_no, sku, qty, expected_date, status FROM inbound_orders WHERE replenish_for=?", (rid,))
            all_stocked = bool(repl_inbs) and all(r["status"] == "STOCKED" for r in repl_inbs)
            detail = " / ".join(f"{r['sku']} {r['qty']}개 → 도착예정 {r['expected_date']}({r['status']})" for r in repl_inbs) \
                or (repl.get("reason") or "발주")
            milestones.insert(1, {
                "key": "replenish", "label": "재고 부족 → 발주",
                # 발주 자체는 성공했고 도착 대기 중이면 '진행'(파랑), 도착·적치 완료면 '완료'(초록)
                "status": "done" if all_stocked else ("in_progress" if repl["status"] == "SUCCESS" else _ms_status(repl["status"])),
                "agent": repl["agent_name"],
                "ts": repl.get("finished_at") or repl.get("created_at"),
                "detail": detail,
                "action_id": repl["action_id"],
            })

    head = (q("SELECT status FROM inbound_orders WHERE inbound_no=?", (rid,)) if kind == "inbound"
            else q("SELECT status FROM outbound_orders WHERE order_no=?", (rid,)))
    cur = head[0]["status"] if head else None
    awaiting = (cur == "AWAITING_STOCK")
    return {"kind": kind, "id": rid, "current_status": cur,
            "current_status_label": _STATUS_LABEL.get(cur, cur), "task_ids": tset[1:],
            "awaiting_stock": awaiting, "milestones": milestones}
