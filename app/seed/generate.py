"""시드 데이터 생성기 (docs/05_SEED_DATA_DESIGN.md 기준).

핵심 원칙(멘토 피드백):
- 일관성: locations.occupied_qty == 해당 Location inventory.qty 합계
- 보관조건 매칭: inventory는 product.storage_type == zone.storage_type 인 Location에만
- 필수 시나리오: 동일SKU 적치(INB003→L-A-001), 피킹(ORD001~004), 출고확정(ORD010),
  병목(특정일 출고 과밀), 재고리스크(SKU_A001 증가추세 HIGH / SKU_A005 LOW)

현실화(C 범위):
- 과거 반년(HISTORY_DAYS) 수요 이력 — 곱셈형 모델(기저×트렌드×요일×계절×Poisson)
- 과거 SHIPPED 출고 이력 = demand_history와 일·SKU 합계 정합 + 정시/지연(정시율 KPI)
- 과거 STOCKED 입고 이력(적치완료율 KPI), 과거 작업 로그(picking/stocking)
- 제품 단가·부피·무게, 유통기한(shelf_life), 재고 상태 다양화(HOLD/QC/DAMAGED)
- 고객 마스터, SKU 롱테일 확대

사용(앱 디렉토리에서):
    python -m seed.generate          # DB 재생성 + 시드 적재
"""
import math
import random
from datetime import date, datetime, time, timedelta

import numpy as np

from db.database import get_connection, init_db

SEED = 42
BASE_DATE = date(2026, 6, 15)            # '오늘'
BASE_DT = datetime(2026, 6, 15, 10, 20)  # 피킹 시나리오 기준 현재시각

HISTORY_DAYS = 180                       # 과거 수요/주문 이력 길이(반년)
N_SKUS = 150                             # 전체 SKU 수(롱테일 포함)
N_CUSTOMERS = 30
WEEKDAY_FACTOR = [1.05, 1.10, 1.05, 1.00, 1.10, 0.60, 0.40]  # Mon..Sun (주말↓)

RNG = np.random.default_rng(SEED)        # 대량 데이터(수요/주문/입고)용 결정적 스트림

# --- Zone 구성: 3x3 그리드 ---
ZONES = [
    ("ZONE_A", "A-입구(일반)", "NORMAL", 10.0, 1, 12),
    ("ZONE_B", "B-일반", "NORMAL", 15.0, 2, 11),
    ("ZONE_C", "C-일반", "NORMAL", 20.0, 3, 11),
    ("ZONE_D", "D-일반", "NORMAL", 25.0, 3, 11),
    ("ZONE_E", "E-냉장", "COLD", 30.0, 4, 11),
    ("ZONE_F", "F-냉장", "COLD", 35.0, 4, 11),
    ("ZONE_G", "G-일반", "NORMAL", 40.0, 5, 11),
    ("ZONE_H", "H-일반", "NORMAL", 45.0, 4, 11),
    ("ZONE_I", "I-저회전/보관", "NORMAL", 55.0, 5, 11),
]
LOC_CAPACITY = 100

# --- 필수 테스트 SKU: (sku, name, cat, storage, fast_moving, safety_stock, pattern, base_demand) ---
# base_demand: 위험등급 불변식 보존용 기저 일수요(A001 증가→HIGH, A005 감소+재고200→LOW)
REQUIRED_SKUS = [
    ("SKU_A001", "A제품-001", "GEN", "NORMAL", 0, 30, "increasing", 20),
    ("SKU_A002", "A제품-002", "GEN", "NORMAL", 0, 20, "stable", 7),
    ("SKU_A003", "A제품-003", "GEN", "NORMAL", 1, 25, "stable", 6),
    ("SKU_A004", "A제품-004", "GEN", "NORMAL", 0, 20, "noisy", 5),
    ("SKU_A005", "A제품-005", "GEN", "NORMAL", 0, 15, "decreasing", 6),
    ("SKU_A006", "A제품-006(체화)", "GEN", "NORMAL", 0, 10, "stable", 0),  # 무동 체화 시연
    ("SKU_A007", "A제품-007(보충)", "GEN", "NORMAL", 1, 10, "stable", 10),  # 피킹면 보충 시연
    ("SKU_C001", "냉장-001", "COLD", "COLD", 0, 15, "stable", 4),
]
DEAD_DEMO_SKU = "SKU_A006"               # 최근 무출고(체화) 시연용 SKU
# 피킹면(PICK) 부족 + 보관(RESERVE) 보유 → 보충 시연용 SKU(아래 preset로 배치)
DEMAND_PATTERNS = ["increasing", "stable", "decreasing", "seasonal", "noisy"]


