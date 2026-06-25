# 04_DATABASE_DESIGN.md

# Database Design

## 1. 목적
SQLite 기반 POC WMS DB 설계를 정의한다. 입고, 적치, 재고, 출고, 피킹, 출고확정, Forecast, 승인 Workflow를 테스트할 수 있어야 한다.

## 2. Entity 목록
| Entity | 설명 |
|---|---|
| products | SKU 기준정보 |
| zones | 창고 Zone 기준정보 |
| locations | Bin/Location 기준정보 |
| inventory | Location 단위 재고 |
| inbound_orders | 입고예정 및 적치대기 |
| outbound_orders | 출고예정 주문 헤더 |
| outbound_order_lines | 출고예정 주문 라인 (SKU 단위) |
| demand_history | SKU별 과거 출고 이력 |
| picking_tasks | 피킹지시 |
| stocking_tasks | 적치지시 |
| shipping_pending | 출고확정대기 |
| action_drafts | 승인 전 Draft Action |
| resources | 운영 자원(작업자/지게차) 수·교대 — DES 입력 |
| process_time_params | 단계별 처리시간 분포 파라미터 — DES 입력 |
| simulation_runs | DES 시뮬레이션 실행 헤더(시나리오, seed, replication 수) |
| simulation_kpis | DES 실행별 산출 KPI(분포 집계 P50/P90/확률) |
| simulation_events | DES 대표 run의 병목 이벤트 타임라인 |
| tool_logs | Tool 실행 로그 |
| rag_logs | RAG 검색 로그 |

## 3. 주요 DDL

### products
```sql
CREATE TABLE products (
    sku TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    storage_type TEXT NOT NULL,
    unit TEXT DEFAULT 'EA',
    volume REAL DEFAULT 1.0,
    weight REAL DEFAULT 1.0,
    fast_moving_flag INTEGER DEFAULT 0,
    safety_stock INTEGER DEFAULT 0,
    shelf_life_managed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### zones
```sql
CREATE TABLE zones (
    zone_id TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    storage_type TEXT NOT NULL,
    distance_from_gate REAL NOT NULL,
    picking_priority INTEGER DEFAULT 5,
    max_capacity INTEGER NOT NULL,
    active_flag INTEGER DEFAULT 1
);
```

### locations
```sql
CREATE TABLE locations (
    location_id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    location_name TEXT,
    capacity INTEGER NOT NULL,
    occupied_qty INTEGER DEFAULT 0,
    available_flag INTEGER DEFAULT 1,
    x_coord REAL DEFAULT 0,
    y_coord REAL DEFAULT 0,
    FOREIGN KEY(zone_id) REFERENCES zones(zone_id)
);
```

### inventory
```sql
CREATE TABLE inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    lot_no TEXT,
    location_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    inbound_date TEXT,
    expiry_date TEXT,
    status TEXT DEFAULT 'AVAILABLE',
    FOREIGN KEY(sku) REFERENCES products(sku),
    FOREIGN KEY(location_id) REFERENCES locations(location_id)
);
```

### inbound_orders
```sql
CREATE TABLE inbound_orders (
    inbound_no TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    expected_date TEXT NOT NULL,
    received_datetime TEXT,
    status TEXT DEFAULT 'PLANNED',
    supplier TEXT,
    FOREIGN KEY(sku) REFERENCES products(sku)
);
```

### outbound_orders
주문 헤더. SKU와 수량은 outbound_order_lines에서 관리한다.
```sql
CREATE TABLE outbound_orders (
    order_no TEXT PRIMARY KEY,
    customer_id TEXT,
    customer_priority INTEGER DEFAULT 1,
    due_datetime TEXT NOT NULL,
    status TEXT DEFAULT 'PLANNED'
);
```

### outbound_order_lines
```sql
CREATE TABLE outbound_order_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    FOREIGN KEY(order_no) REFERENCES outbound_orders(order_no),
    FOREIGN KEY(sku) REFERENCES products(sku)
);
```

### demand_history
```sql
CREATE TABLE demand_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    demand_date TEXT NOT NULL,
    shipped_qty INTEGER NOT NULL,
    FOREIGN KEY(sku) REFERENCES products(sku)
);
```

### action_drafts
```sql
CREATE TABLE action_drafts (
    draft_id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    dry_run_result_json TEXT,
    status TEXT DEFAULT 'PENDING_APPROVAL',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    executed_at TEXT
);
```

### picking_tasks
```sql
CREATE TABLE picking_tasks (
    picking_task_id TEXT PRIMARY KEY,
    order_no TEXT NOT NULL,
    recommended_start_time TEXT,
    estimated_minutes INTEGER,
    status TEXT DEFAULT 'ISSUED',
    draft_id TEXT,
    issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY(order_no) REFERENCES outbound_orders(order_no),
    FOREIGN KEY(draft_id) REFERENCES action_drafts(draft_id)
);
```

### stocking_tasks
```sql
CREATE TABLE stocking_tasks (
    stocking_task_id TEXT PRIMARY KEY,
    inbound_no TEXT NOT NULL,
    location_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    status TEXT DEFAULT 'ISSUED',
    draft_id TEXT,
    issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY(inbound_no) REFERENCES inbound_orders(inbound_no),
    FOREIGN KEY(location_id) REFERENCES locations(location_id),
    FOREIGN KEY(draft_id) REFERENCES action_drafts(draft_id)
);
```

### shipping_pending
```sql
CREATE TABLE shipping_pending (
    pending_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT NOT NULL,
    ready_datetime TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    confirmed_at TEXT,
    FOREIGN KEY(order_no) REFERENCES outbound_orders(order_no)
);
```

### tool_logs
```sql
CREATE TABLE tool_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    success INTEGER DEFAULT 1,
    error_message TEXT,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### rag_logs
