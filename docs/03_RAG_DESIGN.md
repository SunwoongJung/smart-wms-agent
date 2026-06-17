# 03_RAG_DESIGN.md

# RAG Design

## 1. 목적
RAG는 추천 근거, 정책, 산식, SOP, 용어 설명을 제공한다. 의사결정 자체는 Tool이 수행하고, RAG는 Tool 결과를 설명할 근거를 제공한다.

## 2. RAG 적용 영역
| 영역 | 질문 | 검색 문서 |
|---|---|---|
| 적치 설명 | 왜 Zone A야? | stocking_policy.md, scoring_formula.md |
| 피킹 설명 | 왜 ORD001이 1순위야? | picking_policy.md, scoring_formula.md |
| 재고 리스크 | A제품 왜 위험해? | inventory_risk_policy.md |
| SOP 대응 | 부족하면 어떻게 해? | warehouse_operation_sop.md |
| 산식 설명 | 소진일은 어떻게 계산해? | scoring_formula.md |
| 용어 설명 | 출고확정대기가 뭐야? | wms_terms.md |

## 3. 문서 구성
- stocking_policy.md: 동일 SKU 우선, CAPA, 거리, 고회전 SKU 정책
- picking_policy.md: 출고시간, 작업시간, 버퍼, 우선순위 정책
- inventory_risk_policy.md: 예상소진일, 안전재고, 위험등급
- warehouse_operation_sop.md: 재고부족, CAPA부족, 출고임박 대응
- scoring_formula.md: 적치/피킹/Forecast 산식
- wms_terms.md: WMS 용어

## 4. Chunking 전략
| 문서 유형 | Chunk 기준 |
|---|---|
| 정책 | 정책 항목 단위 |
| SOP | 예외상황 단위 |
| 산식 | 산식 1개 단위 |
| 용어 | 용어 1~3개 단위 |

권장 Chunk Size: 800~1500 characters  
권장 Overlap: 100~200 characters

## 5. Metadata
```json
{
  "source": "stocking_policy.md",
  "document_type": "policy",
  "domain": "stocking",
  "section": "same_sku_policy",
  "version": "1.0",
  "priority": "high"
}
```

document_type: policy, sop, formula, glossary, guide  
domain: stocking, picking, inventory, shipping, common

### 인덱싱 시점 근거 메타 (ALR Localization 사전 기록)
DocSeeker ALR 사상을 차용하여, reasoning을 인퍼런스 타임이 아닌 **인제스천(인덱싱) 타임**에 일부 외부화한다. 각 chunk에 아래 메타를 추가로 부여해 질의 시 evidence localization을 가속하고 근거 설명력을 높인다.
```json
{
  "answerable_intents": ["stocking_recommendation", "policy_question"],
  "evidence_summary": "동일 SKU가 있으면 같은 Location 우선 배치"
}
```
- `answerable_intents`: 이 chunk가 근거로 답할 수 있는 intent 목록
- `evidence_summary`: 이 chunk의 핵심 근거 한 줄 요약 (Localization·설명 생성에 사용)

### Section ID 매핑 규칙
Chunk는 각 문서의 `##` 헤딩 단위로 생성하며, 한국어 헤딩을 아래 표 기준의 영문 section id로 변환하여 metadata에 부여한다. 표에 없는 헤딩은 케밥/스네이크 케이스 영문으로 신규 등록한다.

| 문서 | 한국어 헤딩 | section id |
|---|---|---|
| stocking_policy.md | 동일 SKU 우선 정책 | same_sku_policy |
| stocking_policy.md | Zone 잔여용량 정책 | capacity_policy |
| stocking_policy.md | 거리 정책 | distance_policy |
| stocking_policy.md | 고회전 SKU 정책 | fast_moving_policy |
| picking_policy.md | 피킹 시작시간 | picking_start_time |
| picking_policy.md | 예상 피킹시간 | picking_time_estimation |
| picking_policy.md | 우선순위 기준 | picking_priority_policy |
| inventory_risk_policy.md | 위험등급 | risk_level |
| inventory_risk_policy.md | 데이터 부족 Fallback | forecast_fallback |
| warehouse_operation_sop.md | 재고 부족 예상 대응 | sop_stock_shortage |
| warehouse_operation_sop.md | CAPA 부족 대응 | sop_capacity_shortage |
| warehouse_operation_sop.md | 적재 가능 Location 없음 대응 | sop_no_available_location |
| warehouse_operation_sop.md | 피킹지시 미발행 대응 | sop_picking_not_issued |
| warehouse_operation_sop.md | 입고 지연 대응 | sop_inbound_delay |
| warehouse_operation_sop.md | 출고확정 지연 대응 | sop_shipping_confirm_delay |
| scoring_formula.md | 적치 점수 | stocking_score_formula |
| scoring_formula.md | 피킹 우선순위 | picking_priority_formula |
| scoring_formula.md | 예상소진일 | stockout_formula |

## 6. Retrieval Strategy (Evidence-first, ALR + Sufficient Context)
단순 vector search + rerank를 넘어, **근거를 먼저 찾아 고정하고(ALR) → 충분한지 판단하는(Sufficient Context) 게이트와 복구 루프**를 둔다. 설계 사상의 차용 배경은 §6.1을 참조한다.

