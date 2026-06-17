# 13_VISUALIZATION_DESIGN.md

# Visualization & KPI Design

## 1. 목적과 원칙
시각화는 두 목적을 가진다.
1. **운영 현황 모니터링** — 운영자가 당일 처리 상태와 KPI를 한눈에 파악.
2. **DES Explainability** — "언제 부족한가"뿐 아니라 "왜·어디서 병목이 생기는가"를 직관적으로 설명.

원칙:
- 구현 스택: **Streamlit + Plotly**. DES 창고 모사는 **Plotly 시간슬라이더 Heatmap** 방식을 채택한다(`animation_frame` 또는 `st.slider` + 프레임 갱신).
- DES 결과 수치는 단일 값이 아니라 **분포(P50/P90/발생확률)**로 표기한다(07_FORECAST_AND_SIMULATION.md).
- 모든 시각화는 Tool/시뮬레이션 결과(simulation_kpis, simulation_events 등 04_DATABASE_DESIGN.md)에서 산출하며, 임의 생성 수치를 그리지 않는다.

## 2. DES 단일 INSTANCE 시각화 (창고 모사)
특정 1개 DES run(대표 run, 예: P50 시나리오)을 실제 창고처럼 모사한다. 시간축 재생으로 창고 상태 변화를 따라간다.

### 2.0 작업팀 이동 Replay (2인1조)
업무시간(09–18) 동안 **작업팀(지게차+작업자)**의 동선을 창고 평면에서 재생한다(sim/animation.py).
- **대기공간 = 입구**(좌하단). 작업 없으면 입구에서 대기.
- 입고: 입구 → 적치 Zone → 적치 작업(정지) → 입구 복귀. 출고: 입구 → 대상 Zone들 순회 피킹 → 입구(출고).
- **이동 경로 규칙**: 모든 쌍(입구↔Zone, Zone↔Zone)의 **거리 행렬**을 정의(animation.distance_matrix). 현재 위치에서 **가장 가까운 Zone**으로 이동하며, 동률이면 다음 후보까지 거리가 작은 쪽 선택(nearest_route).
- **통로 이동**: 팀은 Zone 위가 아니라 Zone 사이 **통로(아일) 격자**로만 이동(수직/수평 아일). 접근점은 Zone 코너.
- **방향 표시**: 팀 마커는 삼각형 픽토그램으로 진행 방향을 향하고, 작업 Zone 도착 시 해당 Zone을 응시.
- 마커 색: 파랑=이동 / 주황=작업 / 회색=유휴. 팀 수 = min(작업자, 지게차).

### 2.1 Warehouse Floor Replay (핵심)
Zone을 창고 평면 격자(grid)로 배치하고, 시뮬레이션 시간축을 따라 재생한다.
- **표현**: Plotly Heatmap — 각 Zone 셀 색 = 그 시점 점유율(0~100%). 시간 슬라이더/재생 버튼으로 시점 이동.
- **이벤트 오버레이**: 해당 시점 발생 이벤트(입고완료·적치완료·피킹시작·Zone 포화·출고지연·재고부족)를 발생 Zone 셀에 마커/주석으로 표시.
- **자원 표시(간단)**: 작업자/지게차 가동 수를 상단 인디케이터로 표시(아이콘 이동은 POC 범위 외, 색·수치로 대체).
- 데이터: simulation_events(시점·이벤트·Zone), Zone별 시계열 점유율.

### 2.2 Zone Capacity Heatmap
2.1의 점유율 레이어를 독립 화면으로도 제공. Picking/Staging/입고대기/출고대기 Zone 사용률을 시점 이동으로 확인.

### 2.3 Dynamic Inventory Projection
시간 경과에 따른 SKU 재고 트렌드.
- 현재고 + 입고 - 출고 - 예측수요 누적 라인.
- **Near Future = 실선(확정 기반), Far Future = 점선(Forecast 기반)** 으로 시각 구분.
- **P50/P90 신뢰밴드** 음영 표시, 재고 소진 예상 시점·안전재고 도달 시점 마커.

