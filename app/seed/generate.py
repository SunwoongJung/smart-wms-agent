"""시드 데이터 생성기 (docs/05_SEED_DATA_DESIGN.md 기준).

핵심 원칙(멘토 피드백):
- 일관성: locations.occupied_qty == 해당 Location inventory.qty 합계
- 보관조건 매칭: inventory는 product.storage_type == zone.storage_type 인 Location에만
- 필수 시나리오: 동일SKU 적치(INB003→L-A-001), 피킹(ORD001~004), 출고확정(ORD010),
  병목(특정일 출고 과밀), 재고리스크(SKU_A001 증가추세 HIGH)

사용(앱 디렉토리에서):
    python -m seed.generate          # DB 재생성 + 시드 적재
"""
import random
from datetime import date, datetime, timedelta

from db.database import get_connection, init_db

SEED = 42
BASE_DATE = date(2026, 6, 15)          # '오늘'
BASE_DT = datetime(2026, 6, 15, 10, 20)  # 피킹 시나리오 기준 현재시각

# --- Zone 구성: 3x3 그리드 (1행 A,B,C / 2행 D,E,F / 3행 G,H,I) ---
ZONES = [
    # zone_id, name, storage_type, distance, picking_priority, n_locations
    ("ZONE_A", "A-고회전 일반", "NORMAL", 10.0, 1, 12),
    ("ZONE_B", "B-일반", "NORMAL", 15.0, 2, 11),
    ("ZONE_C", "C-일반", "NORMAL", 20.0, 3, 11),
    ("ZONE_D", "D-일반", "NORMAL", 25.0, 3, 11),
    ("ZONE_E", "E-냉장", "COLD", 30.0, 4, 11),
    ("ZONE_F", "F-냉장", "COLD", 35.0, 4, 11),
    ("ZONE_G", "G-냉동", "FROZEN", 40.0, 5, 11),
    ("ZONE_H", "H-일반", "NORMAL", 45.0, 4, 11),
    ("ZONE_I", "I-저회전/보관", "NORMAL", 55.0, 5, 11),
]
LOC_CAPACITY = 100

# --- 필수 테스트 SKU (docs/05 §3) ---
REQUIRED_SKUS = [
    # sku, name, category, storage_type, fast_moving, safety_stock, demand_pattern
    ("SKU_A001", "A제품-001", "GEN", "NORMAL", 0, 30, "increasing"),   # HIGH 위험
    ("SKU_A002", "A제품-002", "GEN", "NORMAL", 0, 20, "stable"),       # 동일SKU 적치
    ("SKU_A003", "A제품-003", "GEN", "NORMAL", 1, 25, "stable"),       # 고회전
    ("SKU_A004", "A제품-004", "GEN", "NORMAL", 0, 20, "noisy"),        # 입고예정 존재
    ("SKU_A005", "A제품-005", "GEN", "NORMAL", 0, 15, "decreasing"),   # 안정 LOW
    ("SKU_C001", "냉장-001", "COLD", "COLD", 0, 15, "stable"),         # 냉장
    ("SKU_F001", "냉동-001", "FROZEN", "FROZEN", 0, 10, "stable"),     # 냉동
]
DEMAND_PATTERNS = ["increasing", "stable", "decreasing", "seasonal", "noisy"]


def _d(d: date) -> str:
    return d.isoformat()


