"""Explanation Agent — 자동 의사결정을 운영자용 한국어 1~2문장으로 설명.

LLM(llm.complete, node='Explanation')로 생성하고, 키 미설정·오류 시 템플릿으로 폴백한다.
설명은 blackboard_actions.explanation에 캐시(최초 조회 시 생성).
"""
import json

from tools.common import q

from bb import actions

_TYPE_LABEL = {
    "CREATE_PICKING_TASK": "피킹작업 생성", "CREATE_INBOUND_TASK": "입고 처리",
    "CREATE_PUTAWAY_TASK": "적치작업 생성", "CREATE_SHIPPING_TASK": "출고준비 생성",
    "ALLOCATE_TEAM": "작업팀 배정", "REPRIORITIZE_PICKING_TASK": "피킹 우선순위 조정",
    "START_ZONE_WORK": "Zone 작업 시작", "FINISH_ZONE_LEG": "Zone 작업 완료",
    "INVENTORY_RISK_ALERT": "결품 위험 경보", "PUTAWAY_BLOCKED": "적치 보류",
    "PLACE_REPLENISHMENT_ORDER": "결품 발주", "ADJUST_INVENTORY": "재고 보정",
}
_STATUS_LABEL = {
    "SUCCESS": "실행 완료", "POLICY_BLOCKED": "자동실행 보류", "FAILED": "실행 실패",
    "SKIPPED_DUPLICATE": "중복으로 생략", "PENDING": "대기", "READY": "실행 준비", "RUNNING": "실행 중",
}
_TARGET_STATE_LABEL = {   # 대상(주문/입고)의 현재 상태를 사람이 읽는 문장으로
    "AWAITING_STOCK": "현재 부족분 발주 후 재고 입고를 대기 중입니다.",
    "PICKING_ISSUED": "재고가 충족되어 피킹이 진행 중입니다.",
    "SHIPPING_PENDING": "피킹이 끝나 출고 준비 단계입니다.",
    "SHIPPED": "출고가 완료되었습니다.",
    "STOCKED": "적치가 완료되어 재고에 반영되었습니다.",
    "RECEIVED": "입고 처리가 완료되었습니다.",
}


def _target_status(a: dict) -> str:
    """대상(주문/입고/작업)의 '현재' 상태 — 액션 자체 status는 고정이라도 대상은 흐른다."""
    tt, tid = a.get("target_type"), a.get("target_id")
    if not tid:
        return ""
    if tt == "order":
        r = q("SELECT status FROM outbound_orders WHERE order_no=?", (tid,))
    elif tt == "inbound":
        r = q("SELECT status FROM inbound_orders WHERE inbound_no=?", (tid,))
    elif tt == "task":
        r = (q("SELECT status FROM picking_tasks WHERE picking_task_id=?", (tid,))
             or q("SELECT status FROM stocking_tasks WHERE stocking_task_id=?", (tid,)))
    else:
        r = None
    return r[0]["status"] if r else ""


def _state_sig(a: dict) -> str:
    """설명 캐시 유효성 시그니처 = 액션 status + 대상 현재 상태 + 발주분 입고여부.
    이 값이 바뀌면(예: 발주대기→피킹진행, 발주분 입고완료) 설명을 새로 생성."""
    extra = ""
    if a.get("action_type") == "PLACE_REPLENISHMENT_ORDER" and a.get("target_id"):
        inbs = q("SELECT status FROM inbound_orders WHERE replenish_for=?", (a["target_id"],))
        extra = "|repl:" + ",".join(sorted(x["status"] for x in inbs)) if inbs else ""
    return f"{a.get('status') or ''}|{_target_status(a)}{extra}"


def _live_summary(a: dict) -> str:
    """대상의 '지금' 상황을 결정적으로 요약 — 과거 실행결과와 달라도 현재를 정확히 반영."""
    at, tid = a.get("action_type"), a.get("target_id")
    if at == "PLACE_REPLENISHMENT_ORDER" and tid:
        inbs = q("SELECT status, expected_date FROM inbound_orders WHERE replenish_for=?", (tid,))
        order = q("SELECT status FROM outbound_orders WHERE order_no=?", (tid,))
        ostat = order[0]["status"] if order else ""
        olabel = _TARGET_STATE_LABEL.get(ostat, ostat)
        if inbs and all(x["status"] == "STOCKED" for x in inbs):
            tail = _TARGET_STATE_LABEL.get(ostat, f"현재 주문 상태는 {ostat}입니다.")
            return f"발주분이 이미 입고 완료되어 재고가 채워졌습니다. {tail}"
        if inbs:
            return f"발주분이 아직 입고되지 않아 대기 중입니다(도착예정 {inbs[0]['expected_date']})."
    return _TARGET_STATE_LABEL.get(_target_status(a), "")


