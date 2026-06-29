"""blackboard_locks — 앱레벨 논리 잠금(동시 실행 충돌 방지). insert 성공 = 획득."""
import sqlite3
from datetime import datetime, timedelta

from db.database import get_connection

from bb.store import ensure_schema

_FMT = "%Y-%m-%d %H:%M:%S"


def acquire(lock_key: str, owner_action_id: str, ttl_seconds: int = 60) -> bool:
    ensure_schema()
    now = datetime.now()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM blackboard_locks WHERE expires_at < ?", (now.strftime(_FMT),))  # 만료 정리
        try:
            conn.execute("INSERT INTO blackboard_locks(lock_key,owner_action_id,acquired_at,expires_at) VALUES(?,?,?,?)",
                         (lock_key, owner_action_id, now.strftime(_FMT),
                          (now + timedelta(seconds=ttl_seconds)).strftime(_FMT)))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    finally:
        conn.close()


def acquire_all(lock_keys, owner_action_id: str, ttl_seconds: int = 60) -> bool:
    """여러 lock을 전부 획득(하나라도 실패하면 획득분 모두 해제)."""
    got = []
    for k in dict.fromkeys(lock_keys):
        if acquire(k, owner_action_id, ttl_seconds):
            got.append(k)
        else:
            for g in got:
                release(g, owner_action_id)
            return False
    return True


def release(lock_key: str, owner_action_id: str | None = None) -> None:
    ensure_schema()
    conn = get_connection()
    try:
        if owner_action_id:
            conn.execute("DELETE FROM blackboard_locks WHERE lock_key=? AND owner_action_id=?", (lock_key, owner_action_id))
        else:
            conn.execute("DELETE FROM blackboard_locks WHERE lock_key=?", (lock_key,))
        conn.commit()
    finally:
        conn.close()


def release_all(lock_keys, owner_action_id: str | None = None) -> None:
    for k in dict.fromkeys(lock_keys):
        release(k, owner_action_id)
