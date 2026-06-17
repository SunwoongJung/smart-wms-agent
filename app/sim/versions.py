"""What-if/시뮬레이션 실행 버전 관리 (로컬, simulation_runs.result_json 기반).

각 실행은 실행시각 기반 version_name(V%Y%m%d-%H%M%S)으로 저장되며,
버전별 KPI/차트를 조회하고 2개 버전을 비교할 수 있다.
"""
import json

from tools.common import q


def list_versions() -> list[dict]:
    return q("""SELECT version_name, sim_run_id, run_type, scenario_json, created_at
                FROM simulation_runs WHERE version_name IS NOT NULL
                ORDER BY created_at DESC""")


def get_version(version_name: str) -> dict | None:
    rows = q("SELECT result_json FROM simulation_runs WHERE version_name=?", (version_name,))
    if not rows or not rows[0]["result_json"]:
        return None
    return json.loads(rows[0]["result_json"])