def _dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def gen_products() -> list[dict]:
    products = []
    storage_by_sku = {}
    pattern_by_sku = {}
    # 필수 SKU
    for sku, name, cat, st, fm, ss, pat in REQUIRED_SKUS:
        products.append(dict(sku=sku, product_name=name, category=cat, storage_type=st,
                             unit="EA", volume=1.0, weight=1.0, fast_moving_flag=fm,
                             safety_stock=ss, shelf_life_managed=1 if st != "NORMAL" else 0))
        storage_by_sku[sku] = st
        pattern_by_sku[sku] = pat
    # 나머지 SKU로 50개 채움 (대부분 NORMAL, 일부 COLD/FROZEN)
    for i in range(len(REQUIRED_SKUS) + 1, 51):
        r = random.random()
        st = "COLD" if r < 0.15 else "FROZEN" if r < 0.25 else "NORMAL"
        fm = 1 if random.random() < 0.25 else 0
        sku = f"SKU_G{i:03d}"
        products.append(dict(sku=sku, product_name=f"일반-{i:03d}", category="GEN",
                             storage_type=st, unit="EA", volume=1.0, weight=1.0,
                             fast_moving_flag=fm, safety_stock=random.randint(10, 40),
                             shelf_life_managed=1 if st != "NORMAL" else 0))
        storage_by_sku[sku] = st
        pattern_by_sku[sku] = random.choice(DEMAND_PATTERNS)
    return products, storage_by_sku, pattern_by_sku


def gen_zones() -> list[dict]:
    rows = []
    for zid, name, st, dist, pp, n in ZONES:
        rows.append(dict(zone_id=zid, zone_name=name, storage_type=st,
                         distance_from_gate=dist, picking_priority=pp,
                         max_capacity=n * LOC_CAPACITY, active_flag=1))
    return rows


def gen_locations() -> tuple[list[dict], dict]:
    rows = []
    zone_of = {}
    for zid, _, st, _, _, n in ZONES:
        letter = zid.split("_")[1]
        for i in range(1, n + 1):
            loc_id = f"L-{letter}-{i:03d}"
            rows.append(dict(location_id=loc_id, zone_id=zid, location_name=loc_id,
                             capacity=LOC_CAPACITY, occupied_qty=0, available_flag=1,
                             x_coord=0.0, y_coord=0.0))
            zone_of[loc_id] = (zid, st)
    return rows, zone_of


