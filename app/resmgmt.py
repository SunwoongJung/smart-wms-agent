"""운영 자원(작업자/지게차) 기준값 조회·업데이트.

What-if에서 의사결정이 내려지면 update_resources로 실제 resources 테이블을 갱신하고,
이후 시뮬레이션의 베이스라인으로 삼는다(des._load_static이 이 값을 읽음).
"""
from db.database import get_connection
from tools.common import q


def get_resources() -> dict:
    d = {r["resource_type"]: r["count"] for r in q("SELECT resource_type, count FROM resources WHERE active_flag=1")}
    return {"worker": d.get("WORKER", 0), "forklift": d.get("FORKLIFT", 0)}


def update_resources(worker: int, forklift: int) -> dict:
    conn = get_connection()
    try:
        conn.execute("UPDATE resources SET count=? WHERE resource_type='WORKER'", (max(1, int(worker)),))
        conn.execute("UPDATE resources SET count=? WHERE resource_type='FORKLIFT'", (max(1, int(forklift)),))
        conn.commit()
    finally:
        conn.close()
    return get_resources()