def _d(d: date) -> str:
    return d.isoformat()


def _dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def _unit_cost(st: str) -> float:
    if st == "COLD":
        return round(float(RNG.uniform(8000, 30000)), -2)
    return round(float(RNG.uniform(2000, 15000)), -2)


def _vol_wt() -> tuple[float, float]:
    return round(float(RNG.uniform(0.2, 3.5)), 2), round(float(RNG.uniform(0.2, 5.0)), 2)


# ---------- 제품 ----------
def gen_products():
    products, storage_by_sku, pattern_by_sku, required_base = [], {}, {}, {}
    for sku, name, cat, st, fm, ss, pat, base in REQUIRED_SKUS:
        vol, wt = _vol_wt()
        products.append(dict(sku=sku, product_name=name, category=cat, storage_type=st,
                             unit="EA", volume=vol, weight=wt, fast_moving_flag=fm,
                             safety_stock=ss, shelf_life_managed=1 if st != "NORMAL" else 0,
                             unit_cost=_unit_cost(st)))
        storage_by_sku[sku] = st
        pattern_by_sku[sku] = pat
        required_base[sku] = base
    for i in range(len(REQUIRED_SKUS) + 1, N_SKUS + 1):
        r = random.random()
        st = "COLD" if r < 0.15 else "NORMAL"      # 냉장 ≈15%, 나머지 일반(냉동 폐지)
        fm = 1 if random.random() < 0.10 else 0     # 고회전 ≈ 전체의 10%
        sku = f"SKU_G{i:03d}"
        vol, wt = _vol_wt()
        products.append(dict(sku=sku, product_name=f"일반-{i:03d}", category="GEN",
                             storage_type=st, unit="EA", volume=vol, weight=wt,
                             fast_moving_flag=fm, safety_stock=random.randint(10, 40),
                             shelf_life_managed=1 if st != "NORMAL" else 0, unit_cost=_unit_cost(st)))
        storage_by_sku[sku] = st
        pattern_by_sku[sku] = random.choice(DEMAND_PATTERNS)
    return products, storage_by_sku, pattern_by_sku, required_base


# ---------- 고객 마스터 ----------
def gen_customers() -> list[dict]:
    regions = ["수도권", "영남", "호남", "충청", "강원"]
    return [dict(customer_id=f"C{i:02d}", customer_name=f"거래처-{i:02d}",
                 priority=int(RNG.integers(1, 6)), region=random.choice(regions))
            for i in range(1, N_CUSTOMERS + 1)]


def gen_zones() -> list[dict]:
    return [dict(zone_id=zid, zone_name=name, storage_type=st, distance_from_gate=dist,
                 picking_priority=pp, max_capacity=n * LOC_CAPACITY, active_flag=1)
            for zid, name, st, dist, pp, n in ZONES]


def gen_locations():
    rows, zone_of = [], {}
    for zid, _, st, _, _, n in ZONES:
        letter = zid.split("_")[1]
        for i in range(1, n + 1):
            loc_id = f"L-{letter}-{i:03d}"
            role = "PICK" if i == 1 else "RESERVE"  # 존마다 첫 로케이션이 피킹면
            rows.append(dict(location_id=loc_id, zone_id=zid, location_name=loc_id,
                             capacity=LOC_CAPACITY, occupied_qty=0, available_flag=1,
                             location_role=role, x_coord=0.0, y_coord=0.0))
            zone_of[loc_id] = (zid, st)
    return rows, zone_of


# ---------- 재고 (보관조건·일관성 + 유통기한·상태 다양화) ----------
def _shelf_life_days(st: str) -> int:
    return int(RNG.integers(20, 60)) if st == "COLD" else int(RNG.integers(150, 365))


