# scoring_formula.md

# 산식 및 점수 계산 문서

## 적치 점수
### Hard Filter (점수 이전 단계, 절대 조건)
보관조건 불일치, CAPA 부족, 사용불가(available_flag=0) Location은 후보 필터링 단계에서 **제외**되며 점수를 계산하지 않는다. 이는 가중치가 아닌 절대 조건이다.

### 가중합 정규화 산식
모든 항목을 0~1로 정규화한 뒤 가중합한다. 거리·잔여용량·혼잡도는 창고/Zone별 기준값으로 min-max 정규화한다.
```text
stocking_score =
  0.30 * same_sku_norm
+ 0.25 * capacity_norm
+ 0.20 * distance_norm
+ 0.15 * turnover_norm
- 0.10 * congestion_norm
```
- 동일 SKU는 **절대 우선이 아닌 가중치(0.30) 우선**이다. 가장 큰 가중치이나 다른 항목(용량·거리)과 균형을 이룬다.
- 추천 결과에는 총점뿐 아니라 **항목별 breakdown**(각 norm 값과 가중 기여분)을 함께 제공한다.

same_sku_norm:
```text
동일 SKU Location 존재 = 1.0
동일 SKU 없음 = 0.0
```

capacity_norm:
```text
zone_remaining_capacity_ratio (0~1)
= (max_capacity - 점유 수량 합계) / max_capacity
```

distance_norm (Zone 거리를 창고 내 min-max로 정규화, 가까울수록 1):
```text
distance_norm = 1 - (distance_from_gate - min_dist) / (max_dist - min_dist)
min_dist/max_dist = 활성 Zone들의 입구 거리 최소/최대값
clip(0, 1)
```

turnover_norm (고회전성, 연속값):
```text
turnover_norm = clip(sku_turnover_rate / zone_max_turnover, 0, 1)
sku_turnover_rate = 최근 N일 평균 출고량 / 평균 재고량 (demand_history 기반)
고회전 SKU가 입구 가까운 Zone에 배치될수록 점수↑ (turnover_norm * distance_norm 상호작용 고려 가능)
```

congestion_norm (혼잡 패널티, 0~1):
```text
zone_occupied_ratio = 점유 수량 합계 / max_capacity
congestion_norm = clip((zone_occupied_ratio - 0.9) / 0.1, 0, 1)   # 90% 초과부터 선형 증가
그 외 = 0
```

### 가중치 민감도 테스트
가중치(0.30/0.25/0.20/0.15/-0.10) 변경 시 추천 순위가 어떻게 바뀌는지 sensitivity test를 수행한다(10_EVALUATION_PLAN.md). 동일 SKU 절대우선이 아닌 가중치 방식이므로, 잔여용량·거리가 크게 우수한 후보가 동일 SKU 후보를 역전할 수 있는지 검증한다.

## 예상 피킹시간
```text
estimated_picking_minutes =
base_minutes
+ (line_count - 1) * 2
+ ceil(total_qty / 10) * 2
+ max_distance_from_gate / 10
```

기본값:
```text
base_minutes = 15
buffer_minutes = 10
```

- line_count: 주문의 라인(SKU) 수
- total_qty: 전체 라인 수량 합계
- max_distance_from_gate: 피킹 대상 Location 중 가장 먼 Zone의 입구 거리(m)

예시: 1개 라인, 수량 20, ZONE_A(10m) 주문은 15 + 0 + 4 + 1 = 20분이다.

## 피킹 시작시간
```text
recommended_start_time = due_datetime - estimated_picking_minutes - buffer_minutes
```

## 피킹 우선순위
```text
picking_priority_score =
deadline_urgency_score
+ customer_priority_score
+ shortage_risk_score
- estimated_picking_time_penalty
- travel_time_penalty
```

deadline_urgency_score:
```text
max(0, 120 - 출고까지 남은 분)
이미 권장 시작시간이 지난 주문 = 120 (최대값 고정, 긴급 피킹)
```

customer_priority_score:
```text
customer_priority * 10
customer_priority: 1(기본) ~ 5(최우선)
```

shortage_risk_score:
```text
주문 라인에 위험등급 HIGH SKU 포함 = 30
주문 라인에 위험등급 MEDIUM SKU 포함 = 15
그 외 = 0
```

estimated_picking_time_penalty:
```text
estimated_picking_minutes * 0.5
```

travel_time_penalty:
```text
max_distance_from_gate * 0.2
```

## 예상소진일
```text
predicted_demand = a * day_index + b
projected_inventory(t) = projected_inventory(t-1) + inbound_qty(t) - outbound_qty(t) - predicted_demand(t)
expected_stockout_date = first date where projected_inventory <= 0
```

## What-if 시뮬레이션
```text
입고 추가: projected_inventory(t)에 additional_inbound_qty를 additional_inbound_date에 가산
수요 변화: predicted_demand(t) * demand_multiplier 적용
출력: 기존 예상소진일과 변경 후 예상소진일 비교
```
