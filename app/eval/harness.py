"""평가 하네스 (docs/10_EVALUATION_PLAN.md).

실행(앱 디렉토리, venv): python -m eval.harness
- 결정성/재현성 하네스(LLM 불필요) + Intent/RAG/Grounding 평가(LLM 사용).
"""
from sim import des, forecast
from tools import picking, stocking
from rag import retriever
from agent.nodes import router_node
from agent.graph import run as agent_run


def _ok(cond):
    return "PASS" if cond else "FAIL"


# ---------- 1. Tool 결정성 ----------
def h_tool_determinism():
    r1 = stocking.recommend_stocking("INB003")
    r2 = stocking.recommend_stocking("INB003")
    t1 = picking.calculate_picking_required_time("ORD002")
    t2 = picking.calculate_picking_required_time("ORD002")
    checks = [
        ("recommend_stocking 동일 결과", r1["recommended_location_id"] == r2["recommended_location_id"] and r1["score"] == r2["score"]),
        ("picking_time 동일 결과", t1 == t2),
    ]
    return "Tool 결정성", checks


# ---------- 2. 적치 정규화 ----------
def h_stocking_normalization():
    r = stocking.recommend_stocking("INB003")
    bd = r.get("breakdown", {})
    checks = [
        ("breakdown 존재", bool(bd)),
        ("모든 항목 0~1", all(0 <= v <= 1 for v in bd.values())),
        ("동일 SKU 추천(L-A-001)", r.get("recommended_location_id") == "L-A-001"),
    ]
    return "적치 정규화", checks


# ---------- 3. DES 재현성 ----------
def h_des_reproducibility():
    a = des.run_des_simulation(horizon_days=7, replications=20, persist=False)
    b = des.run_des_simulation(horizon_days=7, replications=20, persist=False)
    def sd(r): return next(x for x in r["kpis"] if x["kpi_name"] == "shipping_delay_count")["mean"]
    def pw(r): return next(x for x in r["kpis"] if x["kpi_name"] == "picking_wait_minutes")["p90"]
    checks = [
        ("출고지연 mean 재현", sd(a) == sd(b)),
        ("피킹대기 p90 재현", pw(a) == pw(b)),
    ]
    return "DES 재현성(seed 고정)", checks


# ---------- 4. Forecast sanity ----------
def h_forecast():
    checks = [
        ("SKU_A001 = HIGH", forecast.calculate_inventory_risk("SKU_A001")["risk_level"] == "HIGH"),
        ("SKU_A005 = LOW", forecast.calculate_inventory_risk("SKU_A005")["risk_level"] == "LOW"),
    ]
    return "Forecast 위험등급", checks


# ---------- 5. Intent 평가(LLM) ----------
INTENT_CASES = [
    ("오늘 뭐 해야 돼?", "daily_summary"),
    ("INB003 적치 추천해줘", "stocking_recommendation"),
    ("왜 Zone A를 추천했어?", "policy_question"),
    ("SKU_A001 언제 소진돼?", "inventory_risk"),
    ("오늘 피킹 순서 알려줘", "picking_recommendation"),
    ("Zone 점유율 보여줘", "kpi_query"),
    ("이번 주 창고 상황 예측해줘", "simulation_query"),
    ("출고확정대기 보여줘", "shipping_pending_query"),
    ("부족하면 어떻게 대응해?", "risk_response_recommendation"),
    ("오늘 입고예정 보여줘", "inbound_query"),
    ("입고 관련 업무만 요약해줘", "daily_summary"),
    ("오늘 출고 업무만 정리해줘", "daily_summary"),
]


def h_intent():
    checks = []
    for qy, expect in INTENT_CASES:
        got = router_node({"user_query": qy}).get("intent")
        checks.append((f"{qy} → {got} (기대 {expect})", got == expect))
    return "Intent 분류", checks


# ---------- 5b. 요약 scope 추출(LLM) ----------
SCOPE_CASES = [
    ("입고 관련 업무만 요약해줘", "inbound"),
    ("오늘 출고 업무만 정리해줘", "outbound"),
    ("오늘 뭐 해야 돼?", "all"),
]


def h_summary_scope():
    checks = []
    for qy, expect in SCOPE_CASES:
        r = router_node({"user_query": qy})
        sc = (r.get("parameters") or {}).get("scope")
        if sc is None and r.get("intent") == "daily_summary":
            sc = "all"  # scope 미지정 = 전체 요약
        checks.append((f"{qy} → scope={sc} (기대 {expect})", sc == expect))
    return "요약 scope 추출", checks


# ---------- 6. RAG 평가(LLM) ----------
RAG_CASES = [
    ("왜 Zone A를 추천했어?", True, "stocking_policy"),
    ("부족하면 어떻게 대응해?", True, "warehouse_operation_sop"),
    ("출고확정대기가 뭐야?", True, "wms_terms"),
    ("회사 환불 규정 알려줘", False, None),  # abstain
]


def h_rag():
    checks = []
    for qy, answerable, src in RAG_CASES:
        r = retriever.retrieve(qy, intent="policy_question")
        ok = r["answerable"] == answerable
        if answerable and src:
            ok = ok and any(src in e["source"] for e in r["evidence"])
        checks.append((f"{qy} → answerable={r['answerable']} (기대 {answerable})", ok))
    return "RAG/Abstain", checks


# ---------- 7. Answer Grounding(LLM) ----------
def h_grounding():
    fc = forecast.inventory_forecast("SKU_A001")
    date = fc["expected_stockout_date"]
    resp = agent_run("SKU_A001 언제 소진돼?").get("final_response") or ""
    checks = [(f"응답에 소진일 {date} 포함(수치 grounding)", date in resp)]
    return "Answer Grounding", checks


def main():
    harnesses = [h_tool_determinism, h_stocking_normalization, h_des_reproducibility,
                 h_forecast, h_intent, h_summary_scope, h_rag, h_grounding]
    total_p = total_n = 0
    print("=" * 64)
    for h in harnesses:
        name, checks = h()
        p = sum(1 for _, c in checks if c)
        total_p += p
        total_n += len(checks)
        print(f"[{name}] {p}/{len(checks)}")
        for label, c in checks:
            print(f"   {_ok(c)}  {label}")
    print("=" * 64)
    print(f"TOTAL: {total_p}/{total_n} passed ({total_p / total_n * 100:.0f}%)")


if __name__ == "__main__":
    main()