### 2.4 Event Timeline
시뮬레이션 중 주요 이벤트를 시간순 타임라인으로 표시(입고완료·적치완료·피킹시작·피킹존 포화·출고지연·재고부족). 결과뿐 아니라 원인 추적.

### 2.5 Resource Utilization Trend
작업자 가동률·지게차 가동률·피킹 대기 Queue·출고 대기 Queue를 시간축 라인으로 표시. 재고부족/출고지연이 수요 증가 때문인지 자원 부족 때문인지 구분 가능.

## 3. What-if 비교 + 실행 버전 관리
**버전 관리(로컬):** 각 시뮬레이션/What-if 실행은 실행시각 기반 버전명(`V%Y%m%d-%H%M%S`)으로
`simulation_runs`(result_json 포함)에 저장된다. UI에서 버전 목록을 조회하고, 버전별 KPI/차트를
재현하며, **정확히 2개 버전을 선택해 비교**한다(sim/versions.py: list_versions/get_version).

baseline run과 scenario run(또는 임의 2개 버전)을 나란히 비교한다(compare_simulation_scenarios).
- KPI delta 막대/표(예: 출고지연 3건→1건, 피킹대기 P90 42분→18분, 소진일 P50 +3일).
- 2.1~2.5의 핵심 차트를 선택한 2개 버전 2열로 병치하여 시각 비교.

## 4. 운영 KPI 카탈로그
운영 현황 KPI. 시뮬레이션 KPI는 07_FORECAST_AND_SIMULATION.md를 따른다.

| KPI | 산식 | 단위 | 시각화 | 데이터 출처 |
|---|---|---|---|---|
| 입고 처리율 | 처리완료 입고 / 당일 입고예정 | % | 게이지 | inbound_orders |
| 적치 완료율 | STOCKED / 적치대상 | % | 게이지 | inbound_orders, stocking_tasks |
| 피킹 정시 착수율 | 권장시작시간 이내 착수 / 전체 | % | 게이지 | picking_tasks |
| 출고 정시율 (on-time) | due_datetime 이내 출고 / 전체 | % | 게이지/추세 | outbound_orders |
| 재고 회전율 | 기간 출고량 / 평균 재고 | 회 | 막대 | demand_history, inventory |
| 안전재고 미달 SKU 수 | qty < safety_stock인 SKU 수 | 건 | 숫자 카드 | inventory, products |
| HIGH 위험 SKU 수 | risk_level=HIGH 건수 | 건 | 숫자 카드 | scan_inventory_risk |
| Zone별 점유율 | 점유 수량 / max_capacity | % | Heatmap | locations, zones |
| 포화 Zone 수 | 점유율 90% 초과 Zone 수 | 건 | 숫자 카드 | locations, zones |

시뮬레이션 KPI(분포): 예상소진일 P50/P90, 출고지연 건수·발생확률, 평균 피킹 대기 P90, 작업자·지게차 가동률 — simulation_kpis.

## 5. KPI 대시보드 레이아웃 (09_UI_DESIGN.md 연계)
```text
[상단] 운영 KPI 카드 줄: 출고정시율 | HIGH 위험 | 포화 Zone | 적치완료율
[중단] Zone 점유율 Heatmap (현재 시점)  |  재고 위험 Top-N
[하단] (시뮬레이션 진입 시) DES Replay / Inventory Projection / What-if 비교
```

## 6. 구현 메모
- Plotly `graph_objects.Heatmap` + `st.slider`로 시점 제어, 또는 `px` `animation_frame`으로 재생.
- DES Tool(run_des_simulation)이 시점별 Zone 점유율 시계열과 simulation_events를 반환하도록 출력 확장(06_TOOL_DESIGN.md).
- KPI 조회는 query_operation_kpis Tool로 집계(06_TOOL_DESIGN.md), API는 /kpi(08_API_SPEC.md).
