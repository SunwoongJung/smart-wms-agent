# picking_policy.md

# 피킹 정책 문서

## 목적
출고예정 데이터 기반 피킹 우선순위와 권장 시작시간 산정 정책을 정의한다.

## 대상
```text
outbound_orders.status = PLANNED
```

## 피킹 시작시간
```text
recommended_start_time = due_datetime - estimated_picking_minutes - buffer_minutes
```

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

line_count는 주문의 라인(SKU) 수, total_qty는 전체 라인 수량 합계, max_distance_from_gate는 피킹 대상 Location 중 가장 먼 Zone의 입구 거리이다.

## 우선순위 기준
1. 출고 예정시간이 가까운 주문
2. 권장 피킹 시작시간이 도래한 주문
3. 예상 작업시간이 긴 주문
4. 고객 우선순위가 높은 주문
5. 재고 부족 위험이 있는 SKU의 주문

## 긴급 피킹
```text
current_datetime >= recommended_start_time
```

## 승인 정책
피킹지시는 사용자 승인 후 발행한다.
