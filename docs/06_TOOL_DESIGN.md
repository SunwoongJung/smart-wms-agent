# 06_TOOL_DESIGN.md

# Tool Design

## 1. 목적
Tool은 WMS 조회, 추천 계산, Forecast, Draft 생성, 상태변경을 담당한다. LLM은 계산하지 않고 Tool 결과를 해석한다.

## 2. 설계 원칙
- 입력/출력은 JSON 표준
- Tool은 deterministic
- 상태변경 Tool은 승인 후 실행
- 모든 Tool 실행은 tool_logs 저장

## 3. 표준 Tool 목록
본 문서가 Tool 이름의 단일 기준이다. 다른 문서(02 Architecture, 10 Evaluation 등)는 아래 이름을 그대로 사용한다.

| 분류 | Tool | 상태변경 |
|---|---|---|
| 조회 | lookup_inventory | X |
| 조회 | lookup_inbound_orders | X |
| 조회 | lookup_outbound_orders | X |
| 조회 | lookup_shipping_pending | X |
| 조회 | lookup_demand_history | X |
| 조회 | query_operation_kpis | X |
| 적치 | filter_available_locations | X |
| 적치 | check_same_sku_location | X |
| 적치 | calculate_stocking_score | X |
| 적치 | recommend_stocking | X |
| 피킹 | calculate_picking_required_time | X |
| 피킹 | recommend_picking | X |
| Forecast | inventory_forecast | X |
| Forecast | calculate_inventory_risk | X |
| Forecast | scan_inventory_risk | X |
| Simulation | run_des_simulation | X |
| Simulation | simulate_operation_what_if | X |
| Simulation | compare_simulation_scenarios | X |
| Draft | create_stocking_task_draft | X (Draft 생성만) |
| Draft | create_picking_instruction_draft | X (Draft 생성만) |
| Draft | create_shipping_confirm_draft | X (Draft 생성만) |
| Draft | dry_run_action | X (미리보기만) |
| 실행 | approve_action | O |
| 실행 | issue_picking_instruction | O |
| 실행 | issue_stocking_task | O |
| 실행 | confirm_shipping | O |

## 4. 조회 Tool

### lookup_inventory
SKU 기준 현재 재고 조회.
```json
{"sku":"SKU_A001"}
```

### lookup_inbound_orders
입고예정/적치대기 조회. status 필터로 용도를 구분한다.
```json
{"status":["PLANNED","RECEIVED"],"target_date":"2026-06-11"}
```
- 입고예정 조회: status = PLANNED
- 적치대기 조회: status = RECEIVED
- 입고 지연 탐지: status = PLANNED AND expected_date < today

### lookup_outbound_orders
출고예정/미지시 출고 조회. 주문 헤더와 라인을 함께 반환한다.
```json
{"status":["PLANNED"],"target_date":"2026-06-11"}
```
- 미지시 출고(피킹지시 필요) 조회: status = PLANNED

### lookup_shipping_pending
출고확정대기 조회.
```json
{"status":"PENDING"}
```

### lookup_demand_history
SKU별 과거 일자별 출고량 조회. Forecast 입력으로 사용한다.
```json
{"sku":"SKU_A001","days":60}
```

### query_operation_kpis
운영 KPI를 집계 조회한다. KPI 정의·산식은 13_VISUALIZATION_DESIGN.md §4를 따른다.
```json
{"kpis":["on_time_shipping_rate","zone_occupancy","high_risk_sku_count"],"target_date":"2026-06-15"}
```
출력:
```json
{
  "kpis":[
    {"name":"on_time_shipping_rate","value":0.92,"unit":"percent"},
    {"name":"high_risk_sku_count","value":3,"unit":"count"},
    {"name":"zone_occupancy","value":[{"zone_id":"ZONE_A","occupancy":0.88}],"unit":"percent"}
  ]
}
```

## 5. 적치 Tool

### filter_available_locations
조건:
```text
available_flag = 1
Product.storage_type = Zone.storage_type
capacity - occupied_qty >= inbound_qty
```

### check_same_sku_location
동일 SKU가 보관 중인 Location/Zone 존재 여부를 확인한다.
```json
{"sku":"SKU_A002"}
```

### calculate_stocking_score
후보 Location별 적치 점수를 계산한다. 산식은 scoring_formula.md를 따른다. 모든 항목을 0~1 정규화 후 가중합하며, 항목별 breakdown을 반환한다.
```text
stocking_score = 0.30*same_sku_norm + 0.25*capacity_norm + 0.20*distance_norm + 0.15*turnover_norm - 0.10*congestion_norm
```

