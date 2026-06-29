"""Action Executor — 자동 실행의 유일한 상태변경 경로.

순서: idempotency → Policy → Pre-check(운영 DB 최신상태) → Lock → 트랜잭션(핸들러 write) →
      Post-check → commit/ rollback → 상태·감사로그. 핸들러는 단일 conn 트랜잭션으로 원자 실행한다.
"""
import json
import uuid

from db.database import get_connection
from tools.common import q

from bb import actions, audit, locks, policy, reservations, settings
from bb.store import now


# ---------- Pre-check (운영 DB 최신상태) ----------
def _precheck(a: dict) -> dict:
    at = a["action_type"]
    p = json.loads(a.get("payload_json") or "{}")
    if at == "CREATE_PICKING_TASK":
        order_no = p.get("order_no")
        o = q("SELECT status FROM outbound_orders WHERE order_no=?", (order_no,))
        if not o:
            return {"ok": False, "reason": "주문 없음"}
        if o[0]["status"] not in ("PLANNED", "ALLOCATED"):
            return {"ok": False, "reason": f"피킹 불가 상태({o[0]['status']})"}
        if q("SELECT 1 FROM picking_tasks WHERE order_no=? AND status!='CANCELLED'", (order_no,)):
            return {"ok": False, "reason": "이미 피킹작업 존재"}
        short = [ln["sku"] for ln in q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,))
                 if reservations.available(ln["sku"]) < ln["qty"]]
        if short:
            return {"ok": False, "reason": f"가용재고 부족: {','.join(short)}"}
        return {"ok": True}
    return {"ok": True}