def gen_inventory(products, storage_by_sku, locations, zone_of):
    required_set = {s[0] for s in REQUIRED_SKUS}
    shelf_managed = {p["sku"] for p in products if p["shelf_life_managed"]}
    skus_by_storage = {"NORMAL": [], "COLD": []}
    for p in products:
        if p["sku"] in required_set:
            continue
        skus_by_storage[p["storage_type"]].append(p["sku"])
    for st in skus_by_storage:
        if not skus_by_storage[st]:
            skus_by_storage[st] = [p["sku"] for p in products if p["storage_type"] == st]

    inv_rows = []
    occupied = {loc["location_id"]: 0 for loc in locations}
    lot_seq = 1

    def _expiry(sku, inbound_date_str):
        if sku not in shelf_managed:
            return None
        return _d(date.fromisoformat(inbound_date_str) + timedelta(days=_shelf_life_days(storage_by_sku[sku])))

    # 1) 필수 시나리오 재고 사전 배치 (전부 AVAILABLE 유지)
    preset = [
        ("L-A-001", "SKU_A002", 60),   # 동일SKU 적치(INB003 대상)
        ("L-A-002", "SKU_A003", 80),   # 고회전, 입구 근처
        ("L-B-001", "SKU_A001", 120),  # 재고부족 위험(증가추세 → HIGH)
        ("L-B-003", "SKU_A004", 30),   # 3일 뒤 입고예정(INB004)으로 회복
        ("L-B-002", "SKU_A005", 200),  # 안정 LOW
        ("L-E-001", "SKU_C001", 50),   # 냉장 → ZONE_E(COLD)
        ("L-I-001", "SKU_A006", 90),   # 체화 시연(무출고) → ZONE_I(저회전/보관)
        ("L-D-001", "SKU_A007", 8),    # 보충 시연: 피킹면(PICK, ZONE_D) 재고 부족
        ("L-D-003", "SKU_A007", 100),  # 보충 시연: 보관(RESERVE, ZONE_D)에 보충용 재고 보유
    ]
    preset_locs: set = set()
    for loc_id, sku, qty in preset:
        remain, target_loc = qty, loc_id
        while remain > 0:
            free = LOC_CAPACITY - occupied[target_loc]
            if free <= 0:
                target_loc = _next_free_same_zone(target_loc, zone_of, occupied)
                continue
            q = min(remain, free)
            ibd = _d(BASE_DATE - timedelta(days=random.randint(5, 30)))
            inv_rows.append(dict(sku=sku, lot_no=f"LOT{lot_seq:04d}", location_id=target_loc,
                                 qty=q, inbound_date=ibd, expiry_date=_expiry(sku, ibd), status="AVAILABLE"))
            occupied[target_loc] += q
            preset_locs.add(target_loc)
            lot_seq += 1
            remain -= q
            if remain > 0:
                target_loc = _next_free_same_zone(target_loc, zone_of, occupied)

    # 2) 나머지 Location 랜덤 채움 (보관조건 매칭, 일부 상태 다양화)
    for loc in locations:
        loc_id = loc["location_id"]
        if loc_id in preset_locs:
            continue
        zid, st = zone_of[loc_id]
        free = LOC_CAPACITY - occupied[loc_id]
        if free <= 0:
            continue
        if zid == "ZONE_A":
            ratio = random.uniform(0.85, 0.97)
        elif zid == "ZONE_I":
            ratio = random.uniform(0.10, 0.40)
        else:
            ratio = random.uniform(0.40, 0.75)
        to_fill = min(max(0, int(LOC_CAPACITY * ratio) - occupied[loc_id]), free)
        if to_fill <= 0:
            continue
        candidates = skus_by_storage[st]
        for q in _split(to_fill, random.randint(1, 3)):
            if q <= 0:
                continue
            sku = random.choice(candidates)
            ibd = _d(BASE_DATE - timedelta(days=random.randint(1, 45)))
            rr = random.random()  # 상태 다양화(가용 92% / HOLD / QC / DAMAGED)
            status = "AVAILABLE" if rr < 0.92 else "HOLD" if rr < 0.96 else "QC" if rr < 0.98 else "DAMAGED"
            inv_rows.append(dict(sku=sku, lot_no=f"LOT{lot_seq:04d}", location_id=loc_id,
                                 qty=q, inbound_date=ibd, expiry_date=_expiry(sku, ibd), status=status))
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


