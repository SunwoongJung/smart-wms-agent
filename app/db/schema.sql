-- WOONG AI — SQLite schema (docs/04_DATABASE_DESIGN.md 기준)
-- 부모 테이블 먼저 생성(FK 순서).

CREATE TABLE IF NOT EXISTS products (
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
    unit_cost REAL DEFAULT 1000,       -- SKU별 단가(재고가치 KPI 실값용)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT,
    priority INTEGER DEFAULT 3,         -- 1(높음)~5(낮음), 고객별 고정
    region TEXT
);

CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    zone_name TEXT NOT NULL,
    storage_type TEXT NOT NULL,
    distance_from_gate REAL NOT NULL,
    picking_priority INTEGER DEFAULT 5,
    max_capacity INTEGER NOT NULL,
    active_flag INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS locations (
    location_id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL,
    location_name TEXT,
    capacity INTEGER NOT NULL,
    occupied_qty INTEGER DEFAULT 0,
    available_flag INTEGER DEFAULT 1,
    location_role TEXT DEFAULT 'PICK',  -- PICK(피킹면, 전진재고) | RESERVE(보관, 벌크재고)
    x_coord REAL DEFAULT 0,
    y_coord REAL DEFAULT 0,
    FOREIGN KEY(zone_id) REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS inventory (
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

CREATE TABLE IF NOT EXISTS inbound_orders (
    inbound_no TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    expected_date TEXT NOT NULL,
    received_datetime TEXT,
    status TEXT DEFAULT 'PLANNED',
    supplier TEXT,
    FOREIGN KEY(sku) REFERENCES products(sku)
);

CREATE TABLE IF NOT EXISTS outbound_orders (
    order_no TEXT PRIMARY KEY,
    customer_id TEXT,
    customer_priority INTEGER DEFAULT 1,
    due_datetime TEXT NOT NULL,
    shipped_datetime TEXT,             -- 실제 출고시각(과거 SHIPPED 이력; 정시율 KPI용)
    status TEXT DEFAULT 'PLANNED'
);

CREATE TABLE IF NOT EXISTS outbound_order_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,              -- 예정 수량(요청량)
    allocated_qty INTEGER DEFAULT 0,  -- 할당 수량(가용재고 배정량)
    picked_qty INTEGER DEFAULT 0,     -- 피킹 수량
    shipped_qty INTEGER DEFAULT 0,    -- 확정/출고 수량
    line_status TEXT DEFAULT 'PLANNED', -- PLANNED→ALLOCATED/PARTIAL→PICKED→SHIPPED
    FOREIGN KEY(order_no) REFERENCES outbound_orders(order_no),
    FOREIGN KEY(sku) REFERENCES products(sku)
);

CREATE TABLE IF NOT EXISTS demand_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    demand_date TEXT NOT NULL,
    shipped_qty INTEGER NOT NULL,
    FOREIGN KEY(sku) REFERENCES products(sku)
);