```text
1. Intent 확인
2. 필요 evidence 정의 (Analysis)         ← 이 질의에 답하려면 어떤 근거(정책/산식/SOP)가 필요한지 명시
3. 검색 대상 문서군 결정 + Metadata Filter
4. Vector Search (Top-K)
5. PRISM Rerank + 근거 passage 추출 (Localization)  ← 재정렬 + relevance·contribution·evidence_span 산출
6. Sufficient Context Judge               ← 충분성 판단
     ├─ 충분 → 7로
     └─ 부족 → query rewrite / 문서군 확장 후 4로 (재검색 최대 2회)
                 재시도 한도 초과 시 → "문서 근거가 부족합니다" abstain
7. 근거 기반 답변 생성 (Reasoning) → Response Generator
```

### Sufficient Context Judge 출력 필드
```json
{
  "answerable": true,
  "context_sufficiency_score": 0.0,
  "missing_evidence_types": [],
  "required_sources": ["stocking_policy.md#same_sku_policy"],
  "evidence_span": [{"source":"...", "section":"...", "text":"..."}],
  "reranker_contribution": [{"source":"...", "score":0.0}]
}
```
- 재검색 루프는 **최대 2회**로 제한한다(무한 루프 방지). 한도 초과 시 abstain.

## 6.1 이 구조를 차용한 이유
멘토 피드백("RAG의 reasoning·퀄리티 보완, agentic RAG 참고")을 반영하여 세 가지를 **역할이 겹치지 않게** 결합했다.

| 구성 | 출처 | 역할 | 단독 사용 시 한계 |
|---|---|---|---|
| ALR (Analysis-Localization-Reasoning) | DocSeeker (CVPR 멀티모달 문서이해 모델, arXiv:2604.12812) — **모델이 아니라 설계 사상만 차용** | 근거를 먼저 위치특정하고 추론하는 구조. 인덱싱 단계에 근거를 미리 기록 → 근거 설명력↑ | 근거가 코퍼스에 없을 때 멈추는 규칙이 없어 환각 위험 |
| Sufficient Context | Google 계열 연구 (arXiv:2411.06037) | "이 근거로 답해도 되나?" 게이트. 부족 시 abstain 또는 재검색 | 검색·랭킹 품질 자체는 개선 못 함(판정만) |
| PRISM Reranker | arXiv 리랭커 (단순 relevance + contribution·evidence passage 산출) | §5 Localization 단계의 실제 부품 | — |

**왜 결합인가:** ALR은 "잘 찾아 잘 답하는 긍정 경로"의 품질(설명력)을, Sufficient Context는 "답할지/멈출지/더 찾을지"의 제어 경로(환각 방지·복구)를 담당한다. 두 사상이 다루는 축이 달라 보완 관계이며, ALR이 근거를 잘 찾아주면 Sufficient Context의 "거짓 부족" 판정이 줄고, Sufficient Context가 진짜 빈틈을 잡아 재검색을 유도한다 → 멘토가 언급한 agentic RAG / 루프 구조가 완성된다.

**왜 DocSeeker를 모델로 쓰지 않는가:** DocSeeker는 문서 이미지 기반 멀티모달·초장문 모델로 VL-7B 파인튜닝이 필요하다. 본 과제 코퍼스는 텍스트 정책 md 6개로 소규모이므로 모델 도입은 과하며, ALR "흐름"만 차용한다.

**POC 범위 주의:** 코퍼스가 작고 구조화되어 재검색 루프는 자주 발동되지 않을 수 있다. 그래도 SOP·엣지 케이스의 안전망으로 유지하고, 재검색 한도(2회)와 abstain 정책으로 비용·지연을 통제한다.

## 7. Adaptive RAG
RAG 생략 질문:
```text
오늘 입고예정 보여줘
A제품 현재 재고 알려줘
```
RAG 사용 질문:
```text
왜 Zone A를 추천했어?
부족하면 어떻게 대응해야 해?
피킹 시작시간은 어떻게 계산해?
```

## 8. SOP 기반 RAG
Forecast Tool이 예상소진일과 위험등급을 계산하면, RAG는 inventory_risk_policy.md와 warehouse_operation_sop.md를 검색하여 대응방안을 제공한다.

## 9. Response Grounding 원칙
최종 답변에는 Tool 결과, 적용 정책, 사용 산식, 참조 문서, 권장 조치를 포함한다. RAG 문서에 없는 정책을 임의로 생성하지 않는다.

## 10. 임베딩 및 Vector Store
| 항목 | 정의 |
|---|---|
| Vector DB | FAISS (POC). 향후 PostgreSQL/pgvector 전환 가능 |
| 임베딩 모델 | OpenAI `text-embedding-3-small` (한국어 정확도 필요 시 `text-embedding-3-large`). 생성(gpt-5.4)·라우터(gpt-4.1-mini)와 동일 공급자(회사 Azure 호환 게이트웨이) |
| 모델 요구사항 | 한국어 문서 검색 지원, 모델 교체가 가능하도록 임베딩 인터페이스(`EmbeddingProvider`) 추상화. 인덱싱과 질의는 반드시 동일 임베딩 모델 사용, 모델 교체 시 전체 재인덱싱 (인덱스 재생성 스크립트 포함) |
| 인덱스 갱신 | 정책 문서 변경 시 전체 재인덱싱 (POC 규모에서 충분) |

대화 이력은 RAG 대상이 아니다. 문서 검색은 RAG, 대화 문맥은 세션 메모리(02_AGENT_ARCHITECTURE.md §10)로 분리하여 관리한다.

## 11. 평가 기준
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

상세 평가 절차·하네스는 10_EVALUATION_PLAN.md를 따른다.
