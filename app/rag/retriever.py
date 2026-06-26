"""ALR + Sufficient Context + PRISM 리랭커 검색 (docs/03 §6).

흐름: 검색 → PRISM 리랭크(relevance·contribution·evidence_span) → Sufficient Context 게이트
     (부족 시 query rewrite 후 재검색 ≤2) → 근거 반환 / abstain.
PRISM·게이트는 경량 모델(gpt-4.1-mini)로 LLM 호출.
"""
import json

import trace_store
from config import settings
from llm import get_client
from rag.index import search

MAX_RETRIES = 2


def _json_chat(system: str, user: str) -> dict:
    resp = get_client().chat.completions.create(
        model=settings.openai_router_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {}


def prism_rerank(query: str, candidates: list[dict]) -> list[dict]:
    """각 후보의 relevance·contribution·evidence_span 산출 후 재정렬."""
    if not candidates:
        return []
    items = [{"id": c["id"], "text": c["text"][:600]} for c in candidates]
    system = ("당신은 검색 리랭커입니다. 각 문서가 질문에 답하는 데 얼마나 적합한지 평가합니다. "
              "반드시 JSON으로만 답하세요: {\"results\":[{\"id\":..,\"relevance\":0~1,"
              "\"contribution\":0~1,\"evidence_span\":\"핵심 근거 문장\"}]}")
    user = f"질문: {query}\n\n문서들:\n{json.dumps(items, ensure_ascii=False)}"
    scored = {r["id"]: r for r in _json_chat(system, user).get("results", []) if "id" in r}
    out = []
    for c in candidates:
        r = scored.get(c["id"], {})
        out.append({**c,
                    "relevance": float(r.get("relevance", c["similarity"])),
                    "contribution": float(r.get("contribution", 0.0)),
                    "evidence_span": r.get("evidence_span", c["evidence_summary"])})
    out.sort(key=lambda x: x["relevance"] * (0.5 + 0.5 * x["contribution"]), reverse=True)
    return out


def sufficient_context(query: str, evidence: list[dict]) -> dict:
    """검색 근거가 답변에 충분한지 판정."""
    ev = [{"source": e["source"], "evidence_span": e["evidence_span"],
           "relevance": round(e["relevance"], 2)} for e in evidence]
    system = ("당신은 RAG 충분성 판정기입니다. 제공된 근거만으로 질문에 정확히 답할 수 있는지 판단합니다. "
              "근거가 없거나 핵심이 빠졌으면 answerable=false. 반드시 JSON: "
              "{\"answerable\":bool,\"context_sufficiency_score\":0~1,\"missing_evidence_types\":[..]}")
    user = f"질문: {query}\n\n근거:\n{json.dumps(ev, ensure_ascii=False)}"
    j = _json_chat(system, user)
    return {"answerable": bool(j.get("answerable", False)),
            "context_sufficiency_score": float(j.get("context_sufficiency_score", 0.0)),
            "missing_evidence_types": j.get("missing_evidence_types", [])}


def retrieve(query: str, intent: str | None = None, k: int = 5) -> dict:
    """ALR 루프: 검색→리랭크→충분성 판정, 부족 시 재검색(≤2), 한도 초과 시 abstain."""
    q = query
    ranked, judge = [], {"answerable": False, "context_sufficiency_score": 0.0, "missing_evidence_types": []}
    retries = 0
    while True:
        cands = search(q, k=k, intent=intent)
        trace_store.emit(node="RAG Retriever", kind="search", attempt=retries + 1,
                         query=q, candidates=len(cands))
        ranked = prism_rerank(query, cands)
        trace_store.emit(node="RAG Retriever", kind="rerank", attempt=retries + 1,
                         top=[{"source": c.get("source"), "relevance": round(c.get("relevance", 0), 2),
                               "contribution": round(c.get("contribution", 0), 2)} for c in ranked[:3]])
        judge = sufficient_context(query, ranked)
        trace_store.emit(node="RAG Retriever", kind="sufficiency", attempt=retries + 1,
                         answerable=judge["answerable"], score=round(judge["context_sufficiency_score"], 2),
                         missing=judge["missing_evidence_types"])
        if judge["answerable"] or retries >= MAX_RETRIES:
            break
        # query rewrite: 부족한 근거 유형을 질의에 보강
        missing = " ".join(judge["missing_evidence_types"])
        q = f"{query} {missing}".strip()
        retries += 1
        trace_store.emit(node="RAG Retriever", kind="retry", attempt=retries + 1, query=q)
    abstain = not judge["answerable"]
    if abstain:
        trace_store.emit(node="RAG Retriever", kind="abstain")
    return {
        "answerable": judge["answerable"],
        "abstain": abstain,
        "sufficiency": judge,
        "retries": retries,
        "evidence": [] if abstain else [
            {"source": e["source"], "section": e["section"], "evidence_span": e["evidence_span"],
             "relevance": round(e["relevance"], 3), "contribution": round(e["contribution"], 3)}
            for e in ranked[:3]],
        "abstain_message": "문서 근거가 부족합니다." if abstain else None,
    }
