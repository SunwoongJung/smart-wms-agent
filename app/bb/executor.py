"""Action Executor — 자동 실행의 유일한 상태변경 경로.

순서: idempotency → Policy → Pre-check(운영 DB 최신상태) → Lock → 트랜잭션(핸들러 write) →
      Post-check → commit/ rollback → 상태·감사로그. 핸들러는 단일 conn 트랜잭션으로 원자 실행한다.
"""
import json
import uuid

from db.database import get_connection
from tools.common import q

from bb import actions, audit, events, locks, policy, reservations, settings
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
    if at == "CREATE_INBOUND_TASK":
        o = q("SELECT status FROM inbound_orders WHERE inbound_no=?", (p.get("inbound_no"),))
        if not o:
            return {"ok": False, "reason": "입고 없음"}
        if o[0]["status"] != "PLANNED":
            return {"ok": False, "reason": f"입고 처리 불가 상태({o[0]['status']})"}
        return {"ok": True}
    if at == "CREATE_PUTAWAY_TASK":
        o = q("SELECT status FROM inbound_orders WHERE inbound_no=?", (p.get("inbound_no"),))
        if not o or o[0]["status"] != "RECEIVED":
            return {"ok": False, "reason": "입고완료(RECEIVED) 아님"}
        if q("SELECT 1 FROM stocking_tasks WHERE inbound_no=? AND status!='CANCELLED'", (p.get("inbound_no"),)):
            return {"ok": False, "reason": "이미 적치작업 존재"}
        loc = q("SELECT capacity, occupied_qty FROM locations WHERE location_id=?", (p.get("location_id"),))
        if not loc:
            return {"ok": False, "reason": "Location 없음"}
        if (loc[0]["capacity"] - loc[0]["occupied_qty"]) < int(p.get("qty", 0)):
            return {"ok": False, "reason": "Location 용량 부족"}
        return {"ok": True}
    if at == "CREATE_SHIPPING_TASK":
        o = q("SELECT status FROM outbound_orders WHERE order_no=?", (p.get("order_no"),))
        if not o or o[0]["status"] != "PICKING_ISSUED":
            return {"ok": False, "reason": "피킹 완료(PICKING_ISSUED) 아님"}
        if q("SELECT 1 FROM shipping_pending WHERE order_no=? AND status='PENDING'", (p.get("order_no"),)):
            return {"ok": False, "reason": "이미 출고대기 존재"}
        return {"ok": True}
    if at == "ALLOCATE_TEAM":
        tbl = "picking_tasks" if p.get("kind") == "picking" else "stocking_tasks"
        idcol = "picking_task_id" if p.get("kind") == "picking" else "stocking_task_id"
        t = q(f"SELECT worker_id, status FROM {tbl} WHERE {idcol}=?", (p.get("task_id"),))
        if not t:
            return {"ok": False, "reason": "작업 없음"}
        if t[0]["worker_id"]:
            return {"ok": False, "reason": "이미 team 배정됨"}
        if t[0]["status"] != "ISSUED":
            return {"ok": False, "reason": f"team 배정 불가 상태({t[0]['status']})"}
        return {"ok": True}
    if at == "START_ZONE_WORK":
        from bb.zone_work import current_zone, zone_busy
        tbl = "picking_tasks" if p.get("kind") == "picking" else "stocking_tasks"
        idcol = "picking_task_id" if p.get("kind") == "picking" else "stocking_task_id"
        t = q(f"SELECT * FROM {tbl} WHERE {idcol}=?", (p.get("task_id"),))
        if not t:
            return {"ok": False, "reason": "작업 없음"}
        if t[0]["status"] != "TEAM_ASSIGNED":
            return {"ok": False, "reason": f"zone 진입 불가 상태({t[0]['status']})"}
        zid = current_zone(p.get("kind"), t[0])
        if zid and zone_busy(zid, exclude_task_id=p.get("task_id")):
            return {"ok": False, "reason": f"zone 사용중({zid})"}
        return {"ok": True}
    if at == "FINISH_ZONE_LEG":
        tbl = "picking_tasks" if p.get("kind") == "picking" else "stocking_tasks"
        idcol = "picking_task_id" if p.get("kind") == "picking" else "stocking_task_id"
        t = q(f"SELECT status, expected_complete_at FROM {tbl} WHERE {idcol}=?", (p.get("task_id"),))
        if not t:
            return {"ok": False, "reason": "작업 없음"}
        if t[0]["status"] != "IN_PROGRESS":
            return {"ok": False, "reason": f"완료 처리 불가 상태({t[0]['status']})"}
        return {"ok": True}
    if at == "PLACE_REPLENISHMENT_ORDER":
        o = q("SELECT status FROM outbound_orders WHERE order_no=?", (p.get("order_no"),))
        if not o:
            return {"ok": False, "reason": "주문 없음"}
        if o[0]["status"] not in ("PLANNED", "ALLOCATED"):
            return {"ok": False, "reason": f"발주 불가 상태({o[0]['status']})"}
        if not (p.get("shortage") or []):
            return {"ok": False, "reason": "부족분 없음"}
        return {"ok": True}
    if at == "REPRIORITIZE_PICKING_TASK":
        t = q("SELECT status FROM picking_tasks WHERE picking_task_id=?", (p.get("task_id"),))
        if not t:
            return {"ok": False, "reason": "피킹작업 없음"}
        if t[0]["status"] in ("COMPLETED", "CANCELLED"):
            return {"ok": False, "reason": f"변경 불가 상태({t[0]['status']})"}
        return {"ok": True}
    return {"ok": True}


