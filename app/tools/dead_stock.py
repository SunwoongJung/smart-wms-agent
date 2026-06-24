"""체화재고(Dead/Slow-moving) 분석 Tool — 저회전·장기 미출고·유통기한 임박 재고 식별.

실제 WMS의 '체화 재고 조회/체화 예정 조회'에 대응한다. 운영자가 처분/반품/소진촉진을
판단할 수 있도록 회전율·미출고 경과일·유통기한 잔여를 종합해 등급화한다.
"""
from datetime import date

from config import settings
from tools.common import q

SLOW_TURNOVER = 0.05      # 일 회전율(최근14일 평균출고/현재고) 미만 = 저회전
EXPIRY_SOON_DAYS = 14     # 유통기한 잔여일 이하 = 임박 (음수=이미 만료)

_GRADE_RECO = {
    "EXPIRING": "유통기한 임박/만료 — 우선 출고/프로모션 또는 폐기 검토",
    "DEAD": "최근 14일 무출고 — 반품·처분 검토",
    "SLOW": "저회전 — 발주 보류·재고 축소 검토",
}


def _base() -> date:
    return date.fromisoformat(settings.base_date)


def scan_dead_stock(grades: list[str] | None = None) -> dict:
    """체화 후보 SKU를 등급(EXPIRING/DEAD/SLOW)과 재고가치와 함께 반환."""
    base = _base()
    rows = q("""
        SELECT p.sku, p.product_name, p.unit_cost,
               COALESCE((SELECT SUM(qty) FROM inventory i
                         WHERE i.sku=p.sku AND i.status='AVAILABLE'),0) AS stock,
               (SELECT MAX(demand_date) FROM demand_history d
                WHERE d.sku=p.sku AND d.shipped_qty>0) AS last_ship,
               (SELECT AVG(shipped_qty) FROM (SELECT shipped_qty FROM demand_history d2
                 WHERE d2.sku=p.sku ORDER BY demand_date DESC LIMIT 14)) AS avg14,
               (SELECT MIN(expiry_date) FROM inventory i2
                WHERE i2.sku=p.sku AND i2.status='AVAILABLE' AND i2.expiry_date IS NOT NULL) AS nearest_expiry
        FROM products p""")

    items = []
    for r in rows:
        stock = r["stock"] or 0
        if stock <= 0:
            continue
        avg14 = r["avg14"] or 0.0
        turnover = avg14 / stock if stock > 0 else 0.0
        idle = (base - date.fromisoformat(r["last_ship"])).days if r["last_ship"] else 9999
        exp_days = (date.fromisoformat(r["nearest_expiry"]) - base).days if r["nearest_expiry"] else None

        g = []
        if exp_days is not None and exp_days <= EXPIRY_SOON_DAYS:
            g.append("EXPIRING")
        if avg14 == 0:                       # 최근 14일 전혀 출고 없음 = 사실상 무동
            g.append("DEAD")
        elif turnover < SLOW_TURNOVER:
            g.append("SLOW")
        if not g:
            continue

        primary = g[0]
        items.append({
            "sku": r["sku"], "product_name": r["product_name"], "stock": stock,
            "turnover": round(turnover, 4), "idle_days": None if idle == 9999 else idle,
            "nearest_expiry": r["nearest_expiry"], "expiry_days": exp_days,
            "grade": primary, "grades": g,
            "stock_value": round(stock * (r["unit_cost"] or 0)),
            "recommendation": _GRADE_RECO[primary],
        })

    if grades:
        items = [x for x in items if any(gr in grades for gr in x["grades"])]
    items.sort(key=lambda x: x["stock_value"], reverse=True)

    counts = {gr: sum(1 for x in items if gr in x["grades"]) for gr in ("EXPIRING", "DEAD", "SLOW")}
    return {"items": items, "count": len(items), "grade_counts": counts,
            "total_value": sum(x["stock_value"] for x in items)}


def dead_stock_count() -> int:
    return scan_dead_stock()["count"]