def gen_inventory(products, storage_by_sku, locations, zone_of):
    """Location 중심으로 재고를 채우고 occupied_qty를 일관되게 설정."""
    # 랜덤 채움은 generic SKU(SKU_G*)만 사용 — 시나리오 SKU(A001 등)는 preset 수량 그대로 유지
    required_set = {s[0] for s in REQUIRED_SKUS}
    skus_by_storage = {"NORMAL": [], "COLD": [], "FROZEN": []}
    for p in products:
        if p["sku"] in required_set:
            continue
        skus_by_storage[p["storage_type"]].append(p["sku"])
    # 폴백: 특정 보관조건 generic SKU가 없으면 전체에서 채움
    for st in skus_by_storage:
        if not skus_by_storage[st]:
            skus_by_storage[st] = [p["sku"] for p in products if p["storage_type"] == st]

    inv_rows = []
    occupied = {loc["location_id"]: 0 for loc in locations}
    lot_seq = 1

    # 1) 필수 시나리오 재고 사전 배치 (docs/05 §3·§7)
    preset = [
        ("L-A-001", "SKU_A002", 60),   # 동일SKU 적치(INB003 대상)
        ("L-A-002", "SKU_A003", 80),   # 고회전, 입구 근처
        ("L-B-001", "SKU_A001", 120),  # 재고부족 위험, 현재고 120 (증가추세 → HIGH)
        ("L-B-003", "SKU_A004", 30),   # 재고 부족하나 3일 뒤 입고예정(INB004)으로 회복
        ("L-B-002", "SKU_A005", 200),  # 안정 LOW (2 lot로 분할 배치)
        ("L-E-001", "SKU_C001", 50),   # 냉장 → ZONE_E(COLD)
        ("L-G-001", "SKU_F001", 40),   # 냉동 → ZONE_G(FROZEN)
    ]
    preset_locs: set = set()  # 사전배치 Location은 랜덤 채움에서 제외(동일SKU 입고 여유 보존)
    for loc_id, sku, qty in preset:
        remain = qty
        target_loc = loc_id
        while remain > 0:
            free = LOC_CAPACITY - occupied[target_loc]
            if free <= 0:
                target_loc = _next_free_same_zone(target_loc, zone_of, occupied)
                continue
            q = min(remain, free)
            inv_rows.append(dict(sku=sku, lot_no=f"LOT{lot_seq:04d}", location_id=target_loc,
                                 qty=q, inbound_date=_d(BASE_DATE - timedelta(days=random.randint(5, 30))),
                                 expiry_date=None, status="AVAILABLE"))
            occupied[target_loc] += q
            preset_locs.add(target_loc)
            lot_seq += 1
            remain -= q
            if remain > 0:  # A005(200) 등 분할: 같은 Zone의 빈 Location으로
                target_loc = _next_free_same_zone(target_loc, zone_of, occupied)

    # 2) 나머지 Location 랜덤 채움 (보관조건 매칭, ZONE_A는 포화에 가깝게)
    for loc in locations:
        loc_id = loc["location_id"]
        if loc_id in preset_locs:  # 사전배치 Location은 그대로 유지
            continue
        zid, st = zone_of[loc_id]
        free = LOC_CAPACITY - occupied[loc_id]
        if free <= 0:
            continue
        if zid == "ZONE_A":
            ratio = random.uniform(0.85, 0.97)   # 포화 시나리오
        elif zid == "ZONE_I":
            ratio = random.uniform(0.10, 0.40)   # 저회전/보관 여유
        else:
            ratio = random.uniform(0.40, 0.75)
        target = int(LOC_CAPACITY * ratio)
        to_fill = max(0, target - occupied[loc_id])
        to_fill = min(to_fill, free)
        if to_fill <= 0:
            continue
        candidates = skus_by_storage[st]
        n_lots = random.randint(1, 3)
        parts = _split(to_fill, n_lots)
        for q in parts:
            if q <= 0:
                continue
            sku = random.choice(candidates)
            inv_rows.append(dict(sku=sku, lot_no=f"LOT{lot_seq:04d}", location_id=loc_id,
                                 qty=q, inbound_date=_d(BASE_DATE - timedelta(days=random.randint(1, 45))),
                                 expiry_date=None, status="AVAILABLE"))
            occupied[loc_id] += q
            lot_seq += 1

    for loc in locations:
        loc["occupied_qty"] = occupied[loc["location_id"]]
    return inv_rows


def _next_free_same_zone(loc_id, zone_of, occupied):
    zid, _ = zone_of[loc_id]
    for lid, (z, _) in zone_of.items():
        if z == zid and occupied[lid] < LOC_CAPACITY:
            return lid
    return loc_id


def _split(total: int, n: int) -> list[int]:
    if n <= 1:
        return [total]
    cuts = sorted(random.randint(0, total) for _ in range(n - 1))
    parts, prev = [], 0
    for c in cuts:
        parts.append(c - prev)
        prev = c
    parts.append(total - prev)
    return parts


def gen_inbound(products, storage_by_sku) -> list[dict]:
    rows = []
    # 필수: INB003 = SKU_A002 적치대기(RECEIVED) → L-A-001 동일SKU 추천
    rows.append(dict(inbound_no="INB003", sku="SKU_A002", qty=40,
                     expected_date=_d(BASE_DATE), received_datetime=_dt(datetime(2026, 6, 15, 9, 0)),
                     status="RECEIVED", supplier="SUP01"))
    # SKU_A004 3일 뒤 입고예정 (docs/05 §7)
    rows.append(dict(inbound_no="INB004", sku="SKU_A004", qty=100,
                     expected_date=_d(BASE_DATE + timedelta(days=3)), received_datetime=None,
                     status="PLANNED", supplier="SUP02"))
    skus = [p["sku"] for p in products]
    for i in range(5, 53):  # INB003/004 + 48건 = 50
        # 일부는 지연(expected_date < today, PLANNED), 일부 미래 예정/입고완료
        r = random.random()
        if r < 0.2:
            exp = BASE_DATE - timedelta(days=random.randint(1, 3)); status = "PLANNED"  # 지연
            recv = None
        elif r < 0.5:
            exp = BASE_DATE - timedelta(days=random.randint(1, 5)); status = "RECEIVED"  # 적치대기
            recv = _dt(datetime.combine(exp, datetime.min.time()).replace(hour=9))
        else:
            exp = BASE_DATE + timedelta(days=random.randint(0, 7)); status = "PLANNED"
            recv = None
        rows.append(dict(inbound_no=f"INB{i:03d}", sku=random.choice(skus),
                         qty=random.randint(20, 150), expected_date=_d(exp),
                         received_datetime=recv, status=status, supplier=f"SUP{random.randint(1,5):02d}"))
    return rows


