"""blackboard_actions 저장소 — Action 생성(idempotency 강제)·조회·상태전이."""
import json
import sqlite3
import uuid

from db.database import get_connection
from tools.common import q

from bb.store import ensure_schema, now

# 같은 idempotency_key로 아래 상태가 이미 있으면 신규 생성 안 함(중복 방지)
_ACTIVE = ("PENDING", "READY", "RUNNING", "SUCCESS")


def create(agent_name: str, action_type: str, idempotency_key: str, *, event_id=None,
           target_type=None, target_id=None, payload=None, priority_score: float = 0.0,
           risk_score: float = 0.0, auto_executable: bool = False, reason=None) -> dict:
    """Action 생성. 동일 idempotency_key의 활성/성공 Action이 있으면 SKIPPED_DUPLICATE."""
    ensure_schema()
    marks = ",".join("?" for _ in _ACTIVE)
    dup = q(f"SELECT action_id, status FROM blackboard_actions WHERE idempotency_key=? AND status IN ({marks})",
            (idempotency_key, *_ACTIVE))
    if dup:
        return {"action_id": dup[0]["action_id"], "status": "SKIPPED_DUPLICATE", "duplicate_of": dup[0]["action_id"]}
    aid = "A-" + uuid.uuid4().hex[:10]
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO blackboard_actions(action_id,event_id,agent_name,action_type,target_type,
            target_id,payload_json,priority_score,risk_score,idempotency_key,status,auto_executable,reason,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (aid, event_id, agent_name, action_type, target_type, target_id,
                      json.dumps(payload or {}, ensure_ascii=False), priority_score, risk_score,
                      idempotency_key, "PENDING", 1 if auto_executable else 0, reason, now()))
        conn.commit()
    except sqlite3.IntegrityError:        # UNIQUE 경합 = 동시 중복
        conn.close()
        return {"action_id": None, "status": "SKIPPED_DUPLICATE"}
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"action_id": aid, "status": "PENDING"}


def get(action_id: str):
    ensure_schema()
    r = q("SELECT * FROM blackboard_actions WHERE action_id=?", (action_id,))
    return r[0] if r else None


def list_actions(status=None, action_type=None, target_id=None, agent_name=None, limit: int = 200):
    ensure_schema()
    where, params = [], []
    for col, val in (("status", status), ("action_type", action_type),
                     ("target_id", target_id), ("agent_name", agent_name)):
        if val:
            where.append(f"{col}=?"); params.append(val)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return q(f"SELECT * FROM blackboard_actions{clause} ORDER BY created_at DESC, rowid DESC LIMIT ?",
             tuple(params + [limit]))


def update(action_id: str, **fields) -> None:
    """허용 컬럼만 갱신(status, started_at, finished_at, *_result_json, reason, error_message, risk_score 등)."""
    if not fields:
        return
    ensure_schema()
    sets = ", ".join(f"{k}=?" for k in fields)
    conn = get_connection()
    try:
        conn.execute(f"UPDATE blackboard_actions SET {sets} WHERE action_id=?",
                     (*fields.values(), action_id))
        conn.commit()
    finally:
        conn.close()
