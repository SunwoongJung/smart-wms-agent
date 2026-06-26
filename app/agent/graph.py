"""LangGraph 그래프 조립 + 실행 진입점 (docs/02 §2).

START → router → param_extractor →(필수값 누락? clarification→END)→ planner → tool_executor
      → verifier → rag_decision →(RAG 필요? retriever)→ response_generator → approval_gate → END
"""
from langgraph.graph import END, START, StateGraph

from agent import nodes
from agent.state import AgentState


def _after_params(state: dict) -> str:
    return "clarify" if state.get("missing_parameters") else "plan"


def _after_rag_decision(state: dict) -> str:
    return "retrieve" if state.get("rag_required") else "generate"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("router", nodes.router_node)
    g.add_node("param_extractor", nodes.param_extractor_node)
    g.add_node("planner", nodes.planner_node)
    g.add_node("tool_executor", nodes.tool_executor_node)
    g.add_node("verifier", nodes.verifier_node)
    g.add_node("rag_decision", nodes.rag_decision_node)
    g.add_node("rag_retriever", nodes.rag_retriever_node)
    g.add_node("response_generator", nodes.response_generator_node)
    g.add_node("approval_gate", nodes.approval_gate_node)

    g.add_edge(START, "router")
    g.add_edge("router", "param_extractor")
    g.add_conditional_edges("param_extractor", _after_params,
                            {"clarify": "response_generator", "plan": "planner"})
    g.add_edge("planner", "tool_executor")
    g.add_edge("tool_executor", "verifier")
    g.add_edge("verifier", "rag_decision")
    g.add_conditional_edges("rag_decision", _after_rag_decision,
                            {"retrieve": "rag_retriever", "generate": "response_generator"})
    g.add_edge("rag_retriever", "response_generator")
    g.add_edge("response_generator", "approval_gate")
    g.add_edge("approval_gate", END)
    return g.compile()


_GRAPH = None


def run(query: str, user_id: str | None = None, history: list[dict] | None = None) -> dict:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH.invoke({"user_query": query, "user_id": user_id, "history": history or []})


def stream_run(query: str, user_id: str | None = None, history: list[dict] | None = None):
    """노드 단위로 (node_id, 누적 state 스냅샷)을 yield(실시간 동작 스텝핑용).

    stream_mode='updates' → 각 노드 실행 직후 그 노드의 state 델타를 받아 누적한다.
    호출자는 마지막 스냅샷을 최종 state로 사용한다(invoke와 동일 결과).
    """
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    state: dict = {}
    inp = {"user_query": query, "user_id": user_id, "history": history or []}
    for update in _GRAPH.stream(inp, stream_mode="updates"):
        for node_id, delta in (update or {}).items():
            if isinstance(delta, dict):
                state.update(delta)
            yield node_id, dict(state)


if __name__ == "__main__":
    import sys
    r = run(sys.argv[1] if len(sys.argv) > 1 else "오늘 뭐 해야 돼?")
    print("intent:", r.get("intent"), "| approval:", r.get("approval_required"))
    print(r.get("final_response"))
