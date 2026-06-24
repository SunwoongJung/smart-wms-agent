"""실시간 수요 발생 시뮬레이션 (docs/07 확장).

가상 패턴으로 입고/출고 요청을 주기적으로 생성한다. 생성 즉시 DB에 저장하므로
조회 Tool을 쓰는 LLM이 그 시점에 바로 인지할 수 있고, 동시에 SSE로 SPA에 Toast 이벤트를
푸시한다('저장 → 알림' 순서로 조회 일관성 보장).
"""
import asyncio
import random
from datetime import datetime, timedelta

from db.database import get_connection
from tools.common import q

_subscribers: set[asyncio.Queue] = set()
_state = {"running": False, "interval": 8, "count": 0}
_task: asyncio.Task | None = None
_seq = 0


def subscribe() -> asyncio.Queue:
    qe: asyncio.Queue = asyncio.Queue()
    _subscribers.add(qe)
    return qe


def unsubscribe(qe: asyncio.Queue) -> None:
    _subscribers.discard(qe)


async def _broadcast(event: dict) -> None:
    for qe in list(_subscribers):
        await qe.put(event)


def _normal_skus() -> list[str]:
    return [r["sku"] for r in q("SELECT sku FROM products WHERE storage_type='NORMAL' LIMIT 80")]


def generate_event() -> dict:
    """가상 입고/출고 1건을 생성·DB 저장하고 이벤트 dict를 반환(동기 DB)."""
    global _seq
    _seq += 1
    now = datetime.now()
    skus = _normal_skus()
    sku = random.choice(skus) if skus else "SKU_A001"
    conn = get_connection()
    try:
        if random.random() < 0.5:
            order_no = f"RT-O-{now.strftime('%H%M%S')}{_seq:02d}"
            due = now + timedelta(hours=random.randint(2, 8))
            qty = random.randint(5, 40)
            conn.execute("INSERT INTO outbound_orders(order_no,customer_id,customer_priority,due_datetime,status)"
                         " VALUES(?,?,?,?,?)",
                         (order_no, f"C{random.randint(1, 30):02d}", random.randint(1, 5),
                          due.strftime("%Y-%m-%d %H:%M"), "PLANNED"))
            conn.execute("INSERT INTO outbound_order_lines(order_no,sku,qty,line_status) VALUES(?,?,?,'PLANNED')",
                         (order_no, sku, qty))
            conn.commit()
            ev = {"kind": "outbound", "id": order_no, "sku": sku, "qty": qty,
                  "ts": now.strftime("%H:%M:%S"),
                  "message": f"신규 출고 요청 {order_no} · {sku} {qty}개 (납기 {due.strftime('%m-%d %H:%M')})"}
        else:
            inbound_no = f"RT-I-{now.strftime('%H%M%S')}{_seq:02d}"
            exp = (now + timedelta(days=random.randint(0, 2))).date().isoformat()
            qty = random.randint(20, 120)
            conn.execute("INSERT INTO inbound_orders(inbound_no,sku,qty,expected_date,status,supplier)"
                         " VALUES(?,?,?,?,?,?)",
                         (inbound_no, sku, qty, exp, "PLANNED", f"SUP{random.randint(1, 5):02d}"))
            conn.commit()
            ev = {"kind": "inbound", "id": inbound_no, "sku": sku, "qty": qty,
                  "ts": now.strftime("%H:%M:%S"),
                  "message": f"신규 입고 요청 {inbound_no} · {sku} {qty}개 (예정 {exp})"}
    finally:
        conn.close()
    _state["count"] += 1
    return ev


async def emit_once() -> dict:
    ev = generate_event()
    await _broadcast(ev)
    return ev


async def _loop() -> None:
    while _state["running"]:
        try:
            await _broadcast(generate_event())
        except Exception as e:  # noqa: BLE001
            await _broadcast({"kind": "error", "message": str(e)})
        await asyncio.sleep(_state["interval"])


def start(interval: int | None = None) -> dict:
    global _task
    if interval:
        _state["interval"] = max(2, int(interval))
    if not _state["running"]:
        _state["running"] = True
        _task = asyncio.create_task(_loop())
    return status()


def stop() -> dict:
    _state["running"] = False
    return status()


def status() -> dict:
    return {**_state, "subscribers": len(_subscribers)}
