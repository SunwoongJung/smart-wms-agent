-- Blackboard Auto Execution Layer 스키마 (기존 스키마와 충돌 없게 IF NOT EXISTS).
-- 기존 엔티티 참조는 target_type/target_id 또는 실제 컬럼명(sku, order_no, ...)으로 담는다.

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blackboard_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    severity TEXT NOT NULL DEFAULT 'normal',
    source TEXT NOT NULL DEFAULT 'system',
    status TEXT NOT NULL DEFAULT 'NEW',          -- NEW|PROCESSING|PROCESSED|FAILED|IGNORED
    created_at TEXT NOT NULL,
    processed_at TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_bb_events_status ON blackboard_events(status);

CREATE TABLE IF NOT EXISTS blackboard_actions (
    action_id TEXT PRIMARY KEY,
    event_id TEXT,
    agent_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    priority_score REAL NOT NULL DEFAULT 0,
    risk_score REAL NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'PENDING',       -- PENDING|POLICY_BLOCKED|READY|RUNNING|SUCCESS|FAILED|COMPENSATED|SKIPPED_DUPLICATE
    auto_executable INTEGER NOT NULL DEFAULT 0,
    policy_result_json TEXT,
    precheck_result_json TEXT,
    execution_result_json TEXT,
    postcheck_result_json TEXT,
    compensation_result_json TEXT,
    reason TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_bb_actions_status ON blackboard_actions(status);
CREATE INDEX IF NOT EXISTS idx_bb_actions_event ON blackboard_actions(event_id);

CREATE TABLE IF NOT EXISTS blackboard_locks (
    lock_key TEXT PRIMARY KEY,                    -- order:{order_no} | sku:{sku} | location:{location_id} | task:{task_id} | worker:{resource_id}
    owner_action_id TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blackboard_audit_logs (
    log_id TEXT PRIMARY KEY,
    action_id TEXT,
    event_id TEXT,
    agent_name TEXT,
    action_type TEXT,
    phase TEXT NOT NULL,                          -- EVENT_RECEIVED|ACTION_CREATED|POLICY_CHECK|PRECHECK|LOCK_ACQUIRED|EXECUTE|POSTCHECK|COMPENSATION|FINISHED
    before_state_json TEXT,
    after_state_json TEXT,
    message TEXT,
    result TEXT NOT NULL,                         -- OK|FAIL|BLOCKED|SKIPPED
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bb_audit_action ON blackboard_audit_logs(action_id);

CREATE TABLE IF NOT EXISTS inventory_reservations (
    reservation_id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    order_no TEXT,
    task_id TEXT,
    qty INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'RESERVED',      -- RESERVED|CONSUMED|RELEASED|CANCELLED
    created_by_action_id TEXT,
    created_at TEXT NOT NULL,
    released_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_resv_sku ON inventory_reservations(sku, status);
CREATE INDEX IF NOT EXISTS idx_resv_order ON inventory_reservations(order_no);
