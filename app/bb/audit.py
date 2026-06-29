"""blackboard_audit_logs — 자동 실행 감사 추적(단계별 before/after/결과)."""
import json
import uuid

from db.database import get_connection
from tools.common import q

from bb.store import ensure_schema, now


def log(phase: str, result: str = "OK", *, action_id=None, event_id=None, agent_name=None,
        action_type=None, before=None, after=None, message=None) -> None:
    ensure_schema()
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO blackboard_audit_logs(log_id,action_id,event_id,agent_name,action_type,phase,
            before_state_json,after_state_json,message,result,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                     ("L-" + uuid.uuid4().hex[:10], action_id, event_id, agent_name, action_type, phase,
                      json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
                      json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
                      message, result, now()))
        conn.commit()
    finally:
        conn.close()


def list_logs(action_id=None, event_id=None, phase=None, result=None, limit: int = 300):
    ensure_schema()
    where, params = [], []
    for col, val in (("action_id", action_id), ("event_id", event_id), ("phase", phase), ("result", result)):
        if val:
            where.append(f"{col}=?"); params.append(val)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return q(f"SELECT * FROM blackboard_audit_logs{clause} ORDER BY created_at DESC, rowid DESC LIMIT ?",
             tuple(params + [limit]))