# ---------- 입고 (현재 시나리오 + 과거 STOCKED 이력) ----------
def gen_inbound(products):
    rows = []
    rows.append(dict(inbound_no="INB003", sku="SKU_A002", qty=40,
                     expected_date=_d(BASE_DATE), received_datetime=_dt(datetime(2026, 6, 15, 9, 0)),
                     status="RECEIVED", supplier="SUP01"))
    rows.append(dict(inbound_no="INB004", sku="SKU_A004", qty=100,
                     expected_date=_d(BASE_DATE + timedelta(days=3)), received_datetime=None,
                     status="PLANNED", supplier="SUP02"))
    skus = [p["sku"] for p in products]
    for i in range(5, 53):  # 현재 구간 입고 48건
        r = random.random()
        if r < 0.2:
            exp = BASE_DATE - timedelta(days=random.randint(1, 3)); status = "PLANNED"; recv = None
        elif r < 0.5:
            exp = BASE_DATE - timedelta(days=random.randint(1, 5)); status = "RECEIVED"
            recv = _dt(datetime.combine(exp, time(9, 0)))
        else:
            exp = BASE_DATE + timedelta(days=random.randint(0, 7)); status = "PLANNED"; recv = None
        rows.append(dict(inbound_no=f"INB{i:03d}", sku=random.choice(skus),
                         qty=random.randint(20, 150), expected_date=_d(exp),
                         received_datetime=recv, status=status, supplier=f"SUP{random.randint(1,5):02d}"))

    # 과거 STOCKED 입고 이력(보충) — 고회전은 잦게, 일반은 드물게
    ih = 1
    past_stocked = []
    for p in products:
        spacing = 14 if p["fast_moving_flag"] else 35
        day = HISTORY_DAYS - int(RNG.integers(0, spacing))
        while day > 7:
            exp = BASE_DATE - timedelta(days=day)
            recv = datetime.combine(exp, time(9, 0)) + timedelta(hours=int(RNG.integers(0, 6)))
            row = dict(inbound_no=f"IH{ih:06d}", sku=p["sku"], qty=int(RNG.integers(40, 200)),
                       expected_date=_d(exp), received_datetime=_dt(recv), status="STOCKED",
                       supplier=f"SUP{random.randint(1,5):02d}")
            rows.append(row)
            past_stocked.append(row)
            ih += 1
            day -= spacing + int(RNG.integers(-3, 4))
    return rows, past_stocked


