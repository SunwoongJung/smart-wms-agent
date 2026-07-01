# 02_AGENT_ARCHITECTURE.md

# WOONG AI Architecture

## 1. 목적
LangGraph 기반 Agent Architecture를 정의한다. 본 Agent는 창고 운영 데이터를 분석하고 업무 우선순위를 추천하며, 상태 변경 전 승인 절차를 수행한다.

## 2. 전체 Workflow
조건 분기를 포함한 LangGraph 그래프 구조이다.

```text
START
  ↓
Router Node
  ↓
Parameter Extractor Node
  ├─ 필수 파라미터 누락 → Clarification 응답 (사용자 재질문) → END
  ↓
Planner Node ←──────────────┐
  ↓                         │
Tool Executor Node          │
  ↓                         │
Verifier Node               │
  ├─ 검증 실패 → 재계획 (최대 2회) ─┘
  ├─ 재계획 한도 초과 → 오류 응답 → END
  ↓ 검증 통과
RAG Decision Node
  ├─ RAG 불필요 → Response Generator Node
  ↓ RAG 필요
RAG Retriever Node (ALR: 필요 evidence 정의 → 검색 → PRISM Rerank·근거추출)
  ↓
Sufficient Context Node
  ├─ 근거 부족 → query rewrite/문서군 확장 후 재검색 (최대 2회) ──┐
  │     재시도 한도 초과 → "문서 근거가 부족합니다" abstain → Response Generator
  └─ 근거 충분 ↓                                              │
RAG Retriever Node ←──────────────────────────────────────────┘
  ↓
Response Generator Node
  ↓
Approval Gate Node
  ├─ 상태변경 아님 (조회/추천/설명) → END
  ├─ 사용자 거부 → Draft REJECTED → END
  ↓ 사용자 승인
State Update Tool Node
  ↓
END
```

## 3. 적용 Agentic Pattern
| Pattern | Node | 목적 |
|---|---|---|
| Meta Controller | Router | 질의 intent 분류 |
| Planning | Planner | Tool 실행계획 생성 |
| Tool Use | Tool Executor | 조회, 추천, Forecast, 상태변경 |
| ReAct | Planner+Executor | 복합 질의에서 실행/관찰 반복 |
| PEV | Planner+Executor+Verifier | 실행 전후 오류 검증 |
| Dry Run | Approval Gate | 상태변경 전 미리보기 |
| Human-in-the-loop | Approval Gate | 사용자 승인 기반 실행 |
| Adaptive RAG | RAG Decision | 필요한 경우만 문서 검색 |
| Agentic RAG | RAG Retriever + Sufficient Context | ALR(근거 우선) 검색 + 충분성 게이트·재검색 루프 (03_RAG_DESIGN.md §6) |
| Simulator | DES Tool (run_des_simulation) | 자원 제약 하 처리가능성 검증, 확률적 KPI, What-if |

## 4. Intent 체계
| Intent | 설명 | 예시 |
|---|---|---|
| daily_summary | 오늘 할 일 종합 | 오늘 뭐 해야 돼? |
| inbound_query | 입고예정 조회 | 오늘 입고예정 보여줘 |
| stocking_recommendation | 적치 추천 | INB003 적치 추천 |
| stocking_task_create | 적치지시 생성 | 적치지시 생성해줘 |
| outbound_query | 출고예정 조회 | 오늘 출고예정 보여줘 |
| picking_recommendation | 피킹 추천 | 피킹 순서 알려줘 |
| picking_instruction_create | 피킹지시 생성 | ORD001 피킹지시 생성 |
| inventory_risk | 재고 리스크 | A제품 언제 소진돼? |
| risk_response_recommendation | SOP 대응 | 부족하면 어떻게 해? |
| shipping_pending_query | 출고확정대기 조회 | 출고확정대기 보여줘 |
| shipping_confirm | 출고확정 | ORD001 출고확정 |
| kpi_query | 운영 KPI 조회 | 오늘 출고 정시율 어때? Zone 점유율 보여줘 |
| simulation_query | DES 창고상황 예측·What-if | 이번 주 창고 상황 예측해줘, 작업자 1명 늘리면? |
| policy_question | 정책/산식 질문 | 왜 Zone A야? |