```sql
CREATE TABLE rag_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    query TEXT NOT NULL,
    retrieved_sources_json TEXT,
    top_k INTEGER,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### resources
DES 시뮬레이션의 자원 제약. 작업자/지게차 등 자원 유형별 보유 수와 교대 시간.
```sql
CREATE TABLE resources (
    resource_id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,      -- WORKER | FORKLIFT
    count INTEGER NOT NULL,           -- 동시 가용 수 (SimPy Resource capacity)
    shift_start TEXT,                 -- 'HH:MM'
    shift_end TEXT,
    active_flag INTEGER DEFAULT 1
);
```

### process_time_params
단계별 처리시간을 확정값이 아닌 분포로 저장한다. DES가 replication마다 샘플링한다.
```sql
CREATE TABLE process_time_params (
    stage TEXT PRIMARY KEY,           -- INBOUND | STOCKING | PICKING | PACKING_SHIP
    distribution TEXT NOT NULL,       -- TRIANGULAR | LOGNORMAL | WEIBULL
    mean_minutes REAL NOT NULL,
    std_minutes REAL NOT NULL,
    min_minutes REAL,                 -- TRIANGULAR 하한
    max_minutes REAL                  -- TRIANGULAR 상한
);
```

### simulation_runs
DES 실행 1건(시나리오 1개)의 헤더. seed 고정으로 재현성을 보장한다.
```sql
CREATE TABLE simulation_runs (
    sim_run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,           -- BASELINE | WHATIF
    scenario_json TEXT,               -- What-if 조건(작업자 증감, CAPA 변경 등)
    horizon_days INTEGER NOT NULL,
    near_future_days INTEGER DEFAULT 3,
    replications INTEGER DEFAULT 200,
    random_seed INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### simulation_kpis
실행별 KPI를 분포 집계 형태로 저장한다(단일 값이 아님).
```sql
CREATE TABLE simulation_kpis (
    kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_run_id TEXT NOT NULL,
    sku TEXT,                         -- SKU 단위 KPI(소진일 등), 전역 KPI는 NULL
    kpi_name TEXT NOT NULL,           -- expected_stockout_date | shipping_delay_count | picking_wait_minutes | zone_max_occupancy | resource_utilization ...
    p50 REAL,
    p90 REAL,
    mean REAL,
    occurrence_prob REAL,             -- 지연 발생확률 등(0~1)
    unit TEXT,                        -- date | count | minutes | percent
    FOREIGN KEY(sim_run_id) REFERENCES simulation_runs(sim_run_id)
);
```

### simulation_events
대표 run(예: P50 시나리오)의 병목 이벤트 타임라인. Explainability 시각화에 사용.
```sql
CREATE TABLE simulation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_run_id TEXT NOT NULL,
    sim_time TEXT NOT NULL,           -- 시뮬레이션 시각
    event_type TEXT NOT NULL,         -- INBOUND_DONE | STOCKING_DONE | PICKING_START | ZONE_SATURATED | SHIPPING_DELAY | STOCKOUT ...
    detail_json TEXT,
    FOREIGN KEY(sim_run_id) REFERENCES simulation_runs(sim_run_id)
);
```

## 4. 상태값
Inbound: PLANNED, RECEIVED, STOCKING_RECOMMENDED, STOCKING_TASK_CREATED, STOCKED  
Outbound: PLANNED, PICKING_RECOMMENDED, PICKING_DRAFT, PICKING_ISSUED, PICKED, SHIPPING_PENDING, SHIPPED  
Draft: PENDING_APPROVAL, APPROVED, REJECTED, EXECUTED  
Picking/Stocking Task: ISSUED, IN_PROGRESS, COMPLETED, CANCELLED  
Shipping Pending: PENDING, CONFIRMED

## 5. Index
```sql
CREATE INDEX idx_inventory_sku ON inventory(sku);
CREATE INDEX idx_inventory_location ON inventory(location_id);
CREATE INDEX idx_inbound_status ON inbound_orders(status);
CREATE INDEX idx_outbound_status ON outbound_orders(status);
CREATE INDEX idx_outbound_due ON outbound_orders(due_datetime);
CREATE INDEX idx_order_lines_order ON outbound_order_lines(order_no);
CREATE INDEX idx_order_lines_sku ON outbound_order_lines(sku);
CREATE INDEX idx_demand_sku_date ON demand_history(sku, demand_date);
CREATE INDEX idx_locations_zone ON locations(zone_id);
CREATE INDEX idx_shipping_pending_status ON shipping_pending(status);
CREATE INDEX idx_tool_logs_run ON tool_logs(run_id);
CREATE INDEX idx_rag_logs_run ON rag_logs(run_id);
CREATE INDEX idx_sim_kpis_run ON simulation_kpis(sim_run_id);
CREATE INDEX idx_sim_events_run ON simulation_events(sim_run_id);
```

## 6. 상태변경 원칙
```text
추천 → Draft 생성 → 사용자 승인 → 실제 상태변경
```
승인 없이 변경되면 안 되는 테이블: picking_tasks, stocking_tasks, shipping_pending, outbound_orders.status, inbound_orders.status, inventory.qty

## 7. 구현 반영 DDL (2026-06-25)

### 7.1 출고 라인 수량 세분화 (할당 단계)
`outbound_order_lines`에 컬럼 추가:
- `allocated_qty` / `picked_qty` / `shipped_qty` INTEGER DEFAULT 0
- `line_status` TEXT DEFAULT 'PLANNED' (PLANNED→ALLOCATED/PARTIAL→PICKED→SHIPPED)

`outbound_orders.status`에 `ALLOCATED` 추가 — PLANNED/ALLOCATED = 할당·피킹 대상.

### 7.2 2단 재고 (보충)
`locations.location_role` TEXT DEFAULT 'PICK' — PICK(피킹면 전진재고)/RESERVE(보관 벌크). 보충은 RESERVE→PICK 이동.

### 7.3 대화 세션 (Chat UI 메모리)
- `chat_sessions(session_id, user_id, title, created_at, updated_at)`
- `chat_messages(msg_id, session_id, role, content, intent, sources_json, created_at)`

### 7.4 실행 트레이스 (AI 관측)
`agent_traces(run_id, session_id, query, intent, confidence, rag_required, answerable, sufficiency, retries, abstain, approval_required, steps_json, final_response, created_at)`

> 기존 DB는 `ensure_allocation_columns`/`ensure_location_role_column`/`ensure_chat_tables`/`ensure_trace_table`로 무중단 자동 마이그레이션(ALTER/CREATE IF NOT EXISTS).

### 7.5 보관타입 단순화 (2026-06-25)
`storage_type` 값에서 **FROZEN(냉동) 폐지 → COLD(냉장)·NORMAL(일반) 2종만** 사용. zones도 냉장 2개(E·F)·나머지 일반. 냉장 제품은 냉장 존에만 적재(하드 제약, 06 §5).
