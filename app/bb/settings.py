"""Auto Mode 설정(system_settings) — ON/OFF, 의사결정 주기, 사이클당 최대 Action, 시뮬 필요, risk 임계."""
from db.database import get_connection
from tools.common import q

from bb.store import ensure_schema, now

DEFAULTS = {
    "auto_mode_enabled": "false",
    "auto_mode_max_actions_per_cycle": "20",
    "auto_mode_cycle_interval_seconds": "15",   # 의사결정 주기(초)
    "auto_mode_simulation_required": "true",
    "auto_mode_risk_threshold": "0.7",
    "auto_mode_util_block": "0.95",             # 배치 시뮬 팀 가동률 차단 임계
    "auto_mode_step_delay_seconds": "1.2",      # Action 1건 처리 사이 지연(가시화)
    "auto_mode_sim_refresh_seconds": "30",      # 시뮬 KPI 캐시 갱신 주기(백그라운드)
}


def init_defaults() -> None:
    ensure_schema()
    conn = get_connection()
    try:
        for k, v in DEFAULTS.items():
            conn.execute("INSERT OR IGNORE INTO system_settings(key,value,updated_at) VALUES(?,?,?)", (k, v, now()))
        conn.commit()
    finally:
        conn.close()


def get_all() -> dict:
    init_defaults()
    return {r["key"]: r["value"] for r in q("SELECT key, value FROM system_settings")}


def get(key: str, default=None):
    init_defaults()
    r = q("SELECT value FROM system_settings WHERE key=?", (key,))
    return r[0]["value"] if r else default


def set_value(key: str, value) -> None:
    ensure_schema()
    conn = get_connection()
    try:
        conn.execute("INSERT INTO system_settings(key,value,updated_at) VALUES(?,?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                     (key, str(value), now()))
        conn.commit()
    finally:
        conn.close()


def enabled() -> bool:
    return get("auto_mode_enabled", "false") == "true"


def set_enabled(on: bool) -> None:
    set_value("auto_mode_enabled", "true" if on else "false")


def _int(key: str, fallback: int) -> int:
    try:
        return int(float(get(key, fallback)))
    except (TypeError, ValueError):
        return fallback


def cycle_seconds() -> int:
    return max(2, _int("auto_mode_cycle_interval_seconds", 15))


def max_actions_per_cycle() -> int:
    return max(1, _int("auto_mode_max_actions_per_cycle", 20))


def simulation_required() -> bool:
    return get("auto_mode_simulation_required", "true") == "true"


def risk_threshold() -> float:
    try:
        return float(get("auto_mode_risk_threshold", 0.7))
    except (TypeError, ValueError):
        return 0.7


def util_block() -> float:
    try:
        return float(get("auto_mode_util_block", 0.95))
    except (TypeError, ValueError):
        return 0.95


def step_delay() -> float:
    try:
        return max(0.0, float(get("auto_mode_step_delay_seconds", 1.2)))
    except (TypeError, ValueError):
        return 1.2


def sim_refresh_seconds() -> int:
    try:
        return max(5, int(float(get("auto_mode_sim_refresh_seconds", 30))))
    except (TypeError, ValueError):
        return 30
