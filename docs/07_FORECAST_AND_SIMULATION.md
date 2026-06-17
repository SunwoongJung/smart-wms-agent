# 07_FORECAST_AND_SIMULATION.md

# Forecast & Simulation Design

## 1. 목적과 핵심 원칙
본 과제의 재고 리스크 분석은 **단순 수량 예측이 아니라, 예측된 수요·확정 주문을 실제 창고가 운영 제약 안에서 처리 가능한지 검증**하는 것을 목표로 한다.

핵심 원칙:
1. **DES는 수요예측 도구가 아니다.** SimPy 기반 이산사건 시뮬레이션(DES)은 인력·장비·공간 제약 하에서 입고/적치/피킹/패킹/출고 이벤트가 처리 가능한지, 어디서 병목이 생기는지를 검증하는 운영 시뮬레이션 엔진이다.
2. **출력은 단일 값이 아니라 확률적 분포다.** 처리시간과 수요를 분포에서 샘플링하여 시뮬레이션을 N회 반복(replication)하고, 예상소진일·출고지연·대기시간을 P50/P90과 발생확률 형태로 산출한다.
3. **Hybrid Forecast.** 단기는 확정 이벤트 기반, 중장기는 Regression 수요예측 결과를 이벤트로 변환하여 DES에 투입한다.

## 2. Hybrid Forecast 구조
```text
현재 시점
    │
    ├─ Near Future (기본 3일)
    │     확정 입고예정 + 확정 출고예정 + 현재재고 + 운영 자원 제약
    │        └─ SimPy DES (확정 이벤트 기반)
    │
    └─ Far Future (기본 4일 이후)
          과거 출고이력 기반 Regression 수요예측
             └─ 예측 수요 → 가상 출고 이벤트 생성 (수요 불확실성 샘플링)
                  └─ SimPy DES
```
- Near/Far 경계는 기본 3일이며 파라미터로 조정 가능하다.
- 두 구간을 하나의 연속된 타임라인으로 연결하여 산출한다 (09_UI_DESIGN.md의 Hybrid Forecast Timeline).

## 3. 입력 데이터
- inventory (현재재고)
- demand_history (Regression 입력)
- inbound_orders / outbound_orders (확정 이벤트)
- products.safety_stock
- resources (작업자/지게차 수, 교대) — 04_DATABASE_DESIGN.md
- process_time_params (단계별 처리시간 분포) — 04_DATABASE_DESIGN.md
- zones.max_capacity (Zone CAPA)

## 4. Regression 수요예측 (Far Future 입력)
```text
x = day_index
y = shipped_qty
predicted_demand(t) = a * day_index + b
```
- Fallback: 30일↑ Linear Regression / 14일↑ 14일 이동평균 / 7일↑ 7일 이동평균 / 7일 미만 예측 불가
- 점추정 평균을 그대로 쓰지 않고, **예측 수요를 분포의 평균(λ)으로 사용**한다(아래 §6 수요 샘플링).

## 5. DES 목적식 (Objectives)
시뮬레이션이 산출해야 하는 운영 질문이다.
| 목적 | 설명 |
|---|---|
| 재고 소진 시점 | projected_inventory ≤ 0 도달 시점 (분포) |
| 안전재고 도달 시점 | projected_inventory ≤ safety_stock 도달 시점 |
| 출고 지연 발생 | due_datetime을 넘긴 출고 주문 수 |
| 대기 Queue 최소화 | 피킹/패킹/출고 단계별 대기열 길이·대기시간 |
| Zone 포화/적치 실패 | Zone별 최대 점유율, 적치 실패 이벤트 |
| 자원 사용률 | 작업자/지게차 가동률 |
| What-if 서비스레벨 비교 | 조건 변경 시 baseline 대비 delta |

