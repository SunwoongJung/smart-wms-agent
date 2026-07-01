"""Streamlit UI (docs/09_UI_DESIGN.md). 실행: streamlit run ui/app.py (venv 활성화, app/에서)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # app/ 를 path에

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from agent.graph import run as agent_run  # noqa: E402
from sim import des, whatif  # noqa: E402
from tools import drafts, lookups  # noqa: E402
from ui import charts  # noqa: E402

st.set_page_config(page_title="Warehouse Ops Orchestration AI", layout="wide")
st.title("📦 Warehouse Ops Orchestration AI")

PAGE = st.sidebar.radio("메뉴", ["Agent Chat", "KPI Dashboard", "Warehouse Simulation", "Approval"])


# ---------- Agent Chat ----------
if PAGE == "Agent Chat":
    st.subheader("운영 조수와 대화")
    if "history" not in st.session_state:
        st.session_state.history = []
    q = st.chat_input("예: 오늘 뭐 해야 돼? / INB003 적치 추천 / SKU_A001 언제 소진돼?")
    for h in st.session_state.history:
        st.chat_message(h["role"]).write(h["content"])
    if q:
        st.chat_message("user").write(q)
        with st.spinner("처리 중..."):
            s = agent_run(q)
        resp = s.get("final_response") or "(응답 없음)"
        st.chat_message("assistant").write(resp)
        if s.get("approval_required") and s.get("draft_actions"):
            st.warning(f"승인 필요: {s['draft_actions']}")
        if s.get("rag_context"):
            with st.expander("RAG 근거"):
                st.json(s["rag_context"])
        st.session_state.history += [{"role": "user", "content": q}, {"role": "assistant", "content": resp}]


# ---------- KPI Dashboard ----------
elif PAGE == "KPI Dashboard":
    st.subheader("운영 KPI")
    k = lookups.query_operation_kpis(["zone_occupancy", "saturated_zone_count", "safety_stock_below_count"])
    kd = {x["name"]: x["value"] for x in k["kpis"]}
    c1, c2 = st.columns(2)
    c1.metric("포화 Zone 수(>90%)", kd.get("saturated_zone_count"))
    c2.metric("안전재고 미달 SKU", kd.get("safety_stock_below_count"))
    st.plotly_chart(charts.zone_occupancy_heatmap(kd["zone_occupancy"]), use_container_width=True)


# ---------- Warehouse Simulation (메인) ----------
elif PAGE == "Warehouse Simulation":
    from sim import versions
    import resmgmt

    def _kpi(result, name):
        return next((x for x in result["kpis"] if x["kpi_name"] == name), {})

    def _params_caption(result):
        p = result.get("params", {})
        return (f"작업자 {p.get('worker_count')}(Δ{p.get('worker_delta',0)}) · "
                f"지게차 {p.get('forklift_count')}(Δ{p.get('forklift_delta',0)}) · "
                f"팀 {p.get('team_count')} | 시나리오: {result.get('scenario')}")

    def _render_version(result, prefix=""):
        st.caption(_params_caption(result))
        sd, pw = _kpi(result, "shipping_delay_count"), _kpi(result, "picking_wait_minutes")
        m1, m2, m3 = st.columns(3)
        m1.metric("출고지연(mean)", sd.get("mean"))
        m2.metric("피킹대기 P90(분)", pw.get("p90"))
        m3.metric("팀 가동률", _kpi(result, "resource_utilization_team").get("mean"))
        if result.get("movement"):
            components.html(
                charts.team_movement_replay_html(result["movement"], result.get("zone_occupancy_timeseries")),
                height=540,
                scrolling=False,
            )
            members = result["movement"].get("team_members", [])
            if members:
                st.markdown("**팀 구성**")
                st.dataframe([
                    {"팀": tm["team_id"], "작업자": ", ".join(str(x) for x in tm["worker_ids"]),
                     "지게차": tm["forklift_id"]}
                    for tm in members
                ], use_container_width=True, hide_index=True)
            uw = result["movement"].get("unassigned_worker_ids", [])
            uf = result["movement"].get("unassigned_forklift_ids", [])
            if uw or uf:
                st.caption(f"미편성 작업자 {uw or '-'} · 미편성 지게차 {uf or '-'}")
            logs = result["movement"].get("work_log", [])
            if logs:
                st.markdown("**팀별 시간대 작업내역**")
                rows = []
                for row in logs:
                    rows.append({
                        "팀": row["team_id"],
                        "작업자": ", ".join(str(x) for x in row["worker_ids"]),
                        "지게차": row["forklift_id"],
                        "작업": row["job_kind"],
                        "Zone": row["zone_id"],
                        "시작": row["start_time"],
                        "종료": row["end_time"],
                        "분": row["duration_min"],
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.inventory_projection(result["inventory_projection"]),
                        use_container_width=True, key=f"{prefix}inv")
        c2.plotly_chart(charts.event_timeline(result["bottleneck_events"]),
                        use_container_width=True, key=f"{prefix}evt")

    st.subheader("창고상황 예측 (SimPy DES · 작업자2+지게차1 팀)")
    base_res = resmgmt.get_resources()
    st.info(f"현재 베이스라인 — 작업자 {base_res['worker']}명 · 지게차 {base_res['forklift']}대 "
            f"(가용 팀 {min(base_res['worker'] // 2, base_res['forklift'])}조). "
            "팀 = 작업자2+지게차1, 남는 작업자나 지게차는 조를 이룰 수 없습니다.")
    tab_run, tab_view, tab_cmp = st.tabs(["실행", "버전 조회", "버전 비교(2개)"])

    # --- 실행 → 버전 저장 ---
    with tab_run:
        col = st.columns(4)
        horizon = col[0].number_input("horizon(일)", 3, 30, 7)
        reps = col[1].number_input("replications", 10, 300, 40, step=10)
        worker_delta = col[2].number_input("작업자 증감", -2, 5, 0)
        forklift_delta = col[3].number_input("지게차 증감", -2, 5, 0)
        if st.button("시뮬레이션 실행 (버전 저장)"):
            scenario = None
            if worker_delta != 0 or forklift_delta != 0:
                scenario = {"worker_delta": int(worker_delta), "forklift_delta": int(forklift_delta)}
            with st.spinner("DES 실행 중..."):
                if scenario:
                    result = whatif.simulate_operation_what_if(scenario, horizon_days=int(horizon), replications=int(reps))
                else:
                    result = des.run_des_simulation(horizon_days=int(horizon), replications=int(reps))
            st.session_state["last_result"] = result
            st.success(f"저장된 버전: {result['version_name']} ({result['run_type']})")
        if st.session_state.get("last_result"):
            r = st.session_state["last_result"]
            _render_version(r, prefix="run_")
            p = r.get("params", {})
            st.divider()
            st.markdown("**의사결정 반영** — 이 조건을 실제 베이스라인으로 채택")
            if st.button(f"베이스라인 업데이트 → 작업자 {p.get('worker_count')} · 지게차 {p.get('forklift_count')}"):
                newr = resmgmt.update_resources(p.get("worker_count"), p.get("forklift_count"))
                st.success(f"베이스라인 갱신됨: 작업자 {newr['worker']} · 지게차 {newr['forklift']}")

    # --- 버전 조회 ---
    with tab_view:
        vers = versions.list_versions()
        if not vers:
            st.info("저장된 시뮬레이션 버전이 없습니다. '실행' 탭에서 먼저 실행하세요.")
        else:
            labels = [f"{v['version_name']} | {v['run_type']} | {v['scenario_json'] or 'baseline'}" for v in vers]
            pick = st.selectbox("버전 선택", labels)
            r = versions.get_version(pick.split(" | ")[0])
            if r:
                _render_version(r, prefix="view_")

    # --- 버전 비교 (정확히 2개) ---
    with tab_cmp:
        vers = versions.list_versions()
        labels = [f"{v['version_name']} | {v['run_type']} | {v['scenario_json'] or 'baseline'}" for v in vers]
        sel = st.multiselect("비교할 버전 2개 선택", labels, max_selections=2)
        if len(sel) != 2:
            st.info("정확히 2개 버전을 선택하세요.")
        else:
            a = versions.get_version(sel[0].split(" | ")[0])
            b = versions.get_version(sel[1].split(" | ")[0])
            cmp = whatif.compare_simulation_scenarios(a, b)["comparison"]
            st.plotly_chart(charts.whatif_compare(cmp), use_container_width=True, key="cmp_bar")
            cc = st.columns(2)
            with cc[0]:
                st.markdown(f"**A: {a['version_name']}**")
                _render_version(a, prefix="cmpA_")
            with cc[1]:
                st.markdown(f"**B: {b['version_name']}**")
                _render_version(b, prefix="cmpB_")


# ---------- Approval ----------
elif PAGE == "Approval":
    st.subheader("승인 대기 Draft")
    from tools.common import q as _q
    pend = _q("SELECT draft_id, action_type, target_id FROM action_drafts WHERE status='PENDING_APPROVAL'")
    if not pend:
        st.info("승인 대기 Draft가 없습니다.")
    for d in pend:
        with st.container(border=True):
            st.write(d)
            cols = st.columns(2)
            if cols[0].button("승인", key=f"a{d['draft_id']}"):
                st.success(drafts.approve_action(d["draft_id"], True, "operator01"))
            if cols[1].button("거부", key=f"r{d['draft_id']}"):
                st.warning(drafts.approve_action(d["draft_id"], False, "operator01"))