# ---------- 출고 (현재 시나리오 + 과거 SHIPPED 이력, demand_map과 정합) ----------
def gen_outbound(products, customers, demand_map):
    orders, lines = [], []
    line_seq = 1
    normal_skus = [p["sku"] for p in products if p["storage_type"] == "NORMAL"]
    fast_skus = [p["sku"] for p in products if p["fast_moving_flag"] and p["storage_type"] == "NORMAL"]
    order_pool = normal_skus + fast_skus * 4   # 고회전 SKU 출고 빈도 ↑(가중)

    def add_line(order_no, sku, qty, line_status="PLANNED", allocated=0, picked=0, shipped=0):
        nonlocal line_seq
        lines.append(dict(line_id=line_seq, order_no=order_no, sku=sku, qty=qty,
                          allocated_qty=allocated, picked_qty=picked, shipped_qty=shipped,
                          line_status=line_status))
        line_seq += 1

    def add_order(order_no, cust, pri, due, status, shipped=None):
        orders.append(dict(order_no=order_no, customer_id=cust, customer_priority=pri,
                           due_datetime=_dt(due), shipped_datetime=_dt(shipped) if shipped else None,
                           status=status))

    # 필수 피킹 시나리오 (기준시각 10:20)
    add_order("ORD001", "C01", 1, datetime(2026, 6, 15, 11, 0), "PLANNED"); add_line("ORD001", "SKU_A003", 20)
    add_order("ORD002", "C02", 5, datetime(2026, 6, 15, 13, 0), "PLANNED")
    add_line("ORD002", "SKU_A002", 15); add_line("ORD002", "SKU_A003", 10)
    add_order("ORD003", "C03", 1, datetime(2026, 6, 15, 13, 0), "PLANNED"); add_line("ORD003", "SKU_A005", 30)
    add_order("ORD004", "C04", 1, datetime(2026, 6, 15, 15, 0), "PLANNED"); add_line("ORD004", "SKU_A001", 10)
    # 결품(할당 부족) 시연용 — 가용재고를 크게 초과하는 요청
    add_order("ORD005", "C05", 1, datetime(2026, 6, 15, 16, 0), "PLANNED"); add_line("ORD005", "SKU_A001", 300)
    add_order("ORD010", "C10", 2, datetime(2026, 6, 15, 12, 0), "SHIPPING_PENDING"); add_line("ORD010", "SKU_A002", 20)

    # 나머지 현재 구간 + 병목 시나리오 (BASE_DATE+1 오전 과밀)
    bottleneck_day = BASE_DATE + timedelta(days=1)
    for i in range(11, 106):
        if i <= 40:
            due = datetime.combine(bottleneck_day, time(random.choice([9, 10, 11]), random.choice([0, 30])))
        else:
            day = BASE_DATE + timedelta(days=random.randint(0, 5))
            due = datetime.combine(day, time(random.randint(9, 17), random.choice([0, 30])))
        add_order(f"ORD{i:03d}", f"C{random.randint(1, N_CUSTOMERS):02d}", random.randint(1, 5), due, "PLANNED")
        for _ in range(random.randint(1, 3)):
            add_line(f"ORD{i:03d}", random.choice(order_pool), random.randint(5, 40))

    # 과거 SHIPPED 이력 — demand_map(일·SKU 합계)을 주문으로 묶음(정합) + 정시/지연
    shipped_orders = []
    seq = 1
    for day_off in range(HISTORY_DAYS, 0, -1):
        d = BASE_DATE - timedelta(days=day_off)
        items = [(sku, qty) for sku, qty in demand_map.get(d.isoformat(), {}).items() if qty > 0]
        if not items:
            continue
        RNG.shuffle(items)
        i = 0
        while i < len(items):
            chunk = items[i:i + int(RNG.integers(1, 6))]
            i += len(chunk)
            cust = customers[int(RNG.integers(0, len(customers)))]
            due = datetime.combine(d, time(int(RNG.integers(9, 18)), int(RNG.choice([0, 15, 30, 45]))))
            if RNG.random() < 0.85:  # 정시 85%
                ship = due - timedelta(minutes=int(RNG.integers(5, 120)))
            else:
                ship = due + timedelta(minutes=int(RNG.integers(20, 300)))
            ono = f"OH{seq:06d}"; seq += 1
            add_order(ono, cust["customer_id"], cust["priority"], due, "SHIPPED", ship)
            shipped_orders.append(ono)
            for sku, qty in chunk:  # 과거 출고 = 전량 할당·피킹·출고 완료
                add_line(ono, sku, int(qty), "SHIPPED", int(qty), int(qty), int(qty))
    return orders, lines, shipped_orders


# ---------- 수요 이력 (곱셈형 모델 + Poisson) ----------
def _base_demand(p, required_base):
    if p["sku"] in required_base:
        return float(required_base[p["sku"]])
    if p["fast_moving_flag"]:
        return float(RNG.uniform(10, 22))
    return float(max(0.6, RNG.gamma(1.8, 2.3)))   # 롱테일(저회전 다수)


def gen_demand_history(products, pattern_by_sku, required_base):
    """일수요 = 기저(SKU별) × 트렌드(완만) × 요일 × 계절 × Poisson 노이즈."""
    rows, demand_map = [], {}
    for p in products:
        sku, pat = p["sku"], pattern_by_sku[p["sku"]]
        base = _base_demand(p, required_base)
        phase = float(RNG.uniform(0, 2 * math.pi))
        season_amp = 0.35 if pat == "seasonal" else 0.10
        for k in range(HISTORY_DAYS):
            d = BASE_DATE - timedelta(days=HISTORY_DAYS - k)
            if sku == DEAD_DEMO_SKU:                  # 체화 시연: 전 기간 무출고
                rows.append(dict(sku=sku, demand_date=_d(d), shipped_qty=0))
                demand_map.setdefault(d.isoformat(), {})[sku] = 0
                continue
            frac = k / HISTORY_DAYS
            trend = 1 + 0.5 * frac if pat == "increasing" else 1 - 0.4 * frac if pat == "decreasing" else 1.0
            season = 1 + season_amp * math.sin(2 * math.pi * k / 7 + phase)
            mean = base * trend * season * WEEKDAY_FACTOR[d.weekday()]
            if pat == "noisy":
                mean *= float(RNG.uniform(0.4, 1.9))
            qty = int(RNG.poisson(max(0.05, mean)))
            rows.append(dict(sku=sku, demand_date=_d(d), shipped_qty=qty))
            demand_map.setdefault(d.isoformat(), {})[sku] = qty
    return rows, demand_map


