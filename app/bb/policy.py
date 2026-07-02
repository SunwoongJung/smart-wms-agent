"""Policy Checker — Action Type별 자동실행 가부 + 필요한 lock 키 산출.

위험 Action은 자동실행 금지(POLICY_BLOCKED). 업무 상태 검증(가용수량 등)은 Pre-check(executor)가 담당.
"""
import json

AUTO_ALLOWED = {
    "CREATE_INBOUND_TASK", "CREATE_PUTAWAY_TASK", "CREATE_PICKING_TASK",
    "REPRIORITIZE_PICKING_TASK", "CREATE_SHIPPING_TASK",
    "ALLOCATE_TEAM", "START_ZONE_WORK", "FINISH_ZONE_LEG",
    "PLACE_REPLENISHMENT_ORDER",
}
AUTO_BLOCKED = {
    "ADJUST_INVENTORY", "CANCEL_ORDER", "CANCEL_SHIPMENT", "CONFIRM_SHIPPING_COMPLETE",
    "CONFIRM_INVENTORY_ADJUSTMENT", "SEND_FINAL_CONFIRMATION_TO_EXTERNAL_SYSTEM",
}


def lock_keys(action: dict) -> list[str]:
    at = action["action_type"]
    p = json.loads(action.get("payload_json") or "{}")
    if at == "CREATE_PICKING_TASK":
        keys = [f"order:{p.get('order_no')}"] + [f"sku:{s}" for s in p.get("skus", [])]
    elif at == "CREATE_PUTAWAY_TASK":
        keys = [f"sku:{p.get('sku')}", f"location:{p.get('location_id')}"]
    elif at == "CREATE_INBOUND_TASK":
        keys = [f"inbound:{p.get('inbound_no')}"]
    elif at == "CREATE_SHIPPING_TASK":
        keys = [f"order:{p.get('order_no')}"]
    elif at == "PLACE_REPLENISHMENT_ORDER":
        keys = [f"order:{p.get('order_no')}"]
    elif at == "REPRIORITIZE_PICKING_TASK":
        keys = [f"task:{p.get('task_id')}"]
    elif at == "ALLOCATE_TEAM":
        keys = [f"task:{p.get('task_id')}"]
    elif at in ("START_ZONE_WORK", "FINISH_ZONE_LEG"):
        keys = [f"task:{p.get('task_id')}", f"zone:{p.get('zone_id')}"]
    else:
        keys = []
    return [k for k in keys if not k.endswith(":None")]


def check(action: dict, risk_threshold: float) -> dict:
    at = action["action_type"]
    if at in AUTO_BLOCKED:
        return {"auto": False, "status": "POLICY_BLOCKED", "reason": "위험 Action — 자동실행 금지", "lock_keys": []}
    if at not in AUTO_ALLOWED:
        return {"auto": False, "status": "POLICY_BLOCKED", "reason": f"미허용 Action: {at}", "lock_keys": []}
    risk = float(action.get("risk_score") or 0)
    if risk > risk_threshold:
        return {"auto": False, "status": "POLICY_BLOCKED",
                "reason": f"risk_score {risk} > 임계 {risk_threshold}", "lock_keys": []}
    return {"auto": True, "status": "READY", "reason": "자동실행 허용", "lock_keys": lock_keys(action)}