### recommend_stocking
filter_available_locations → check_same_sku_location → calculate_stocking_score를 종합하여 최종 추천한다.
```json
{"inbound_no":"INB003"}
```
출력:
```json
{
  "recommended_location_id":"L-A-001",
  "score":0.87,
  "breakdown":{"same_sku_norm":1.0,"capacity_norm":0.72,"distance_norm":0.90,"turnover_norm":0.65,"congestion_norm":0.0},
  "reasons":["동일 SKU 존재","잔여 CAPA 충분","입구 거리 우수"],
  "candidates":[],
  "approval_required":true
}
```

## 6. 피킹 Tool

### calculate_picking_required_time
멀티라인 주문 기준 예상 피킹시간 계산. 기본값 base_minutes = 15, buffer_minutes = 10.
```text
estimated_minutes = base_minutes + (line_count - 1) * 2 + ceil(total_qty / 10) * 2 + max_distance_from_gate / 10
```

### recommend_picking
미지시 출고 주문의 우선순위와 권장 시작시간을 계산한다.
```json
{"current_datetime":"2026-06-11 10:20"}
```
권장 시작시간:
```text
recommended_start_time = due_datetime - estimated_minutes - buffer_minutes
```
우선순위 점수는 scoring_formula.md의 picking_priority_score를 따른다.

## 7. Forecast Tool

### inventory_forecast
```json
{"sku":"SKU_A001","forecast_days":30}
```
처리:
```text
demand_history 조회
Linear Regression 학습 (데이터 부족 시 이동평균 fallback)
향후 forecast_days일 예측
현재재고 + 입고예정 - 출고예정 - 예측출고 누적
예상소진일, 안전재고 도달일 산출
```

### calculate_inventory_risk
inventory_forecast 결과로 위험등급을 판정한다.
```text
HIGH: 7일 이내 소진
MEDIUM: 14일 이내 소진
LOW: 14일 초과 또는 소진 없음
WATCH: 소진은 아니지만 안전재고 이하 도달
```

### scan_inventory_risk
전체 SKU에 대해 inventory_forecast + calculate_inventory_risk를 일괄 수행한다. Daily Summary와 /risk/scan에서 사용한다.
```json
{"risk_levels":["HIGH","MEDIUM","WATCH"]}
```

## 7.1 Simulation Tool (SimPy DES)
DES는 인력·장비·Zone CAPA 제약 하에서 입출고 이벤트의 처리가능성을 검증하는 엔진이다. 출력은 단일 값이 아닌 확률적 분포(P50/P90/발생확률)이다. 산식·구조는 07_FORECAST_AND_SIMULATION.md를 따른다.

### run_des_simulation
Hybrid Forecast(Near: 확정 이벤트 / Far: Regression→가상 이벤트) + 자원 제약을 반영하여 N회 반복(Monte Carlo) 시뮬레이션을 수행하고 baseline KPI 분포를 산출한다.
```json
{"horizon_days":14,"near_future_days":3,"replications":200,"random_seed":42}
```
출력:
```json
{
  "sim_run_id":"SIM-001",
  "kpis":[
    {"sku":"SKU_A001","kpi_name":"expected_stockout_date","p50":"2026-06-21","p90":"2026-06-18","unit":"date"},
    {"kpi_name":"shipping_delay_count","mean":3,"p90":5,"occurrence_prob":0.62,"unit":"count"},
    {"kpi_name":"picking_wait_minutes","p50":28,"p90":42,"unit":"minutes"},
    {"kpi_name":"zone_max_occupancy","sku":null,"p90":0.94,"unit":"percent"},
    {"kpi_name":"resource_utilization","mean":0.81,"unit":"percent"}
  ],
  "zone_occupancy_timeseries":[
    {"sim_time":"D1 09:00","occupancy":{"ZONE_A":0.62,"ZONE_B":0.40}}
  ],
  "inventory_projection":[
    {"sku":"SKU_A001","sim_time":"D1","p50_qty":110,"p90_qty":95,"segment":"near"}
  ],
  "bottleneck_events":[
    {"sim_time":"D2 14:00","event_type":"SHIPPING_DELAY","detail":{"order_no":"ORD021"}}
  ]
}
```
> 대표 run(예: P50)의 `zone_occupancy_timeseries`·`inventory_projection`·`bottleneck_events`는 13_VISUALIZATION_DESIGN.md의 Warehouse Floor Replay / Inventory Projection / Event Timeline 입력으로 사용된다.

