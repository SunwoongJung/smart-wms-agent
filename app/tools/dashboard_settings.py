"""KPI Dashboard 목표량(기준선) 서버 영구 저장 — 모든 사용자 공유 설정."""
from db.database import get_connection
from tools.common import q

DEFAULTS = {
    "kpi_target_zone_occupancy": "0.80",   # Zone 점유율 목표(평균 80% 유지)
    "kpi_target_utilization": "0.90",      # 작업팀 가동률 목표(90% 유지)
}


def get_all() -> dict:
    rows = {r["key"]: r["value"] for r in q("SELECT key, value FROM dashboard_settings")}
    return {**DEFAULTS, **rows}


def get_float(key: str) -> float:
    return float(get_all().get(key, DEFAULTS.get(key, 0)))


def set_value(key: str, value: float) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO dashboard_settings(key,value,updated_at) VALUES(?,?,datetime('now','localtime')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value)),
        )
        conn.commit()
    finally:
        conn.close()
