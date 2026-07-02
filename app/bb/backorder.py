"""재고 부족 발주(백오더) 흐름 — 출고 결품 시 부족분만큼 입고 발주를 넣고 주문을 대기시킨다.

· 발주: inbound_orders에 replenish_for=출고주문 으로 생성, 도착예정일=오늘+리드타임(실제 일).
· 대기: 해당 출고주문 status=AWAITING_STOCK.
· 재개: 재고가 채워지면(실제 도착 또는 '바로 보충') AWAITING_STOCK 주문을 PLANNED로 되돌리고
        NEW_OUTBOUND_ORDER를 재발행해 피킹을 다시 태운다.
"""
import uuid
from datetime import date, datetime, timedelta

from db.database import get_connection
from tools.common import q

from bb import events, reservations
from bb.store import now

AWAITING = "AWAITING_STOCK"


def lead_time_days(sku: str) -> int:
    r = q("SELECT lead_time_days FROM products WHERE sku=?", (sku,))
    return int(r[0]["lead_time_days"]) if r and r[0]["lead_time_days"] is not None else 3


def place_orders(conn, order_no: str, shortage: list[dict]) -> list[dict]:
    """부족 SKU마다 입고 발주 생성 + 출고주문을 AWAITING_STOCK으로. (executor 트랜잭션 내 호출)"""
    created = []
    today = date.today()
    for s in shortage:
        sku, qty = s["sku"], int(s["qty"])
        if qty <= 0:
            continue
        lt = lead_time_days(sku)
        inbound_no = "RT-R-" + uuid.uuid4().hex[:8]
        exp = (today + timedelta(days=lt)).isoformat()
        conn.execute("""INSERT INTO inbound_orders(inbound_no,sku,qty,expected_date,status,supplier,replenish_for)
                        VALUES(?,?,?,?,?,?,?)""",
                     (inbound_no, sku, qty, exp, "PLANNED", "REPL", order_no))
        created.append({"inbound_no": inbound_no, "sku": sku, "qty": qty,
                        "lead_time_days": lt, "expected_date": exp})
    conn.execute("UPDATE outbound_orders SET status=? WHERE order_no=?", (AWAITING, order_no))
    return created


def _pick_location(sku: str) -> str | None:
    """가상 보충 시 재고를 넣을 위치 — 동일 SKU 기존 위치 우선, 없으면 임의 위치."""
    r = q("SELECT location_id FROM inventory WHERE sku=? ORDER BY inventory_id LIMIT 1", (sku,))
    if r:
        return r[0]["location_id"]
    r = q("SELECT location_id FROM locations ORDER BY location_id LIMIT 1")
    return r[0]["location_id"] if r else None


def awaiting_orders() -> list[dict]:
    """발주 대기(AWAITING_STOCK) 출고주문 + 발주분(입고예정) 상세 — 자동발주 배지 숫자의 근거."""
    out = []
    for o in q("""SELECT order_no, created_at FROM outbound_orders WHERE status=?
                  ORDER BY created_at DESC, rowid DESC""", (AWAITING,)):
        lines = q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (o["order_no"],))
        inbs = q("""SELECT inbound_no, sku, qty, expected_date, status FROM inbound_orders
                    WHERE replenish_for=? ORDER BY expected_date""", (o["order_no"],))
        out.append({"order_no": o["order_no"], "created_at": o["created_at"],
                    "lines": lines, "replenishments": inbs})
    return out


def resume_fillable() -> list[str]:
    """이제 충족 가능한 AWAITING_STOCK 출고주문을 PLANNED로 되돌리고 피킹 재트리거."""
    resumed = []
    conn = get_connection()
    try:
        orders = conn.execute("SELECT order_no FROM outbound_orders WHERE status=?", (AWAITING,)).fetchall()
        for o in orders:
            lines = conn.execute("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?",
                                 (o["order_no"],)).fetchall()
            if lines and all(reservations.available(ln["sku"]) >= ln["qty"] for ln in lines):
                conn.execute("UPDATE outbound_orders SET status='PLANNED' WHERE order_no=?", (o["order_no"],))
                resumed.append(o["order_no"])
        conn.commit()
    finally:
        conn.close()
    for order_no in resumed:
        events.add_event("NEW_OUTBOUND_ORDER", "order", order_no, source="backorder-resume")
    return resumed


def arrive_due_replenishments() -> list[str]:
    """도착예정일이 된 발주분(REPL, PLANNED)을 입고 도착 이벤트로 흘려보낸다(실제 리드타임 경과)."""
    today = date.today().isoformat()
    due = q("""SELECT inbound_no FROM inbound_orders
               WHERE supplier='REPL' AND status='PLANNED' AND expected_date<=?
                 AND inbound_no NOT IN (SELECT target_id FROM blackboard_events
                                        WHERE event_type='NEW_INBOUND_ARRIVAL')""", (today,))
    for r in due:
        events.add_event("NEW_INBOUND_ARRIVAL", "inbound", r["inbound_no"], source="replenish-arrival")
    return [r["inbound_no"] for r in due]


def replenish_now(order_no: str) -> dict:
    """'바로 보충' — 이 주문의 발주분을 가상으로 즉시 입고·적치 완료 처리(실제 재고 반영) 후 주문 재개."""
    inbs = q("""SELECT inbound_no, sku, qty FROM inbound_orders
                WHERE replenish_for=? AND status!='STOCKED'""", (order_no,))
    stocked = []
    conn = get_connection()
    try:
        for ib in inbs:
            loc = _pick_location(ib["sku"])
            if loc:
                conn.execute("""INSERT INTO inventory(sku,lot_no,location_id,qty,inbound_date,expiry_date,status)
                                VALUES(?,?,?,?,?,NULL,'AVAILABLE')""",
                             (ib["sku"], f"REPL-{ib['inbound_no']}", loc, ib["qty"], now()[:10]))
                conn.execute("UPDATE locations SET occupied_qty=occupied_qty+? WHERE location_id=?",
                             (ib["qty"], loc))
            conn.execute("""UPDATE inbound_orders SET status='STOCKED', received_datetime=?
                            WHERE inbound_no=?""", (now(), ib["inbound_no"]))
            stocked.append({"inbound_no": ib["inbound_no"], "sku": ib["sku"], "qty": ib["qty"], "location_id": loc})
        conn.commit()
    finally:
        conn.close()
    for s in stocked:
        events.add_event("INVENTORY_CHANGED", "sku", s["sku"], {"qty": s["qty"]}, source="replenish-now")
    resumed = resume_fillable()
    return {"order_no": order_no, "stocked": stocked, "resumed": resumed}