## 6. DES 제약사항 (Constraints) 과 확률 모델
### 자원 (SimPy Resource) — 팀 모델
작업은 팀 단위로 수행한다. **1팀 = 작업자 2 + 지게차 1**. 동시 가용 팀 수 = **min(작업자 수 // 2, 지게차 수)**.
(남는 작업자나 지게차는 조를 이루지 못한다.) 한 작업(입고+적치, 또는 피킹+패킹)을 한 팀이 처리하며, 팀이 입구↔Zone을 이동한다.
| 자원 | 모델 | 출처 |
|---|---|---|
| 작업팀 | `simpy.Resource(capacity=min(worker_count // 2, forklift_count))` | resources |
| Zone 공간 | 용량 한도까지만 적치(초과=STOCKING_FAILED) | zones |

- **업무시간 09–18** 내에서 작업/이동이 일어난다(애니메이션은 이 구간만 표현).
- 팀 수 = min(작업자//2, 지게차)이므로, **병목 자원**(작업자 또는 지게차)을 늘려야 팀이 증가한다. 비병목 자원만 늘리면 효과가 없다.
- **베이스라인 갱신**: What-if 결과를 의사결정으로 채택하면 resources 테이블의 작업자/지게차 수를 실제 갱신하여 새 베이스라인으로 삼는다(app/resmgmt.py).

### 처리시간 분포 (확정값이 아닌 분포로 모델링)
모두 음수가 나오지 않는 양의 시간 분포를 사용한다. `process_time_params.distribution`로 단계별 지정하며, 분포 종류는 교체 가능하다(TRIANGULAR / LOGNORMAL / WEIBULL 허용 — Weibull은 멘토 제안 대안).
| 단계 | 기본 분포 | 선택 근거 |
|---|---|---|
| 입고 처리 | Triangular(min/mode/max) | 실측 데이터 없이 "최소~보통~최대"만 합리적 추정 가능할 때 적합 (POC 시드) |
| 적치 처리 | Triangular | 〃 |
| 피킹 처리 | Lognormal(양수·우편향) | 작업시간은 음수가 없고 가끔 길게 끌리는 꼬리(long tail)가 있어 우편향 분포가 현실적 |
| 패킹/출고 처리 | Triangular | 〃 |

### 수요 불확실성 (Far Future)
```text
predicted_demand(t) = Regression 평균 λ(t)
가상 출고량(t) ~ Poisson(λ(t))   # replication마다 재샘플링
```
- **Poisson**: 단위 기간당 발생하는 이산 출고 건수/수량을 세는 표준 분포(평균=분산=λ).
- 회귀의 점추정 평균을 그대로 쓰지 않고 그 평균을 λ로 삼아 매 replication마다 재샘플링하는 것이 "단일 점추정 → 확률적 분포"의 실제 구현 지점이다.
- Near Future는 확정 입출고 이벤트라 시점이 고정되며, 무작위성은 처리시간에서만 들어온다.

### 기타 제약
- 출고 마감시간(due_datetime), 입고 예정 지연 가능성, 피킹 우선순위 정책(recommend_picking 순서 반영)

## 7. 확률적 산출 (Monte Carlo Replication)
```text
for run in 1..N (기본 N=200, seed 고정):
    처리시간·수요를 분포에서 샘플링
    SimPy DES 1회 실행
    run별 KPI 기록
→ KPI를 분포로 집계 (P50, P90, 발생확률)
```
- **seed 고정 시 동일 입력은 동일 KPI 분포를 재현**해야 한다(10_EVALUATION_PLAN.md의 DES harness).
- 출력 KPI 분포는 특정 모수분포를 가정하지 않는 **경험적(표본) 분포**다. N개 run 표본의 percentile로 P50/P90을 산출한다.

## 8. 출력 KPI (분포 형태)
| KPI | 산출 형태 |
|---|---|
| 예상소진일 | P50 / P90 날짜 (예: P50 2026-06-21, P90 2026-06-18) |
| 안전재고 도달일 | P50 / P90 날짜 |
| 출고 지연 주문 수 | 평균 / P90 / 지연발생확률 |
| 평균 피킹 대기시간 | 평균 / P90 (분) |
| Zone별 최대 점유율 | 평균 / P90 (%) |
| 작업자·장비 사용률 | 평균 (%) |
| 병목 이벤트 타임라인 | run 대표 1건(예: P50 시나리오) |

> 응답·UI에서 수치를 인용할 때는 단일 값이 아니라 "P50 …, P90 …" 또는 "지연 발생확률 NN%" 형태로 표기한다.

## 9. What-if 시뮬레이션
baseline 대비 운영 조건 변경 시나리오를 비교한다(06_TOOL_DESIGN.md의 simulate_operation_what_if / compare_simulation_scenarios).

조건 예:
```text
작업자 1명 추가 / 지게차 1대 감소 / 특정 Zone CAPA 20% 축소
A제품 출고량 30% 증가 / 입고 1일 지연 / 피킹 우선순위 정책 변경
```
출력(baseline vs scenario):
```text
Baseline:  예상소진일 P50 2026-06-18 | 출고지연 평균 3건 | 피킹대기 P90 42분
Scenario:  예상소진일 P50 2026-06-21 | 출고지연 평균 1건 | 피킹대기 P90 18분
```

## 10. 한계와 확장
- Regression은 추세 예측에만 적합하며 계절성·프로모션에 약하다 → 향후 Prophet/XGBoost로 확장.
- 처리시간 분포 파라미터는 시드 데이터 기반 가정값이며, 실제 WMS 연동 시 실측 분포로 교체한다.
- N(replication 수)은 정확도-속도 트레이드오프이며 기본 200에서 조정한다.
