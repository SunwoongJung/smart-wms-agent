"""적치 Tool (docs/06 §5). 산식: rag/scoring_formula.md (0~1 정규화 가중합)."""
from tools.common import (W_CAPACITY, W_CONGESTION, W_DISTANCE, W_SAME_SKU,
                          W_TURNOVER, clip, q)


def _product(sku: str) -> dict | None:
    r = q("SELECT * FROM products WHERE sku=?", (sku,))
    return r[0] if r else None


def filter_available_locations(sku: str, inbound_qty: int) -> dict:
    """보관조건 일치 + 사용가능 + 잔여용량 >= inbound_qty 인 Location (hard filter)."""
    p = _product(sku)
    if not p:
        return {"candidates": [], "error": "SKU 없음"}
    rows = q("""SELECT l.location_id, l.zone_id, l.capacity, l.occupied_qty,
                       (l.capacity - l.occupied_qty) AS remaining_capacity,
                       z.distance_from_gate
                FROM locations l JOIN zones z ON z.zone_id=l.zone_id
                WHERE l.available_flag=1 AND z.active_flag=1
                  AND z.storage_type=? AND (l.capacity - l.occupied_qty) >= ?
                ORDER BY remaining_capacity DESC""",
             (p["storage_type"], inbound_qty))
    return {"candidates": rows}


def check_same_sku_location(sku: str) -> dict:
    rows = q("""SELECT DISTINCT i.location_id, l.zone_id
                FROM inventory i JOIN locations l ON l.location_id=i.location_id
                WHERE i.sku=? AND i.qty>0""", (sku,))
    return {"exists": len(rows) > 0,
            "locations": [r["location_id"] for r in rows],
            "zones": sorted({r["zone_id"] for r in rows})}


def _zone_aggregates() -> dict:
    return {r["zone_id"]: r for r in q("""
        SELECT z.zone_id, z.max_capacity, z.distance_from_gate, z.active_flag,
               COALESCE(SUM(l.occupied_qty),0) AS occ
        FROM zones z LEFT JOIN locations l ON l.zone_id=z.zone_id GROUP BY z.zone_id""")}


def _sku_turnover(sku: str) -> float:
    """최근 14일 평균 출고량 / 현재 총재고 (간이 회전율)."""
    avg = q("SELECT AVG(shipped_qty) a FROM (SELECT shipped_qty FROM demand_history "
            "WHERE sku=? ORDER BY demand_date DESC LIMIT 14)", (sku,))[0]["a"] or 0.0
    stock = q("SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE sku=?", (sku,))[0]["s"] or 0
    return avg / stock if stock > 0 else (avg / 1.0)


def _max_turnover() -> float:
    skus = [r["sku"] for r in q("SELECT sku FROM products")]
    vals = [_sku_turnover(s) for s in skus]
    return max(vals) if vals else 1.0


def calculate_stocking_score(sku: str, candidates: list[str]) -> dict:
    """후보 Location별 0~1 정규화 가중합 점수 + breakdown."""
    if not candidates:
        return {"scores": []}
    zagg = _zone_aggregates()
    dists = [z["distance_from_gate"] for z in zagg.values() if z["active_flag"] == 1]
    min_d, max_d = min(dists), max(dists)
    same = set(check_same_sku_location(sku)["locations"])
    turnover_norm = clip(_sku_turnover(sku) / (_max_turnover() or 1.0))
    # 고회전 SKU는 입구 근처 적재가 더 중요 → 거리 가중을 2배로
    fast = bool((_product(sku) or {}).get("fast_moving_flag"))
    w_dist = W_DISTANCE * (2 if fast else 1)

    marks = ",".join("?" for _ in candidates)
    locs = q(f"""SELECT l.location_id, l.zone_id, z.distance_from_gate AS dist
                 FROM locations l JOIN zones z ON z.zone_id=l.zone_id
                 WHERE l.location_id IN ({marks})""", tuple(candidates))

    scores = []
    for lo in locs:
        z = zagg[lo["zone_id"]]
        zmax = z["max_capacity"] or 1
        zocc_ratio = z["occ"] / zmax
        cap_norm = clip((zmax - z["occ"]) / zmax)
        dist_norm = clip(1 - (lo["dist"] - min_d) / (max_d - min_d)) if max_d > min_d else 1.0
        cong_norm = clip((zocc_ratio - 0.9) / 0.1) if zocc_ratio > 0.9 else 0.0
        same_norm = 1.0 if lo["location_id"] in same else 0.0
        score = (W_SAME_SKU * same_norm + W_CAPACITY * cap_norm + w_dist * dist_norm
                 + W_TURNOVER * turnover_norm - W_CONGESTION * cong_norm)
        scores.append({
            "location_id": lo["location_id"],
            "score": round(score, 4),
            "breakdown": {
                "same_sku_norm": round(same_norm, 3), "capacity_norm": round(cap_norm, 3),
                "distance_norm": round(dist_norm, 3), "turnover_norm": round(turnover_norm, 3),
                "congestion_norm": round(cong_norm, 3),
            },
        })
    scores.sort(key=lambda s: s["score"], reverse=True)
    return {"scores": scores}


def recommend_stocking(inbound_no: str) -> dict:
    r = q("SELECT inbound_no, sku, qty FROM inbound_orders WHERE inbound_no=?", (inbound_no,))
    if not r:
        return {"error": "입고번호 없음"}
    sku, qty = r[0]["sku"], r[0]["qty"]
    cands = filter_available_locations(sku, qty)["candidates"]
    if not cands:
        return {"recommended_location_id": None, "candidates": [],
                "reasons": ["적재 가능 Location 없음 — SOP 검토 필요"], "approval_required": False}
    scored = calculate_stocking_score(sku, [c["location_id"] for c in cands])["scores"]
    best = scored[0]
    bd = best["breakdown"]
    reasons = []
    if bd["same_sku_norm"] >= 1:
        reasons.append("동일 SKU 존재")
    if bd["capacity_norm"] >= 0.5:
        reasons.append("잔여 CAPA 충분")
    if bd["distance_norm"] >= 0.7:
        reasons.append("입구 거리 우수")
    if bd["turnover_norm"] >= 0.6:
        reasons.append("고회전 SKU")
    return {"recommended_location_id": best["location_id"], "score": best["score"],
            "breakdown": bd, "reasons": reasons, "candidates": scored[:5],
            "approval_required": True}
