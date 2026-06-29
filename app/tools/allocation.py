"""할당(Allocation) Tool — 출고 주문에 가용재고를 배정하고 결품(shortage)을 식별한다.

실제 WMS의 출고 흐름(예정→할당→피킹→확정→상차)에서 '할당' 단계를 담당한다.
할당은 '주문이 요구하는 수량을 실제 가용재고(AVAILABLE)로 채울 수 있는가'를 판정하며,
채우지 못하는 수량은 결품(shortage)으로 표시된다. 결품 판정이 곧 '예상 결품 조회'다.
"""
from datetime import date, timedelta

from config import settings
from db.database import get_connection
from tools.common import q

ACTIONABLE = ("PLANNED", "ALLOCATED")  # 아직 출고되지 않은, 할당 대상 주문


def ensure_allocation_columns() -> None:
    """기존 DB의 outbound_order_lines에 할당 관련 컬럼이 없으면 추가(1회)."""
    conn = get_connection()
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(outbound_order_lines)").fetchall()]
        defs = {"allocated_qty": "INTEGER DEFAULT 0", "picked_qty": "INTEGER DEFAULT 0",
                "shipped_qty": "INTEGER DEFAULT 0", "line_status": "TEXT DEFAULT 'PLANNED'"}
        added = False
        for c, ddl in defs.items():
            if c not in cols:
                conn.execute(f"ALTER TABLE outbound_order_lines ADD COLUMN {c} {ddl}")
                added = True
        if added:
            conn.commit()
    finally:
        conn.close()


def _available_map(skus: list[str]) -> dict:
    """SKU별 현재 가용재고(AVAILABLE) 합계 — 즉시 할당 가능한 on-hand."""
    skus = [s for s in dict.fromkeys(skus)]
    if not skus:
        return {}
    marks = ",".join("?" for _ in skus)
    rows = q(f"""SELECT sku, COALESCE(SUM(qty),0) s FROM inventory
                 WHERE status='AVAILABLE' AND sku IN ({marks}) GROUP BY sku""", tuple(skus))
    have = {r["sku"]: r["s"] for r in rows}
    from bb.reservations import reserved_map           # 예약재고 단일출처 차감(가용 = on_hand - reserved)
    resv = reserved_map(skus)
    return {s: max(0, have.get(s, 0) - resv.get(s, 0)) for s in skus}


def _atp_map(skus: list[str], until: str) -> dict:
    """SKU별 ATP(Available-To-Promise) = 현재 가용재고 + until일까지 도착하는 입고예정.

    예상 결품은 현재고만이 아니라 곧 들어올 입고까지 고려해야 과대평가되지 않는다.
    """
    atp = _available_map(skus)
    if not atp:
        return {}
    marks = ",".join("?" for _ in atp)
    rows = q(f"""SELECT sku, COALESCE(SUM(qty),0) s FROM inbound_orders
                 WHERE status IN ('PLANNED','RECEIVED') AND expected_date<=? AND sku IN ({marks})
                 GROUP BY sku""", (until, *atp.keys()))
    for r in rows:
        atp[r["sku"]] = atp.get(r["sku"], 0) + r["s"]
    return atp


def calculate_allocation(order_no: str) -> dict:
    """단일 주문의 라인별 할당 가능량(현재 가용재고 기준, 독립 관점)."""
    lines = q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (order_no,))
    if not lines:
        return {"order_no": order_no, "error": "주문 라인 없음"}
    avail = _available_map([l["sku"] for l in lines])
    remaining = dict(avail)
    out = []
    for l in lines:
        req, have = l["qty"], remaining.get(l["sku"], 0)
        alloc = min(req, have)
        remaining[l["sku"]] = have - alloc
        out.append({"sku": l["sku"], "requested": req, "available": avail.get(l["sku"], 0),
                    "allocatable": alloc, "shortage": req - alloc})
    short = sum(x["shortage"] for x in out)
    return {"order_no": order_no, "lines": out, "total_shortage": short,
            "fully_allocatable": short == 0}