### simulate_operation_what_if
운영 조건을 변경한 시나리오 1건을 시뮬레이션한다(작업자 증감, 지게차 증감, Zone CAPA 변경, 수요 배수, 입고 지연, 피킹 우선순위 변경).
```json
{
  "base_sim_run_id":"SIM-001",
  "scenario":{"worker_delta":1,"forklift_delta":0,"zone_capa_multiplier":{"ZONE_A":0.8},"demand_multiplier":1.3,"inbound_delay_days":0}
}
```
출력: run_des_simulation과 동일한 KPI 분포 구조(시나리오 run).

### compare_simulation_scenarios
baseline run과 scenario run의 KPI 분포 delta를 비교한다.
```json
{"baseline_sim_run_id":"SIM-001","scenario_sim_run_id":"SIM-002"}
```
출력:
```json
{
  "comparison":[
    {"kpi_name":"expected_stockout_date","baseline_p50":"2026-06-18","scenario_p50":"2026-06-21","delta_days":3},
    {"kpi_name":"shipping_delay_count","baseline_mean":3,"scenario_mean":1,"delta":-2},
    {"kpi_name":"picking_wait_minutes","baseline_p90":42,"scenario_p90":18,"delta":-24}
  ]
}
```

## 8. Draft / Approval Tool

### create_stocking_task_draft
적치지시 Draft 생성. action_drafts에 PENDING_APPROVAL로 저장한다.

### create_picking_instruction_draft
피킹지시 Draft 생성.

### create_shipping_confirm_draft
출고확정 Draft 생성. 생성 시 dry_run_action을 자동 수행하여 dry_run_result_json에 저장한다.

### dry_run_action
Draft의 상태변경 결과를 실제 반영 없이 미리 계산한다.
```json
{"draft_id":"DRF-SHP-001"}
```
출력 예 (출고확정):
```json
{
  "order_no":"ORD010",
  "changes":[
    {"table":"outbound_orders","field":"status","before":"SHIPPING_PENDING","after":"SHIPPED"},
    {"table":"inventory","sku":"SKU_A002","qty_change":-20}
  ],
  "warnings":[]
}
```

### approve_action
사용자 승인을 기록하고 해당 실행 Tool을 호출한다. 승인 없는 Draft는 실행되지 않는다.

### issue_picking_instruction / issue_stocking_task / confirm_shipping
승인된 Draft에 대해서만 실제 상태를 변경한다.

## 9. Tool 입출력 스키마 요약
모든 Tool은 JSON 입출력을 사용하며, 공통적으로 `success: bool`, `error: str | null`을 포함한다. 아래는 Tool별 입력 파라미터와 주요 출력 키이다.

