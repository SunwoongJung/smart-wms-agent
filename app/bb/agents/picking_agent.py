"""Picking Agent — 출고 이벤트를 보고 CREATE_PICKING_TASK / REPRIORITIZE_PICKING_TASK를 제안.

빌드 6~8: NEW_OUTBOUND_ORDER → CREATE_PICKING_TASK(예약 포함, executor가 실행).
가용/우선순위 판단은 기존 tools(allocation·picking)를 재사용한다.
"""
from bb import reservations
from tools.common import q

NAME = "PickingAgent"
EVENTS = {"NEW_OUTBOUND_ORDER", "SHIPMENT_DUE_SOON", "PICKING_DELAYED"}


def handles(event_type: str) -> bool:
    return event_type in EVENTS


def propose(event: dict) -> list[dict]:
    if event["event_type"] != "NEW_OUTBOUND_ORDER":
        return []
    order_no = event.get("target_id")
    if not order_no:
        return []
    lines = q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,))
    if not lines:
        return []
    # 가용재고 부족분이 있으면 피킹을 제안하지 않는다(AutoOrderAgent가 발주·대기 처리).
    if any(reservations.available(ln["sku"]) < ln["qty"] for ln in lines):
        return []
    skus = list(dict.fromkeys(l["sku"] for l in lines))
    o = q("SELECT customer_priority, due_datetime FROM outbound_orders WHERE order_no=?", (order_no,))
    pri = (o[0]["customer_priority"] if o else 3)
    return [dict(
        agent_name=NAME, action_type="CREATE_PICKING_TASK",
        idempotency_key=f"CREATE_PICKING_TASK:{order_no}",
        event_id=event["event_id"], target_type="order", target_id=order_no,
        payload={"order_no": order_no, "skus": skus},
        priority_score=float(100 - pri * 10), auto_executable=True,
        reason=f"신규 출고주문 {order_no}(SKU {','.join(skus)}) 피킹작업 자동 생성",
    )]
