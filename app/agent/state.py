"""Agent 상태 정의 (docs/02_AGENT_ARCHITECTURE.md §6, §10)."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    user_query: str
    user_id: str | None
    intent: str | None
    intent_confidence: float | None
    parameters: dict
    missing_parameters: list[str]
    plan: list[str]
    tool_results: dict
    verification_results: dict
    rag_required: bool
    rag_context: list[dict]
    rag_context_sufficient: bool | None
    rag_retry_count: int
    draft_actions: list[dict]
    approval_required: bool
    final_response: str | None
    error: str | None


# 인텐트 목록 (docs/02 §4 + KPI/시뮬레이션 확장)
INTENTS = [
    "daily_summary", "inbound_query", "stocking_recommendation", "stocking_task_create",
    "outbound_query", "picking_recommendation", "picking_instruction_create",
    "inventory_risk", "risk_response_recommendation", "shipping_pending_query",
    "shipping_confirm", "kpi_query", "simulation_query", "policy_question",
    "greeting", "out_of_scope",
]

# 인텐트별 필수 파라미터
REQUIRED_PARAMS = {
    "stocking_recommendation": ["inbound_no"],
    "stocking_task_create": ["inbound_no", "location_id"],
    "picking_instruction_create": ["order_no"],
    "inventory_risk": ["sku"],
    "shipping_confirm": ["order_no"],
}

# RAG(근거 설명) 필요 인텐트
RAG_INTENTS = {"policy_question", "stocking_recommendation", "picking_recommendation",
               "inventory_risk", "risk_response_recommendation"}

# 상태변경(승인 필요) 인텐트
STATE_CHANGE_INTENTS = {"stocking_task_create", "picking_instruction_create", "shipping_confirm"}