| Tool | 입력 파라미터 | 주요 출력 |
|---|---|---|
| lookup_inventory | sku: str | inventory: list[{location_id, lot_no, qty, expiry_date}], total_qty: int |
| lookup_inbound_orders | status: list[str], target_date?: str | orders: list[{inbound_no, sku, qty, expected_date, status}] |
| lookup_outbound_orders | status: list[str], target_date?: str | orders: list[{order_no, due_datetime, customer_priority, status, lines: list[{sku, qty}]}] |
| lookup_shipping_pending | status?: str | pending: list[{order_no, ready_datetime, status}] |
| lookup_demand_history | sku: str, days: int | history: list[{demand_date, shipped_qty}], days_available: int |
| query_operation_kpis | kpis: list[str], target_date?: str | kpis: list[{name, value, unit}] |
| filter_available_locations | sku: str, inbound_qty: int | candidates: list[{location_id, zone_id, remaining_capacity}] |
| check_same_sku_location | sku: str | exists: bool, locations: list[str], zones: list[str] |
| calculate_stocking_score | sku: str, candidates: list[str] | scores: list[{location_id, score, breakdown: dict}] |
| recommend_stocking | inbound_no: str | recommended_location_id: str, score: float, reasons: list[str], candidates: list, approval_required: bool |
| calculate_picking_required_time | order_no: str | estimated_minutes: int, line_count: int, total_qty: int, max_distance: float |
| recommend_picking | current_datetime: str | recommendations: list[{order_no, priority_rank, recommended_start_time, estimated_minutes, urgent: bool}] |
| inventory_forecast | sku: str, forecast_days: int | expected_stockout_date: str\|null, safety_stock_reach_date: str\|null, daily_projection: list, method: "linear_regression"\|"ma_14"\|"ma_7"\|"insufficient_data" |
| calculate_inventory_risk | sku: str | risk_level: "HIGH"\|"MEDIUM"\|"LOW"\|"WATCH", expected_stockout_date: str\|null |
| scan_inventory_risk | risk_levels?: list[str] | risks: list[{sku, risk_level, expected_stockout_date}] |
| run_des_simulation | horizon_days: int, near_future_days?: int, replications?: int, random_seed: int | sim_run_id: str, kpis: list[{sku?, kpi_name, p50?, p90?, mean?, occurrence_prob?, unit}], zone_occupancy_timeseries: list, inventory_projection: list, bottleneck_events: list |
| simulate_operation_what_if | base_sim_run_id: str, scenario: dict | sim_run_id: str, kpis: list[...] (동일 구조) |
| compare_simulation_scenarios | baseline_sim_run_id: str, scenario_sim_run_id: str | comparison: list[{kpi_name, baseline_*, scenario_*, delta}] |
| create_stocking_task_draft | inbound_no: str, location_id: str | draft_id: str, status: "PENDING_APPROVAL" |
| create_picking_instruction_draft | order_no: str | draft_id: str, status: "PENDING_APPROVAL" |
| create_shipping_confirm_draft | order_no: str | draft_id: str, dry_run: dict, status: "PENDING_APPROVAL" |
| dry_run_action | draft_id: str | changes: list[{table, field, before, after}], warnings: list[str] |
| approve_action | draft_id: str, approved: bool, user_id: str | status: "EXECUTED"\|"REJECTED", executed_action: dict\|null |
| issue_picking_instruction | draft_id: str | picking_task_id: str, order_status: "PICKING_ISSUED" |
| issue_stocking_task | draft_id: str | stocking_task_id: str, inbound_status: "STOCKING_TASK_CREATED" |
| confirm_shipping | draft_id: str | order_status: "SHIPPED", inventory_changes: list |

## 10. 예외 처리
| 예외 | 처리 |
|---|---|
| SKU 없음 | 사용자 확인 요청 (clarification) |
| 적재 가능 Location 없음 | SOP 검색 (적재 가능 Location 없음 대응) |
| CAPA 부족 | SOP 검색 (CAPA 부족 대응) |
| Forecast 데이터 7일 미만 | 예측 불가, 데이터 부족 안내 |
| Forecast 데이터 7~29일 | 이동평균 fallback (7일/14일) |
| 승인 없음 | Draft 상태 유지 |
| Dry Run 경고 존재 | 경고 표시 후 사용자 판단 위임 |

## 11. 구현 반영 Tool (2026-06-25)
실 WMS 흐름 반영으로 신규 Tool·Draft 액션 추가.

### 11.1 할당(allocation.py)
- `calculate_allocation(order_no)`: on-hand 기준 라인별 할당가능/결품.
- `scan_allocation(target_date, within_days=0)`: ATP(현재고+입고예정) 기준 근미래 납기 주문 할당 시뮬레이션 → 예상 결품.
- `apply_allocation`: 라인 allocated_qty/line_status, 주문 status=ALLOCATED.

### 11.2 체화재고(dead_stock.py)
- `scan_dead_stock(grades)`: EXPIRING(유통기한 임박/만료)/DEAD(최근14일 무출고)/SLOW(저회전) 등급화 + 재고가치.

### 11.3 보충(replenishment.py)
- `scan_replenishment()`: 피킹면 < 목표(수요×2일, 최소 안전재고) & 보관 보유 → 보충 추천(긴급도순).
- `execute_replenishment(...)`: RESERVE→PICK 재고 이동.

### 11.4 Draft 액션 확장
기존 STOCKING/PICKING/SHIPPING에 **ALLOCATION / REPLENISH / DISPOSAL** 추가. 모두 dry-run + 승인 후 실행.
DISPOSAL은 해당 SKU의 AVAILABLE 재고를 HOLD로 전환(출고 풀 제외).

### 11.5 고회전 적치 가중 (2026-06-25)
`calculate_stocking_score`에서 **고회전 SKU(fast_moving_flag)는 거리 가중을 2배(0.20→0.40)** 적용 → 입구 근처 존 우선 선택. (회전율 가중은 SKU 단위 상수라 위치 순위에 영향이 없던 한계를 보완.) 보관조건 일치(냉장→냉장 존)는 여전히 하드 필터.