def scan_allocation(target_date: str | None = None, within_days: int | None = None) -> dict:
    """근미래 납기 출고 주문을 ATP(현재고+입고예정) 풀에 대해 우선순위(고객우선순위→납기)순으로
    할당 시뮬레이션해 각 주문의 충족/결품을 산출한다(읽기전용 '예상 결품' 분석).

    같은 SKU를 여러 주문이 경쟁하면 우선순위가 높은 주문이 먼저 재고를 가져간다.
    범위: target_date 지정 시 해당일, 미지정 시 기준일~기준일+within_days(기본 0=당일).
    """
    ensure_allocation_columns()
    base = date.fromisoformat(settings.base_date)
    sql = ("SELECT order_no, customer_priority, due_datetime FROM outbound_orders "
           "WHERE status IN ('PLANNED','ALLOCATED')")
    params: tuple = ()
    if target_date:
        sql += " AND substr(due_datetime,1,10)=?"
        params = (target_date,)
        until = target_date
    else:
        wd = within_days if within_days is not None else 0  # 기본: 기준일 당일
        until = (base + timedelta(days=wd)).isoformat()
        sql += " AND substr(due_datetime,1,10)<=?"
        params = (until,)
    sql += " ORDER BY customer_priority ASC, due_datetime ASC"
    orders = q(sql, params)

    pool = _atp_map([r["sku"] for r in q("SELECT DISTINCT sku FROM outbound_order_lines")], until)
    results, shortage_orders, shortage_sku = [], [], {}
    for o in orders:
        o_req = o_alloc = o_short = 0
        for l in q("SELECT sku, qty FROM outbound_order_lines WHERE order_no=?", (o["order_no"],)):
            have = pool.get(l["sku"], 0)
            alloc = min(l["qty"], have)
            pool[l["sku"]] = have - alloc
            o_req += l["qty"]
            o_alloc += alloc
            sh = l["qty"] - alloc
            if sh > 0:
                o_short += sh
                shortage_sku[l["sku"]] = shortage_sku.get(l["sku"], 0) + sh
        rec = {"order_no": o["order_no"], "customer_priority": o["customer_priority"],
               "due_datetime": o["due_datetime"], "requested": o_req, "allocatable": o_alloc,
               "shortage": o_short, "status": "SHORT" if o_short > 0 else "ALLOCATABLE"}
        results.append(rec)
        if o_short > 0:
            shortage_orders.append(rec)
    return {"orders": results, "shortage_orders": shortage_orders,
            "shortage_sku": [{"sku": k, "shortage": v}
                             for k, v in sorted(shortage_sku.items(), key=lambda x: -x[1])],
            "shortage_order_count": len(shortage_orders),
            "actionable_order_count": len(results)}


def expected_shortage_count(target_date: str | None = None) -> int:
    return scan_allocation(target_date)["shortage_order_count"]


def apply_allocation(order_no: str) -> dict:
    """주문에 할당을 확정 기록(승인된 draft 실행용). 라인별 allocated_qty/line_status,
    주문 status='ALLOCATED' 갱신. 결품이 있으면 해당 라인은 PARTIAL."""
    ensure_allocation_columns()
    calc = calculate_allocation(order_no)
    if calc.get("error"):
        return calc
    all_full = True
    conn = get_connection()
    try:
        for ln in calc["lines"]:
            ls = "ALLOCATED" if ln["shortage"] == 0 else "PARTIAL"
            if ln["shortage"] > 0:
                all_full = False
            conn.execute("UPDATE outbound_order_lines SET allocated_qty=?, line_status=? "
                         "WHERE order_no=? AND sku=?", (ln["allocatable"], ls, order_no, ln["sku"]))
        conn.execute("UPDATE outbound_orders SET status='ALLOCATED' WHERE order_no=?", (order_no,))
        conn.commit()
    finally:
        conn.close()
    return {"order_no": order_no, "order_status": "ALLOCATED", "fully_allocated": all_full,
            "total_shortage": calc["total_shortage"], "lines": calc["lines"]}
