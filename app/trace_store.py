"""에이전트 실행 트레이스 — LangGraph 노드 흐름 + RAG 검색 과정을 per-run 저장(Phoenix식 관측).

기존 tool_logs/rag_logs는 챗 그래프가 직접 도구를 호출해 채워지지 않으므로, 매 /chat 실행의
최종 상태에서 노드별 입출력을 재구성해 agent_traces에 저장한다. AI 동작 검증 화면이 이를 읽는다.
"""
import json
import threading
import uuid
from datetime import datetime

from db.database import get_connection
from tools.common import q

# 노드 내부 세밀 이벤트 버스 — 동기 그래프가 한 스레드에서 돌므로 thread-local 싱크.
# /chat/stream 워커가 set_sink로 SSE 큐 push를 걸고, retriever 등 내부에서 emit() 호출.
_emit_local = threading.local()


def set_sink(fn) -> None:
    _emit_local.sink = fn


def clear_sink() -> None:
    _emit_local.sink = None


def emit(**event) -> None:
    fn = getattr(_emit_local, "sink", None)
    if fn:
        try:
            fn(event)
        except Exception:
            pass


def ensure_trace_table() -> None:
    conn = get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS agent_traces (
            run_id TEXT PRIMARY KEY, session_id TEXT, query TEXT, intent TEXT, confidence REAL,
            rag_required INTEGER, answerable INTEGER, sufficiency REAL, retries INTEGER,
            abstain INTEGER, approval_required INTEGER, steps_json TEXT, final_response TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
    finally:
        conn.close()


def build_steps(state: dict) -> list[dict]:
    """최종 상태에서 노드 실행 경로를 논리적으로 재구성."""
    steps = [{"node": "Router", "label": "의도 분류(LLM)",
              "out": {"intent": state.get("intent"), "confidence": state.get("intent_confidence"),
                      "parameters": state.get("parameters", {})}}]
    missing = state.get("missing_parameters") or []
    steps.append({"node": "Param Extractor", "label": "필수 파라미터 검증",
                  "out": {"missing_parameters": missing}})
    if missing:
        steps.append({"node": "Response Generator", "label": "되묻기(clarify)",
                      "out": {"final_response": state.get("final_response")}})
        return steps
    steps.append({"node": "Planner", "label": "실행 계획", "out": {"plan": state.get("plan", [])}})
    tr = state.get("tool_results", {}) or {}
    steps.append({"node": "Tool Executor", "label": "도구 실행",
                  "out": {"tools": [k for k in tr.keys() if not k.startswith("_")],
                          "error": state.get("error")}})
    steps.append({"node": "Verifier", "label": "결과 검증",
                  "out": {"verification_results": state.get("verification_results", {})}})
    rag_req = bool(state.get("rag_required"))
    steps.append({"node": "RAG Decision", "label": "문서검색 필요 판단", "out": {"rag_required": rag_req}})
    if rag_req:
        suff = state.get("_rag_sufficiency") or {}
        steps.append({"node": "RAG Retriever", "label": "검색·PRISM 리랭크·충분성 게이트",
                      "out": {"evidence": state.get("rag_context", []),
                              "answerable": state.get("rag_context_sufficient"),
                              "sufficiency_score": suff.get("context_sufficiency_score"),
                              "missing_evidence_types": suff.get("missing_evidence_types", []),
                              "retries": state.get("rag_retry_count"),
                              "abstain": bool(state.get("_rag_abstain"))}})
    steps.append({"node": "Response Generator", "label": "응답 생성(LLM)",
                  "out": {"final_response": state.get("final_response")}})
    steps.append({"node": "Approval Gate", "label": "승인 게이트(HITL)",
                  "out": {"approval_required": bool(state.get("approval_required")),
                          "draft_actions": state.get("draft_actions", [])}})
    return steps


def save(state: dict, session_id: str | None = None, query: str | None = None) -> str:
    ensure_trace_table()
    run_id = "R-" + uuid.uuid4().hex[:8]
    suff = state.get("_rag_sufficiency") or {}
    steps = build_steps(state)
    conn = get_connection()
    try:
        conn.execute("""INSERT INTO agent_traces(run_id,session_id,query,intent,confidence,rag_required,
            answerable,sufficiency,retries,abstain,approval_required,steps_json,final_response,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (run_id, session_id, query or state.get("user_query"), state.get("intent"),
                      state.get("intent_confidence"), 1 if state.get("rag_required") else 0,
                      1 if state.get("rag_context_sufficient") else 0,
                      suff.get("context_sufficiency_score"), state.get("rag_retry_count"),
                      1 if state.get("_rag_abstain") else 0, 1 if state.get("approval_required") else 0,
                      json.dumps(steps, ensure_ascii=False, default=str), state.get("final_response"),
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    finally:
        conn.close()
    return run_id


def list_traces(limit: int = 40, session_id: str | None = None) -> list[dict]:
    ensure_trace_table()
    where = "WHERE session_id=? " if session_id else ""
    params = (session_id, limit) if session_id else (limit,)
    return q(f"""SELECT run_id, query, intent, confidence, rag_required, answerable, retries,
                abstain, approval_required, created_at FROM agent_traces {where}
                ORDER BY created_at DESC, rowid DESC LIMIT ?""", params)


def get_trace(run_id: str) -> dict | None:
    ensure_trace_table()
    rows = q("SELECT * FROM agent_traces WHERE run_id=?", (run_id,))
    if not rows:
        return None
    t = rows[0]
    t["steps"] = json.loads(t.pop("steps_json") or "[]")
    return t


# 그래프 노드 ID → (표시이름, 라벨, out 추출기) — build_steps와 동일 포맷(프론트 renderStepBody 재사용)
GRAPH_NODE_STEP = {
    "router": ("Router", "의도 분류(LLM)",
               lambda s: {"intent": s.get("intent"), "confidence": s.get("intent_confidence"),
                          "parameters": s.get("parameters", {})}),
    "param_extractor": ("Param Extractor", "필수 파라미터 검증",
                        lambda s: {"missing_parameters": s.get("missing_parameters") or []}),
    "planner": ("Planner", "실행 계획", lambda s: {"plan": s.get("plan", [])}),
    "tool_executor": ("Tool Executor", "도구 실행",
                      lambda s: {"tools": [k for k in (s.get("tool_results") or {}) if not k.startswith("_")],
                                 "error": s.get("error")}),
    "verifier": ("Verifier", "결과 검증",
                 lambda s: {"verification_results": s.get("verification_results", {})}),
    "rag_decision": ("RAG Decision", "문서검색 필요 판단",
                     lambda s: {"rag_required": bool(s.get("rag_required"))}),
    "rag_retriever": ("RAG Retriever", "검색·PRISM 리랭크·충분성 게이트",
                      lambda s: {"evidence": s.get("rag_context", []),
                                 "answerable": s.get("rag_context_sufficient"),
                                 "sufficiency_score": (s.get("_rag_sufficiency") or {}).get("context_sufficiency_score"),
                                 "missing_evidence_types": (s.get("_rag_sufficiency") or {}).get("missing_evidence_types", []),
                                 "retries": s.get("rag_retry_count"),
                                 "abstain": bool(s.get("_rag_abstain"))}),
    "response_generator": ("Response Generator", "응답 생성(LLM)",
                           lambda s: {"final_response": s.get("final_response")}),
    "approval_gate": ("Approval Gate", "승인 게이트(HITL)",
                      lambda s: {"approval_required": bool(s.get("approval_required")),
                                 "draft_actions": s.get("draft_actions", [])}),
}


def live_step(node_id: str, state: dict) -> dict | None:
    """실행 중 노드 1개가 끝난 시점의 스텝 dict(표시이름·라벨·out)."""
    m = GRAPH_NODE_STEP.get(node_id)
    if not m:
        return None
    name, label, fn = m
    return {"node": name, "label": label, "out": fn(state)}
