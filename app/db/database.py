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