CREATE TABLE IF NOT EXISTS action_drafts (
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

CREATE TABLE IF NOT EXISTS picking_tasks (
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

CREATE TABLE IF NOT EXISTS stocking_tasks (
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

CREATE TABLE IF NOT EXISTS shipping_pending (
    pending_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT NOT NULL,
    ready_datetime TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    confirmed_at TEXT,
    FOREIGN KEY(order_no) REFERENCES outbound_orders(order_no)
);

-- DES 입력
CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,      -- WORKER | FORKLIFT
    shift_start TEXT,
    shift_end TEXT,
    active_flag INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS process_time_params (
    stage TEXT PRIMARY KEY,           -- INBOUND | STOCKING | PICKING | PACKING_SHIP
    distribution TEXT NOT NULL,       -- TRIANGULAR | LOGNORMAL | WEIBULL
    mean_minutes REAL NOT NULL,
    std_minutes REAL NOT NULL,
    min_minutes REAL,
    max_minutes REAL
);

-- DES 결과
CREATE TABLE IF NOT EXISTS simulation_runs (
    sim_run_id TEXT PRIMARY KEY,
    version_name TEXT,                 -- 실행시각 기반 버전명 (예: V20260616-211530)
    run_type TEXT NOT NULL,           -- BASELINE | WHATIF
    scenario_json TEXT,
    horizon_days INTEGER NOT NULL,
    near_future_days INTEGER DEFAULT 3,
    replications INTEGER DEFAULT 200,
    random_seed INTEGER NOT NULL,
    result_json TEXT,                 -- 전체 결과(kpis·timeseries·inv_proj·events) — 버전별 차트 재현용
    worker_count INTEGER,             -- 해석된 작업자 수(버전 dropdown 라벨·비교용)
    forklift_count INTEGER,           -- 해석된 지게차 수
    team_count INTEGER,               -- 해석된 팀 수
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_kpis (
    kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_run_id TEXT NOT NULL,
    sku TEXT,
    kpi_name TEXT NOT NULL,
    p50 REAL,
    p90 REAL,
    mean REAL,
    occurrence_prob REAL,
    unit TEXT,
    FOREIGN KEY(sim_run_id) REFERENCES simulation_runs(sim_run_id)
);

CREATE TABLE IF NOT EXISTS simulation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sim_run_id TEXT NOT NULL,
    sim_time TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail_json TEXT,
    FOREIGN KEY(sim_run_id) REFERENCES simulation_runs(sim_run_id)
);

-- 대화 세션(Chat UI 이력 저장·복원 + 멀티턴 맥락)
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                -- user | assistant
    content TEXT NOT NULL,
    intent TEXT,
    sources_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
);

-- 에이전트 실행 트레이스(LangGraph 노드 흐름 + RAG 과정 관측)
CREATE TABLE IF NOT EXISTS agent_traces (
    run_id TEXT PRIMARY KEY,
    session_id TEXT,
    query TEXT,
    intent TEXT,
    confidence REAL,
    rag_required INTEGER,
    answerable INTEGER,
    sufficiency REAL,
    retries INTEGER,
    abstain INTEGER,
    approval_required INTEGER,
    steps_json TEXT,
    final_response TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 로그
CREATE TABLE IF NOT EXISTS tool_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    success INTEGER DEFAULT 1,
    error_message TEXT,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    query TEXT NOT NULL,
    retrieved_sources_json TEXT,
    top_k INTEGER,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- KPI Dashboard(docs 13) 목표량(기준선) 서버 영구 저장 — 모든 사용자 공유
CREATE TABLE IF NOT EXISTS dashboard_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 작업팀 가동률 등, 실측 완료로그가 없는 과거 구간(운영 시나리오상 미처리 백로그 기간)을
-- 채우는 가상 과거값. 실측 데이터가 있으면 항상 실측이 우선하고, 없을 때만 폴백으로 사용.
CREATE TABLE IF NOT EXISTS kpi_synthetic_fill (
    metric TEXT NOT NULL,
    fill_date TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (metric, fill_date)
);

-- Index
CREATE INDEX IF NOT EXISTS idx_inventory_sku ON inventory(sku);
CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory(location_id);
CREATE INDEX IF NOT EXISTS idx_inbound_status ON inbound_orders(status);
CREATE INDEX IF NOT EXISTS idx_outbound_status ON outbound_orders(status);
CREATE INDEX IF NOT EXISTS idx_outbound_due ON outbound_orders(due_datetime);
CREATE INDEX IF NOT EXISTS idx_order_lines_order ON outbound_order_lines(order_no);
CREATE INDEX IF NOT EXISTS idx_order_lines_sku ON outbound_order_lines(sku);
CREATE INDEX IF NOT EXISTS idx_demand_sku_date ON demand_history(sku, demand_date);
CREATE INDEX IF NOT EXISTS idx_locations_zone ON locations(zone_id);
CREATE INDEX IF NOT EXISTS idx_shipping_pending_status ON shipping_pending(status);
CREATE INDEX IF NOT EXISTS idx_tool_logs_run ON tool_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_rag_logs_run ON rag_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_sim_kpis_run ON simulation_kpis(sim_run_id);
CREATE INDEX IF NOT EXISTS idx_sim_events_run ON simulation_events(sim_run_id);
