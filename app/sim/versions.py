"""What-if/시뮬레이션 실행 버전 관리 (로컬, simulation_runs.result_json 기반).

각 실행은 실행시각 기반 version_name(V%Y%m%d-%H%M%S)으로 저장되며,
버전별 KPI/차트를 조회하고 2개 버전을 비교할 수 있다.
"""
import json

from db.database import get_connection
from tools.common import q

_VERSION_COLS = ("worker_count", "forklift_count", "team_count")


def ensure_version_columns() -> None:
    """기존 simulation_runs에 자원 수 컬럼이 없으면 추가하고 result_json에서 백필(1회)."""
    conn = get_connection()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(simulation_runs)").fetchall()]
        missing = [c for c in _VERSION_COLS if c not in cols]
        if not missing:
            return
        for c in missing:
            conn.execute(f"ALTER TABLE simulation_runs ADD COLUMN {c} INTEGER")
        for row in conn.execute(
                "SELECT sim_run_id, result_json FROM simulation_runs WHERE result_json IS NOT NULL").fetchall():
            try:
                p = json.loads(row["result_json"]).get("params", {}) or {}
            except Exception:
                continue
            conn.execute("UPDATE simulation_runs SET worker_count=?, forklift_count=?, team_count=? WHERE sim_run_id=?",
                         (p.get("worker_count"), p.get("forklift_count"), p.get("team_count"), row["sim_run_id"]))
        conn.commit()
    finally:
        conn.close()


def list_versions() -> list[dict]:
    """버전 목록(최신순) + 해석된 자원 수(작업자/지게차/팀)."""
    ensure_version_columns()
    return q("""SELECT version_name, sim_run_id, run_type, scenario_json, created_at,
                  worker_count, forklift_count, team_count
                FROM simulation_runs WHERE version_name IS NOT NULL
                ORDER BY created_at DESC""")


def get_version(version_name: str) -> dict | None:
    rows = q("SELECT result_json FROM simulation_runs WHERE version_name=?", (version_name,))
    if not rows or not rows[0]["result_json"]:
        return None
    return json.loads(rows[0]["result_json"])
