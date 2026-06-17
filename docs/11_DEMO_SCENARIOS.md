# 11_DEMO_SCENARIOS.md

# Demo Scenarios

## Demo 1: 오늘 뭐 해야 돼?
기대:
- 피킹 필요
- 적치 필요
- 재고 위험
- 출고확정대기

## Demo 2: INB003 적치 추천
기대:
- 추천 Location
- 점수
- 동일 SKU/CAPA/거리 근거
- 승인 요청

## Demo 3: 왜 Zone A야?
기대:
- stocking_policy.md
- scoring_formula.md
- 적용 데이터 설명

## Demo 4: 오늘 피킹해야 할 것 알려줘
기대:
- ORD001 1순위
- 권장 시작시간 10:30

## Demo 5: SKU_A001 언제 소진돼?
기대:
- Linear Regression
- 예상소진일
- 위험등급 HIGH

## Demo 6: 부족하면 어떻게 대응해?
기대:
- inventory_risk_policy.md
- warehouse_operation_sop.md
- 입고예정 확인, 긴급보충 검토

## Demo 7: ORD001 피킹지시 생성해줘
기대:
- Draft 생성
- 승인 요청
- 승인 후 PICKING_ISSUED

## Demo 8: ORD010 출고확정해줘
기대:
- Dry Run
- 승인 요청
- 승인 후 SHIPPED

## Demo 9: 이번 주 창고 상황 예측해줘 (메인)
기대:
- DES 실행(run_des_simulation), KPI 분포(예상소진일 P50/P90, 출고지연 발생확률 등)
- Warehouse Floor Replay(시간 슬라이더), Zone Heatmap, 재고 트렌드 시각화

## Demo 10: 작업자 1명 더 투입하면 출고지연 줄어?
기대:
- What-if(simulate_operation_what_if: worker_delta=1) → baseline 대비 비교
- 출고지연 건수↓, 피킹 대기 P90↓ 시각 비교

## Demo 11: 6/15에 SKU_A001 100개 입고되면?
기대:
- 수요/입고 변경 What-if → 소진일 P50/P90 변화 비교

## Demo 12: 오늘 출고 정시율이랑 Zone 점유율 보여줘
기대:
- query_operation_kpis → KPI 카드 + Zone 점유율 Heatmap
