"""블랙보드 스키마 보장 + 공통 헬퍼. WAL로 동시성(읽기-쓰기 병행) 확보."""
import random
from datetime import datetime
from pathlib import Path

from db.database import get_connection

ZONE_WORK_MINUTES_RANGE = (5, 20)   # zone별 결정론적 작업시간 범위(팀·SKU 무관)
LEAD_TIME_DAYS_RANGE = (1, 5)       # SKU별 결정론적 발주 리드타임(일)

_SCHEMA = Path(__file__).resolve().parent / "schema.sql"
_ensured = False


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _add_cols(conn, table: str, cols: dict) -> None:
    have = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    for c, ddl in cols.items():
        if c not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {c} {ddl}")


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
        _add_cols(conn, "resources", {"skill": "TEXT", "zone_id": "TEXT"})
        _add_cols(conn, "picking_tasks", {
            "worker_id": "TEXT", "priority": "INTEGER DEFAULT 0",
            "worker_id_2": "TEXT", "forklift_id": "TEXT",
            "started_at": "TEXT", "expected_complete_at": "TEXT",
            "zone_sequence": "TEXT", "zone_index": "INTEGER DEFAULT 0",
        })
        _add_cols(conn, "stocking_tasks", {
            "worker_id": "TEXT", "worker_id_2": "TEXT", "forklift_id": "TEXT",
            "started_at": "TEXT", "expected_complete_at": "TEXT", "zone_id": "TEXT",
        })
        _add_cols(conn, "blackboard_actions", {"explanation": "TEXT", "explanation_sig": "TEXT"})
        _add_cols(conn, "zones", {"work_minutes": "REAL"})
        _add_cols(conn, "products", {"lead_time_days": "INTEGER"})
        _add_cols(conn, "inbound_orders", {"replenish_for": "TEXT"})   # 발주분: 어느 출고주문 때문인지
        _backfill_zone_work_minutes(conn)
        _backfill_stocking_zone_id(conn)
        _backfill_lead_time(conn)
        conn.commit()
    finally:
        conn.close()
    _ensured = True


def _backfill_zone_work_minutes(conn) -> None:
    """zone별 결정론적 작업시간(분) — 팀·SKU 무관, zone_id로 시드해 재실행해도 동일값."""
    for r in conn.execute("SELECT zone_id FROM zones WHERE work_minutes IS NULL").fetchall():
        lo, hi = ZONE_WORK_MINUTES_RANGE
        v = random.Random(f"zone_work:{r['zone_id']}").randint(lo, hi)
        conn.execute("UPDATE zones SET work_minutes=? WHERE zone_id=?", (float(v), r["zone_id"]))


def _backfill_stocking_zone_id(conn) -> None:
    conn.execute("""UPDATE stocking_tasks SET zone_id=(
        SELECT l.zone_id FROM locations l WHERE l.location_id=stocking_tasks.location_id
    ) WHERE zone_id IS NULL""")


def _backfill_lead_time(conn) -> None:
    """SKU별 결정론적 발주 리드타임(일) — sku로 시드해 재실행해도 동일값."""
    lo, hi = LEAD_TIME_DAYS_RANGE
    for r in conn.execute("SELECT sku FROM products WHERE lead_time_days IS NULL").fetchall():
        v = random.Random(f"lead_time:{r['sku']}").randint(lo, hi)
        conn.execute("UPDATE products SET lead_time_days=? WHERE sku=?", (v, r["sku"]))