# ---------- 핸들러 (단일 conn 트랜잭션 내 write) ----------
def _h_create_picking(conn, a: dict) -> dict:
    p = json.loads(a.get("payload_json") or "{}")
    order_no = p["order_no"]
    lines = conn.execute("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,)).fetchall()
    line_count = len(lines)
    total = sum(l["qty"] for l in lines)
    est = round(8 + (line_count - 1) * 2 + (total // 10) * 2)   # 간이 소요시간(분)
    task_id = "PCK-" + uuid.uuid4().hex[:6]
    conn.execute("INSERT INTO picking_tasks(picking_task_id,order_no,estimated_minutes,status) VALUES(?,?,?,?)",
                 (task_id, order_no, est, "ISSUED"))
    conn.execute("UPDATE outbound_orders SET status='PICKING_ISSUED' WHERE order_no=?", (order_no,))
    resv = []
    for ln in lines:
        rid = "RV-" + uuid.uuid4().hex[:8]
        conn.execute("""INSERT INTO inventory_reservations(reservation_id,sku,order_no,task_id,qty,status,
            created_by_action_id,created_at) VALUES(?,?,?,?,?, 'RESERVED', ?, ?)""",
                     (rid, ln["sku"], order_no, task_id, ln["qty"], a["action_id"], now()))
        resv.append(rid)
    return {"picking_task_id": task_id, "order_no": order_no, "estimated_minutes": est, "reservations": resv}


_HANDLERS = {"CREATE_PICKING_TASK": _h_create_picking}


def _postcheck(conn, a: dict, result: dict) -> dict:
    if a["action_type"] == "CREATE_PICKING_TASK":
        if not conn.execute("SELECT 1 FROM picking_tasks WHERE picking_task_id=?", (result["picking_task_id"],)).fetchone():
            return {"ok": False, "reason": "피킹작업 생성 확인 실패"}
        st = conn.execute("SELECT status FROM outbound_orders WHERE order_no=?", (result["order_no"],)).fetchone()
        if not st or st["status"] != "PICKING_ISSUED":
            return {"ok": False, "reason": "주문 상태 미반영"}
        return {"ok": True}
    return {"ok": True}


def _success_exists(idem_key: str, exclude: str) -> bool:
    r = q("SELECT 1 FROM blackboard_actions WHERE idempotency_key=? AND status='SUCCESS' AND action_id!=?",
          (idem_key, exclude))
    return bool(r)


def _finish(action_id, status, *, reason=None, error=None, **jsons):
    fields = {"status": status, "finished_at": now()}
    if reason is not None:
        fields["reason"] = reason
    if error is not None:
        fields["error_message"] = error
    fields.update(jsons)
    actions.update(action_id, **fields)


def execute(action_id: str) -> dict:
    a = actions.get(action_id)
    if not a:
        return {"status": "NOT_FOUND"}
    if a["status"] not in ("PENDING", "READY"):
        return {"status": a["status"], "skipped": True}
    base = dict(action_id=action_id, event_id=a.get("event_id"),
                agent_name=a.get("agent_name"), action_type=a["action_type"])

    # 1) idempotency
    if _success_exists(a["idempotency_key"], action_id):
        _finish(action_id, "SKIPPED_DUPLICATE", reason="중복 SUCCESS 존재")
        audit.log("FINISHED", "SKIPPED", message="중복 SUCCESS", **base)
        return {"status": "SKIPPED_DUPLICATE"}

    # 2) Policy
    pol = policy.check(a, settings.risk_threshold())
    audit.log("POLICY_CHECK", "OK" if pol["auto"] else "BLOCKED", message=pol["reason"], **base)
    actions.update(action_id, policy_result_json=json.dumps(pol, ensure_ascii=False), reason=pol["reason"])
    if not pol["auto"]:
        _finish(action_id, "POLICY_BLOCKED", reason=pol["reason"])
        return {"status": "POLICY_BLOCKED", "reason": pol["reason"]}

    # 3) Pre-check
    pre = _precheck(a)
    audit.log("PRECHECK", "OK" if pre["ok"] else "FAIL", message=pre.get("reason"), **base)
    actions.update(action_id, precheck_result_json=json.dumps(pre, ensure_ascii=False))
    if not pre["ok"]:
        _finish(action_id, "FAILED", reason=pre.get("reason"), error=pre.get("reason"))
        return {"status": "FAILED", "reason": pre.get("reason")}

    # 4) Lock (실패 시 PENDING 유지 → 다음 사이클 재시도)
    lks = pol["lock_keys"]
    if not locks.acquire_all(lks, action_id, ttl_seconds=60):
        audit.log("LOCK_ACQUIRED", "FAIL", message="lock 경합 — 재시도 대기", **base)
        return {"status": "PENDING", "retry": True, "reason": "lock 경합"}
    audit.log("LOCK_ACQUIRED", "OK", message=", ".join(lks), **base)
    actions.update(action_id, status="RUNNING", started_at=now())

    # 5) 트랜잭션 실행
    conn = get_connection()
    try:
        handler = _HANDLERS.get(a["action_type"])
        if not handler:
            raise RuntimeError(f"핸들러 미구현: {a['action_type']}")
        result = handler(conn, a)
        post = _postcheck(conn, a, result)
        if not post["ok"]:
            conn.rollback()
            audit.log("POSTCHECK", "FAIL", message=post.get("reason"), **base)
            _finish(action_id, "FAILED", reason=post.get("reason"), error=post.get("reason"),
                    postcheck_result_json=json.dumps(post, ensure_ascii=False))
            return {"status": "FAILED", "reason": post.get("reason")}
        conn.commit()
        audit.log("EXECUTE", "OK", after=result, **base)
        audit.log("POSTCHECK", "OK", **base)
        audit.log("FINISHED", "OK", **base)
        _finish(action_id, "SUCCESS",
                execution_result_json=json.dumps(result, ensure_ascii=False, default=str),
                postcheck_result_json=json.dumps(post, ensure_ascii=False))
        return {"status": "SUCCESS", "result": result}
    except Exception as e:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        audit.log("EXECUTE", "FAIL", message=str(e), **base)
        _finish(action_id, "FAILED", error=str(e), reason=f"실행 오류: {e}")
        return {"status": "FAILED", "error": str(e)}
    finally:
        conn.close()
        locks.release_all(lks, action_id)