def gen_outbound(products):
    orders, lines = [], []
    line_seq = 1
    normal_skus = [p["sku"] for p in products if p["storage_type"] == "NORMAL"]

    def add_line(order_no, sku, qty):
        nonlocal line_seq
        lines.append(dict(line_id=line_seq, order_no=order_no, sku=sku, qty=qty))
        line_seq += 1

    # 필수 피킹 시나리오 (docs/05 §6), 기준시각 10:20
    orders.append(dict(order_no="ORD001", customer_id="C01", customer_priority=1,
                       due_datetime=_dt(datetime(2026, 6, 15, 11, 0)), status="PLANNED"))
    add_line("ORD001", "SKU_A003", 20)  # ZONE_A
    orders.append(dict(order_no="ORD002", customer_id="C02", customer_priority=5,
                       due_datetime=_dt(datetime(2026, 6, 15, 13, 0)), status="PLANNED"))
    add_line("ORD002", "SKU_A002", 15); add_line("ORD002", "SKU_A003", 10)
    orders.append(dict(order_no="ORD003", customer_id="C03", customer_priority=1,
                       due_datetime=_dt(datetime(2026, 6, 15, 13, 0)), status="PLANNED"))
    add_line("ORD003", "SKU_A005", 30)
    orders.append(dict(order_no="ORD004", customer_id="C04", customer_priority=1,
                       due_datetime=_dt(datetime(2026, 6, 15, 15, 0)), status="PLANNED"))
    add_line("ORD004", "SKU_A001", 10)  # HIGH 위험 SKU 포함

    # 출고확정 시나리오: ORD010 (SHIPPING_PENDING)
    orders.append(dict(order_no="ORD010", customer_id="C10", customer_priority=2,
                       due_datetime=_dt(datetime(2026, 6, 15, 12, 0)), status="SHIPPING_PENDING"))
    add_line("ORD010", "SKU_A002", 20)

    # 나머지 + 병목 시나리오 (BASE_DATE+1 오전에 과밀 배치)
    bottleneck_day = BASE_DATE + timedelta(days=1)
    for i in range(11, 106):  # 5 explicit + 95건 = 100
        if i <= 40:  # 30건을 병목일 09~12시에 몰아넣음 → 작업자 3명 처리 한계 초과
            hh = random.choice([9, 10, 11]); mm = random.choice([0, 30])
            due = datetime.combine(bottleneck_day, datetime.min.time()).replace(hour=hh, minute=mm)
        else:
            day = BASE_DATE + timedelta(days=random.randint(0, 5))
            due = datetime.combine(day, datetime.min.time()).replace(
                hour=random.randint(9, 17), minute=random.choice([0, 30]))
        orders.append(dict(order_no=f"ORD{i:03d}", customer_id=f"C{i:02d}",
                           customer_priority=random.randint(1, 5),
                           due_datetime=_dt(due), status="PLANNED"))
        for _ in range(random.randint(1, 3)):
            add_line(f"ORD{i:03d}", random.choice(normal_skus), random.randint(5, 40))
    return orders, lines


