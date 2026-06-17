# 01_PRD.md

# Smart WMS Agent PRD

## 1. 문서 목적
Smart WMS Agent의 제품 요구사항을 정의한다. 본 서비스는 간단한 WMS 데이터를 기반으로 창고 운영자가 자연어로 오늘 해야 할 업무, 적치 필요 건, 피킹 필요 건, 재고 리스크, 출고확정대기 건, 운영 KPI를 확인하고, 필요한 경우 승인 기반으로 작업지시를 생성할 수 있도록 지원하는 Agentic AI 서비스이다. **메인 기능은 SimPy DES 기반 창고상황 예측·What-if 시뮬레이션**이며, 모든 결과는 시각적으로 제공한다.

## 2. 제품 개요
Smart WMS Agent는 창고 운영자를 위한 Warehouse Operations Copilot이다. 사용자가 "오늘 뭐 해야 돼?"라고 물으면 Agent는 WMS 데이터를 조회하고 다음을 종합한다.

- 피킹지시가 필요한 출고예정 건
- 적치가 필요한 입고예정 또는 입고완료 건
- 과거 출고이력 기반 재고 부족 예상 품목
- 출고확정대기 건
- SOP 기준 대응이 필요한 예외 상황

예시 응답:

```text
오늘 우선 처리할 업무는 3건입니다.

1. 10:30 ORD001 피킹 지시 필요
   - 출고 예정시간: 11:00
   - 예상 피킹 소요시간: 20분
   - 버퍼시간: 10분

2. A제품 재고 부족 예상
   - 예상 소진일: 2026-06-18
   - 위험등급: HIGH
   - 대응방안: 입고예정 확인 및 긴급 보충 검토

3. 신규 입고건 적치 필요
   - 입고번호: INB003
   - 추천 Zone: Zone A
   - 추천 사유: 동일 SKU 존재, 잔여 CAPA 충분, 입구 거리 우수
```

## 3. 제품 목표

### 3.1 업무 목표
| 업무 영역 | 목표 |
|---|---|
| 입고/적치 | 입고예정 데이터를 확인하고 적치 위치를 추천한다. |
| 피킹/출고 | 출고예정 데이터를 확인하고 피킹 우선순위와 시작 예정시간을 추천한다. |
| 재고 리스크 | 과거 출고 이력 기반으로 재고 소진일을 예측하고 위험 품목을 탐지한다. |
| 설명 가능성 | 추천 이유를 정책 문서, 산식, Tool 결과 기반으로 설명한다. |
| 작업 실행 | 사용자가 승인한 경우에만 적치지시, 피킹지시, 출고확정을 생성한다. |

### 3.2 기술 목표
| 기술 요소 | 적용 목적 |
|---|---|
| LLM / 임베딩 모델 | OpenAI 단일(회사 Azure 호환 게이트웨이): 생성/추론 = gpt-5.4, 라우터 = gpt-4.1-mini, 임베딩 = text-embedding-3-small |
| LangGraph | Agent workflow, 상태 전이, 조건 분기 구현 |
| Tool Use | 재고조회, 적치추천, 피킹계산, KPI 집계, Forecast·DES 수행 |
| RAG | 정책 근거, 산식, SOP, 용어 설명 (ALR + Sufficient Context, 03_RAG_DESIGN.md) |
| SQLite | POC용 WMS 데이터 저장소 |
| Linear Regression | 과거 출고이력 기반 수요예측 (DES Far Future 입력) |
| SimPy DES | **메인 기능** — 자원 제약 하 창고상황 예측·What-if, 확률적 KPI 분포 (07_FORECAST_AND_SIMULATION.md) |
| Streamlit + Plotly | 시각화 — DES 창고 모사 Replay, Zone Heatmap, 재고 트렌드, KPI 대시보드 (13_VISUALIZATION_DESIGN.md) |
| Human-in-the-loop | 작업지시 생성 및 출고확정 전 사용자 승인 |
| Verifier | Tool 결과와 최종 답변 간 정합성 검증 |

