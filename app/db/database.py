"""SQLite 연결 및 스키마 초기화.

사용(앱 디렉토리에서):
    python -m db.database --reset    # DB 재생성
"""
import sqlite3
from pathlib import Path

from config import settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """FK 활성화 + Row 팩토리 적용된 커넥션 반환. db 디렉토리는 자동 생성."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")   # 동시 접근(컨트롤 루프·시뮬 스레드) 시 잠금 대기 후 재시도
    return conn


def init_db(reset: bool = False) -> None:
    """schema.sql 로 테이블·인덱스를 생성한다. reset=True 면 기존 DB 삭제 후 재생성."""
    if reset and settings.db_path.exists():
        settings.db_path.unlink()
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def ensure_row_timestamps() -> None:
    """모든 사용자 테이블에 created_at/updated_at 컬럼과 자동 채움 트리거를 보장한다(idempotent).

    - created_at: INSERT 시 트리거가 채움(명시값이 있으면 유지 — bb 테이블 등과 충돌 없음).
    - updated_at: UPDATE 시 트리거가 갱신(SQLite는 기본적으로 재귀 트리거 OFF라 무한루프 없음).
    기존 행의 created_at은 현재시각으로 1회 백필. 가상(FTS)·시스템 테이블은 제외.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for r in rows:
            t, sql = r["name"], (r["sql"] or "").upper()
            if "VIRTUAL" in sql or "USING FTS" in sql or " WITHOUT ROWID" in sql:
                continue
            cols = [c["name"] for c in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
            try:
                if "created_at" not in cols:
                    conn.execute(f'ALTER TABLE "{t}" ADD COLUMN created_at TEXT')
                if "updated_at" not in cols:
                    conn.execute(f'ALTER TABLE "{t}" ADD COLUMN updated_at TEXT')
                conn.execute(f"UPDATE \"{t}\" SET created_at=datetime('now','localtime') WHERE created_at IS NULL")
                conn.execute(f'DROP TRIGGER IF EXISTS "trg_{t}_created"')
                conn.execute(
                    f'CREATE TRIGGER "trg_{t}_created" AFTER INSERT ON "{t}" '
                    f"WHEN NEW.created_at IS NULL BEGIN "
                    f"UPDATE \"{t}\" SET created_at=datetime('now','localtime') WHERE rowid=NEW.rowid; END")
                # WHEN NEW.updated_at IS OLD.updated_at → 트리거가 스스로를 다시 물지 않음(재귀 방지, 재귀트리거 설정 무관)
                conn.execute(f'DROP TRIGGER IF EXISTS "trg_{t}_updated"')
                conn.execute(
                    f'CREATE TRIGGER "trg_{t}_updated" AFTER UPDATE ON "{t}" '
                    f"WHEN NEW.updated_at IS OLD.updated_at BEGIN "
                    f"UPDATE \"{t}\" SET updated_at=datetime('now','localtime') WHERE rowid=NEW.rowid; END")
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()


def list_tables() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    reset = "--reset" in sys.argv
    init_db(reset=reset)
    tables = list_tables()
    print(f"DB initialized at {settings.db_path} (reset={reset})")
    print(f"{len(tables)} tables: {', '.join(tables)}")