# ---------- 핸들러 (단일 conn 트랜잭션 내 write) ----------
def _h_create_picking(conn, a: dict) -> dict:
    from bb.zone_work import zone_sequence_for_skus
    p = json.loads(a.get("payload_json") or "{}")
    order_no = p["order_no"]
    lines = conn.execute("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,)).fetchall()
    line_count = len(lines)
    total = sum(l["qty"] for l in lines)
    est = round(8 + (line_count - 1) * 2 + (total // 10) * 2)   # 간이 소요시간(분)
    task_id = "PCK-" + uuid.uuid4().hex[:6]
    zone_seq = zone_sequence_for_skus(list(dict.fromkeys(l["sku"] for l in lines)))
    conn.execute("""INSERT INTO picking_tasks(picking_task_id,order_no,estimated_minutes,status,zone_sequence,zone_index,issued_at)
                    VALUES(?,?,?,?,?,0,?)""", (task_id, order_no, est, "ISSUED", json.dumps(zone_seq), now()))
    conn.execute("UPDATE outbound_orders SET status='PICKING_ISSUED' WHERE order_no=?", (order_no,))
    resv = []
    for ln in lines:
        rid = "RV-" + uuid.uuid4().hex[:8]
        conn.execute("""INSERT INTO inventory_reservations(reservation_id,sku,order_no,task_id,qty,status,
            created_by_action_id,created_at) VALUES(?,?,?,?,?, 'RESERVED', ?, ?)""",
                     (rid, ln["sku"], order_no, task_id, ln["qty"], a["action_id"], now()))
        resv.append(rid)
    return {"picking_task_id": task_id, "order_no": order_no, "estimated_minutes": est, "reservations": resv}


def _h_create_inbound(conn, a: dict) -> dict:
    p = json.loads(a.get("payload_json") or "{}")
    conn.execute("UPDATE inbound_orders SET status='RECEIVED', received_datetime=? WHERE inbound_no=?",
                 (now(), p["inbound_no"]))
    return {"inbound_no": p["inbound_no"], "status": "RECEIVED"}


def _h_create_putaway(conn, a: dict) -> dict:
    p = json.loads(a.get("payload_json") or "{}")
    inbound_no, sku, loc, qty = p["inbound_no"], p["sku"], p["location_id"], int(p["qty"])
    task_id = "STK-" + uuid.uuid4().hex[:6]
    zone_id = conn.execute("SELECT zone_id FROM locations WHERE location_id=?", (loc,)).fetchone()
    zone_id = zone_id["zone_id"] if zone_id else None
    conn.execute("""INSERT INTO stocking_tasks(stocking_task_id,inbound_no,location_id,qty,status,zone_id,issued_at)
                    VALUES(?,?,?,?,?,?,?)""", (task_id, inbound_no, loc, qty, "ISSUED", zone_id, now()))
    conn.execute("UPDATE inbound_orders SET status='STOCKING_TASK_CREATED' WHERE inbound_no=?", (inbound_no,))
    conn.execute("UPDATE locations SET occupied_qty=occupied_qty+? WHERE location_id=?", (qty, loc))  # 위치 임시 점유
    return {"stocking_task_id": task_id, "inbound_no": inbound_no, "location_id": loc, "qty": qty}


def _h_create_shipping(conn, a: dict) -> dict:
    p = json.loads(a.get("payload_json") or "{}")
    order_no = p["order_no"]
    cur = conn.execute("INSERT INTO shipping_pending(order_no,ready_datetime,status) VALUES(?,?, 'PENDING')",
                       (order_no, now()))
    conn.execute("UPDATE outbound_orders SET status='SHIPPING_PENDING' WHERE order_no=?", (order_no,))
    return {"order_no": order_no, "pending_id": cur.lastrowid, "status": "SHIPPING_PENDING"}


def _h_allocate_team(conn, a: dict) -> dict:
    """team = worker 2 + forklift 1(원자적 배정). 배정 즉시 zone 진입 대기(TEAM_ASSIGNED)로 전환."""
    p = json.loads(a.get("payload_json") or "{}")
    tbl = "picking_tasks" if p.get("kind") == "picking" else "stocking_tasks"
    idcol = "picking_task_id" if p.get("kind") == "picking" else "stocking_task_id"
    conn.execute(f"""UPDATE {tbl} SET worker_id=?, worker_id_2=?, forklift_id=?, status='TEAM_ASSIGNED'
                     WHERE {idcol}=?""",
                 (p["worker_id"], p["worker_id_2"], p["forklift_id"], p["task_id"]))
    return {"task_id": p["task_id"], "kind": p.get("kind"),
            "worker_id": p["worker_id"], "worker_id_2": p["worker_id_2"], "forklift_id": p["forklift_id"]}


def _h_start_zone_work(conn, a: dict) -> dict:
    from datetime import datetime, timedelta

    from bb.zone_work import current_zone, zone_minutes
    p = json.loads(a.get("payload_json") or "{}")
    tbl = "picking_tasks" if p.get("kind") == "picking" else "stocking_tasks"
    idcol = "picking_task_id" if p.get("kind") == "picking" else "stocking_task_id"
    t = conn.execute(f"SELECT * FROM {tbl} WHERE {idcol}=?", (p["task_id"],)).fetchone()
    zid = current_zone(p.get("kind"), dict(t))
    started = datetime.strptime(now(), "%Y-%m-%d %H:%M:%S")
    mins = zone_minutes(zid) if zid else 0.0
    expected = (started + timedelta(minutes=mins)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(f"""UPDATE {tbl} SET status='IN_PROGRESS', started_at=?, expected_complete_at=?
                     WHERE {idcol}=?""", (now(), expected, p["task_id"]))
    return {"task_id": p["task_id"], "kind": p.get("kind"), "zone_id": zid,
            "work_minutes": mins, "expected_complete_at": expected}


def _deplete_inventory(conn, sku: str, qty: int) -> None:
    """FIFO(유통기한 임박 우선) 재고 실제 차감 — 피킹 완료 시 재고원장 반영 + 로케이션 점유 해제.

    로케이션 occupied_qty는 적치 지시 시 예약(+)되므로, 피킹으로 빠질 때 같은 양만큼 해제(−)해야
    실재고와 일관된다(안 하면 occupied_qty가 계속 부풀어 적치 사전검증이 부당하게 막힘)."""
    remaining = qty
    rows = conn.execute("""SELECT inventory_id, location_id, qty FROM inventory
                           WHERE sku=? AND status='AVAILABLE' AND qty>0
                           ORDER BY (expiry_date IS NULL), expiry_date ASC, inbound_date ASC""", (sku,)).fetchall()
    for r in rows:
        if remaining <= 0:
            break
        take = min(remaining, r["qty"])
        left = r["qty"] - take
        if left > 0:
            conn.execute("UPDATE inventory SET qty=? WHERE inventory_id=?", (left, r["inventory_id"]))
        else:
            conn.execute("DELETE FROM inventory WHERE inventory_id=?", (r["inventory_id"],))
        conn.execute("UPDATE locations SET occupied_qty=MAX(0, occupied_qty-?) WHERE location_id=?",
                     (take, r["location_id"]))   # 피킹으로 빠진 만큼 점유 해제(음수 방지)
        remaining -= take


def _h_finish_zone_leg(conn, a: dict) -> dict:
    """목표 zone 작업시간 종료 — 적치는 즉시 완료, 피킹은 남은 zone이 있으면 다음 zone으로 전진."""
    from bb.zone_work import is_last_zone
    p = json.loads(a.get("payload_json") or "{}")
    kind, task_id = p.get("kind"), p["task_id"]
    if kind == "picking":
        t = conn.execute("SELECT * FROM picking_tasks WHERE picking_task_id=?", (task_id,)).fetchone()
        if not is_last_zone(kind, dict(t)):
            conn.execute("""UPDATE picking_tasks SET zone_index=zone_index+1, status='TEAM_ASSIGNED',
                            started_at=NULL, expected_complete_at=NULL WHERE picking_task_id=?""", (task_id,))
            return {"task_id": task_id, "kind": kind, "advanced": True, "finalized": False}
        order_no = t["order_no"]
        conn.execute("""UPDATE picking_tasks SET status='COMPLETED', completed_at=? WHERE picking_task_id=?""",
                     (now(), task_id))
        resv = conn.execute("""SELECT reservation_id, sku, qty FROM inventory_reservations
                               WHERE task_id=? AND status='RESERVED'""", (task_id,)).fetchall()
        for r in resv:
            _deplete_inventory(conn, r["sku"], r["qty"])
            conn.execute("UPDATE inventory_reservations SET status='CONSUMED', released_at=? WHERE reservation_id=?",
                         (now(), r["reservation_id"]))
        return {"task_id": task_id, "kind": kind, "advanced": False, "finalized": True, "order_no": order_no}

    # stocking — zone 1개뿐이라 바로 완료
    t = conn.execute("SELECT * FROM stocking_tasks WHERE stocking_task_id=?", (task_id,)).fetchone()
    inbound_no = t["inbound_no"]
    inb = conn.execute("SELECT sku, qty FROM inbound_orders WHERE inbound_no=?", (inbound_no,)).fetchone()
    conn.execute("UPDATE stocking_tasks SET status='STOCKED', completed_at=? WHERE stocking_task_id=?",
                 (now(), task_id))
    conn.execute("UPDATE inbound_orders SET status='STOCKED' WHERE inbound_no=?", (inbound_no,))
    conn.execute("""INSERT INTO inventory(sku,lot_no,location_id,qty,inbound_date,expiry_date,status)
                    VALUES(?,?,?,?,?,NULL,'AVAILABLE')""",
                 (inb["sku"], f"LOT-{inbound_no}", t["location_id"], inb["qty"], now()[:10]))
    return {"task_id": task_id, "kind": kind, "advanced": False, "finalized": True, "inbound_no": inbound_no}


def _h_reprioritize_picking(conn, a: dict) -> dict:
    p = json.loads(a.get("payload_json") or "{}")
    conn.execute("UPDATE picking_tasks SET priority=? WHERE picking_task_id=?",
                 (int(p["new_priority"]), p["task_id"]))
    return {"task_id": p["task_id"], "new_priority": int(p["new_priority"])}


def _h_place_replenishment(conn, a: dict) -> dict:
    """결품 출고주문 → 부족분 발주(입고 생성) + 주문 AWAITING_STOCK."""
    from bb import backorder
    p = json.loads(a.get("payload_json") or "{}")
    order_no, shortage = p["order_no"], p.get("shortage") or []
    created = backorder.place_orders(conn, order_no, shortage)
    return {"order_no": order_no, "replenishment_inbounds": created, "status": backorder.AWAITING}


_HANDLERS = {
    "CREATE_PICKING_TASK": _h_create_picking,
    "CREATE_INBOUND_TASK": _h_create_inbound,
    "CREATE_PUTAWAY_TASK": _h_create_putaway,
    "CREATE_SHIPPING_TASK": _h_create_shipping,
    "ALLOCATE_TEAM": _h_allocate_team,
    "START_ZONE_WORK": _h_start_zone_work,
    "FINISH_ZONE_LEG": _h_finish_zone_leg,
    "REPRIORITIZE_PICKING_TASK": _h_reprioritize_picking,
    "PLACE_REPLENISHMENT_ORDER": _h_place_replenishment,
}


def _emit_followups(a: dict, result: dict) -> None:
    """실행 성공 후 다음 에이전트를 깨우는 체인 이벤트(블랙보드 data-driven 연쇄)."""
    at = a["action_type"]
    if at == "CREATE_INBOUND_TASK":
        events.add_event("NEED_PUTAWAY", "inbound", result.get("inbound_no"), source="chain")
    elif at == "CREATE_PUTAWAY_TASK":
        events.add_event("TASK_CREATED", "task", result.get("stocking_task_id"), {"kind": "stocking"}, source="chain")
    elif at == "CREATE_PICKING_TASK":
        events.add_event("TASK_CREATED", "task", result.get("picking_task_id"), {"kind": "picking"}, source="chain")
    elif at == "FINISH_ZONE_LEG" and result.get("finalized") and result.get("kind") == "picking":
        events.add_event("TASK_COMPLETED", "order", result.get("order_no"), source="chain")


def _postcheck(conn, a: dict, result: dict) -> dict:
    at = a["action_type"]
    if at == "CREATE_PICKING_TASK":
        if not conn.execute("SELECT 1 FROM picking_tasks WHERE picking_task_id=?", (result["picking_task_id"],)).fetchone():
            return {"ok": False, "reason": "피킹작업 생성 확인 실패"}
        st = conn.execute("SELECT status FROM outbound_orders WHERE order_no=?", (result["order_no"],)).fetchone()
        if not st or st["status"] != "PICKING_ISSUED":
            return {"ok": False, "reason": "주문 상태 미반영"}
        return {"ok": True}
    if at == "CREATE_INBOUND_TASK":
        st = conn.execute("SELECT status FROM inbound_orders WHERE inbound_no=?", (result["inbound_no"],)).fetchone()
        return {"ok": bool(st and st["status"] == "RECEIVED"), "reason": "입고상태 미반영"}
    if at == "CREATE_PUTAWAY_TASK":
        ok = conn.execute("SELECT 1 FROM stocking_tasks WHERE stocking_task_id=?", (result["stocking_task_id"],)).fetchone()
        return {"ok": bool(ok), "reason": "적치작업 확인 실패"}
    if at == "CREATE_SHIPPING_TASK":
        ok = conn.execute("SELECT 1 FROM shipping_pending WHERE order_no=? AND status='PENDING'", (result["order_no"],)).fetchone()
        return {"ok": bool(ok), "reason": "출고대기 확인 실패"}
    if at == "ALLOCATE_TEAM":
        tbl = "picking_tasks" if result.get("kind") == "picking" else "stocking_tasks"
        idcol = "picking_task_id" if result.get("kind") == "picking" else "stocking_task_id"
        w = conn.execute(f"SELECT worker_id, status FROM {tbl} WHERE {idcol}=?", (result["task_id"],)).fetchone()
        ok = bool(w and w["worker_id"] == result["worker_id"] and w["status"] == "TEAM_ASSIGNED")
        return {"ok": ok, "reason": "team 배정 확인 실패"}
    if at == "START_ZONE_WORK":
        tbl = "picking_tasks" if result.get("kind") == "picking" else "stocking_tasks"
        idcol = "picking_task_id" if result.get("kind") == "picking" else "stocking_task_id"
        w = conn.execute(f"SELECT status, started_at FROM {tbl} WHERE {idcol}=?", (result["task_id"],)).fetchone()
        return {"ok": bool(w and w["status"] == "IN_PROGRESS" and w["started_at"]), "reason": "zone 시작 확인 실패"}
    if at == "FINISH_ZONE_LEG":
        tbl = "picking_tasks" if result.get("kind") == "picking" else "stocking_tasks"
        idcol = "picking_task_id" if result.get("kind") == "picking" else "stocking_task_id"
        w = conn.execute(f"SELECT status FROM {tbl} WHERE {idcol}=?", (result["task_id"],)).fetchone()
        if not w:
            return {"ok": False, "reason": "작업 없음"}
        expect = "TEAM_ASSIGNED" if result.get("advanced") else ("STOCKED" if result.get("kind") != "picking" else "COMPLETED")
        return {"ok": w["status"] == expect, "reason": "완료 처리 확인 실패"}
    if at == "REPRIORITIZE_PICKING_TASK":
        pr = conn.execute("SELECT priority FROM picking_tasks WHERE picking_task_id=?", (result["task_id"],)).fetchone()
        return {"ok": bool(pr and pr["priority"] == result["new_priority"]), "reason": "우선순위 미반영"}
    if at == "PLACE_REPLENISHMENT_ORDER":
        st = conn.execute("SELECT status FROM outbound_orders WHERE order_no=?", (result["order_no"],)).fetchone()
        return {"ok": bool(st and st["status"] == "AWAITING_STOCK"), "reason": "발주 대기 상태 미반영"}
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
        _emit_followups(a, result)            # 다음 에이전트를 깨우는 체인 이벤트
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