## 4. 사용자
| 사용자 | 설명 |
|---|---|
| 창고 운영자 | 당일 입고, 적치, 출고, 피킹, 재고 리스크를 확인하고 작업을 지시한다. |
| 창고 관리자 | 운영 상황과 리스크를 확인하고 우선순위를 조정한다. |
| 시스템 관리자 | Seed data, 정책 문서, Tool 실행 로그, 평가 결과를 관리한다. |

## 5. 핵심 기능

### 5.1 오늘 할 일 요약
사용자 질문:
```text
오늘 뭐 해야 돼?
오늘 우선 처리할 일 알려줘
지금 기준으로 위험하거나 처리해야 할 작업 있어?
```
Agent는 미지시 출고, 피킹 시작 필요, 적치대기, 재고 부족 예상, 출고확정대기를 종합한다.

### 5.2 적치 추천
입고예정 또는 입고완료 후 적치대기 데이터가 존재하는 경우 Agent는 적치 후보 Location을 계산하고 추천한다.

추천 규칙:
```text
1. 적재 가능 Location 필터링
2. 동일 품목 Location 존재 여부 확인
3. 동일 품목 Location이 있으면 해당 Location 우선
4. 동일 품목 Location이 없으면 Zone 잔여용량 내림차순
5. 잔여용량이 같으면 입구 거리 오름차순
6. 고회전 품목이면 가까운 Zone에 가중치 부여
```

상태변경 원칙:
```text
추천 → 사용자 확인 → 승인 → 적치지시 생성
```

### 5.3 피킹 우선순위 추천
피킹 추천 기준:
- 출고 예정시간
- 예상 피킹 작업시간
- 이동거리
- 품목 수
- 작업 버퍼시간
- 고객 우선순위
- 재고 부족 위험

피킹 시작 예정시간:
```text
피킹 시작 예정시간 = 출고 예정시간 - 예상 피킹 작업시간 - 버퍼시간
```

### 5.4 창고상황 예측 (메인 기능, DES 기반)
본 제품의 핵심 기능이다. 단순 수량 예측이 아니라, 예측된 수요·확정 주문을 **실제 창고가 인력·장비·공간 제약 안에서 처리 가능한지** SimPy 이산사건 시뮬레이션(DES)으로 검증한다.

처리 흐름:
```text
1. Near Future: 확정 입출고 + 현재고 + 자원 제약 → SimPy DES
2. Far Future: 과거 출고이력 Linear Regression 수요예측 → 가상 출고 이벤트 → SimPy DES
3. 처리시간·수요를 분포에서 샘플링하여 N회 반복(Monte Carlo)
4. 예상소진일·출고지연·피킹대기·Zone 포화·자원 가동률을 분포(P50/P90/발생확률)로 산출
5. 결과를 시각화(창고 모사 Replay, Zone Heatmap, 재고 트렌드)로 제공
```
산식·구조는 07_FORECAST_AND_SIMULATION.md, 시각화는 13_VISUALIZATION_DESIGN.md를 따른다.

### 5.4.1 What-if 시뮬레이션
주문/재고/운영 조건이 변했을 때를 baseline 대비 비교한다. 예: 작업자 1명 추가, 지게차 1대 감소, 특정 Zone CAPA 축소, A제품 출고 30% 증가, 입고 1일 지연, 피킹 우선순위 변경. 결과는 baseline vs scenario KPI delta + 시각 비교로 제공한다.

### 5.5 SOP 기반 대응방안 추천
재고 리스크 또는 운영 예외가 발생한 경우 Agent는 SOP 문서를 검색하여 대응방안을 제안한다.

적용 대상:
- 재고 부족 예상
- CAPA 부족
- 적재 가능 Location 없음
- 출고시간 임박
- 피킹지시 미발행
- 입고 지연
- 출고확정 지연

### 5.6 추천 근거 설명
설명 구조:
```text
1. 결론
2. 사용된 데이터
3. 적용된 산식
4. 적용된 정책 문서
5. Tool 실행 결과
6. 예외 또는 주의사항
```

### 5.7 출고확정대기 조회 및 확정
출고확정은 반드시 승인 후 수행한다.
```text
확정 대상 조회 → Dry Run → 사용자 승인 → 출고확정
```

