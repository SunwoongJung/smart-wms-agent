"""Zone 작업시간·점유 판정 — 적치/피킹 공통.

Zone 작업시간(work_minutes)은 zone별 결정론적 고정값(팀·SKU 무관, bb/store.py에서 1회 백필).
Zone 점유는 별도 락 테이블 없이 작업 테이블(stocking_tasks/picking_tasks) 자체를 단일 소스로 판정한다:
"해당 zone에 started_at이 찍힌 IN_PROGRESS 작업이 있는가" = 사용중. Zone 동시용량은 1(엄격한 단일 점유).
"""
import json

from tools.common import q


def zone_minutes(zone_id: str) -> float:
    r = q("SELECT work_minutes FROM zones WHERE zone_id=?", (zone_id,))
    return float(r[0]["work_minutes"]) if r and r[0]["work_minutes"] is not None else 10.0


def zone_sequence_for_skus(skus: list[str]) -> list[str]:
    """주어진 SKU들의 재고가 있는 zone을 distance_from_gate 오름차순으로 나열(중복 제거) — 피킹 동선."""
    if not skus:
        return []
    marks = ",".join("?" for _ in skus)
    rows = q(f"""SELECT DISTINCT z.zone_id, z.distance_from_gate FROM inventory i
                 JOIN locations l ON l.location_id=i.location_id
                 JOIN zones z ON z.zone_id=l.zone_id
                 WHERE i.sku IN ({marks}) AND i.status='AVAILABLE'
                 ORDER BY z.distance_from_gate ASC""", tuple(skus))
    seq = [r["zone_id"] for r in rows]
    return seq or []


def zone_busy(zone_id: str, exclude_task_id: str | None = None) -> bool:
    """해당 zone에 이미 점유 중(IN_PROGRESS + started_at 존재)인 다른 작업이 있는가."""
    if not zone_id:
        return False
    st = q("""SELECT stocking_task_id id FROM stocking_tasks
              WHERE zone_id=? AND status='IN_PROGRESS' AND started_at IS NOT NULL""", (zone_id,))
    pk = q("""SELECT picking_task_id id FROM picking_tasks
              WHERE status='IN_PROGRESS' AND started_at IS NOT NULL
                AND json_extract(zone_sequence, '$[' || zone_index || ']')=?""", (zone_id,))
    busy_ids = [r["id"] for r in st] + [r["id"] for r in pk]
    if exclude_task_id:
        busy_ids = [i for i in busy_ids if i != exclude_task_id]
    return bool(busy_ids)


def current_zone(kind: str, task: dict) -> str | None:
    """작업의 '지금 목표 zone'. 적치=zone_id 고정, 피킹=zone_sequence[zone_index]."""
    if kind == "stocking":
        return task.get("zone_id")
    seq = json.loads(task.get("zone_sequence") or "[]")
    idx = task.get("zone_index") or 0
    return seq[idx] if 0 <= idx < len(seq) else None


def is_last_zone(kind: str, task: dict) -> bool:
    if kind == "stocking":
        return True
    seq = json.loads(task.get("zone_sequence") or "[]")
    idx = task.get("zone_index") or 0
    return idx >= len(seq) - 1
