"""inventory_reservations — 예약재고 단일 출처 + 가용수량 통일 계산.

가용 = on_hand(AVAILABLE 재고) - reserved(예약).  (HOLD/QC/DAMAGED는 AVAILABLE이 아니므로 이미 제외)
이 모듈의 available()/reserved_map()을 allocation·forecast 등 가용 판단이 필요한 모든 곳이 사용한다.
"""
import uuid

from db.database import get_connection
from tools.common import q

from bb.store import ensure_schema, now


def on_hand(sku: str) -> int:
    return q("SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE sku=? AND status='AVAILABLE'", (sku,))[0]["s"]


def blocked(sku: str) -> int:
    return q("SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE sku=? AND status IN ('HOLD','QC','DAMAGED')", (sku,))[0]["s"]


def reserved(sku: str) -> int:
    ensure_schema()
    return q("SELECT COALESCE(SUM(qty),0) s FROM inventory_reservations WHERE sku=? AND status='RESERVED'", (sku,))[0]["s"]


def available(sku: str) -> int:
    return on_hand(sku) - reserved(sku)


def reserved_map(skus) -> dict:
    """SKU별 예약합(가용 계산 시 한 번에 빼기 위함)."""
    ensure_schema()
    skus = list(dict.fromkeys(skus))
    if not skus:
        return {}
    marks = ",".join("?" for _ in skus)
    rows = q(f"""SELECT sku, COALESCE(SUM(qty),0) s FROM inventory_reservations
                 WHERE status='RESERVED' AND sku IN ({marks}) GROUP BY sku""", tuple(skus))
    d = {r["sku"]: r["s"] for r in rows}
    return {s: d.get(s, 0) for s in skus}


def reserve(sku: str, qty: int, *, order_no=None, task_id=None, action_id=None) -> str:
    ensure_schema()
    rid = "RV-" + uuid.uuid4().hex[:8]
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO inventory_reservations(reservation_id,sku,order_no,task_id,qty,status,
            created_by_action_id,created_at) VALUES(?,?,?,?,?, 'RESERVED', ?, ?)""",
                     (rid, sku, order_no, task_id, int(qty), action_id, now()))
        conn.commit()
    finally:
        conn.close()
    return rid


def set_status(reservation_id: str, status: str) -> None:
    """RESERVED → CONSUMED(피킹/출고 확정) | RELEASED/CANCELLED(실패·취소)."""
    ensure_schema()
    released = now() if status in ("RELEASED", "CANCELLED", "CONSUMED") else None
    conn = get_connection()
    try:
        conn.execute("UPDATE inventory_reservations SET status=?, released_at=? WHERE reservation_id=?",
                     (status, released, reservation_id))
        conn.commit()
    finally:
        conn.close()


def release_by_order(order_no: str, status: str = "RELEASED") -> int:
    ensure_schema()
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE inventory_reservations SET status=?, released_at=? "
                           "WHERE order_no=? AND status='RESERVED'", (status, now(), order_no))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
