"""Inbound Agent — NEW_INBOUND_ARRIVAL → CREATE_INBOUND_TASK(입고 처리=RECEIVED)."""
from tools.common import q

NAME = "InboundAgent"
EVENTS = {"NEW_INBOUND_ARRIVAL"}


def handles(event_type: str) -> bool:
    return event_type in EVENTS


def propose(event: dict) -> list[dict]:
    inb = event.get("target_id")
    if not inb:
        return []
    o = q("SELECT sku, qty, status FROM inbound_orders WHERE inbound_no=?", (inb,))
    if not o or o[0]["status"] != "PLANNED":
        return []
    return [dict(agent_name=NAME, action_type="CREATE_INBOUND_TASK",
                 idempotency_key=f"CREATE_INBOUND_TASK:{inb}", event_id=event["event_id"],
                 target_type="inbound", target_id=inb, payload={"inbound_no": inb},
                 priority_score=50.0, auto_executable=True,
                 reason=f"입고 도착 {inb}(SKU {o[0]['sku']} {o[0]['qty']}개) 입고작업 자동 생성")]