## 5. Node 상세

### 5.1 Router Node
자연어 질의를 업무 intent로 분류한다. 상태변경 질문인지 조회성 질문인지 구분한다. 모든 질문에 모든 Tool을 실행하지 않도록 비용과 응답시간을 제어한다.

### 5.2 Parameter Extractor Node
질문에서 SKU, inbound_no, order_no, zone_id, location_id, target_date, action_type을 추출한다. 부족한 값이 있으면 clarification으로 분기한다.

### 5.3 Planner Node
업무 intent와 파라미터를 기준으로 Tool 실행 순서를 계획한다. 예를 들어 재고 리스크 질의는 재고조회, 출고이력조회, 입고예정조회, Forecast, 위험등급계산, SOP검색 순서로 계획한다.

### 5.4 Tool Executor Node
실제 업무 계산을 수행한다. LLM이 임의 계산하지 않도록 DB 조회, 점수 계산, Forecast, Draft 생성을 Tool로 분리한다.

### 5.5 Verifier Node
Tool 결과가 업무 규칙을 지키는지 검증한다. CAPA 초과, 보관조건 불일치, 피킹 시작시간 오류, Tool 결과와 응답 수치 불일치를 차단한다.

### 5.6 RAG Decision Node
RAG가 필요한지 판단한다. 단순 조회에는 RAG를 생략하고, 추천 근거/정책/SOP/산식 질문에만 RAG를 사용한다.

### 5.7 RAG Retriever Node
ALR(Analysis-Localization-Reasoning) 사상을 차용한다. ①질의에 필요한 evidence 유형을 정의하고 ②정책·산식·SOP·용어 문서를 검색한 뒤 ③PRISM 리랭커로 재정렬하며 근거 passage(evidence span)와 contribution을 추출한다. 결과는 Sufficient Context Node로 전달된다. 상세는 03_RAG_DESIGN.md §6.

### 5.7.1 Sufficient Context Node
검색된 근거가 질의에 답하기 충분한지 판정한다(Google Sufficient Context 사상). 충분하면 Response Generator로, 부족하면 query rewrite/문서군 확장으로 재검색한다(최대 2회). 한도 초과 시 "문서 근거가 부족합니다"로 abstain한다. 근거 없는 답변 생성을 차단하는 게이트 역할이다. 차용 배경·필드는 03_RAG_DESIGN.md §6.1.

### 5.8 Response Generator Node
결론, 수치, 근거, 산식, 정책, 권장조치, 승인 필요 여부를 포함한 최종 응답을 생성한다.

### 5.9 Approval Gate Node
적치지시, 피킹지시, 출고확정 같은 상태변경 작업 전 사용자 승인을 요구한다.

### 5.10 State Update Tool Node
승인된 Draft에 대해서만 실제 DB 상태를 변경한다.

## 6. Agent State Schema
```python
class AgentState(TypedDict):
    user_query: str
    user_id: str | None
    intent: str | None
    intent_confidence: float | None
    parameters: dict
    missing_parameters: list[str]
    plan: list[dict]
    tool_results: dict
    verification_results: dict
    rag_required: bool
    rag_queries: list[str]
    rag_context: list[dict]
    rag_context_sufficient: bool | None   # Sufficient Context 판정
    rag_retry_count: int                  # 재검색 횟수 (최대 2)
    draft_actions: list[dict]
    approval_required: bool
    approval_status: str | None
    final_response: str | None
    error: str | None
```

## 7. 주요 Workflow
Tool 이름은 06_TOOL_DESIGN.md의 표준 Tool 목록을 따른다.

