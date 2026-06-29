"""blackboard_events 저장소 — 실시간/준실시간 이벤트 적재·조회·상태전이."""
import json
import uuid

from db.database import get_connection
from tools.common import q

from bb.store import ensure_schema, now

# 자동 생산되는 이벤트(realtime) + 수동/연쇄 이벤트
EVENT_TYPES = (
    "NEW_INBOUND_ARRIVAL", "NEW_OUTBOUND_ORDER", "INVENTORY_CHANGED", "PICKING_DELAYED",
    "TASK_COMPLETED", "TASK_CREATED", "ZONE_CAPACITY_CHANGED", "WORKER_AVAILABLE",
    "WORKER_UNAVAILABLE", "SHIPMENT_DUE_SOON", "MANUAL_TRIGGER",
)
_SEV_ORDER = "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END"


def add_event(event_type: str, target_type=None, target_id=None, payload=None,
              severity: str = "normal", source: str = "system") -> str:
    ensure_schema()
    eid = "E-" + uuid.uuid4().hex[:10]
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO blackboard_events(event_id,event_type,target_type,target_id,payload_json,
            severity,source,status,created_at) VALUES(?,?,?,?,?,?,?, 'NEW', ?)""",
                     (eid, event_type, target_type, target_id,
                      json.dumps(payload or {}, ensure_ascii=False), severity, source, now()))
        conn.commit()
    finally:
        conn.close()
    return eid


def list_events(status=None, event_type=None, target_id=None, limit: int = 100):
    ensure_schema()
    where, params = [], []
    if status:
        where.append("status=?"); params.append(status)
    if event_type:
        where.append("event_type=?"); params.append(event_type)
    if target_id:
        where.append("target_id=?"); params.append(target_id)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return q(f"SELECT * FROM blackboard_events{clause} ORDER BY created_at DESC, rowid DESC LIMIT ?",
             tuple(params + [limit]))


def new_events(limit: int = 100):
    """미처리(NEW) 이벤트를 severity 우선·시간순으로."""
    ensure_schema()
    return q(f"""SELECT * FROM blackboard_events WHERE status='NEW'
                 ORDER BY {_SEV_ORDER}, created_at ASC LIMIT ?""", (limit,))


def set_status(event_id: str, status: str, error: str | None = None) -> None:
    ensure_schema()
    processed = now() if status in ("PROCESSED", "FAILED", "IGNORED") else None
    conn = get_connection()
    try:
        conn.execute("UPDATE blackboard_events SET status=?, processed_at=?, error_message=? WHERE event_id=?",
                     (status, processed, error, event_id))
        conn.commit()
    finally:
        conn.close()
