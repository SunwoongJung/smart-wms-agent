"""Inventory Risk Agent — 결품 위험 감지 → 알림성 Action(자동실행 금지).

재고 보정(ADJUST_INVENTORY)은 자동 실행하지 않으므로, 위험 시 INVENTORY_RISK_ALERT를 생성해
정책상 POLICY_BLOCKED로 남기고 운영자가 보게 한다.
"""
from bb import reservations
from tools.common import q

NAME = "InventoryRiskAgent"
EVENTS = {"NEW_OUTBOUND_ORDER", "INVENTORY_CHANGED"}


def handles(event_type: str) -> bool:
    return event_type in EVENTS


def propose(event: dict) -> list[dict]:
    if event["event_type"] != "NEW_OUTBOUND_ORDER":
        return []
    order_no = event.get("target_id")
    if not order_no:
        return []
    short = []
    for ln in q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,)):
        avail = reservations.available(ln["sku"])
        if avail < ln["qty"]:
            short.append(f"{ln['sku']}(부족 {ln['qty'] - avail})")
    if not short:
        return []
    return [dict(agent_name=NAME, action_type="INVENTORY_RISK_ALERT",
                 idempotency_key=f"INVENTORY_RISK_ALERT:{order_no}", event_id=event["event_id"],
                 target_type="order", target_id=order_no, payload={"order_no": order_no, "shortage": short},
                 auto_executable=False, risk_score=0.9,
                 reason=f"출고 {order_no} 결품 위험: {', '.join(short)} — 자동실행 보류")]
