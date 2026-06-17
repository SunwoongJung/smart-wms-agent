"""수요예측(Linear Regression) + 재고 위험등급 (docs/06 §7, docs/07 §4~8).

DES의 Far Future 입력(수요 평균 λ)과 피킹 우선순위의 위험등급을 제공한다.
"""
from datetime import date, timedelta

import numpy as np

from config import settings
from tools.common import q


def _base_date() -> date:
    return date.fromisoformat(settings.base_date)


def fit_demand(sku: str):
    """일별 출고량으로 수요 예측 함수 f(k)=미래 k일째 예상 수요 반환.

    Fallback(docs/07 §8): 30일↑ LR / 14일↑ MA14 / 7일↑ MA7 / 7일 미만 예측불가.
    """
    rows = q("SELECT shipped_qty FROM demand_history WHERE sku=? ORDER BY demand_date", (sku,))
    n = len(rows)
    if n < 7:
        return None, "insufficient_data"
    y = np.array([r["shipped_qty"] for r in rows], dtype=float)
    if n >= 30:
        x = np.arange(n)
        a, b = np.polyfit(x, y, 1)
        return (lambda k: max(0.0, a * (n - 1 + k) + b)), "linear_regression"
    if n >= 14:
        m = float(y[-14:].mean())
        return (lambda k: max(0.0, m)), "ma_14"
    m = float(y[-7:].mean())
    return (lambda k: max(0.0, m)), "ma_7"


def inventory_forecast(sku: str, forecast_days: int = 30) -> dict:
    p = q("SELECT safety_stock FROM products WHERE sku=?", (sku,))
    if not p:
        return {"error": "SKU 없음"}
    safety = p[0]["safety_stock"]
    f, method = fit_demand(sku)
    cur = q("SELECT COALESCE(SUM(qty),0) s FROM inventory WHERE sku=?", (sku,))[0]["s"]

    if method == "insufficient_data":
        return {"sku": sku, "method": method, "current_stock": cur, "safety_stock": safety,
                "expected_stockout_date": None, "safety_stock_reach_date": None, "daily_projection": []}

    base = _base_date()
    # 개입 없을 때의 추세 투영: 현재고 + 입고예정 - 예측수요.
    # 예측수요(predicted_demand)는 출고이력 기반이라 이미 출고를 포함하므로 확정출고를 별도 차감하지
    # 않는다(이중 차감 방지). 확정 입출고의 자원제약 처리가능성은 DES(des.py)가 담당한다.
    inbound = {}
    for r in q("SELECT expected_date, qty FROM inbound_orders WHERE sku=? AND status='PLANNED'", (sku,)):
        inbound[r["expected_date"]] = inbound.get(r["expected_date"], 0) + r["qty"]

    inv = float(cur)
    proj, stockout, safety_reach = [], None, None
    for k in range(1, forecast_days + 1):
        ds = (base + timedelta(days=k)).isoformat()
        inv += inbound.get(ds, 0)
        inv -= f(k)
        proj.append({"date": ds, "projected_inventory": round(inv, 1)})
        if stockout is None and inv <= 0:
            stockout = ds
        if safety_reach is None and inv <= safety:
            safety_reach = ds

    return {"sku": sku, "method": method, "current_stock": cur, "safety_stock": safety,
            "expected_stockout_date": stockout, "safety_stock_reach_date": safety_reach,
            "daily_projection": proj}


def calculate_inventory_risk(sku: str) -> dict:
    fc = inventory_forecast(sku)
    if fc.get("method") == "insufficient_data":
        return {"sku": sku, "risk_level": "UNKNOWN", "expected_stockout_date": None}
    so, sd = fc["expected_stockout_date"], fc["safety_stock_reach_date"]
    base = _base_date()
    level = "LOW"
    if so:
        days = (date.fromisoformat(so) - base).days
        level = "HIGH" if days <= 7 else "MEDIUM" if days <= 14 else "LOW"
    elif sd:
        level = "WATCH"
    return {"sku": sku, "risk_level": level,
            "expected_stockout_date": so, "safety_stock_reach_date": sd}


def scan_inventory_risk(risk_levels: list[str] | None = None) -> dict:
    out = []
    for r in q("SELECT sku FROM products"):
        risk = calculate_inventory_risk(r["sku"])
        out.append({"sku": r["sku"], "risk_level": risk["risk_level"],
                    "expected_stockout_date": risk["expected_stockout_date"]})
    if risk_levels:
        out = [x for x in out if x["risk_level"] in risk_levels]
    return {"risks": out}


def risk_level_map() -> dict:
    """{sku: risk_level} — recommend_picking의 shortage_risk_score 주입용."""
    return {x["sku"]: x["risk_level"] for x in scan_inventory_risk()["risks"]}