### 5.8 KPI 조회
운영자가 당일 운영 KPI를 자연어로 조회한다. 예: "오늘 출고 정시율 어때?", "Zone 점유율 보여줘", "위험 SKU 몇 건이야?". KPI 카탈로그(출고 정시율, 적치 완료율, 재고 회전율, Zone 점유율, HIGH 위험 건수 등)와 시각화는 13_VISUALIZATION_DESIGN.md §4를 따른다.

### 5.9 시각화
모든 결과는 시각적으로 제공한다(Streamlit + Plotly).
- **DES 1개 instance 창고 모사**: 시간 슬라이더 재생으로 Zone 점유율 변화·이벤트를 실제 창고처럼 표현(Warehouse Floor Replay).
- 결과 시각화: Zone Capacity Heatmap, 재고 수준 트렌드(Dynamic Inventory Projection, P50/P90 밴드), Event Timeline, 자원 가동률, What-if baseline vs scenario 비교.
- 운영 KPI 대시보드.
상세는 13_VISUALIZATION_DESIGN.md.

## 6. 범위 제외
- 실제 WMS/ERP/OMS 연동
- 실시간 바코드 스캔 연동
- 작업자 단말 연동
- 복잡한 최적화 알고리즘
- 실제 배차/TMS 연동
- 강화학습 기반 최적화
- 대규모 멀티창고 운영
- 권한/인증 체계 고도화

## 7. Agent 역할 경계
Agent는 업무 intent 분류, Tool 선택, Tool 결과 해석, RAG 문서 검색, 추천 사유 설명, Draft 생성, 승인 요청을 수행한다.  
Agent는 LLM 단독으로 적치 위치, 피킹 우선순위, 재고 수량, CAPA, 출고시간을 생성하지 않는다.

## 8. 주요 데이터
| 데이터 | 설명 |
|---|---|
| products | SKU, 품명, 카테고리, 보관조건, 고회전 여부, 안전재고 |
| zones | Zone 코드, 보관조건, 입구 거리, 피킹 우선도 |
| locations | Location 코드, Zone, CAPA, 현재 점유량, 사용 가능 여부 |
| inventory | SKU, Lot, Location, 수량, 입고일, 유통기한 |
| inbound_orders | 입고예정 데이터, SKU, 수량, 예정일, 상태 |
| outbound_orders | 출고예정 주문 헤더, 출고예정시간, 고객 우선순위, 상태 |
| outbound_order_lines | 출고예정 주문 라인, SKU, 수량 (주문당 1~N라인) |
| demand_history | SKU별 과거 일자별 출고량 |

## 9. RAG 문서
- stocking_policy.md
- picking_policy.md
- inventory_risk_policy.md
- warehouse_operation_sop.md
- scoring_formula.md
- wms_terms.md

## 10. 적용 패턴
- Meta-Controller / Router
- Planning
- Tool Use
- ReAct
- PEV
- Dry-Run Harness
- Human-in-the-loop
- Adaptive RAG
- Agentic RAG (ALR + Sufficient Context)
- Simulator (SimPy DES, What-if)

## 11. 성공 기준
| 기준 | 목표 |
|---|---|
| 자연어 질의 처리 | 주요 업무 intent를 분류하고 적절한 Tool 실행 |
| 적치 추천 | CAPA, 동일 SKU, 거리, 고회전 기준 반영 |
| 피킹 추천 | 출고시간과 작업시간을 고려한 우선순위 산출 |
| 창고상황 예측 (메인) | SimPy DES로 자원 제약 하 처리가능성 검증, KPI를 확률 분포(P50/P90)로 산출 |
| What-if 시뮬레이션 | 운영 조건 변경 시 baseline 대비 delta 산출·비교 |
| KPI 조회 | 운영 KPI(출고 정시율, Zone 점유율, 위험 건수 등) 조회 |
| 시각화 | DES 창고 모사 Replay, Zone Heatmap, 재고 트렌드, KPI 대시보드 제공 |
| RAG 설명 | 추천 근거와 SOP 대응방안을 문서 기반으로 설명 (ALR + Sufficient Context) |
| 승인 제어 | 적치지시, 피킹지시, 출고확정은 승인 후 실행 |
