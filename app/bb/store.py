"""블랙보드 스키마 보장 + 공통 헬퍼. WAL로 동시성(읽기-쓰기 병행) 확보."""
from datetime import datetime
from pathlib import Path

from db.database import get_connection

_SCHEMA = Path(__file__).resolve().parent / "schema.sql"
_ensured = False


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema() -> None:
    """블랙보드 테이블 생성 + WAL + resources에 skill/zone 컬럼 보강(1회)."""
    global _ensured
    if _ensured:
        return
    conn = get_connection()
    try:
        try:
            conn.execute("PRAGMA journal_mode=WAL")   # 컨트롤 루프(스레드) + realtime 동시 write 대비
        except Exception:
            pass
        conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(resources)").fetchall()]
        for c in ("skill", "zone_id"):
            if c not in cols:
                conn.execute(f"ALTER TABLE resources ADD COLUMN {c} TEXT")
        conn.commit()
    finally:
        conn.close()
    _ensured = True
