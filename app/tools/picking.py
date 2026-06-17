"""피킹 Tool (docs/06 §6). 산식: rag/scoring_formula.md."""
import math
from datetime import datetime, timedelta

from tools.common import BASE_PICKING_MINUTES, BUFFER_MINUTES, q

_FMT = "%Y-%m-%d %H:%M"


def _order_lines(order_no: str) -> list[dict]:
    return q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,))


def _max_distance_for_skus(skus: list[str]) -> float:
    if not skus:
        return 0.0
    marks = ",".join("?" for _ in skus)
    r = q(f"""SELECT MAX(z.distance_from_gate) d
              FROM inventory i JOIN locations l ON l.location_id=i.location_id
              JOIN zones z ON z.zone_id=l.zone_id WHERE i.sku IN ({marks})""", tuple(skus))
    return r[0]["d"] or 0.0


def calculate_picking_required_time(order_no: str) -> dict:
    lines = _order_lines(order_no)
    line_count = len(lines)
    total_qty = sum(l["qty"] for l in lines)
    max_dist = _max_distance_for_skus([l["sku"] for l in lines])
    est = (BASE_PICKING_MINUTES + (line_count - 1) * 2
           + math.ceil(total_qty / 10) * 2 + max_dist / 10)
    return {"order_no": order_no, "estimated_minutes": round(est),
            "line_count": line_count, "total_qty": total_qty, "max_distance": max_dist}


def recommend_picking(current_datetime: str, risk_levels: dict | None = None) -> dict:
    """미지시(PLANNED) 출고 주문의 우선순위·권장 시작시간 산출.

    risk_levels: {sku: 'HIGH'|'MEDIUM'} — Phase 4(calculate_inventory_risk) 결과를 주입.
    미주입 시 shortage_risk_score=0.
    """
    risk_levels = risk_levels or {}
    now = datetime.strptime(current_datetime, _FMT)
    orders = q("SELECT order_no, due_datetime, customer_priority FROM outbound_orders WHERE status='PLANNED'")
    recs = []
    for o in orders:
        ct = calculate_picking_required_time(o["order_no"])
        est = ct["estimated_minutes"]
        due = datetime.strptime(o["due_datetime"], _FMT)
        mins_left = (due - now).total_seconds() / 60
        rec_start = due - timedelta(minutes=est + BUFFER_MINUTES)
        urgent = rec_start <= now
        deadline_urgency = 120 if urgent else max(0, 120 - mins_left)
        customer = o["customer_priority"] * 10
        skus = [l["sku"] for l in _order_lines(o["order_no"])]
        shortage = 0
        for s in skus:
            lv = risk_levels.get(s)
            if lv == "HIGH":
                shortage = max(shortage, 30)
            elif lv == "MEDIUM":
                shortage = max(shortage, 15)
        score = (deadline_urgency + customer + shortage
                 - est * 0.5 - ct["max_distance"] * 0.2)
        recs.append({"order_no": o["order_no"], "priority_score": round(score, 2),
                     "recommended_start_time": rec_start.strftime(_FMT),
                     "estimated_minutes": est, "urgent": urgent,
                     "due_datetime": o["due_datetime"]})
    recs.sort(key=lambda r: r["priority_score"], reverse=True)
    for i, r in enumerate(recs, 1):
        r["priority_rank"] = i
    return {"recommendations": recs}
