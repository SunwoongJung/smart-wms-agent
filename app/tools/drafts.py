"""Draft / Approval / 실행 Tool (docs/06 §8). 상태변경은 승인 후에만 수행.

흐름: create_*_draft → dry_run_action → approve_action → issue_*/confirm_shipping
"""
import json
import uuid
from datetime import datetime

from db.database import get_connection
from tools.common import q
from tools.picking import calculate_picking_required_time

_NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731


def _draft_id(prefix: str) -> str:
    return f"DRF-{prefix}-{uuid.uuid4().hex[:6]}"


def _get_draft(draft_id: str) -> dict | None:
    r = q("SELECT * FROM action_drafts WHERE draft_id=?", (draft_id,))
    return r[0] if r else None


# ---------- Draft 생성 ----------
def create_stocking_task_draft(inbound_no: str, location_id: str) -> dict:
    inb = q("SELECT sku, qty FROM inbound_orders WHERE inbound_no=?", (inbound_no,))
    if not inb:
        return {"error": "입고번호 없음"}
    payload = {"inbound_no": inbound_no, "location_id": location_id,
               "sku": inb[0]["sku"], "qty": inb[0]["qty"]}
    did = _draft_id("STK")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO action_drafts(draft_id,action_type,target_id,payload_json,status)"
                     " VALUES(?,?,?,?,?)",
                     (did, "STOCKING", inbound_no, json.dumps(payload, ensure_ascii=False), "PENDING_APPROVAL"))
        conn.commit()
    finally:
        conn.close()
    return {"draft_id": did, "status": "PENDING_APPROVAL"}


def create_picking_instruction_draft(order_no: str) -> dict:
    if not q("SELECT 1 FROM outbound_orders WHERE order_no=?", (order_no,)):
        return {"error": "주문번호 없음"}
    payload = {"order_no": order_no}
    did = _draft_id("PCK")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO action_drafts(draft_id,action_type,target_id,payload_json,status)"
                     " VALUES(?,?,?,?,?)",
                     (did, "PICKING", order_no, json.dumps(payload, ensure_ascii=False), "PENDING_APPROVAL"))
        conn.commit()
    finally:
        conn.close()
    return {"draft_id": did, "status": "PENDING_APPROVAL"}


def create_shipping_confirm_draft(order_no: str) -> dict:
    if not q("SELECT 1 FROM outbound_orders WHERE order_no=?", (order_no,)):
        return {"error": "주문번호 없음"}
    payload = {"order_no": order_no}
    did = _draft_id("SHP")
    conn = get_connection()
    try:
        conn.execute("INSERT INTO action_drafts(draft_id,action_type,target_id,payload_json,status)"
                     " VALUES(?,?,?,?,?)",
                     (did, "SHIPPING", order_no, json.dumps(payload, ensure_ascii=False), "PENDING_APPROVAL"))
        conn.commit()
    finally:
        conn.close()
    dry = dry_run_action(did)  # 생성 시 Dry Run 자동 수행
    return {"draft_id": did, "dry_run": dry, "status": "PENDING_APPROVAL"}


# ---------- Dry Run ----------
def dry_run_action(draft_id: str) -> dict:
    d = _get_draft(draft_id)
    if not d:
        return {"error": "draft 없음"}
    payload = json.loads(d["payload_json"])
    changes: list[dict] = []
    warnings: list[str] = []

    if d["action_type"] == "STOCKING":
        loc = q("SELECT capacity, occupied_qty FROM locations WHERE location_id=?", (payload["location_id"],))
        inb = q("SELECT status FROM inbound_orders WHERE inbound_no=?", (payload["inbound_no"],))
        changes.append({"table": "inbound_orders", "field": "status",
                        "before": inb[0]["status"] if inb else None, "after": "STOCKING_TASK_CREATED"})
        changes.append({"table": "stocking_tasks", "field": "신규", "after": payload["location_id"]})
        if loc and (loc[0]["capacity"] - loc[0]["occupied_qty"]) < payload["qty"]:
            warnings.append("잔여용량 부족 — CAPA 확인 필요")

    elif d["action_type"] == "PICKING":
        o = q("SELECT status FROM outbound_orders WHERE order_no=?", (payload["order_no"],))
        ct = calculate_picking_required_time(payload["order_no"])
        changes.append({"table": "outbound_orders", "field": "status",
                        "before": o[0]["status"] if o else None, "after": "PICKING_ISSUED"})
        changes.append({"table": "picking_tasks", "field": "estimated_minutes", "after": ct["estimated_minutes"]})

    elif d["action_type"] == "SHIPPING":
        o = q("SELECT status FROM outbound_orders WHERE order_no=?", (payload["order_no"],))
        changes.append({"table": "outbound_orders", "field": "status",
                        "before": o[0]["status"] if o else None, "after": "SHIPPED"})
        for ln in q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (payload["order_no"],)):
            stock = q("SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE sku=?", (ln["sku"],))[0]["s"]
            changes.append({"table": "inventory", "sku": ln["sku"], "qty_change": -ln["qty"]})
            if stock < ln["qty"]:
                warnings.append(f"{ln['sku']} 재고 부족(보유 {stock} < 출고 {ln['qty']})")

    result = {"changes": changes, "warnings": warnings}
    conn = get_connection()
    try:
        conn.execute("UPDATE action_drafts SET dry_run_result_json=? WHERE draft_id=?",
                     (json.dumps(result, ensure_ascii=False), draft_id))
        conn.commit()
    finally:
        conn.close()
    return result


