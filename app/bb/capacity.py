"""실시간 작업팀 가용/백로그 지표 — DES 예측이 아닌 현재 DB 상태 기준(쿼리 한 번).

팀 = 작업자 2 + 지게차 1. 팀을 점유한 작업(TEAM_ASSIGNED·IN_PROGRESS) 수 = 사용중 팀.
'대기'는 미처리(ISSUED, 아직 팀 미배정) 작업 — 지시는 나갔으나 팀이 없어 실작업을 못 하는 백로그.
"""
import resmgmt
from tools.common import q

_BUSY = ("TEAM_ASSIGNED", "IN_PROGRESS")


def snapshot() -> dict:
    r = resmgmt.get_resources()
    total = max(0, min(r["worker"] // 2, r["forklift"]))
    marks = ",".join("?" for _ in _BUSY)
    busy = q(f"""SELECT COUNT(*) n FROM (
        SELECT picking_task_id FROM picking_tasks WHERE worker_id IS NOT NULL AND status IN ({marks})
        UNION ALL
        SELECT stocking_task_id FROM stocking_tasks WHERE worker_id IS NOT NULL AND status IN ({marks})
    )""", (*_BUSY, *_BUSY))[0]["n"]
    available = max(0, total - busy)
    # 미처리(ISSUED · 팀 미배정) = 지시만 나가고 실작업 대기 중인 백로그
    waiting_picking = q("SELECT COUNT(*) n FROM picking_tasks WHERE status='ISSUED' AND worker_id IS NULL")[0]["n"]
    waiting_stocking = q("SELECT COUNT(*) n FROM stocking_tasks WHERE status='ISSUED' AND worker_id IS NULL")[0]["n"]
    inprog_picking = q("SELECT COUNT(*) n FROM picking_tasks WHERE status='IN_PROGRESS'")[0]["n"]
    inprog_stocking = q("SELECT COUNT(*) n FROM stocking_tasks WHERE status='IN_PROGRESS'")[0]["n"]
    waiting_total = waiting_picking + waiting_stocking
    awaiting_stock = q("SELECT COUNT(*) n FROM outbound_orders WHERE status='AWAITING_STOCK'")[0]["n"]
    return {
        "total_teams": total, "busy_teams": busy, "available_teams": available,
        "waiting_picking": waiting_picking, "waiting_stocking": waiting_stocking,
        "waiting_total": waiting_total,
        "in_progress_picking": inprog_picking, "in_progress_stocking": inprog_stocking,
        "in_progress_total": inprog_picking + inprog_stocking,
        "team_short": available <= 0 and waiting_total > 0,   # 팀 부족으로 백로그 정체
        "awaiting_stock": awaiting_stock,                     # 발주 대기(결품) 출고주문 수
    }