def gen_shipping_pending(orders) -> list[dict]:
    pending = ["ORD010"] + [o["order_no"] for o in orders
                            if o["status"] == "PLANNED" and o["order_no"].startswith("ORD")][:19]
    rows = []
    for pid, ono in enumerate(pending[:20], 1):
        rows.append(dict(pending_id=pid, order_no=ono,
                         ready_datetime=_dt(datetime(2026, 6, 15, random.randint(9, 14), 0)),
                         status="PENDING", confirmed_at=None))
    return rows


# ---------- 과거 작업 로그(picking/stocking COMPLETED) ----------
def gen_past_tasks(past_stocked, shipped_orders, locations):
    normal_locs = [loc["location_id"] for loc in locations if loc["location_id"].startswith(("L-A", "L-B", "L-C"))]
    stk_rows, pck_rows = [], []
    for n, inb in enumerate(past_stocked, 1):
        recv = datetime.strptime(inb["received_datetime"], "%Y-%m-%d %H:%M")
        stk_rows.append(dict(stocking_task_id=f"STKH{n:06d}", inbound_no=inb["inbound_no"],
                             location_id=normal_locs[n % len(normal_locs)], qty=inb["qty"],
                             status="STOCKED", completed_at=_dt(recv + timedelta(hours=1))))
    for n, ono in enumerate(shipped_orders, 1):
        if n % 5 != 0:   # 20% 표본만 작업 로그화
            continue
        pck_rows.append(dict(picking_task_id=f"PCKH{n:06d}", order_no=ono,
                             estimated_minutes=int(RNG.integers(8, 40)), status="COMPLETED"))
    return stk_rows, pck_rows


def gen_resources() -> list[dict]:
    rows = []
    for i in range(1, 4):
        rows.append(dict(resource_id=f"W-{i:02d}", resource_type="WORKER",
                         shift_start="08:00", shift_end="17:00", active_flag=1))
    for i in range(1, 3):
        rows.append(dict(resource_id=f"F-{i:02d}", resource_type="FORKLIFT",
                         shift_start="08:00", shift_end="17:00", active_flag=1))
    return rows


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
    global RNG
    random.seed(SEED)
    RNG = np.random.default_rng(SEED)
    init_db(reset=reset)

    products, storage_by_sku, pattern_by_sku, required_base = gen_products()
    customers = gen_customers()
    zones = gen_zones()
    locations, zone_of = gen_locations()
    inventory = gen_inventory(products, storage_by_sku, locations, zone_of)
    demand, demand_map = gen_demand_history(products, pattern_by_sku, required_base)
    inbound, past_stocked = gen_inbound(products)
    orders, lines, shipped_orders = gen_outbound(products, customers, demand_map)
    pending = gen_shipping_pending(orders)
    stk_tasks, pck_tasks = gen_past_tasks(past_stocked, shipped_orders, locations)
    resources = gen_resources()
    ptp = gen_process_time_params()

    conn = get_connection()
    try:
        _insert(conn, "products", products)
        _insert(conn, "customers", customers)
        _insert(conn, "zones", zones)
        _insert(conn, "locations", locations)
        _insert(conn, "inventory", inventory)
        _insert(conn, "inbound_orders", inbound)
        _insert(conn, "outbound_orders", orders)
        _insert(conn, "outbound_order_lines", lines)
        _insert(conn, "demand_history", demand)
        _insert(conn, "shipping_pending", pending)
        _insert(conn, "stocking_tasks", stk_tasks)
        _insert(conn, "picking_tasks", pck_tasks)
        _insert(conn, "resources", resources)
        _insert(conn, "process_time_params", ptp)
        conn.commit()
    finally:
        conn.close()

    return dict(products=len(products), customers=len(customers), zones=len(zones),
                locations=len(locations), inventory=len(inventory), inbound=len(inbound),
                outbound=len(orders), lines=len(lines), demand=len(demand), pending=len(pending),
                stocking_tasks=len(stk_tasks), picking_tasks=len(pck_tasks),
                resources=len(resources), process_time_params=len(ptp))


if __name__ == "__main__":
    counts = generate(reset=True)
    print("Seed loaded:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
