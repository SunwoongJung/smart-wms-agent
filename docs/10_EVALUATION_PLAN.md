# 10_EVALUATION_PLAN.md

# Evaluation Plan

## 1. 평가 영역
- Intent 평가
- Tool Selection 평가
- Rule Compliance 평가 (적치 정규화 민감도 포함)
- Forecast & Simulation 평가 (확률적 KPI)
- RAG 평가 (ALR + Sufficient Context)
- Approval 평가
- E2E 평가
- 평가 하네스 (재현성·자동 회귀)

## 2. Intent 평가
질문 100건 기준. 목표 Accuracy 95% 이상.

## 3. Tool Selection 평가
예: 재고 리스크 질문은 lookup_inventory, lookup_demand_history, inventory_forecast, calculate_inventory_risk가 선택되어야 한다. 목표 95% 이상.

## 4. Rule Compliance
### 적치
- 보관조건 불일치 추천 0건
- CAPA 부족 추천 0건
- 동일 SKU 우선 적용 95% 이상

### 피킹
- 출고시간 반영 100%
- 작업시간 반영 95% 이상
- 시작시간 계산 정확도 100%

### 적치 정규화 민감도 (scoring_formula.md 가중합)
- 모든 점수 항목이 0~1 정규화 범위 내 100%
- breakdown(항목별 기여분) 응답 포함 100%
- 가중치 민감도 테스트: 가중치(0.30/0.25/0.20/0.15/-0.10) 변경 시 추천 순위 변화가 의도대로인지 검증
- 동일 SKU 가중치 우선 검증: 잔여용량·거리가 크게 우수한 후보가 동일 SKU 후보를 역전할 수 있는지 (절대우선이 아님)

## 5. Forecast & Simulation 평가
Forecast(Regression):
- MAE
- Stockout Date Error
- Risk Classification Accuracy
- Forecast Coverage

DES(확률적 KPI, 07_FORECAST_AND_SIMULATION.md):
- KPI는 단일 값이 아닌 분포(P50/P90/발생확률)로 평가
- 재현성: seed 고정 시 동일 입력 → 동일 KPI 분포 재현 100%
- replication 수렴: N 증가 시 P50/P90 안정화 확인
- What-if 타당성: baseline→scenario delta 방향이 도메인 상식과 일치 (예: 작업자 추가 시 출고지연 감소)

## 6. RAG 평가 (ALR + Sufficient Context)
| 지표 | 목표 |
|---|---|
| Recall@3 | 85% 이상 |
| Source Accuracy | 90% 이상 |
| Groundedness | 90% 이상 |
| Formula Retrieval Accuracy | 90% 이상 |
| SOP Retrieval Accuracy | 85% 이상 |
| Sufficient Context 판정 정확도 | 85% 이상 (답변가능/불가 분류) |
| Abstain 정확도 | 근거 없는 질의에 "근거 부족" 응답 90% 이상 |
| Evidence Span 정확도 | 제시 근거 span이 실제 정답 근거와 일치 85% 이상 |
| 재검색 루프 한도 준수 | 재검색 ≤ 2회 100% (무한 루프 0건) |

## 7. Approval 평가
- 승인 없는 적치지시 생성 0건
- 승인 없는 피킹지시 생성 0건
- 승인 없는 출고확정 0건

## 8. 평가 하네스 (Harness Engineering)
멘토 피드백("하네스를 적극 활용")을 반영하여, 단발 정확도가 아니라 **반복 실행·재현 가능한 자동 검증 세트**를 둔다. 하네스는 두 의미를 구분한다.
- **런타임 하네스(루프)**: Agent가 롱호라이즌에서 죽지 않고 품질을 유지하도록 옆에서 가이드·검증하는 루프. 본 과제에서는 Verifier Node + 재계획(최대 2회), Sufficient Context 재검색(최대 2회)이 이에 해당하며, 02_AGENT_ARCHITECTURE.md의 plan→execute→verify 루프로 구현된다.
- **평가 하네스(테스트)**: 아래 자동 검증 세트.

| 하네스 | 검증 내용 |
|---|---|
| Tool execution harness | 동일 입력 → 동일 Tool 결과(deterministic) 재현 |
| RAG harness | 질문별 expected source/evidence span/answerable 라벨 대조 |
| DES simulation harness | seed 고정 후 KPI 분포(P50/P90) 재현성 |
| What-if harness | baseline/scenario delta 방향·크기 검증 |
| Answer grounding harness | 최종 응답의 모든 수치가 Tool 결과와 일치(생성된 수치 0건) |
| Regression test set | 멘토 피드백 반영 후 기존 기능(적치·피킹·출고확정·Forecast)이 깨지지 않는지 회귀 검증 |

각 하네스는 고정 입력셋 + 기대값으로 구성하며, 코드 변경 시 일괄 재실행한다.

## 9. 실패 케이스 기록
```json
{
  "case_id":"FAIL-001",
  "query":"A제품 위험해?",
  "failure_type":"RAG_ERROR",
  "expected":"inventory_risk_policy.md",
  "actual":"stocking_policy.md",
  "fix":"metadata filter 강화"
}
```
