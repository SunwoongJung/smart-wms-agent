# 12_IMPLEMENTATION_ROADMAP.md

# Implementation Roadmap

## Phase 1. Project Setup
- Python 프로젝트 생성
- 디렉토리 구조 생성
- 환경설정
- requirements.txt
- LLM·임베딩 모델 확정(OpenAI 단일, 회사 Azure OpenAI 호환 게이트웨이): 생성/추론 = gpt-5.4, 라우터/추출 = gpt-4.1-mini, 임베딩 = text-embedding-3-small
- OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_API_VERSION 설정, AzureOpenAI 클라이언트(app/llm.py)

## Phase 2. Database & Seed
- SQLite schema
- Seed data generator
- products/zones/locations
- inventory/inbound/outbound
- demand_history
- resources/process_time_params (DES 입력)
- 병목 유발 시나리오 시드 (What-if 데모용)

## Phase 3. Tool Engine
- 조회 Tool
- 적치 Tool
- 피킹 Tool
- Draft/Approval Tool
- Dry Run Tool

## Phase 4. Forecast & Simulation
- Linear Regression 수요예측 (Far Future 입력)
- SimPy DES 엔진 (자원/처리시간 분포, Hybrid Forecast)
- Monte Carlo replication → KPI 분포(P50/P90/발생확률)
- 위험등급 판정
- What-if 시뮬레이션 + baseline/scenario 비교

## Phase 5. RAG (ALR + Sufficient Context)
- 정책 문서 작성
- Chunking
- Metadata (+ 인덱싱 시점 근거 메타: answerable_intents, evidence_summary)
- FAISS index
- PRISM 리랭커 (근거 passage·contribution 추출)
- Sufficient Context Judge + 재검색 루프(최대 2회)·abstain 정책
- Retrieval test

## Phase 6. LangGraph
- AgentState
- Router
- Parameter Extractor
- Planner
- Tool Executor
- Verifier
- RAG Decision
- Approval Gate

## Phase 7. API
- /chat
- /recommend/stocking
- /recommend/picking
- /forecast
- /simulate (DES · What-if)
- /kpi
- /approve
- /trace

## Phase 8. UI & Visualization (Streamlit + Plotly)
- Streamlit Chat
- Today Operations
- KPI Dashboard
- Warehouse Simulation: DES Floor Replay(시간 슬라이더), Zone Heatmap, Inventory Projection, Event Timeline, Resource Trend
- What-if baseline vs scenario 비교
- Approval
- Trace Viewer
- RAG Sources
- 명세: 13_VISUALIZATION_DESIGN.md

## Phase 9. Evaluation
- Intent eval
- Tool eval
- RAG eval
- Forecast eval
- E2E demo

## Phase 10. Enhancement
- Hybrid Search
- Reranker
- Forecast chart
- PostgreSQL 전환
- 실제 WMS API 연동
- Dreaming Memory (세션 종료 후 비동기 memory consolidation — 02_AGENT_ARCHITECTURE.md §10, 차순위)
- DES 처리시간 분포 실측값 교체, replication 수 튜닝
