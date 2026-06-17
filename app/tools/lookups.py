"""조회 Tool (docs/06 §4) + 운영 KPI 조회 (docs/13 §4)."""
from tools.common import q


def lookup_inventory(sku: str) -> dict:
    inv = q("SELECT location_id, lot_no, qty, expiry_date FROM inventory "
            "WHERE sku=? AND status='AVAILABLE' ORDER BY location_id", (sku,))
    return {"sku": sku, "inventory": inv, "total_qty": sum(r["qty"] for r in inv)}


def lookup_inbound_orders(status: list[str], target_date: str | None = None) -> dict:
    marks = ",".join("?" for _ in status)
    params = list(status)
    sql = (f"SELECT inbound_no, sku, qty, expected_date, status FROM inbound_orders "
           f"WHERE status IN ({marks})")
    if target_date:
        sql += " AND expected_date=?"
        params.append(target_date)
    return {"orders": q(sql, tuple(params))}


def lookup_outbound_orders(status: list[str], target_date: str | None = None) -> dict:
    marks = ",".join("?" for _ in status)
    params = list(status)
    sql = (f"SELECT order_no, due_datetime, customer_priority, status FROM outbound_orders "
           f"WHERE status IN ({marks})")
    if target_date:
        sql += " AND substr(due_datetime,1,10)=?"
        params.append(target_date)
    orders = q(sql, tuple(params))
    for o in orders:
        o["lines"] = q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (o["order_no"],))
    return {"orders": orders}


def lookup_shipping_pending(status: str = "PENDING") -> dict:
    return {"pending": q("SELECT pending_id, order_no, ready_datetime, status "
                         "FROM shipping_pending WHERE status=? ORDER BY ready_datetime", (status,))}


def lookup_demand_history(sku: str, days: int = 60) -> dict:
    rows = q("SELECT demand_date, shipped_qty FROM demand_history WHERE sku=? "
             "ORDER BY demand_date DESC LIMIT ?", (sku, days))
    rows.reverse()
    return {"history": rows, "days_available": len(rows)}


def query_operation_kpis(kpis: list[str], target_date: str | None = None) -> dict:
    """운영 KPI 조회. forecast 의존 KPI(on_time_shipping_rate, high_risk_sku_count)는
    Phase 4(Forecast/DES)에서 보강한다. 현재는 DB로 계산 가능한 KPI를 반환."""
    out = []
    for name in kpis:
        if name == "zone_occupancy":
            rows = q("""SELECT z.zone_id, ROUND(COALESCE(SUM(l.occupied_qty),0)*1.0/z.max_capacity,3) AS occupancy
                        FROM zones z LEFT JOIN locations l ON l.zone_id=z.zone_id
                        GROUP BY z.zone_id ORDER BY z.zone_id""")
            out.append({"name": name, "value": rows, "unit": "percent"})
        elif name == "saturated_zone_count":
            n = q("""SELECT COUNT(*) n FROM (SELECT z.zone_id,
                       COALESCE(SUM(l.occupied_qty),0)*1.0/z.max_capacity AS r
                       FROM zones z LEFT JOIN locations l ON l.zone_id=z.zone_id
                       GROUP BY z.zone_id) WHERE r > 0.9""")[0]["n"]
            out.append({"name": name, "value": n, "unit": "count"})
        elif name == "safety_stock_below_count":
            n = q("""SELECT COUNT(*) n FROM (SELECT p.sku, p.safety_stock,
                       COALESCE((SELECT SUM(qty) FROM inventory i WHERE i.sku=p.sku),0) AS stock
                       FROM products p) WHERE stock < safety_stock""")[0]["n"]
            out.append({"name": name, "value": n, "unit": "count"})
        elif name == "stocking_completion_rate":
            r = q("""SELECT
                       SUM(CASE WHEN status='STOCKED' THEN 1 ELSE 0 END)*1.0
                       / NULLIF(SUM(CASE WHEN status IN ('RECEIVED','STOCKING_RECOMMENDED','STOCKING_TASK_CREATED','STOCKED') THEN 1 ELSE 0 END),0) AS rate
                     FROM inbound_orders""")[0]["rate"]
            out.append({"name": name, "value": round(r, 3) if r is not None else None, "unit": "percent"})
        else:
            # forecast/이력 의존 KPI는 Phase 4에서 구현
            out.append({"name": name, "value": None, "unit": None, "note": "Phase 4에서 구현 예정"})
    return {"kpis": out}
