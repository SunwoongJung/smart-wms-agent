"""Outbound Agent — 출고 임박/피킹 완료 처리.

SHIPMENT_DUE_SOON(order) → REPRIORITIZE_PICKING_TASK(우선순위 상향).
TASK_COMPLETED(order) → CREATE_SHIPPING_TASK(출고준비). 출고 '확정'은 자동 실행하지 않는다.
"""
from tools.common import q

NAME = "OutboundAgent"
EVENTS = {"SHIPMENT_DUE_SOON", "TASK_COMPLETED"}


def handles(event_type: str) -> bool:
    return event_type in EVENTS


def propose(event: dict) -> list[dict]:
    et, tgt = event["event_type"], event.get("target_id")
    if not tgt:
        return []
    if et == "SHIPMENT_DUE_SOON":
        pt = q("SELECT picking_task_id FROM picking_tasks WHERE order_no=? AND status='ISSUED' "
               "ORDER BY issued_at DESC LIMIT 1", (tgt,))
        if not pt:
            return []
        task_id = pt[0]["picking_task_id"]
        return [dict(agent_name=NAME, action_type="REPRIORITIZE_PICKING_TASK",
                     idempotency_key=f"REPRIORITIZE_PICKING_TASK:{task_id}:99", event_id=event["event_id"],
                     target_type="task", target_id=task_id,
                     payload={"task_id": task_id, "new_priority": 99},
                     priority_score=60.0, auto_executable=True,
                     reason=f"출고 임박 {tgt} — 피킹 우선순위 상향")]
    if et == "TASK_COMPLETED":
        o = q("SELECT status FROM outbound_orders WHERE order_no=?", (tgt,))
        if not o or o[0]["status"] != "PICKING_ISSUED":
            return []
        return [dict(agent_name=NAME, action_type="CREATE_SHIPPING_TASK",
                     idempotency_key=f"CREATE_SHIPPING_TASK:{tgt}", event_id=event["event_id"],
                     target_type="order", target_id=tgt, payload={"order_no": tgt},
                     priority_score=55.0, auto_executable=True,
                     reason=f"피킹 완료 {tgt} — 출고준비 자동 생성")]
    return []