### Daily Summary
```text
lookup_outbound_orders (status=PLANNED, 미지시 출고)
→ recommend_picking
→ lookup_inbound_orders (status=RECEIVED, 적치대기)
→ recommend_stocking
→ scan_inventory_risk
→ lookup_shipping_pending
→ Response Generator (종합 요약 생성)
```

### Stocking Recommendation
```text
lookup_inbound_orders
→ filter_available_locations
→ check_same_sku_location
→ calculate_stocking_score
→ recommend_stocking
→ Verifier
→ RAG (stocking_policy, scoring_formula)
→ Response Generator
```

### Inventory Risk
```text
lookup_inventory
→ lookup_demand_history
→ lookup_inbound_orders (status=PLANNED, 입고예정)
→ inventory_forecast (Far Future 수요예측)
→ run_des_simulation (자원 제약 하 KPI 분포)
→ calculate_inventory_risk
→ RAG (inventory_risk_policy, warehouse_operation_sop)
→ Response Generator
```

### Shipping Confirm
```text
lookup_shipping_pending
→ create_shipping_confirm_draft (Dry Run 자동 수행)
→ Approval Gate (Dry Run 결과 표시 + 승인 요청)
→ confirm_shipping
```

## 8. 설계 원칙
1. LLM은 계산하지 않는다.
2. Tool이 계산한다.
3. LLM은 결과를 설명한다.
4. RAG는 정책과 SOP 근거를 제공한다.
5. 상태 변경은 승인 후 수행한다.
6. 모든 추천은 Tool trace로 추적 가능해야 한다.

## 9. Agent 페르소나 및 응답 원칙
System Prompt에 반영할 Agent 정체성 정의이다.

| 항목 | 정의 |
|---|---|
| Agent 이름 | WOONG AI |
| 주요 역할 | 창고 운영 Copilot. 업무 intent 분류, Tool 실행 결과 해석, 정책·산식 기반 근거 설명, Draft 생성과 승인 요청 |
| 핵심 목표 | 운영자가 당일 우선 처리할 업무를 빠짐없이, 근거와 함께 파악하고 안전하게 실행하도록 지원 |
| 사용 LLM | OpenAI 단일(회사 Azure OpenAI 호환 게이트웨이). 생성/추론/Tool: `gpt-5.4`(Response Generator), 라우터·파라미터 추출: `gpt-4.1-mini`(경량). 임베딩: `text-embedding-3-small`(한국어 극대화 필요 시 `-large`) — RAG 검색 전용. AzureOpenAI 클라이언트(app/llm.py), model-agnostic 인터페이스 |

### 톤앤매너
- 간결한 존댓말을 사용한다 ("~입니다", "~가 필요합니다").
- 결론을 먼저 말하고 근거를 뒤에 붙인다 (결론 → 수치 → 근거/산식 → 권장조치).
- 모든 수치는 Tool 결과를 그대로 인용하며, "약", "아마" 같은 추측 표현을 쓰지 않는다.
- HIGH 위험, 출고시간 임박 등 긴급 건은 응답 첫머리에 배치한다.
- 이모지, 과장 표현, 불필요한 사과를 사용하지 않는다.
- 상태변경 작업은 반드시 "승인이 필요합니다"를 명시하고 변경 내용을 요약해 보여준다.

### 응답 금지 영역
- Tool 결과 없이 재고 수량, 위치, 시간 등 수치를 생성하는 것
- RAG 문서에 없는 정책·SOP를 임의로 만들어 설명하는 것
- 승인 없이 상태변경이 완료된 것처럼 표현하는 것
- WMS 업무 범위 밖 질문에 답변하는 것 (범위 밖 질문은 지원 가능한 업무 목록을 안내)

## 10. 대화 메모리 및 세션 관리
AgentState는 단일 질의 1회 처리용이며, 멀티턴 문맥은 별도의 SessionState로 관리하여 각 턴 시작 시 AgentState에 주입한다.