# ---------- 승인 + 실행 ----------
def approve_action(draft_id: str, approved: bool, user_id: str) -> dict:
    d = _get_draft(draft_id)
    if not d:
        return {"error": "draft 없음"}
    if d["status"] != "PENDING_APPROVAL":
        return {"error": f"승인 불가 상태: {d['status']}"}
    conn = get_connection()
    try:
        if not approved:
            conn.execute("UPDATE action_drafts SET status='REJECTED' WHERE draft_id=?", (draft_id,))
            conn.commit()
            return {"status": "REJECTED", "executed_action": None}
        conn.execute("UPDATE action_drafts SET status='APPROVED', approved_at=? WHERE draft_id=?",
                     (_NOW(), draft_id))
        conn.commit()
    finally:
        conn.close()

    dispatch = {"STOCKING": issue_stocking_task, "PICKING": issue_picking_instruction,
                "SHIPPING": confirm_shipping}
    executed = dispatch[d["action_type"]](draft_id)

    conn = get_connection()
    try:
        conn.execute("UPDATE action_drafts SET status='EXECUTED', executed_at=? WHERE draft_id=?",
                     (_NOW(), draft_id))
        conn.commit()
    finally:
        conn.close()
    return {"status": "EXECUTED", "executed_action": executed}


# ---------- 실행 Tool (승인된 Draft만 호출됨) ----------
def issue_stocking_task(draft_id: str) -> dict:
    d = _get_draft(draft_id)
    payload = json.loads(d["payload_json"])
    task_id = f"STK-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    try:
        conn.execute("INSERT INTO stocking_tasks(stocking_task_id,inbound_no,location_id,qty,status,draft_id)"
                     " VALUES(?,?,?,?,?,?)",
                     (task_id, payload["inbound_no"], payload["location_id"], payload["qty"], "ISSUED", draft_id))
        conn.execute("UPDATE inbound_orders SET status='STOCKING_TASK_CREATED' WHERE inbound_no=?",
                     (payload["inbound_no"],))
        conn.commit()
    finally:
        conn.close()
    return {"stocking_task_id": task_id, "inbound_status": "STOCKING_TASK_CREATED"}


def issue_picking_instruction(draft_id: str) -> dict:
    d = _get_draft(draft_id)
    payload = json.loads(d["payload_json"])
    ct = calculate_picking_required_time(payload["order_no"])
    task_id = f"PCK-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    try:
        conn.execute("INSERT INTO picking_tasks(picking_task_id,order_no,estimated_minutes,status,draft_id)"
                     " VALUES(?,?,?,?,?)",
                     (task_id, payload["order_no"], ct["estimated_minutes"], "ISSUED", draft_id))
        conn.execute("UPDATE outbound_orders SET status='PICKING_ISSUED' WHERE order_no=?",
                     (payload["order_no"],))
        conn.commit()
    finally:
        conn.close()
    return {"picking_task_id": task_id, "order_status": "PICKING_ISSUED"}


def confirm_shipping(draft_id: str) -> dict:
    d = _get_draft(draft_id)
    payload = json.loads(d["payload_json"])
    order_no = payload["order_no"]
    changes = []
    conn = get_connection()
    try:
        for ln in conn.execute("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,)).fetchall():
            remaining = ln["qty"]
            lots = conn.execute("SELECT inventory_id, location_id, qty FROM inventory "
                                "WHERE sku=? AND qty>0 ORDER BY inventory_id", (ln["sku"],)).fetchall()
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(remaining, lot["qty"])
                conn.execute("UPDATE inventory SET qty=qty-? WHERE inventory_id=?", (take, lot["inventory_id"]))
                conn.execute("UPDATE locations SET occupied_qty=occupied_qty-? WHERE location_id=?",
                             (take, lot["location_id"]))
                remaining -= take
            changes.append({"sku": ln["sku"], "qty_change": -(ln["qty"] - max(remaining, 0)),
                            "shortfall": remaining if remaining > 0 else 0})
        conn.execute("UPDATE outbound_orders SET status='SHIPPED' WHERE order_no=?", (order_no,))
        conn.execute("UPDATE shipping_pending SET status='CONFIRMED', confirmed_at=? WHERE order_no=?",
                     (_NOW(), order_no))
        conn.commit()
    finally:
        conn.close()
    return {"order_status": "SHIPPED", "inventory_changes": changes}
