# 05_SEED_DATA_DESIGN.md

# Seed Data Design

## 1. 목적
Agent 주요 기능을 검증할 수 있는 업무 시나리오형 Seed Data를 정의한다.

## 2. 권장 규모
| 데이터 | 규모 |
|---|---:|
| products | 50 SKU |
| zones | 9 (3x3 그리드) |
| locations | 100 |
| inventory | 500 |
| inbound_orders | 50 |
| outbound_orders | 100 |
| outbound_order_lines | 180 (주문당 1~3라인) |
| demand_history | SKU당 60일 |
| shipping_pending | 20 |
| resources | 작업자 3, 지게차 2 (기본) |
| process_time_params | 4단계(INBOUND/STOCKING/PICKING/PACKING_SHIP) |

## 3. 필수 테스트 SKU
| SKU | 목적 |
|---|---|
| SKU_A001 | 재고 부족 위험, Forecast 테스트 |
| SKU_A002 | 동일 SKU 적치 테스트 |
| SKU_A003 | 고회전 적치 가중치 테스트 |
| SKU_C001 | 냉장 Zone 필터 테스트 |
| SKU_F001 | 냉동 Zone 필터 테스트 |

## 4. Zone 구성 (3x3 그리드: 1행 A,B,C / 2행 D,E,F / 3행 G,H,I)
| Zone | 보관조건 | 거리 | 목적 |
|---|---|---:|---|
| ZONE_A | NORMAL | 10m | 고회전 일반품(포화 시나리오) |
| ZONE_B | NORMAL | 15m | 일반 재고 |
| ZONE_C | NORMAL | 20m | 일반 재고 |
| ZONE_D | NORMAL | 25m | 일반 재고 |
| ZONE_E | COLD | 30m | 냉장품 |
| ZONE_F | COLD | 35m | 냉장품 |
| ZONE_G | FROZEN | 40m | 냉동품 |
| ZONE_H | NORMAL | 45m | 일반 재고 |
| ZONE_I | NORMAL | 55m | 저회전/보관용 |

시각화(13_VISUALIZATION_DESIGN.md)의 Warehouse Floor Replay는 이 9개 Zone을 3x3 격자 Heatmap으로 표현한다.

## 5. 적치 시나리오
- 동일 SKU Location 존재: INB003/SKU_A002는 L-A-001 추천
- 동일 SKU 없음: Zone 잔여용량 기준 추천
- 고회전 SKU: 가까운 Zone 가중치 적용
- 보관조건 불일치: NORMAL Zone 제외, COLD/FROZEN만 후보
- CAPA 부족: SOP 대응 필요

## 6. 피킹 시나리오
현재시간 10:20 기준:
| Order | Due | 라인수 | 총수량 | 특이사항 | 기대 |
|---|---|---:|---:|---|---|
| ORD001 | 11:00 | 1 | 20 | ZONE_A, 권장시작 10:30 | 1순위 (출고시간 임박) |
| ORD002 | 13:00 | 2 | 25 | customer_priority=5 | 2순위 (고객 우선순위로 ORD003보다 우선) |
| ORD003 | 13:00 | 1 | 30 | customer_priority=1 | 3순위 |
| ORD004 | 15:00 | 1 | 10 | SKU_A001 포함 (HIGH 위험) | shortage_risk_score 가점 검증 |

검증 포인트:
- ORD001: 출고시간 기반 1순위와 권장시작시간 10:30 (estimated 20분 + buffer 10분)
- ORD002 vs ORD003: 동일 출고시간에서 customer_priority 반영 여부
- ORD002: 멀티라인 주문의 예상 피킹시간 계산 (line_count 반영)
- ORD004: 재고 부족 위험 SKU 가점 반영 여부

## 6.1 출고확정 시나리오
- ORD010: 피킹완료 후 출고확정대기(SHIPPING_PENDING) 상태로 생성
- Demo 8에서 Dry Run → 승인 → SHIPPED 전환을 검증한다
- shipping_pending 20건 중 ORD010을 포함하여 최소 3건은 당일 확정 대상으로 생성

## 7. 재고 리스크 시나리오
- SKU_A001: 현재재고 120, 최근 출고 증가 추세, HIGH 위험
- SKU_A004: 재고 부족이나 3일 뒤 입고예정 존재
- SKU_A005: 안정 재고, LOW 위험

## 7.1 DES 자원·처리시간 시드
DES 시뮬레이션 입력. 처리시간은 확정값이 아닌 분포 파라미터로 생성한다.

resources (기본 구성):
| resource_id | type | count | shift |
|---|---|---:|---|
| W-01 | WORKER | 3 | 08:00~17:00 |
| F-01 | FORKLIFT | 2 | 08:00~17:00 |

process_time_params (예시, 분 단위):
| stage | distribution | mean | std | min | max |
|---|---|---:|---:|---:|---:|
| INBOUND | TRIANGULAR | 12 | 4 | 6 | 24 |
| STOCKING | TRIANGULAR | 8 | 3 | 4 | 18 |
| PICKING | LOGNORMAL | 15 | 5 | — | — |
| PACKING_SHIP | TRIANGULAR | 10 | 3 | 5 | 20 |

## 7.2 병목 유발 시나리오 (What-if 데모용)
What-if 시뮬레이션이 의미 있는 delta를 보이려면, baseline에서 **의도적으로 병목이 발생**하도록 시드를 구성한다.
- 특정일(예: 2026-06-16) 출고 주문을 자원 대비 과밀하게 배치 → 작업자 3명으로는 마감 내 처리 불가, 출고지연 발생
- 검증: `작업자 1명 추가` What-if → 출고지연 평균 감소, 피킹 대기 P90 감소가 눈에 보여야 함
- ZONE_A를 고회전품으로 90% 이상 채워 → `ZONE_A CAPA 20% 축소` What-if 시 적치 실패/Zone 포화 발생
- SKU_A001(HIGH 위험)의 Far Future 수요를 증가 추세로 → `수요 30% 증가` What-if 시 소진일 P50 단축

## 8. Demand History 생성 패턴
- increasing
- stable
- decreasing
- seasonal
- noisy

Forecast 검증을 위해 SKU_A001은 증가 추세로 생성한다.

## 9. 산출 파일
```text
seed/products.csv
seed/zones.csv
seed/locations.csv
seed/inventory.csv
seed/inbound_orders.csv
seed/outbound_orders.csv
seed/outbound_order_lines.csv
seed/demand_history.csv
seed/picking_tasks.csv
seed/stocking_tasks.csv
seed/shipping_pending.csv
seed/resources.csv
seed/process_time_params.csv
```