def _ctx(a: dict) -> dict:
    """LLM/템플릿 공통 컨텍스트(민감/장황 필드 제거, 핵심만)."""
    def j(key):
        try:
            return json.loads(a.get(key) or "null")
        except Exception:
            return None
    return {
        "현재상황(지금 시점 사실, 최우선 반영)": _live_summary(a),
        "대상현재상태": _target_status(a),
        "에이전트": a.get("agent_name"),
        "동작": a.get("action_type"),
        "대상": f"{a.get('target_type')}:{a.get('target_id')}",
        "액션상태": a.get("status"),
        "대상정보": j("payload_json"),
        "정책결과": j("policy_result_json"),
        "사전검증": j("precheck_result_json"),
        "실행결과(과거 처리 시점 스냅샷 — 현재와 다르면 무시)": j("execution_result_json"),
        "근거": a.get("reason"),
        "오류": a.get("error_message"),
    }


def template(a: dict) -> str:
    """LLM 없이도 항상 동작하는 결정적 설명."""
    at = _TYPE_LABEL.get(a.get("action_type"), a.get("action_type") or "동작")
    st = _STATUS_LABEL.get(a.get("status"), a.get("status") or "")
    agent = a.get("agent_name") or "시스템"
    tgt = a.get("target_id") or "-"
    reason = a.get("reason") or ""
    if a.get("status") == "SUCCESS":
        body = f"{agent}가 대상 {tgt}에 대해 '{at}'을(를) 자동으로 수행해 {st}했습니다."
    elif a.get("status") == "POLICY_BLOCKED":
        body = f"{agent}의 '{at}'은(는) 정책/시뮬 판단으로 {st}되었습니다."
    elif a.get("status") == "FAILED":
        body = f"{agent}의 '{at}'이(가) {st}했습니다."
    elif a.get("status") == "SKIPPED_DUPLICATE":
        body = f"동일 작업이 이미 존재하여 '{at}'을(를) {st}했습니다."
    else:
        body = f"{agent}의 '{at}' — 현재 {st}."
    if reason:
        body = f"{body} 근거: {reason}"
    tgt_note = _live_summary(a)   # 대상의 '지금' 상황(발주분 입고완료·재고충족 / 대기 중 등)
    return f"{body} {tgt_note}" if tgt_note else body


def _llm(a: dict) -> str:
    import llm
    sys = ("너는 창고 자동운영(WMS) 시스템의 설명 담당이다. 주어진 자동 의사결정 1건을 "
           "운영자에게 한국어 1~2문장으로 간결히 설명하라. 어떤 에이전트가 무엇을, 왜(정책·사전검증·근거), "
           "어떤 결과로 처리했는지 포함하되 JSON·코드·영문 필드명은 노출하지 말고 자연스러운 업무 문장으로 써라. "
           "특히 '현재상황'과 '대상현재상태'는 지금 시점의 사실이고 '실행결과'는 과거 처리 시점 스냅샷이다. "
           "둘이 다르면 반드시 현재 상황을 기준으로 지금 상태를 설명하라(예: 발주 후 재고가 채워졌으면 '대기 중'이 아니라 '재고 충족·진행 중'으로).")
    user = "다음 의사결정을 설명해줘:\n" + json.dumps(_ctx(a), ensure_ascii=False, indent=2)
    resp = llm.complete([{"role": "system", "content": sys}, {"role": "user", "content": user}],
                        node="Explanation")
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("빈 응답")
    return text


def generate(a: dict, use_llm: bool = True) -> tuple[str, str]:
    """(설명, source) — source는 'llm' 또는 'template'."""
    if use_llm:
        try:
            return _llm(a), "llm"
        except Exception:
            pass
    return template(a), "template"


def explain(action_id: str, regenerate: bool = False, use_llm: bool = True) -> dict:
    a = actions.get(action_id)
    if not a:
        return {"error": "not found"}
    sig = _state_sig(a)
    # 대상 상태가 캐시 생성 시점과 같을 때만 캐시 반환 — 상태가 바뀌면(예: 발주대기→피킹진행) 새로 생성
    if a.get("explanation") and a.get("explanation_sig") == sig and not regenerate:
        return {"action_id": action_id, "explanation": a["explanation"], "source": "cache"}
    text, source = generate(a, use_llm=use_llm)
    actions.update(action_id, explanation=text, explanation_sig=sig)
    return {"action_id": action_id, "explanation": text, "source": source}
