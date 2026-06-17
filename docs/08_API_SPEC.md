# 08_API_SPEC.md

# API Specification

## 1. 공통 응답
```json
{
  "success": true,
  "run_id": "RUN-001",
  "data": {},
  "message": "처리 완료",
  "tool_trace": [],
  "rag_sources": []
}
```

## 2. POST /chat
자연어 질의 처리.
```json
{"user_query":"오늘 뭐 해야 돼?","user_id":"operator01"}
```

## 3. GET /inbound
입고예정/적치대기 조회.

## 4. POST /recommend/stocking
```json
{"inbound_no":"INB003"}
```

## 5. POST /stocking/draft
적치지시 Draft 생성.

## 6. GET /outbound
출고예정 조회. 주문 헤더와 라인(outbound_order_lines)을 함께 반환한다.
```json
{
  "order_no":"ORD002",
  "due_datetime":"2026-06-11 13:00",
  "customer_priority":5,
  "status":"PLANNED",
  "lines":[
    {"sku":"SKU_A002","qty":15},
    {"sku":"SKU_A003","qty":10}
  ]
}
```

## 7. POST /recommend/picking
```json
{"current_datetime":"2026-06-11 10:20"}
```

## 8. POST /picking/draft
피킹지시 Draft 생성.

## 9. POST /forecast
```json
{"sku":"SKU_A001","forecast_days":30}
```

## 10. POST /risk/scan
전체 SKU 리스크 스캔.

## 11. POST /simulate
SimPy DES 시뮬레이션. 운영 자원 제약 하에서 KPI 분포(P50/P90/발생확률)를 산출한다.

baseline 실행:
```json
{"horizon_days":14,"near_future_days":3,"replications":200,"random_seed":42}
```

What-if 실행 + 비교 (baseline run 대비):
```json
{
  "base_sim_run_id":"SIM-001",
  "scenario":{"worker_delta":1,"forklift_delta":0,"zone_capa_multiplier":{"ZONE_A":0.8},"demand_multiplier":1.3}
}
```
응답은 KPI 분포(run_des_simulation) 또는 baseline/scenario delta 비교(compare_simulation_scenarios)를 반환한다. Tool 정의는 06_TOOL_DESIGN.md를 따른다.

## 11.1 POST /kpi
운영 KPI 조회. KPI 정의·산식은 13_VISUALIZATION_DESIGN.md §4를 따른다.
```json
{"kpis":["on_time_shipping_rate","zone_occupancy","high_risk_sku_count"],"target_date":"2026-06-15"}
```
응답은 query_operation_kpis Tool 출력(name/value/unit)을 반환한다.

## 12. GET /shipping/pending
출고확정대기 조회.

## 12.1 POST /shipping/draft
출고확정 Draft 생성. 생성 시 Dry Run을 자동 수행하여 변경 미리보기를 함께 반환한다.
```json
{"order_no":"ORD010"}
```
응답:
```json
{
  "draft_id":"DRF-SHP-001",
  "dry_run":{
    "changes":[
      {"table":"outbound_orders","field":"status","before":"SHIPPING_PENDING","after":"SHIPPED"},
      {"table":"inventory","sku":"SKU_A002","qty_change":-20}
    ],
    "warnings":[]
  },
  "approval_required":true
}
```

## 13. POST /approve
Draft 승인 및 실행.
```json
{"draft_id":"DRF-PCK-001","approved":true,"user_id":"operator01"}
```

## 14. GET /trace/{run_id}
Agent 실행 trace 조회.
