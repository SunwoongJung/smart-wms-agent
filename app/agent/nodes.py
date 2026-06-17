"""LangGraph 노드 구현 (docs/02 §5).

Router(LLM) → ParamExtractor(검증) → Planner(규칙) → ToolExecutor(핸들러) →
Verifier(규칙) → RAG Decision/Retriever/Sufficient → ResponseGenerator(LLM) → ApprovalGate.
계산은 Tool이, 설명은 LLM이 담당(docs/02 §8).
"""
import json

from config import settings
from llm import get_client
from rag import retriever
from sim import des, forecast, whatif
from tools import drafts, lookups, picking, stocking

from agent.state import (RAG_INTENTS, REQUIRED_PARAMS, STATE_CHANGE_INTENTS)


def _json_chat(system: str, user: str, model: str) -> dict:
    resp = get_client().chat.completions.create(
        model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"})
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {}


def _current_dt() -> str:
    return f"{settings.base_date} 10:20"


# ---------- 1. Router (intent + parameters, LLM) ----------
def router_node(state: dict) -> dict:
    system = (
        "당신은 WMS 운영 조수의 라우터입니다. 사용자 질의의 intent와 파라미터를 추출해 JSON으로만 답하세요.\n"
        "intent 정의:\n"
        "- policy_question: 추천/판단의 '이유·근거·정책·산식'을 묻는 질문. 예: \"왜 Zone A야?\", "
        "\"왜 ORD001이 1순위야?\", \"소진일은 어떻게 계산해?\"\n"
        "- stocking_recommendation: 특정 입고건 적치 위치 추천. 예: \"INB003 적치 추천해줘\"\n"
        "- picking_recommendation: 피킹 순서/우선순위 추천. 예: \"오늘 피킹 순서 알려줘\"\n"
        "- inventory_risk: 특정 SKU 소진/위험. 예: \"SKU_A001 언제 소진돼?\"\n"
        "- kpi_query: 운영 KPI 조회. 예: \"Zone 점유율 보여줘\", \"출고 정시율 어때?\"\n"
        "- simulation_query: 창고상황 예측·What-if. 예: \"이번 주 예측\", \"작업자 1명 늘리면?\"\n"
        "- daily_summary: \"오늘 뭐 해야 돼?\" 류 종합. 특정 영역만 요약/정리 요청도 daily_summary로 분류하고 "
        "parameters.scope에 영역을 넣는다(all|inbound|outbound|picking|risk|shipping). "
        "예: \"입고 업무만 요약\"·\"적치대기만 정리\"→scope=inbound, \"출고만 정리\"→scope=outbound, "
        "\"피킹만\"→scope=picking, \"재고위험만\"→scope=risk. 영역 한정이 없으면 scope=all.\n"
        "- inbound_query / outbound_query / shipping_pending_query: 데이터 '목록'을 그대로 보여달라는 단순 조회"
        "(\"입고예정 보여줘\"). '요약/정리/업무'는 조회가 아니라 daily_summary(scope)로 분류한다.\n"
        "- stocking_task_create / picking_instruction_create / shipping_confirm: 지시 생성·출고확정(상태변경)\n"
        "- risk_response_recommendation: \"부족하면 어떻게 대응?\" SOP 대응\n"
        "- greeting: 인사·잡담. 예: \"안녕?\", \"고마워\", \"잘 지내?\"\n"
        "- out_of_scope: WMS 운영과 무관한 질문(날씨·일반상식 등)\n"
        "규칙: 질의에 '왜', '이유', '어떻게 계산'이 있으면 policy_question 을 우선한다. "
        "단순 인사·감사는 greeting(업무 목록을 나열하지 말 것).\n"
        "parameters 키(있을 때만): sku, inbound_no, order_no, location_id, zone_id, target_date, kpis, scenario, scope.\n"
        '형식: {"intent":..,"confidence":0~1,"parameters":{..}}'
    )
    j = _json_chat(system, state["user_query"], settings.openai_router_model)
    return {"intent": j.get("intent"), "intent_confidence": j.get("confidence"),
            "parameters": j.get("parameters", {}) or {}}


# ---------- 2. Parameter Extractor (필수값 검증) ----------
def param_extractor_node(state: dict) -> dict:
    req = REQUIRED_PARAMS.get(state.get("intent"), [])
    params = state.get("parameters", {})
    missing = [p for p in req if not params.get(p)]
    return {"missing_parameters": missing}


# ---------- 3. Planner (규칙 기반) ----------
def planner_node(state: dict) -> dict:
    return {"plan": [state.get("intent") or "unknown"]}


# ---------- 4. Tool Executor (인텐트 핸들러) ----------
def _h_daily_summary(p):
    """오늘 할 일 종합. scope로 영역을 한정한다(all|inbound|outbound|picking|risk|shipping)."""
    scope = p.get("scope") or "all"
    out = {"_scope": scope}
    if scope in ("all", "inbound"):
        out["stocking_wait"] = lookups.lookup_inbound_orders(["RECEIVED"])["orders"]    # 적치대기
        if scope == "inbound":  # 입고 전용 요약에선 입고예정도 함께(전체 '할 일'엔 미포함)
            out["inbound_planned"] = lookups.lookup_inbound_orders(["PLANNED"])["orders"]
    if scope in ("all", "picking", "outbound"):
        out["picking"] = picking.recommend_picking(_current_dt(), forecast.risk_level_map())["recommendations"][:5]
    if scope in ("all", "risk"):
        out["inventory_risk"] = forecast.scan_inventory_risk(["HIGH", "MEDIUM", "WATCH"])["risks"]
    if scope in ("all", "shipping"):
        out["shipping_pending"] = lookups.lookup_shipping_pending()["pending"]
    return out


def _h_stocking_reco(p):
    return {"recommendation": stocking.recommend_stocking(p["inbound_no"])}


def _h_inventory_risk(p):
    return {"forecast": forecast.inventory_forecast(p["sku"]),
            "risk": forecast.calculate_inventory_risk(p["sku"])}


def _h_picking_reco(p):
    return {"recommendations": picking.recommend_picking(_current_dt(), forecast.risk_level_map())["recommendations"][:10]}


def _h_kpi(p):
    kpis = p.get("kpis") or ["zone_occupancy", "saturated_zone_count", "safety_stock_below_count"]
    return lookups.query_operation_kpis(kpis)


def _h_simulation(p):
    sc = p.get("scenario")
    if sc:
        base = des.run_des_simulation(horizon_days=7, replications=40)
        scen = whatif.simulate_operation_what_if(sc, horizon_days=7, replications=40)
        return {"baseline": base, "scenario": scen,
                "comparison": whatif.compare_simulation_scenarios(base, scen)["comparison"]}
    return {"baseline": des.run_des_simulation(horizon_days=7, replications=40)}


def _h_inbound_query(p):
    return lookups.lookup_inbound_orders(p.get("status") or ["PLANNED", "RECEIVED"], p.get("target_date"))


def _h_outbound_query(p):
    return lookups.lookup_outbound_orders(["PLANNED"], p.get("target_date"))


def _h_shipping_pending(p):
    return lookups.lookup_shipping_pending()


def _h_risk_response(p):
    return {"risks": forecast.scan_inventory_risk(["HIGH", "MEDIUM"])["risks"]}


def _h_stocking_create(p):
    return {"draft": drafts.create_stocking_task_draft(p["inbound_no"], p["location_id"])}


def _h_picking_create(p):
    d = drafts.create_picking_instruction_draft(p["order_no"])
    return {"draft": d, "dry_run": drafts.dry_run_action(d["draft_id"]) if "draft_id" in d else None}


def _h_shipping_confirm(p):
    return {"draft": drafts.create_shipping_confirm_draft(p["order_no"])}


_HANDLERS = {
    "daily_summary": _h_daily_summary, "stocking_recommendation": _h_stocking_reco,
    "inventory_risk": _h_inventory_risk, "picking_recommendation": _h_picking_reco,
    "kpi_query": _h_kpi, "simulation_query": _h_simulation, "inbound_query": _h_inbound_query,
    "outbound_query": _h_outbound_query, "shipping_pending_query": _h_shipping_pending,
    "risk_response_recommendation": _h_risk_response, "stocking_task_create": _h_stocking_create,
    "picking_instruction_create": _h_picking_create, "shipping_confirm": _h_shipping_confirm,
    "policy_question": lambda p: {}, "greeting": lambda p: {}, "out_of_scope": lambda p: {},
}

GREETING_MSG = ("안녕하세요, Smart WMS Agent입니다. 오늘 할 일 요약, 적치·피킹 추천, "
                "재고 소진 예측, 창고 시뮬레이션(What-if), KPI 조회를 도와드립니다. 무엇을 도와드릴까요?")
OUT_OF_SCOPE_MSG = ("WMS 운영 업무만 지원합니다. 오늘 할 일, 적치·피킹 추천, 재고 리스크 예측, "
                    "창고 시뮬레이션, KPI 조회 등을 요청해 주세요.")


def tool_executor_node(state: dict) -> dict:
    handler = _HANDLERS.get(state.get("intent"))
    if not handler:
        return {"tool_results": {}, "error": "지원하지 않는 intent"}
    try:
        return {"tool_results": handler(state.get("parameters", {}))}
    except Exception as e:  # noqa: BLE001
        return {"tool_results": {}, "error": f"Tool 실행 오류: {e}"}


# ---------- 5. Verifier (규칙 검증) ----------
def verifier_node(state: dict) -> dict:
    res, tr = {}, state.get("tool_results", {})
    rec = tr.get("recommendation")
    if rec and rec.get("recommended_location_id"):
        bd = rec.get("breakdown", {})
        res["score_in_range"] = all(0 <= bd.get(k, 0) <= 1 for k in bd)
    return {"verification_results": res}


# ---------- 6. RAG Decision / Retriever / Sufficient ----------
def rag_decision_node(state: dict) -> dict:
    return {"rag_required": state.get("intent") in RAG_INTENTS}


def rag_retriever_node(state: dict) -> dict:
    r = retriever.retrieve(state["user_query"], intent=state.get("intent"))
    return {"rag_context": r["evidence"], "rag_context_sufficient": r["answerable"],
            "rag_retry_count": r["retries"],
            "_rag_abstain": r["abstain"], "_rag_abstain_msg": r.get("abstain_message")}


# ---------- 7. Response Generator (LLM, gpt-5.4) ----------
_PERSONA = (
    "당신은 'Smart WMS Agent', 창고 운영 Copilot입니다. 간결한 존댓말로 답합니다.\n"
    "원칙: 결론을 먼저, 그 다음 수치→근거/산식→권장조치 순. 모든 수치는 제공된 Tool 결과를 그대로 인용하고 "
    "임의 생성하지 않습니다('약','아마' 금지). HIGH 위험·출고임박은 첫머리에. 이모지·과장 금지.\n"
    "상태변경(적치/피킹지시·출고확정)은 반드시 '승인이 필요합니다'를 명시합니다.\n"
    "RAG 근거가 부족(abstain)하면 정책을 지어내지 말고 '문서 근거가 부족합니다'라고 답합니다."
)


def response_generator_node(state: dict) -> dict:
    if state.get("intent") == "greeting":
        return {"final_response": GREETING_MSG}
    if state.get("intent") == "out_of_scope":
        return {"final_response": OUT_OF_SCOPE_MSG}
    if state.get("missing_parameters"):
        return {"final_response": f"다음 정보가 필요합니다: {', '.join(state['missing_parameters'])}"}
    if state.get("_rag_abstain") and state.get("intent") == "policy_question":
        return {"final_response": state.get("_rag_abstain_msg") or "문서 근거가 부족합니다."}
    tr = state.get("tool_results", {}) or {}
    context = {"intent": state.get("intent"), "tool_results": tr,
               "rag_evidence": state.get("rag_context", [])}
    scope = tr.get("_scope")
    scope_note = ""
    if state.get("intent") == "daily_summary" and scope and scope != "all":
        labels = {"inbound": "입고/적치대기", "outbound": "출고예정", "picking": "피킹",
                  "risk": "재고위험", "shipping": "출고확정대기"}
        scope_note = (f"[요약 범위] 이번 답변은 '{labels.get(scope, scope)}' 영역만 다루세요. "
                      "그 외 영역(피킹·출고·재고위험 등)은 언급하지 마세요.\n")
    user = (scope_note + "아래 Tool 결과와 RAG 근거를 바탕으로 운영자에게 답하세요. JSON 아님, 자연어.\n"
            + json.dumps(context, ensure_ascii=False, default=str)[:6000])
    resp = get_client().chat.completions.create(
        model=settings.openai_chat_model,
        messages=[{"role": "system", "content": _PERSONA}, {"role": "user", "content": user}])
    return {"final_response": resp.choices[0].message.content}


# ---------- 8. Approval Gate ----------
def approval_gate_node(state: dict) -> dict:
    if state.get("intent") in STATE_CHANGE_INTENTS:
        draft = (state.get("tool_results", {}) or {}).get("draft", {})
        return {"approval_required": True, "draft_actions": [draft] if draft else []}
    return {"approval_required": False}