def gen_demand_history(products, pattern_by_sku) -> list[dict]:
    rows = []
    for p in products:
        sku = p["sku"]
        pat = pattern_by_sku[sku]
        base = random.randint(2, 8)  # 현실적 일 수요 (재고 커버일수 확보)
        for day_idx in range(60):
            d = BASE_DATE - timedelta(days=60 - day_idx)
            if pat == "increasing":
                val = base + day_idx * 0.5 + random.gauss(0, 2)
            elif pat == "decreasing":
                val = base + (60 - day_idx) * 0.3 + random.gauss(0, 2)
            elif pat == "seasonal":
                val = base + 5 * (1 + __import__("math").sin(day_idx / 7)) + random.gauss(0, 2)
            elif pat == "noisy":
                val = base + random.gauss(0, 6)
            else:  # stable
                val = base + random.gauss(0, 2)
            rows.append(dict(sku=sku, demand_date=_d(d), shipped_qty=max(0, round(val))))
    return rows


def gen_shipping_pending(orders) -> list[dict]:
    rows = []
    # ORD010 포함, 당일 확정 대상 20건
    pending_orders = ["ORD010"] + [o["order_no"] for o in orders
                                   if o["order_no"] not in ("ORD010",)][:19]
    pid = 1
    for ono in pending_orders[:20]:
        rows.append(dict(pending_id=pid, order_no=ono,
                         ready_datetime=_dt(datetime(2026, 6, 15, random.randint(9, 14), 0)),
                         status="PENDING", confirmed_at=None))
        pid += 1
    return rows


def gen_resources() -> list[dict]:
    return [
        dict(resource_id="W-01", resource_type="WORKER", count=3,
             shift_start="08:00", shift_end="17:00", active_flag=1),
        dict(resource_id="F-01", resource_type="FORKLIFT", count=2,
             shift_start="08:00", shift_end="17:00", active_flag=1),
    ]


def gen_process_time_params() -> list[dict]:
    return [
        dict(stage="INBOUND", distribution="TRIANGULAR", mean_minutes=12, std_minutes=4, min_minutes=6, max_minutes=24),
        dict(stage="STOCKING", distribution="TRIANGULAR", mean_minutes=8, std_minutes=3, min_minutes=4, max_minutes=18),
        dict(stage="PICKING", distribution="LOGNORMAL", mean_minutes=15, std_minutes=5, min_minutes=None, max_minutes=None),
        dict(stage="PACKING_SHIP", distribution="TRIANGULAR", mean_minutes=10, std_minutes=3, min_minutes=5, max_minutes=20),
    ]


def _insert(conn, table: str, rows: list[dict]):
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(r[c] for c in cols) for r in rows])


def generate(reset: bool = True):
    random.seed(SEED)
    init_db(reset=reset)

    products, storage_by_sku, pattern_by_sku = gen_products()
    zones = gen_zones()
    locations, zone_of = gen_locations()
    inventory = gen_inventory(products, storage_by_sku, locations, zone_of)
    inbound = gen_inbound(products, storage_by_sku)
    orders, lines = gen_outbound(products)
    demand = gen_demand_history(products, pattern_by_sku)
    pending = gen_shipping_pending(orders)
    resources = gen_resources()
    ptp = gen_process_time_params()

    conn = get_connection()
    try:
        _insert(conn, "products", products)
        _insert(conn, "zones", zones)
        _insert(conn, "locations", locations)
        _insert(conn, "inventory", inventory)
        _insert(conn, "inbound_orders", inbound)
        _insert(conn, "outbound_orders", orders)
        _insert(conn, "outbound_order_lines", lines)
        _insert(conn, "demand_history", demand)
        _insert(conn, "shipping_pending", pending)
        _insert(conn, "resources", resources)
        _insert(conn, "process_time_params", ptp)
        conn.commit()
    finally:
        conn.close()

    return dict(products=len(products), zones=len(zones), locations=len(locations),
                inventory=len(inventory), inbound=len(inbound), outbound=len(orders),
                lines=len(lines), demand=len(demand), pending=len(pending),
                resources=len(resources), process_time_params=len(ptp))


if __name__ == "__main__":
    counts = generate(reset=True)
    print("Seed loaded:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
