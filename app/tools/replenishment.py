"""재고 보충(Replenishment) Tool — 피킹 로케이션(pick-face)을 보관(reserve)에서 보충.

2단 재고 모델: PICK 로케이션은 피킹이 직접 집는 전진 재고, RESERVE는 벌크 보관.
피킹 로케이션이 목표 커버리지(최근 수요 × COVER_DAYS, 최소 안전재고) 미만이고 보관에
재고가 있으면 보충을 추천한다. 실제 WMS의 '재고 보충 / 보관→피킹 로케이션 이동'에 대응하며
'피킹 로케이션 결품 예측'의 근거가 된다.
"""
from db.database import get_connection
from tools.common import q

COVER_DAYS = 2  # 피킹 로케이션이 최소로 커버해야 할 수요 일수


def ensure_location_role_column() -> None:
    conn = get_connection()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(locations)").fetchall()]
        if "location_role" not in cols:
            conn.execute("ALTER TABLE locations ADD COLUMN location_role TEXT DEFAULT 'PICK'")
            conn.commit()
    finally:
        conn.close()


def _avg_daily_demand(sku: str) -> float:
    r = q("SELECT AVG(shipped_qty) a FROM (SELECT shipped_qty FROM demand_history "
          "WHERE sku=? ORDER BY demand_date DESC LIMIT 14)", (sku,))
    return r[0]["a"] or 0.0


def scan_replenishment() -> dict:
    """피킹면 부족 + 보관 보유 SKU에 대해 보충 추천(긴급도순)."""
    ensure_location_role_column()
    safety = {r["sku"]: r["safety_stock"] for r in q("SELECT sku, safety_stock FROM products")}
    rows = q("""SELECT i.sku, l.zone_id, l.location_id, l.location_role, COALESCE(SUM(i.qty),0) qty
                FROM inventory i JOIN locations l ON l.location_id=i.location_id
                WHERE i.status='AVAILABLE' GROUP BY i.sku, l.location_id""")
    by: dict = {}
    for r in rows:
        e = by.setdefault((r["sku"], r["zone_id"]),
                          {"pick_qty": 0, "reserve_qty": 0, "pick_loc": None, "reserves": []})
        if r["location_role"] == "PICK":
            e["pick_qty"] += r["qty"]
            e["pick_loc"] = e["pick_loc"] or r["location_id"]
        else:
            e["reserve_qty"] += r["qty"]
            if r["qty"] > 0:
                e["reserves"].append((r["location_id"], r["qty"]))

    recs = []
    for (sku, zone), e in by.items():
        if e["pick_loc"] is None or e["reserve_qty"] <= 0:
            continue
        avg = _avg_daily_demand(sku)
        target = max(safety.get(sku, 0), round(avg * COVER_DAYS))
        if target <= 0 or e["pick_qty"] >= target:
            continue
        move = min(target - e["pick_qty"], e["reserve_qty"])
        if move <= 0:
            continue
        recs.append({"sku": sku, "zone_id": zone, "pick_location": e["pick_loc"],
                     "from_location": e["reserves"][0][0], "pick_qty": e["pick_qty"],
                     "reserve_qty": e["reserve_qty"], "avg_daily_demand": round(avg, 2),
                     "target": target, "recommend_qty": move,
                     "coverage_days": round(e["pick_qty"] / avg, 1) if avg > 0 else None})
    recs.sort(key=lambda r: r["pick_qty"] / r["target"])  # 커버리지 낮은(긴급) 순
    return {"recommendations": recs, "count": len(recs)}


def replenishment_needed_count() -> int:
    return scan_replenishment()["count"]


def execute_replenishment(sku: str, from_location: str, to_location: str, qty: int) -> dict:
    """보관→피킹 로케이션으로 재고 이동(승인된 draft 실행용)."""
    conn = get_connection()
    try:
        remaining = qty
        for lot in conn.execute("SELECT inventory_id, qty FROM inventory "
                                "WHERE sku=? AND location_id=? AND status='AVAILABLE' AND qty>0 "
                                "ORDER BY inventory_id", (sku, from_location)).fetchall():
            if remaining <= 0:
                break
            take = min(remaining, lot["qty"])
            conn.execute("UPDATE inventory SET qty=qty-? WHERE inventory_id=?", (take, lot["inventory_id"]))
            remaining -= take
        moved = qty - remaining
        # 피킹 로케이션의 동일 SKU 재고에 합산(없으면 신규 LOT)
        existing = conn.execute("SELECT inventory_id FROM inventory WHERE sku=? AND location_id=? "
                                "AND status='AVAILABLE' ORDER BY inventory_id LIMIT 1",
                                (sku, to_location)).fetchone()
        if existing:
            conn.execute("UPDATE inventory SET qty=qty+? WHERE inventory_id=?", (moved, existing["inventory_id"]))
        else:
            conn.execute("INSERT INTO inventory(sku,lot_no,location_id,qty,status) VALUES(?,?,?,?,'AVAILABLE')",
                         (sku, f"RPL-{from_location}", to_location, moved))
        conn.execute("UPDATE locations SET occupied_qty=occupied_qty-? WHERE location_id=?", (moved, from_location))
        conn.execute("UPDATE locations SET occupied_qty=occupied_qty+? WHERE location_id=?", (moved, to_location))
        conn.commit()
    finally:
        conn.close()
    return {"sku": sku, "from_location": from_location, "to_location": to_location,
            "moved_qty": moved, "shortfall": remaining}