### SessionState Schema
```python
class SessionState(TypedDict):
    session_id: str
    user_id: str
    history: list[dict]          # 최근 10턴 윈도우 버퍼 (질문, 응답 요약, intent)
    active_draft_ids: list[str]  # 승인 대기 중인 Draft
    last_intent: str | None
    last_entities: dict          # 최근 언급된 sku, order_no, inbound_no, zone_id
```

### 메모리 전략
| 항목 | 정의 |
|---|---|
| 메모리 유형 | 윈도우 버퍼 (최근 10턴) + 구조화 세션 슬롯 (active_draft_ids, last_entities) |
| 멀티턴 해소 | "승인해줘" → active_draft_ids 참조, "그 제품은?" → last_entities로 대명사 해소, 해소 불가 시 clarification |
| 세션 초기화 | 30분 무활동 시 세션 종료. 새 세션은 빈 history로 시작 |
| Draft 영속성 | PENDING_APPROVAL Draft는 DB(action_drafts)에 저장되어 세션과 무관하게 유지. 세션 만료 후에도 draft_id로 승인 가능 |
| 장기 메모리 | POC 범위 제외. 모든 영속 상태는 DB(action_drafts, tool_logs, rag_logs)로 관리 |

### 장기 메모리 (Dreaming Memory) — 차순위 Enhancement (Phase 10 이후)
멘토 제안. POC에서는 구현하지 않고 **설계만 남겨둔다**(손이 많이 가므로 후순위). 구현 시 방향:
- 세션 종료 후 **비동기 memory consolidation** 수행 (대화 전체를 그대로 적재하지 않음).
- 안정적인 **운영 선호 / 반복 이슈 / 자주 언급되는 SKU**만 구조화하여 요약 저장. 예: "사용자는 출고 임박 건을 재고 리스크보다 우선 확인하는 경향".
- 저장 전 필터링: 개인정보, 일회성 지시, 잘못된 추론은 제외.
- **장기 메모리는 답변 근거(RAG)가 아니라 개인화·업무 편의용으로만 사용**한다(근거는 RAG, 문맥은 세션, 개인화는 장기 메모리로 역할 분리).
- 단순 로그 적재가 아닌 유사 항목 통합(consolidation)이 핵심.

## 11. 구현 반영 (2026-06-25)

### 11.1 Intent 확장 (실 WMS 흐름)
실 WMS(BGF로지스) 메뉴를 참조해 출고 할당·체화재고·보충 인텐트를 추가했다.
- 조회: `allocation_query`(할당현황·예상 결품), `dead_stock_query`(체화재고), `replenishment_query`(피킹면 보충)
- 상태변경(승인 필요): `allocation_create`, `disposal_create`, `replenish_create`
- STATE_CHANGE_INTENTS / REQUIRED_PARAMS / ToolExecutor 핸들러에 반영.

### 11.2 멀티턴 맥락 (§10 단기 메모리 구현)
- AgentState에 `history`(최근 6턴) 추가, `run(query, user_id, history)`로 주입.
- Router: 이전 대화로 대명사·생략 해소("그거 할당해줘" → 직전 order_no).
- Response Generator: `recent_dialogue`를 컨텍스트에 포함해 연속성 유지.
- 영속화는 서버 DB(chat_sessions/chat_messages, 04 §7 참고). 장기 메모리(§10)는 설계만 유지.

### 11.3 실행 트레이스(관측)
- 매 `/chat` 실행의 최종 상태에서 노드 경로를 재구성해 `agent_traces`에 저장(trace_store).
- LangGraph 미선언 채널 드롭 방지를 위해 `_rag_sufficiency/_rag_abstain/_rag_abstain_msg`를 State에 선언.
- AI 동작 검증 화면(09 §10)이 조회: Router→ParamExtractor→…→RAG(PRISM·충분성)→Response→Approval.
