# 09_UI_DESIGN.md

# UI Design

## 1. 목적
Streamlit 기반 UI를 설계한다. 운영자는 자연어 질문, 업무 대시보드, 추천 결과, 승인 버튼, Tool Trace, RAG 근거를 확인한다.

## 2. 메뉴
- Agent Chat
- Today Operations
- KPI Dashboard
- Warehouse Simulation (DES · What-if)  ← 메인
- Inbound & Stocking
- Outbound & Picking
- Inventory Risk
- Shipping Confirmation
- Trace & Logs
- Policy Documents

시각화 스택은 Streamlit + Plotly이며, 차트·KPI 명세는 13_VISUALIZATION_DESIGN.md를 따른다.

## 3. Agent Chat
자연어 입력과 응답을 제공한다.
예:
```text
오늘 뭐 해야 돼?
A제품 언제 소진돼?
INB003 적치 추천해줘
```

## 4. Today Operations
| 구분 | 대상 | 권장시간 | 상태 | Action |
|---|---|---|---|---|
| 피킹 | ORD001 | 10:30 | 추천 | 지시 생성 |
| 재고위험 | SKU_A001 | 6/18 소진 | HIGH | 대응 보기 |
| 적치 | INB003 | 즉시 | 추천 | 지시 생성 |
| 출고확정 | ORD010 | 즉시 | 대기 | 확정 |

## 4.1 KPI Dashboard
운영 KPI를 한눈에 제공한다. KPI 정의·산식은 13_VISUALIZATION_DESIGN.md §4.
- 상단 KPI 카드: 출고 정시율 | HIGH 위험 SKU 수 | 포화 Zone 수 | 적치 완료율
- Zone 점유율 Heatmap (현재 시점)
- 재고 위험 Top-N 리스트

## 4.2 Warehouse Simulation (DES · What-if) — 메인 화면
DES 1개 instance를 실제 창고처럼 모사하고 결과를 시각화한다(13_VISUALIZATION_DESIGN.md §2~3).
- **시뮬레이션 설정**: horizon_days, replications, random_seed / What-if 조건(작업자·지게차 증감, Zone CAPA, 수요 배수, 입고 지연)
- **Warehouse Floor Replay**: Zone 격자 Heatmap + 시간 슬라이더/재생, 이벤트 마커
- **Zone Capacity Heatmap** (시점 이동)
- **Dynamic Inventory Projection**: 재고 트렌드 (Near 실선·Far 점선, P50/P90 밴드, 소진 마커)
- **Event Timeline / Resource Utilization Trend**
- **What-if 비교**: baseline vs scenario KPI delta + 차트 병치
- KPI 분포 카드: 예상소진일 P50/P90, 출고지연 건수·발생확률, 평균 피킹 대기 P90

## 5. 적치 추천 화면
- 입고번호
- SKU
- 추천 Zone/Location
- 점수
- 추천사유
- 적치지시 생성 버튼

## 6. 피킹 추천 화면
- 주문번호
- 출고시간
- 예상작업시간
- 권장시작시간
- 우선순위
- 피킹지시 생성 버튼

## 7. 재고 리스크 화면
- SKU
- 현재재고
- 안전재고
- 예상소진일
- 위험등급
- SOP 대응
- 과거/예측 차트

## 7.1 출고확정 화면
- 주문번호
- 출고확정대기 도래시간
- Dry Run 변경 미리보기 (상태 전환, 재고 차감)
- 경고 사항
- 출고확정 버튼 (승인)

## 8. Trace 화면
- run_id
- intent
- Tool input/output
- RAG sources
- Verifier 결과
- 승인 여부

## 9. MVP 우선순위
1. Agent Chat
2. Today Operations
3. Approval 버튼
4. Warehouse Simulation (DES Replay + What-if) — 메인 기능
5. KPI Dashboard
6. Tool Trace
7. Inventory Risk 상세
