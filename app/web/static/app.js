// WOONG AI — SPA (P1~P5)
const $ = (s) => document.querySelector(s);
let META = { base_date: null };
let LAST = { result: null, forecast: null, comparison: null, insightTab: "inv", kpiDashboard: null, kpiTargets: null };
let CHAT = { sessionId: null, sessions: [], filter: "" };

const kpi = (res, name) => (res.kpis || []).find((k) => k.kpi_name === name) || {};
const fmtNum = (v, d = 1) => (v == null ? "—" : Number(v).toFixed(d));
const safeText = (s) => (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const KPI_META = {
  zone_occupancy: { label: "Zone 점유율", desc: "각 Zone의 전체 용량 대비 현재 적재량 비율", unit: "%" },
  saturated_zone_count: { label: "포화 Zone 수", desc: "점유율이 90%를 초과한 Zone 개수", unit: "개" },
  safety_stock_below_count: { label: "안전재고 미달 SKU 수", desc: "현재 재고가 안전재고보다 낮은 SKU 개수", unit: "개" },
  stocking_completion_rate: { label: "입고 완료율", desc: "입고 대상 중 적치 완료 상태인 건의 비율", unit: "%" },
  expected_shortage_count: { label: "예상 결품 주문 수", desc: "현재 가용재고로 요청 수량을 채우지 못하는(할당 부족) 출고 주문 수", unit: "건" },
  dead_stock_count: { label: "체화재고 SKU 수", desc: "저회전·최근 14일 무출고·유통기한 임박 중 하나 이상에 해당하는 SKU 수", unit: "개" },
  replenishment_needed_count: { label: "보충 필요 SKU 수", desc: "피킹 로케이션이 목표 재고 미만이고 보관에 보충 가능 재고가 있는 SKU 수", unit: "개" },
  shipping_delay_count: { label: "출고 지연 건수", desc: "시뮬레이션 기간 내 납기 초과가 발생한 출고 건수", unit: "건" },
  shipping_delay_cost: { label: "지연 비용(가중)", desc: "납기 초과 비용 — 고회전 SKU 포함 주문은 일반의 10배로 가중", unit: "" },
  picking_wait_minutes: { label: "피킹 대기 시간", desc: "피킹 작업이 시작되기 전까지 대기한 시간", unit: "분" },
  resource_utilization_team: { label: "작업팀 가동률", desc: "작업자 2명과 지게차 1대로 구성된 작업팀의 평균 사용률", unit: "%" },
  zone_max_occupancy: { label: "Zone 최대 점유율", desc: "시뮬레이션 중 각 Zone이 도달한 최대 점유율", unit: "%" },
  expected_stockout_date: { label: "예상 재고 소진일", desc: "시뮬레이션상 특정 SKU 재고가 소진될 것으로 예상되는 날짜", unit: "일자" },
};
const DATASET_ORDER = ["snapshot", "products", "zones", "locations", "inventory", "inbound_orders", "outbound_orders", "outbound_order_lines", "shipping_pending", "stocking_tasks", "picking_tasks", "resources", "process_time_params", "demand_history", "action_drafts", "simulation_runs", "simulation_kpis", "simulation_events"];
const DATASET_META = {
  snapshot: ["현재 스냅샷", "현재 창고 상태를 집계한 요약"],
  products: ["상품 마스터", "SKU별 상품명, 카테고리, 보관유형, 안전재고 등 기준 정보"],
  zones: ["Zone 마스터", "창고 Zone별 보관유형, 거리, 우선순위, 최대 용량"],
  locations: ["Location 마스터", "실제 적치 위치별 소속 Zone, 용량, 현재 점유 수량"],
  inventory: ["재고 원장", "SKU, LOT, 위치, 수량, 입고일, 유통기한, 재고 상태"],
  inbound_orders: ["입고 요청", "입고번호별 SKU, 수량, 예정일, 입고/적치 상태, 공급사"],
  outbound_orders: ["출고 요청", "출고번호별 고객, 우선순위, 납기, 출고 상태"],
  outbound_order_lines: ["출고 요청 라인", "출고 요청에 포함된 SKU별 수량 상세"],
  shipping_pending: ["출고 대기", "피킹/포장 후 출고 확정 대기 중인 건"],
  stocking_tasks: ["적치 작업", "입고 건을 특정 location에 적치하도록 발행된 작업"],
  picking_tasks: ["피킹 작업", "출고 주문에 대해 발행된 피킹 작업"],
  resources: ["작업 리소스", "작업자, 지게차 개별 ID와 활성 상태"],
  process_time_params: ["공정 시간 파라미터", "입고, 적치, 피킹, 포장/출고 단계별 시간 분포 파라미터"],
  demand_history: ["수요 이력", "SKU별 과거 출고 수요량"],
  action_drafts: ["승인 Draft", "승인 대기/승인/거부된 상태변경 후보 작업"],
  simulation_runs: ["시뮬레이션 실행 이력", "실행 버전, baseline/what-if 유형, 조건, 생성시각"],
  simulation_kpis: ["시뮬레이션 KPI 원장", "시뮬레이션 실행별 KPI 산출값"],
  simulation_events: ["시뮬레이션 이벤트", "재고소진, 출고지연, Zone 포화 등 시뮬레이션 중 발생 이벤트"],
};
const kpiLabel = (name) => (KPI_META[name] && KPI_META[name].label) || name;
const kpiDesc = (name) => (KPI_META[name] && KPI_META[name].desc) || "";

function daysFromBase(dateStr) {
  if (!dateStr || !META.base_date) return null;
  return Math.round((new Date(dateStr + "T00:00:00") - new Date(META.base_date + "T00:00:00")) / 86400000);
}
function earliestStockout(res) {
  const so = (res.kpis || []).filter((k) => k.kpi_name === "expected_stockout_date" && k.p50);
  if (!so.length) return null;
  so.sort((x, y) => new Date(x.p50) - new Date(y.p50));
  return so[0];
}
function cmpRow(comparison, name) { return (comparison || []).find((c) => c.kpi_name === name); }

function deltaChip(row, field, lowerIsBetter = true) {
  if (!row) return `<span class="kpi-delta flat">기준</span>`;
  const b = row["baseline_" + field], d = row["delta_" + field];
  if (b == null || d == null || !b) return `<span class="kpi-delta flat">기준 대비 —</span>`;
  const pct = (d / Math.abs(b)) * 100;
  const cls = d === 0 ? "flat" : (lowerIsBetter ? d < 0 : d > 0) ? "down" : "up";
  const arrow = d === 0 ? "→" : d < 0 ? "▼" : "▲";
  return `<span class="kpi-delta ${cls}">${arrow} ${Math.abs(pct).toFixed(1)}%<span class="base">기준 대비</span></span>`;
}

function renderKpis(res, comparison, invValue) {
  const sd = kpi(res, "shipping_delay_count"), pw = kpi(res, "picking_wait_minutes"), ut = kpi(res, "resource_utilization_team");
  const dc = kpi(res, "shipping_delay_cost");
  const so = earliestStockout(res), soDays = so ? daysFromBase(so.p50) : null;
  const cards = [
    { ico: "🕐", label: kpiLabel("shipping_delay_count"), val: fmtNum(sd.mean, 2), unit: "건", delta: deltaChip(cmpRow(comparison, "shipping_delay_count"), "mean") },
    { ico: "💸", label: kpiLabel("shipping_delay_cost"), val: fmtNum(dc.mean, 0), unit: "", delta: deltaChip(cmpRow(comparison, "shipping_delay_cost"), "mean") },
    { ico: "⏳", label: kpiLabel("picking_wait_minutes"), val: fmtNum(pw.p90, 1), unit: "분", delta: deltaChip(cmpRow(comparison, "picking_wait_minutes"), "p90") },
    { ico: "👥", label: kpiLabel("resource_utilization_team"), val: ut.mean != null ? fmtNum(ut.mean * 100, 1) : "—", unit: "%", delta: deltaChip(cmpRow(comparison, "resource_utilization_team"), "mean", false) },
    { ico: "📅", label: kpiLabel("expected_stockout_date"), val: soDays != null ? "D+" + soDays : "—", unit: "", delta: `<span class="kpi-delta flat">${so ? so.p50 : "소진 없음"}</span>` },
    { ico: "💰", label: "총 재고 비용", val: invValue != null ? "₩" + (invValue / 1e6).toFixed(1) + "M" : "—", unit: "", delta: `<span class="kpi-delta flat">예시 단가 기준</span>` },
  ];
  $("#kpi-row").innerHTML = cards.map((c) => `
    <div class="kpi"><div class="kpi-top"><span class="kpi-ico">${c.ico}</span>${c.label}</div>
      <div class="kpi-val">${c.val}<span class="unit">${c.unit}</span></div>${c.delta}</div>`).join("");
}

function pct(v, d = 1) { return v == null ? "—" : (Number(v) * 100).toFixed(d) + "%"; }
function fmtDuration(sec) {
  if (sec == null) return "—";
  sec = Math.max(0, Math.round(Number(sec)));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const parts = [];
  if (h) parts.push(`${h}시간`);
  if (m) parts.push(`${m}분`);
  parts.push(`${s}초`);
  return parts.join(" ");
}

async function loadKpiTargets() {
  LAST.kpiTargets = await fetch("/kpi/targets").then((x) => x.json()).catch(() => ({}));
  const zi = $("#target-zone-occupancy"), ui = $("#target-utilization");
  if (zi && document.activeElement !== zi) zi.value = Math.round((LAST.kpiTargets.kpi_target_zone_occupancy ?? 0.8) * 100);
  if (ui && document.activeElement !== ui) ui.value = Math.round((LAST.kpiTargets.kpi_target_utilization ?? 0.9) * 100);
  return LAST.kpiTargets;
}

async function saveKpiTarget(key, pctValue) {
  await fetch("/kpi/targets", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, value: Math.max(0, Math.min(100, Number(pctValue) || 0)) / 100 }),
  }).catch(() => {});
  await loadKpiTargets();
  await loadOperationKpis();
  await loadUtilizationTrend();
}

async function loadOperationKpis() {
  LAST.kpiDashboard = await fetch("/kpi/dashboard").then((x) => x.json()).catch(() => null);
  renderKpiDashboard();
  return LAST.kpiDashboard;
}

function renderOpsKpis() {
  const d = LAST.kpiDashboard; if (!d) return;
  const over = d.zone_over_target_list || [];
  $("#ops-kpi-row").innerHTML = [
    { ico: "▦", label: "Zone 점유율", val: pct(d.zone_occupancy_avg), delta: `<span class="kpi-delta flat">목표 ${pct(d.zone_occupancy_target)}</span>` },
    { ico: "👥", label: "작업팀 가동률", val: pct(d.team_utilization), delta: `<span class="kpi-delta flat">목표 ${pct(d.team_utilization_target)}</span>` },
    { ico: "🕐", label: "출고지연 건수", val: d.shipping_delay_count ?? "—", unit: "건", delta: `<span class="kpi-delta ${d.shipping_delay_count ? "up" : "flat"}">목표 0건</span>` },
    { ico: "📦", label: "적치지연 건수", val: d.putaway_delay_count ?? "—", unit: "건", delta: `<span class="kpi-delta ${d.putaway_delay_count ? "up" : "flat"}">목표 0건</span>` },
    { ico: "⏱", label: "피킹 대기 시간", val: fmtDuration(d.picking_wait_seconds), delta: `<span class="kpi-delta flat">${d.picking_wait_sample ? `실측 ${d.picking_wait_sample}건 평균` : "실측 데이터 없음"}${d.picking_wait_waiting_now ? ` · 대기중 ${d.picking_wait_waiting_now}건` : ""}</span>` },
    { ico: "!", label: "목표량 초과 Zone 수", val: d.zone_over_target_count ?? "—", unit: "개", delta: `<span class="kpi-delta flat">${over.length ? over.join(", ") : "없음"}</span>` },
    { ico: "🚫", label: "품절 SKU 수", val: d.out_of_stock_count ?? "—", unit: "개", delta: `<span class="kpi-delta ${d.out_of_stock_count ? "up" : "flat"}">재고 0 (수요 있음)</span>` },
    { ico: "⏳", label: "1주 내 소진 예상 재고", val: d.stockout_within_week_count ?? "—", unit: "건", delta: `<span class="kpi-delta flat">재고>0 · 목록은 하단 카드</span>` },
    { ico: "💰", label: "재고금액", val: d.inventory_value != null ? "₩" + (d.inventory_value / 1e6).toFixed(1) + "M" : "—", delta: `<span class="kpi-delta flat">기준일 ${d.reference_date || "—"}</span>` },
  ].map((c) => `
    <div class="kpi"><div class="kpi-top"><span class="kpi-ico">${c.ico}</span>${c.label}</div>
      <div class="kpi-val">${c.val}<span class="unit">${c.unit || ""}</span></div>${c.delta}</div>`).join("");

  const zones = d.zone_occupancy_list || [];
  if (!zones.length) {
    $("#zone-kpi-chart").innerHTML = `<div class="kpi-empty">Zone 점유율 데이터 없음</div>`;
  } else {
    svgBars($("#zone-kpi-chart"), zones.map((z) => ({
      label: z.zone_id,
      bars: [{ name: "점유율", value: Math.round(Number(z.occupancy || 0) * 100), color: Number(z.occupancy || 0) > d.zone_occupancy_target ? "#e1483b" : "#2f6bff" }],
    })), { hline: { y: Math.round(d.zone_occupancy_target * 100), label: "목표", color: "#e1483b" } });
  }

  renderStockoutList(d);
}

function renderStockoutList(d) {
  const el = $("#stockout-list"); if (!el) return;
  const oos = d.out_of_stock_items || [], within = d.stockout_within_week_items || [];
  let html = "";
  // 품절(재고 0) — 소진 예상과 별도 표기
  html += `<div class="so-sub">🚫 품절 (재고 0) ${d.out_of_stock_count ?? 0}건</div>`;
  html += oos.length
    ? `<table><thead><tr><th>SKU</th><th>일평균 소진</th></tr></thead><tbody>
        ${oos.map((it) => `<tr><td>${it.sku}</td><td class="num">${it.avg_daily_demand}</td></tr>`).join("")}</tbody></table>`
    : `<div class="kpi-empty">품절 SKU 없음</div>`;
  // 1주 내 소진 예상(재고>0)
  html += `<div class="so-sub">⏳ 1주 내 소진 예상 (재고>0) ${d.stockout_within_week_count ?? 0}건</div>`;
  html += within.length
    ? `<table><thead><tr><th>SKU</th><th>현재고</th><th>일평균 소진</th><th>소진까지(일)</th></tr></thead><tbody>
        ${within.map((it) => `<tr><td>${it.sku}</td><td class="num">${it.qty}</td><td class="num">${it.avg_daily_demand}</td><td class="num">${it.days_left}</td></tr>`).join("")}</tbody></table>`
    : `<div class="kpi-empty">1주 내 소진 예상 SKU 없음</div>`;
  el.innerHTML = html;
}

async function loadUtilizationTrend() {
  const r = await fetch("/kpi/trend/utilization?days=7").then((x) => x.json()).catch(() => null);
  const el = $("#util-trend-chart"); if (!el) return;
  if (!r || !r.series || !r.series.length) { el.innerHTML = `<div class="kpi-empty">데이터 없음</div>`; return; }
  const target = (LAST.kpiTargets && LAST.kpiTargets.kpi_target_utilization) ?? 0.9;
  svgLine(el, {
    labels: r.series.map((x) => x.date.slice(5)),
    series: [{ name: "가동률", color: "#2f6bff", area: true,
               values: r.series.map((x) => x.value == null ? null : Math.round(x.value * 100)) }],
    hlines: [{ y: Math.round(target * 100), label: "목표", color: "#e1483b" }],
  });
}

async function loadDelayTrend() {
  const r = await fetch("/kpi/trend/delays?days=7").then((x) => x.json()).catch(() => null);
  const el = $("#delay-trend-chart"); if (!el) return;
  if (!r || !r.series || !r.series.length) { el.innerHTML = `<div class="kpi-empty">데이터 없음</div>`; return; }
  svgBars(el, r.series.map((x) => ({
    label: x.date.slice(5),
    bars: [
      { name: "출고지연", value: x.shipping_delay_count, color: "#e1483b" },
      { name: "적치지연", value: x.putaway_delay_count, color: "#f0a13a" },
    ],
  })));
}

function renderKpiDashboard() {
  const sub = $("#kpi-board-sub");
  const d = LAST.kpiDashboard;
  if (sub) sub.textContent = `실제 운영 데이터 기준 KPI입니다. 기준일: ${d && d.reference_date ? d.reference_date : "-"}`;
  if (d) renderOpsKpis();
}

let DATA = { dataset: "snapshot", poll: null };

function renderDatasetTabs() {
  const bar = $("#dataset-tabs"); if (!bar) return;
  bar.innerHTML = DATASET_ORDER.map((id) =>
    `<button class="ds-tab${id === DATA.dataset ? " active" : ""}" data-ds="${id}">${DATASET_META[id][0]}</button>`).join("");
  bar.querySelectorAll(".ds-tab").forEach((b) => b.addEventListener("click", () => {
    DATA.dataset = b.dataset.ds;
    renderDatasetTabs();
    loadRawData();
  }));
}

function setupDataBrowser() {
  const bar = $("#dataset-tabs"); if (!bar) return;
  renderDatasetTabs();
}

function renderSnapshot(s) {
  if (!s) return;
  const sim = s.latest_simulation ? `${s.latest_simulation.version_name} · ${s.latest_simulation.run_type}` : "없음";
  const cards = [
    ["작업자", `${s.worker}명`, `지게차 ${s.forklift}대 · 가용 팀 ${s.team_count}조`],
    ["총 재고", fmtNum(s.inventory_units, 0), `재고가치 ₩${(Number(s.inventory_value || 0) / 1e6).toFixed(1)}M`],
    ["입고 대기", `${s.counts.inbound_waiting}건`, `적치대기 ${s.counts.stocking_waiting}건`],
    ["출고 작업", `${s.counts.outbound_planned}건`, `출고대기 ${s.counts.shipping_pending}건`],
    ["위험 지표", `${s.safety_stock_below_count} SKU`, `포화 Zone ${s.saturated_zone_count}개`],
    ["입고 완료율", pct(s.stocking_completion_rate), "입고 대상 대비 STOCKED 비율"],
    ["승인 대기", `${s.counts.action_drafts_pending}건`, "상태변경 Draft"],
    ["상품 마스터", `${s.counts.products}개`, "등록 SKU 수"],
    ["시뮬레이션", sim, "최신 저장 버전"],
    ["기준일", s.base_date, "운영 데이터 기준일"],
  ];
  $("#snapshot-grid").innerHTML = cards.map(([label, val, note]) => `
    <div class="snap-card"><div class="snap-label">${safeText(label)}</div>
      <div class="snap-value">${safeText(val)}</div><div class="snap-note">${safeText(note)}</div></div>`).join("");
}

async function loadDataSnapshot() {
  const s = await fetch("/data/snapshot").then((x) => x.json());
  renderSnapshot(s);
  return s;
}

function cellValue(v) {
  if (v == null) return "";
  const raw = typeof v === "object" ? JSON.stringify(v) : String(v);
  return safeText(raw.length > 180 ? raw.slice(0, 180) + "..." : raw);
}

function renderRawTable(data) {
  const meta = DATASET_META[data.dataset] || [data.dataset, ""];
  $("#data-table-title").textContent = meta[0];
  const desc = $("#data-table-desc"); if (desc) desc.textContent = meta[1] || "";
  const liveOn = DATA.poll && LIVE.running && data.dataset !== "snapshot";
  $("#data-table-meta").textContent = `${data.total}건${liveOn ? " · 🔴 실시간 자동갱신(3초)" : ""}`;
  if (!data.rows || !data.rows.length) {
    $("#raw-data-table").innerHTML = `<div class="raw-empty">조회 결과가 없습니다.</div>`;
    return;
  }
  const cols = Object.keys(data.rows[0]);
  $("#raw-data-table").innerHTML = `
    <table><thead><tr>${cols.map((c) => `<th>${safeText(c)}</th>`).join("")}</tr></thead>
    <tbody>${data.rows.map((row) => `<tr>${cols.map((c) => `<td>${cellValue(row[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

async function loadRawData() {
  const dataset = DATA.dataset || "snapshot";
  if (dataset === "snapshot") {
    const s = await loadDataSnapshot();
    renderRawTable({
      dataset: "snapshot",
      total: 1,
      rows: [{ ...s, counts: JSON.stringify(s.counts), latest_simulation: JSON.stringify(s.latest_simulation) }],
    });
    return;
  }
  const data = await fetch(`/data/${encodeURIComponent(dataset)}?limit=200&offset=0`).then((x) => x.json());
  renderRawTable(data);
}

async function refreshDataBrowser() {
  await loadDataSnapshot().catch(() => {});
  await loadRawData().catch(() => {});
}

// 데이터 탭: 실시간 수요 ON일 때 현재 표를 3초마다 자동 갱신(새 행이 최신순으로 위에 쌓임)
function enterData() {
  if (DATA.poll) clearInterval(DATA.poll);
  DATA.poll = setInterval(() => {
    if (LIVE.running) { loadRawData().catch(() => {}); loadDataSnapshot().catch(() => {}); }
  }, 3000);
}
function leaveData() { if (DATA.poll) { clearInterval(DATA.poll); DATA.poll = null; } }

/* ---------- 자체 SVG 차트 ---------- */
function svgLine(el, cfg) {
  const W = 560, H = 250, pl = 46, pr = 14, pt = 16, pb = 30;
  const n = cfg.labels.length;
  const vals = [];
  cfg.series.forEach((s) => vals.push(...s.values.filter((v) => v != null)));
  (cfg.hlines || []).forEach((h) => vals.push(h.y));
  let mn = Math.min(0, ...vals), mx = Math.max(...vals, 1);
  if (mx === mn) mx = mn + 1;
  const X = (i) => pl + (n <= 1 ? 0 : (i * (W - pl - pr)) / (n - 1));
  const Y = (v) => pt + (1 - (v - mn) / (mx - mn)) * (H - pt - pb);
  let svg = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  for (let g = 0; g <= 4; g++) {
    const yy = pt + (g / 4) * (H - pt - pb), vv = mx - (g / 4) * (mx - mn);
    svg += `<line x1="${pl}" y1="${yy}" x2="${W - pr}" y2="${yy}" stroke="#eef1f6"/>`;
    svg += `<text x="${pl - 6}" y="${yy + 3}" font-size="9" fill="#9aa3b0" text-anchor="end">${Math.round(vv)}</text>`;
  }
  cfg.labels.forEach((lb, i) => { if (n <= 12 || i % 2 === 0) svg += `<text x="${X(i)}" y="${H - 10}" font-size="9" fill="#9aa3b0" text-anchor="middle">${lb}</text>`; });
  (cfg.hlines || []).forEach((h) => {
    svg += `<line x1="${pl}" y1="${Y(h.y)}" x2="${W - pr}" y2="${Y(h.y)}" stroke="${h.color}" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  });
  cfg.series.forEach((s) => {
    const pts = s.values.map((v, i) => (v == null ? null : `${X(i)},${Y(v)}`)).filter(Boolean).join(" ");
    if (s.area) svg += `<polygon points="${X(0)},${Y(mn)} ${pts} ${X(n - 1)},${Y(mn)}" fill="${s.color}" fill-opacity="0.10"/>`;
    svg += `<polyline points="${pts}" fill="none" stroke="${s.color}" stroke-width="2.4" stroke-dasharray="${s.dashed ? "6 5" : ""}"/>`;
    s.values.forEach((v, i) => { if (v != null) svg += `<circle cx="${X(i)}" cy="${Y(v)}" r="2.6" fill="${s.color}"/>`; });
  });
  svg += `</svg>`;
  const legend = `<div class="chart-legend">` +
    cfg.series.map((s) => `<span><i style="border-color:${s.color};${s.dashed ? "border-top-style:dashed" : ""}"></i>${s.name}</span>`).join("") +
    (cfg.hlines || []).map((h) => `<span><i style="border-color:${h.color};border-top-style:dashed"></i>${h.label}</span>`).join("") +
    `</div>`;
  el.innerHTML = svg + legend + `<div class="chart-tip"></div>`;
  // 툴팁
  const node = el.querySelector("svg"), tip = el.querySelector(".chart-tip");
  node.addEventListener("mousemove", (e) => {
    const r = node.getBoundingClientRect();
    const vx = ((e.clientX - r.left) / r.width) * W;
    let i = Math.round((vx - pl) / ((W - pl - pr) / Math.max(1, n - 1)));
    i = Math.max(0, Math.min(n - 1, i));
    const lines = cfg.series.map((s) => `${s.name}: ${s.values[i] == null ? "—" : Math.round(s.values[i])}`).join("<br>");
    tip.innerHTML = `<b>${cfg.labels[i]}</b><br>${lines}`;
    tip.style.left = ((X(i) / W) * r.width) + "px";
    tip.style.top = ((Y(cfg.series[0].values[i] ?? mn) / H) * r.height) + "px";
    tip.style.display = "block";
  });
  node.addEventListener("mouseleave", () => { tip.style.display = "none"; });
}

function svgBars(el, groups, opts = {}) {
  const W = 560, H = 250, pl = 46, pr = 14, pt = 16, pb = 36, gap = 40;
  const allv = groups.flatMap((g) => g.bars.map((b) => b.value));
  if (opts.hline) allv.push(opts.hline.y);
  const mx = Math.max(...allv, 1);
  const gw = (W - pl - pr - gap * (groups.length - 1)) / groups.length;
  const Y = (v) => pt + (1 - v / mx) * (H - pt - pb);
  let svg = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  for (let g = 0; g <= 4; g++) { const yy = pt + (g / 4) * (H - pt - pb); svg += `<line x1="${pl}" y1="${yy}" x2="${W - pr}" y2="${yy}" stroke="#eef1f6"/>`; }
  groups.forEach((grp, gi) => {
    const gx = pl + gi * (gw + gap), bw = gw / grp.bars.length - 8;
    grp.bars.forEach((b, bi) => {
      const x = gx + bi * (gw / grp.bars.length), y = Y(b.value);
      svg += `<rect x="${x}" y="${y}" width="${bw}" height="${H - pb - y}" rx="4" fill="${b.color}"/>`;
      svg += `<text x="${x + bw / 2}" y="${y - 4}" font-size="9" fill="#5d6573" text-anchor="middle">${Math.round(b.value)}</text>`;
    });
    svg += `<text x="${gx + gw / 2}" y="${H - 12}" font-size="10" fill="#5d6573" text-anchor="middle">${grp.label}</text>`;
  });
  if (opts.hline) {
    const hy = Y(opts.hline.y);
    svg += `<line x1="${pl}" y1="${hy}" x2="${W - pr}" y2="${hy}" stroke="${opts.hline.color || "#e1483b"}" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  }
  svg += `</svg>`;
  const names = groups[0].bars.map((b) => `<span><i style="border-color:${b.color};border-top-width:8px"></i>${b.name}</span>`).join("")
    + (opts.hline ? `<span><i style="border-color:${opts.hline.color || "#e1483b"};border-top-style:dashed"></i>${opts.hline.label || "목표"}</span>` : "");
  el.innerHTML = svg + `<div class="chart-legend">${names}</div>`;
}

function renderInsight() {
  const el = $("#insight-chart");
  if (LAST.insightTab === "inv") {
    const fc = LAST.forecast && LAST.forecast.forecast;
    if (!fc || !fc.daily_projection || !fc.daily_projection.length) { el.textContent = "재고 추이 데이터 없음"; return; }
    const dp = fc.daily_projection.slice(0, 14);
    svgLine(el, {
      labels: dp.map((d) => d.date.slice(5)),
      series: [{ name: `재고(예측) · ${LAST.forecast.sku || ""}`, values: dp.map((d) => d.projected_inventory), color: "#2f6bff", area: true }],
      hlines: fc.safety_stock != null ? [{ y: fc.safety_stock, label: "안전재고 임계선", color: "#e1483b" }] : [],
    });
  } else {
    const r = LAST.result, c = LAST.comparison;
    const sd = kpi(r, "shipping_delay_count"), pw = kpi(r, "picking_wait_minutes");
    if (c) {
      const a = cmpRow(c, "shipping_delay_count"), b = cmpRow(c, "picking_wait_minutes");
      svgBars(el, [
        { label: "출고지연(mean)", bars: [{ name: "기준", value: a.baseline_mean, color: "#9db4e8" }, { name: "시나리오", value: a.scenario_mean, color: "#2f6bff" }] },
        { label: "피킹 P90(분)", bars: [{ name: "기준", value: b.baseline_p90, color: "#9db4e8" }, { name: "시나리오", value: b.scenario_p90, color: "#2f6bff" }] },
      ]);
    } else {
      svgBars(el, [
        { label: "출고지연(mean)", bars: [{ name: "mean", value: sd.mean || 0, color: "#2f6bff" }] },
        { label: "피킹 P90(분)", bars: [{ name: "p90", value: pw.p90 || 0, color: "#2f6bff" }] },
      ]);
    }
  }
}

/* ---------- Agent Copilot ---------- */
function recommendScenario(p) {
  const w = p.worker_count, f = p.forklift_count, teams = Math.min(Math.floor(w / 2), f);
  if (Math.floor(w / 2) <= f) { const dw = w % 2 === 0 ? 2 : 1; return { worker_delta: dw, forklift_delta: 0, label: `작업자 +${dw}명 증원` }; }
  return { worker_delta: 0, forklift_delta: 1, label: "지게차 +1대 투입" };
}
async function loadCopilot(params) {
  const sc = recommendScenario(params);
  const body = { horizon_days: Number($("#horizon").value), replications: 15, scenario: { worker_delta: sc.worker_delta, forklift_delta: sc.forklift_delta } };
  const resp = await fetch("/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((x) => x.json());
  const c = resp.comparison || [];
  const rows = [
    ["출고지연(mean)", cmpRow(c, "shipping_delay_count"), "mean", true, "분"],
    ["피킹처리 P90", cmpRow(c, "picking_wait_minutes"), "p90", true, "분"],
    ["팀 가동률", cmpRow(c, "resource_utilization_team"), "mean", false, "", true],
  ];
  const items = rows.map(([label, row, fld, lower, unit, pctv]) => {
    if (!row) return "";
    const b = row["baseline_" + fld], s = row["scenario_" + fld], d = row["delta_" + fld];
    const pct = b ? (d / Math.abs(b)) * 100 : 0;
    const improved = lower ? d < 0 : d > 0;
    const fmt = (v) => pctv ? (v * 100).toFixed(1) + "%" : Number(v).toFixed(1) + unit;
    return `<div class="reco-item"><span class="chk">✔</span>${label}: ${fmt(b)} → ${fmt(s)}
      <span class="imp ${improved ? "down" : "up"}">${d < 0 ? "▼" : "▲"} ${Math.abs(pct).toFixed(1)}%</span></div>`;
  }).join("");
  $("#copilot-body").innerHTML = `
    <div class="lead">인사이트에 근거한 시뮬레이션 결과를 분석하여 최적의 운영 전략을 제안드립니다.</div>
    <div class="reco-card">
      <div class="reco-title">추천: ${sc.label}</div>
      <div class="reco-sub">${sc.label} 시 다음 효과를 얻을 것으로 예상됩니다.</div>
      <div class="reco-list">${items}</div>
      <div class="reco-foot">신뢰도: 시뮬레이션 ${body.replications}회 기반 · 시나리오 ${JSON.stringify(body.scenario)}</div>
    </div>`;
}

/* ---------- 데이터 로드 ---------- */
async function loadResources() {
  const r = await fetch("/resources").then((x) => x.json());
  META = r;
  $("#baseline-banner").textContent =
    `현재 베이스라인 — 작업자 ${r.worker}명 · 지게차 ${r.forklift}대 (가용 팀 ${r.team_count}조). 팀 = 작업자2+지게차1, 남는 작업자나 지게차는 조를 이룰 수 없습니다.`;
  return r;
}
const setUpdated = () => { $("#updated").textContent = "최근 갱신 : " + new Date().toLocaleTimeString("ko-KR"); };

async function fetchForecast(sku) {
  if (!sku) return null;
  const fc = await fetch("/forecast", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sku, forecast_days: 14 }) }).then((x) => x.json());
  fc.sku = sku; return fc;
}

/* ---------- 버전 조회/비교 + 통합 렌더 (single source of truth = 표시 버전) ---------- */
let VERSIONS = [];
function verLabel(v) {
  const w = v.worker_count == null ? "?" : v.worker_count;
  const f = v.forklift_count == null ? "?" : v.forklift_count;
  return `${v.version_name} · ${v.run_type} · 작업자 ${w}/지게차 ${f}`;
}
async function loadVersions() {
  const r = await fetch("/simulation/versions").then((x) => x.json()).catch(() => ({ versions: [] }));
  VERSIONS = r.versions || [];
  const opts = VERSIONS.map((v) => `<option value="${v.version_name}">${verLabel(v)}</option>`).join("");
  const dv = $("#ver-display"), cv = $("#ver-compare");
  const keepD = dv.value, keepC = cv.value;
  dv.innerHTML = opts || `<option value="">(버전 없음)</option>`;
  cv.innerHTML = `<option value="">(비교 안 함)</option>` + opts;
  if (keepD) dv.value = keepD;
  if (keepC) cv.value = keepC;
}
// 표시 버전(+선택적 비교 기준) 하나로 KPI·인사이트·트윈·타임라인을 일괄 렌더
async function renderAll(result, comparison) {
  if (!result) return;
  LAST.result = result; LAST.comparison = comparison || null;
  window.__lastParams = result.params;
  renderKpis(result, LAST.comparison, META.inventory_value);
  renderKpiDashboard();
  const so = earliestStockout(result);
  LAST.forecast = await fetchForecast(so ? so.sku : "SKU_A001");
  renderInsight();
  renderTwin(result.movement, result.zone_occupancy_timeseries);   // 트윈 = 표시 버전
  renderTimeline(result.bottleneck_events);                        // 타임라인 = 같은 버전의 이벤트
  const cmpName = $("#ver-compare").value;
  $("#version-badge").textContent = `표시: ${result.version_name} (${result.run_type})`
    + (comparison && cmpName ? ` · 비교기준 ${cmpName}` : "");
  updateCommitState(result);
  setUpdated();
}
function updateCommitState(result) {
  const btn = $("#commit-baseline");
  const isWhatif = !!result && result.run_type === "WHATIF";
  btn.disabled = !isWhatif;
  btn.title = isWhatif ? "이 버전의 작업자/지게차 수를 운영 기준으로 반영합니다"
                       : "What-if 버전을 선택하면 활성화됩니다";
}
async function selectVersion() {
  const dv = $("#ver-display").value; if (!dv) return;
  const cv = $("#ver-compare").value;
  const result = await fetch(`/simulation/versions/${encodeURIComponent(dv)}`).then((x) => x.json()).catch(() => null);
  if (!result || result.error) { $("#version-badge").textContent = "버전 로드 실패"; return; }
  let comparison = null;
  if (cv && cv !== dv) {
    const cmp = await fetch(`/simulation/compare?base=${encodeURIComponent(cv)}&target=${encodeURIComponent(dv)}`)
      .then((x) => x.json()).catch(() => null);
    comparison = (cmp && cmp.comparison) || null;
  }
  await renderAll(result, comparison);
}

async function runSim() {
  const btn = $("#run-sim"); btn.disabled = true; btn.textContent = "실행 중...";
  const body = { horizon_days: Number($("#horizon").value), replications: Number($("#reps").value) };
  const wd = Number($("#worker-delta").value), fd = Number($("#forklift-delta").value);
  if (wd !== 0 || fd !== 0) body.scenario = { worker_delta: wd, forklift_delta: fd };
  try {
    const resp = await fetch("/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((x) => x.json());
    const result = resp.scenario || resp;
    await loadVersions();                                          // 새 버전 목록 반영
    $("#ver-display").value = result.version_name || "";
    $("#ver-compare").value = resp.comparison && resp.baseline ? (resp.baseline.version_name || "") : "";
    await renderAll(result, resp.comparison || null);             // 방금 실행 버전을 표시 버전으로
    if (result.run_type === "BASELINE") loadCopilot(result.params).catch(() => {});
  } catch (e) {
    $("#version-badge").textContent = "실행 오류: " + e;
  } finally {
    btn.disabled = false; btn.textContent = "▶ 시뮬레이션 실행";
  }
}

async function commitBaseline() {
  // 표시 중인(WHATIF) 버전의 해석된 자원 수를 운영 기준으로 반영
  const dv = $("#ver-display").value;
  let p = window.__lastParams;
  if (dv) {
    const result = await fetch(`/simulation/versions/${encodeURIComponent(dv)}`).then((x) => x.json()).catch(() => null);
    if (result && result.params) p = result.params;
  }
  if (!p) return;
  $("#commit-baseline").disabled = true;
  await fetch(`/resources/update?worker=${p.worker_count}&forklift=${p.forklift_count}`, { method: "POST" }).catch(() => {});
  $("#worker-delta").value = 0; $("#forklift-delta").value = 0;   // 델타 초기화(다음 실행에 중복 가산 방지)
  await loadResources();
  await loadOperationKpis().catch(() => {});
  await runSim();                                                 // 새 기준으로 BASELINE 재실행(델타 0)
}

async function refreshDashboard() {
  await loadResources();
  await loadOperationKpis().catch(() => {});
  await refreshDataBrowser().catch(() => {});
  await runSim();
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
  const panel = $("#panel-" + name); if (panel) panel.classList.remove("hidden");
  if (name !== "auto") leaveAuto();
  if (name !== "data") leaveData();
  if (name === "approval") loadApproval().catch(() => {});
  if (name === "trace") { loadTraces().catch(() => {}); loadSessionInto(TRACE_CTX).catch(() => {}); }
  if (name === "auto") enterAuto();
  if (name === "data") { refreshDataBrowser().catch(() => {}); enterData(); }
  if (name === "kpi") {
    loadKpiTargets().then(loadOperationKpis).catch(() => {});
    loadUtilizationTrend().catch(() => {});
    loadDelayTrend().catch(() => {});
  }
}
function setupTabs() {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => activateTab(t.dataset.tab)));
  document.querySelectorAll("#insight-tabs .seg-btn").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#insight-tabs .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); LAST.insightTab = b.dataset.it; renderInsight();
  }));
  const dv = $("#ver-display"), cv = $("#ver-compare");
  if (dv) dv.addEventListener("change", selectVersion);
  if (cv) cv.addEventListener("change", selectVersion);
}

/* ---------- 디지털 트윈 (2D SVG) ---------- */
let COLDZONES = new Set();
async function loadZoneTypes() {
  try {
    const z = await fetch("/data/zones?limit=20").then((x) => x.json());
    COLDZONES = new Set((z.rows || []).filter((r) => r.storage_type === "COLD").map((r) => r.zone_id));
  } catch (_) { COLDZONES = new Set(); }
}
const TW = { frames: [], occByDay: {}, zpos: {}, entrance: [1, -0.5], idx: 0, timer: null };
const TW_W = 560, TW_H = 300, TW_XMIN = -1, TW_XMAX = 3, TW_YMIN = -1.2, TW_YMAX = 2.8, ZH = 0.4;
const txc = (x) => ((x - TW_XMIN) / (TW_XMAX - TW_XMIN)) * TW_W;
const tyc = (y) => (1 - (y - TW_YMIN) / (TW_YMAX - TW_YMIN)) * TW_H;
const STATE_COLOR = { MOVING: "#1f77b4", WORKING: "#d62728", IDLE: "#999999" };
const JOB_META = { INBOUND: { color: "#028090", icon: "📥", label: "적치" }, OUTBOUND: { color: "#f0a13a", icon: "🛒", label: "피킹" } };
function occColor(r) {
  r = Math.max(0, Math.min(r || 0, 1));
  return `rgb(255,${Math.round(255 * (1 - r) ** 1.6)},${Math.round(255 * (1 - r) ** 1.9)})`;
}
function dirArrow(h) { h = ((h % 360) + 360) % 360; return h < 45 || h >= 315 ? "⬆" : h < 135 ? "➡" : h < 225 ? "⬇" : "⬅"; }

function twFrameSvg(i) {
  const f = TW.frames[i]; if (!f) return "";
  const day = String(f.time).split(" ")[0];
  const occ = TW.occByDay[day] || TW.occByDay[Object.keys(TW.occByDay)[0]] || {};
  let s = `<svg viewBox="0 0 ${TW_W} ${TW_H}" preserveAspectRatio="none">`;
  // zones
  for (const [z, p] of Object.entries(TW.zpos)) {
    const x0 = txc(p[0] - ZH), y0 = tyc(p[1] + ZH), w = txc(p[0] + ZH) - x0, h = tyc(p[1] - ZH) - y0;
    const ratio = occ[z] || 0;
    const cold = COLDZONES.has(z);
    s += `<rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="6" fill="${occColor(ratio)}" stroke="${cold ? "#3b82f6" : "#c7d2e6"}" stroke-width="${cold ? 2 : 1}"${cold ? ' stroke-dasharray="4 3"' : ""}/>`;
    if (cold) {
      s += `<rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="6" fill="#3b82f6" fill-opacity="0.12"/>`;
      s += `<text x="${x0 + 11}" y="${y0 + 15}" font-size="12">❄</text>`;
    }
    s += `<text x="${txc(p[0])}" y="${tyc(p[1]) - 4}" font-size="11" font-weight="600" fill="#33415a" text-anchor="middle">${z.replace("ZONE_", "")}</text>`;
    s += `<text x="${txc(p[0])}" y="${tyc(p[1]) + 11}" font-size="9" fill="#5d6573" text-anchor="middle">${Math.round(ratio * 100)}%</text>`;
  }
  // entrance
  s += `<text x="${txc(TW.entrance[0])}" y="${tyc(TW.entrance[1]) + 16}" font-size="10" fill="#333" text-anchor="middle">입구</text>`;
  s += `<polygon points="${txc(TW.entrance[0])},${tyc(TW.entrance[1]) - 2} ${txc(TW.entrance[0]) - 6},${tyc(TW.entrance[1]) + 8} ${txc(TW.entrance[0]) + 6},${tyc(TW.entrance[1]) + 8}" fill="#333"/>`;
  // teams — 작업 중이면 적치(청록)/피킹(주황)으로 링 색 구분 + 작업 배지
  (f.teams || []).forEach((m) => {
    const cx = txc(m.x), cy = tyc(m.y);
    const jm = m.state === "WORKING" && m.job ? JOB_META[m.job] : null;
    const col = jm ? jm.color : (STATE_COLOR[m.state] || "#999");
    s += `<circle cx="${cx}" cy="${cy}" r="12" fill="${col}" fill-opacity="0.16" stroke="${col}" stroke-width="1.6"/>`;
    s += `<text x="${cx}" y="${cy + 5}" font-size="14" text-anchor="middle">🚜</text>`;
    s += `<text x="${cx}" y="${cy - 14}" font-size="12" fill="${col}" text-anchor="middle">${dirArrow(m.heading)}</text>`;
    if (jm) s += `<text x="${cx + 13}" y="${cy - 7}" font-size="12" text-anchor="middle">${jm.icon}</text>`;
  });
  s += `</svg>`;
  return s;
}
function twSetFrame(i) {
  TW.idx = Math.max(0, Math.min(i, TW.frames.length - 1));
  $("#tw-svg").innerHTML = twFrameSvg(TW.idx);
  $("#tw-range").value = String(TW.idx);
  $("#tw-time").textContent = TW.frames[TW.idx] ? TW.frames[TW.idx].time : "--";
}
function renderTwin(movement, occTs) {
  if (TW.timer) { clearInterval(TW.timer); TW.timer = null; $("#tw-play").textContent = "▶ 재생"; }
  if (!movement || !movement.frames || !movement.frames.length) { $("#tw-svg").textContent = "이동 데이터 없음"; return; }
  TW.frames = movement.frames; TW.zpos = movement.zone_pos || {}; TW.entrance = movement.entrance || [1, -0.5];
  TW.occByDay = {};
  (occTs || []).forEach((row) => { const d = String(row.sim_time).split(" ")[0]; if (!(d in TW.occByDay)) TW.occByDay[d] = row.occupancy || {}; });
  $("#tw-teaminfo").textContent = `· 팀 ${movement.team_count}조 (작업자 ${movement.team_count * 2}+지게차 ${movement.team_count})`;
  $("#tw-range").max = String(TW.frames.length - 1);
  twSetFrame(0);
}
function twTogglePlay() {
  if (TW.timer) { clearInterval(TW.timer); TW.timer = null; $("#tw-play").textContent = "▶ 재생"; return; }
  $("#tw-play").textContent = "⏸ 정지";
  TW.timer = setInterval(() => twSetFrame((TW.idx + 1) % TW.frames.length), 220);
}

/* ---------- Event Timeline ---------- */
const EVT_META = {
  STOCKOUT: ["stockout", "재고소진"], SHIPPING_DELAY: ["delay", "출고지연"],
  STOCKING_FAILED: ["stocking", "적치실패"], ZONE_SATURATED: ["stocking", "Zone 포화"],
};
function renderTimeline(events) {
  const el = $("#evt-list");
  if (!events || !events.length) { el.innerHTML = `<div class="evt-empty">병목 이벤트 없음</div>`; return; }
  el.innerHTML = events.slice(0, 14).map((e) => {
    const [cls, label] = EVT_META[e.event_type] || ["info", e.event_type];
    const d = e.detail || {};
    const detail = d.order_no ? `${d.order_no} 지연` : d.sku ? `${d.sku} 부족 ${d.short || ""}` : d.zone_id ? `${d.zone_id} (+${d.overflow || ""})` : "";
    return `<div class="evt-item"><span class="evt-time">${e.sim_time}</span>
      <span class="evt-badge ${cls}">${label}</span><span class="evt-detail">${detail}</span></div>`;
  }).join("");
}

async function loadSessions() {
  try {
    const r = await fetch("/sessions?user_id=operator01").then((x) => x.json());
    CHAT.sessions = r.sessions || [];
  } catch (_) { CHAT.sessions = []; }
  renderSessions();
}
function renderSessions() {
  const list = $("#chat-list"); if (!list) return;
  const f = CHAT.filter.trim().toLowerCase();
  const items = CHAT.sessions.filter((s) => !f || (s.title || "").toLowerCase().includes(f));
  if (!items.length) {
    list.innerHTML = `<div class="ci-empty">${f ? "검색 결과 없음" : "대화 이력이 없습니다"}</div>`;
    return;
  }
  list.innerHTML = items.map((s) => {
    const when = (s.updated_at || "").replace("T", " ").slice(5, 16);
    const active = s.session_id === CHAT.sessionId ? " active" : "";
    return `<div class="chat-item${active}" data-sid="${safeText(s.session_id)}">
      <div class="ci-title">💬 ${safeText(s.title || "새 대화")}</div>
      <div class="ci-meta">${safeText(when)} · ${s.msg_count || 0}메시지</div></div>`;
  }).join("");
  list.querySelectorAll(".chat-item").forEach((el) =>
    el.addEventListener("click", () => openSession(el.dataset.sid)));
}
async function openSession(sid) {
  if (!sid) return;
  CHAT.sessionId = sid;
  const r = await fetch(`/sessions/${sid}`).then((x) => x.json()).catch(() => null);
  const msgs = (r && r.messages) || [];
  renderMessages(CHAT_CTX, msgs);     // Agent Chat 표면
  renderMessages(TRACE_CTX, msgs);    // AI 관측 표면
  TRACE.runId = null;
  loadTraces(sid).catch(() => {});    // 이 세션의 실행 이력만
  const active = document.querySelector(".tab.active");
  const at = active && active.dataset.tab;
  if (at !== "chat" && at !== "trace") activateTab("chat");  // 다른 탭이면 채팅으로
  renderSessions();
}

/* ---------- Agent Chat ---------- */
const CHAT_SUGGESTS = ["오늘 뭐 해야 돼?", "SKU_A001 언제 소진돼?", "왜 Zone A를 추천했어?", "이번 주 창고 상황 예측해줘"];
const CHAT_EMPTY_HTML = `<div class="chat-empty" id="chat-empty">
  <div class="ce-title">무엇을 도와드릴까요?</div>
  <div class="ce-sub">오늘 할 일, 적치·피킹 추천, 재고 소진 예측, 시뮬레이션을 자연어로 물어보세요.</div>
</div>`;
const TRACE_EMPTY_HTML = `<div class="chat-empty"><div class="ce-title">AI 동작 관측</div>
  <div class="ce-sub">질문하면 노드 동작이 단계별로 보입니다. 좌측에서 세션을 선택하세요.</div></div>`;
// 두 채팅 표면: Agent Chat(스텝 숨김) / AI 관측(스텝 표시)
const CHAT_CTX = { inner: "thread-inner", scroll: "chat-scroll", root: "chat-root", text: "chat-text", send: "chat-send", steps: false, emptyHtml: CHAT_EMPTY_HTML };
const TRACE_CTX = { inner: "trace-thread-inner", scroll: "trace-scroll", root: "trace-chat-root", text: "trace-text", send: "trace-send", steps: true, emptyHtml: TRACE_EMPTY_HTML };

function renderMessages(ctx, msgs) {
  const innerEl = document.getElementById(ctx.inner); if (!innerEl) return;
  const root = document.getElementById(ctx.root);
  innerEl.innerHTML = "";
  if (!msgs || !msgs.length) { if (root) root.classList.add("is-empty"); innerEl.innerHTML = ctx.emptyHtml; return; }
  if (root) root.classList.remove("is-empty");
  msgs.forEach((m) => {
    if (m.role === "user") appendBubble("user", escapeHtml(m.content), ctx);
    else {
      let src = []; try { src = JSON.parse(m.sources_json || "[]"); } catch (_) {}
      appendBubble("bot", escapeHtml(m.content).replace(/\n/g, "<br>") + renderSources(src), ctx);
    }
  });
}
async function loadSessionInto(ctx) {
  if (!CHAT.sessionId) { renderMessages(ctx, []); return; }
  const r = await fetch(`/sessions/${CHAT.sessionId}`).then((x) => x.json()).catch(() => null);
  renderMessages(ctx, (r && r.messages) || []);
}
const escapeHtml = (s) => (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const chatScrollBottom = (ctx) => { const sc = document.getElementById((ctx || CHAT_CTX).scroll); if (sc) sc.scrollTop = sc.scrollHeight; };
const chatThread = () => $("#thread-inner") || $("#chat-scroll");

function appendBubble(role, inner, ctx) {
  ctx = ctx || CHAT_CTX;
  const innerEl = document.getElementById(ctx.inner);
  const empty = innerEl.querySelector(".chat-empty"); if (empty) empty.remove();
  const root = document.getElementById(ctx.root); if (root) root.classList.remove("is-empty");
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  const who = role === "user" ? "사용자" : "Woong AI";
  wrap.innerHTML = `<div class="role-tag">${who} :</div><div class="bubble">${inner}</div>`;
  innerEl.appendChild(wrap);
  chatScrollBottom(ctx);
  return wrap;
}
function renderSources(sources) {
  if (!sources || !sources.length) return "";
  const items = sources.map((s) => `<span class="src">${escapeHtml(s.source)}${s.section ? " · " + escapeHtml(s.section) : ""}</span>`).join("");
  return `<div class="msg-src"><span class="src-label">근거</span>${items}</div>`;
}
function renderDryRun(dry) {
  if (!dry || (!(dry.changes || []).length && !(dry.warnings || []).length)) return "";
  const ch = (dry.changes || []).map((c) => {
    const tgt = (c.table || "") + (c.field ? "." + c.field : "") + (c.sku ? " (" + c.sku + ")" : "");
    const val = c.after !== undefined ? c.after : (c.qty_change !== undefined ? c.qty_change : "");
    const bef = (c.before !== undefined && c.before !== null) ? escapeHtml(c.before) + " → " : "";
    return `<li>${escapeHtml(tgt)}: ${bef}${escapeHtml(val)}</li>`;
  }).join("");
  const wn = (dry.warnings || []).map((w) => `<li class="warn">⚠ ${escapeHtml(w)}</li>`).join("");
  return `<ul class="dry">${ch}${wn}</ul>`;
}
function renderApproval(drafts, toolResults) {
  if (!drafts || !drafts.length) return "";
  const d = drafts[0], id = d.draft_id || "";
  const TYPE = { STK: "적치지시 생성", PCK: "피킹지시 발행", SHP: "출고확정" };
  const label = TYPE[(id.split("-")[1] || "")] || "상태 변경";
  const dry = d.dry_run || (toolResults && toolResults.dry_run) || null;
  return `<div class="approval" data-draft="${escapeHtml(id)}">
    <div class="ap-head">⚠ 승인이 필요한 작업 — ${label}</div>
    <div class="ap-id">${escapeHtml(id)}</div>
    ${renderDryRun(dry)}
    <div class="ap-actions">
      <button class="btn-primary ap-yes">승인</button>
      <button class="btn-ghost ap-no">거부</button>
    </div></div>`;
}
function wireApproval(node, toolResults, onDone) {
  const box = node.classList && node.classList.contains("approval") ? node : node.querySelector(".approval");
  if (!box) return;
  const id = box.dataset.draft;
  const done = (txt, cls) => {
    box.innerHTML = `<div class="ap-done ${cls}">${txt}</div>`;
    if (onDone) setTimeout(onDone, 700);
  };
  const call = async (approved) => {
    box.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      const res = await fetch("/approve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft_id: id, approved, user_id: "operator01" }) }).then((x) => x.json());
      if (res.error) { done("처리 오류: " + escapeHtml(res.error), "err"); return; }
      if (approved) { done("✓ 승인되어 실행되었습니다. (" + escapeHtml(res.status || "EXECUTED") + ")", "ok"); loadResources().catch(() => {}); }
      else done("✕ 거부되었습니다. (REJECTED 보관)", "no");
    } catch (e) { done("요청 실패: " + escapeHtml(String(e)), "err"); }
  };
  box.querySelector(".ap-yes").addEventListener("click", () => call(true));
  box.querySelector(".ap-no").addEventListener("click", () => call(false));
}
// ---------- Approval 탭 ----------
const ACTION_LABEL = { ALLOCATION: "할당", STOCKING: "적치지시", PICKING: "피킹지시",
  SHIPPING: "출고확정", REPLENISH: "재고보충", DISPOSAL: "처분" };

function apDrawCard(d, pending) {
  const label = ACTION_LABEL[d.action_type] || d.action_type;
  const when = (d.executed_at || d.approved_at || d.created_at || "").replace("T", " ").slice(5, 16);
  const head = `<div class="ap-top"><span class="ap-type">${safeText(label)}</span>
    <span class="ap-target">${safeText(d.target_id || "")}</span>
    ${pending ? "" : `<span class="ap-status ${d.status}">${safeText(d.status)}</span>`}
    <span class="ap-when">${safeText(when)}</span></div>`;
  if (pending) {
    return `<div class="ap-card approval" data-draft="${safeText(d.draft_id)}">${head}
      ${renderDryRun(d.dry_run)}
      <div class="ap-actions"><button class="btn-primary ap-yes">승인</button>
        <button class="btn-ghost ap-no">거부</button></div></div>`;
  }
  return `<div class="ap-card">${head}${renderDryRun(d.dry_run)}</div>`;
}

async function loadApproval() {
  const [pend, hist] = await Promise.all([
    fetch("/drafts?status=PENDING_APPROVAL").then((x) => x.json()),
    fetch("/drafts?status=EXECUTED,REJECTED&limit=20").then((x) => x.json()),
  ]);
  const pending = pend.drafts || [], history = hist.drafts || [];
  const cnt = $("#ap-pending-count"); cnt.textContent = pending.length;
  cnt.classList.toggle("zero", pending.length === 0);
  $("#ap-pending-list").innerHTML = pending.length
    ? pending.map((d) => apDrawCard(d, true)).join("")
    : `<div class="kpi-empty">승인 대기 작업이 없습니다.</div>`;
  $("#ap-pending-list").querySelectorAll(".approval").forEach((node) => wireApproval(node, null, loadApproval));
  $("#ap-history-list").innerHTML = history.length
    ? history.map((d) => apDrawCard(d, false)).join("")
    : `<div class="kpi-empty">처리 내역이 없습니다.</div>`;
}

// ---------- AI 관측(trace) 탭 ----------
let TRACE = { runId: null, items: [] };

async function loadTraces(sessionId) {
  const sid = sessionId !== undefined ? sessionId : CHAT.sessionId;
  const url = sid ? `/traces?limit=40&session_id=${encodeURIComponent(sid)}` : "/traces?limit=40";
  try { TRACE.items = (await fetch(url).then((x) => x.json())).traces || []; }
  catch (_) { TRACE.items = []; }
  const badge = $("#trace-sess"); if (badge) badge.textContent = sid ? "· " + sid : "· 세션 미선택";
  renderTraceList();
  if (TRACE.items.length) {
    if (!TRACE.runId || !TRACE.items.some((t) => t.run_id === TRACE.runId)) openTrace(TRACE.items[0].run_id);
  } else {
    TRACE.runId = null;
    const d = $("#trace-detail"); if (d) d.innerHTML = `<div class="kpi-empty">이 세션의 실행 이력이 없습니다. 아래에서 질문해 보세요.</div>`;
  }
}
function renderTraceList() {
  const el = $("#trace-list"); if (!el) return;
  if (!TRACE.items.length) { el.innerHTML = `<div class="kpi-empty">실행 이력이 없습니다. Agent Chat에서 질문해 보세요.</div>`; return; }
  el.innerHTML = TRACE.items.map((t) => {
    const when = (t.created_at || "").replace("T", " ").slice(5, 16);
    const flags = (t.rag_required ? `<span class="tr-flag rag">RAG</span>` : "")
      + (t.abstain ? `<span class="tr-flag abst">abstain</span>` : "")
      + (t.approval_required ? `<span class="tr-flag appr">승인</span>` : "");
    return `<div class="tr-item${t.run_id === TRACE.runId ? " active" : ""}" data-run="${safeText(t.run_id)}">
      <div class="tr-q">${safeText((t.query || "").slice(0, 60))}</div>
      <div class="tr-meta"><span class="tr-intent">${safeText(t.intent || "-")}</span>${flags}
        ${t.total_tokens != null ? `<span class="tr-tok">${t.total_tokens}tok</span>` : ""}
        <span class="tr-time">${safeText(when)}</span></div></div>`;
  }).join("");
  el.querySelectorAll(".tr-item").forEach((n) => n.addEventListener("click", () => openTrace(n.dataset.run)));
}
function kv(k, v) { return `<span class="fs-kv"><b>${k}</b> ${safeText(v)}</span>`; }
function renderStepBody(s) {
  const o = s.out || {};
  if (s.node === "Router") return kv("intent", o.intent) + kv("confidence", o.confidence != null ? Number(o.confidence).toFixed(2) : "—")
    + (Object.keys(o.parameters || {}).length ? `<div>${Object.entries(o.parameters).map(([k, v]) => `<span class="fs-chip">${safeText(k)}=${safeText(v)}</span>`).join("")}</div>` : "");
  if (s.node === "Param Extractor") return (o.missing_parameters || []).length ? kv("누락", (o.missing_parameters).join(", ")) : `<span class="fs-chip">필수값 충족</span>`;
  if (s.node === "Planner") return (o.plan || []).map((p) => `<span class="fs-chip">${safeText(p)}</span>`).join("") || "—";
  if (s.node === "Tool Executor") return (o.tools || []).length ? (o.tools).map((t) => `<span class="fs-chip">${safeText(t)}</span>`).join("") : `<span class="fs-chip">도구 없음</span>` + (o.error ? kv("error", o.error) : "");
  if (s.node === "Verifier") { const v = o.verification_results || {}; return Object.keys(v).length ? Object.entries(v).map(([k, val]) => kv(k, val)).join("") : `<span class="fs-chip">해당 없음</span>`; }
  if (s.node === "RAG Decision") return `<span class="fs-chip">${o.rag_required ? "검색 수행" : "검색 불필요"}</span>`;
  if (s.node === "RAG Retriever") {
    const ev = (o.evidence || []).map((e) => {
      const rel = Number(e.relevance || 0);
      return `<div class="ev-row"><div><div class="ev-src">${safeText(e.source)}${e.section ? " · " + safeText(e.section) : ""}</div>
        <div class="ev-span">${safeText(e.evidence_span || "")}</div></div>
        <div class="ev-score">rel ${rel.toFixed(2)} · con ${Number(e.contribution || 0).toFixed(2)}<span class="ev-bar" style="width:${Math.round(rel * 40)}px"></span></div></div>`;
    }).join("");
    return kv("answerable", o.answerable) + kv("충분성", o.sufficiency_score != null ? Number(o.sufficiency_score).toFixed(2) : "—")
      + kv("재검색", o.retries) + (o.abstain ? `<span class="tr-flag abst">abstain</span>` : "")
      + (o.missing_evidence_types || []).map((m) => `<span class="fs-chip">missing: ${safeText(m)}</span>`).join("")
      + (ev ? `<div style="margin-top:8px">${ev}</div>` : "");
  }
  if (s.node === "Response Generator") return `<div class="fs-resp">${safeText((o.final_response || "").slice(0, 280))}${(o.final_response || "").length > 280 ? "…" : ""}</div>`;
  if (s.node === "Approval Gate") return o.approval_required ? `<span class="tr-flag appr">승인 필요</span> ${(o.draft_actions || []).map((d) => `<span class="fs-chip">${safeText(d.draft_id || "")}</span>`).join("")}` : `<span class="fs-chip">승인 불필요</span>`;
  return "";
}
async function openTrace(runId) {
  TRACE.runId = runId; renderTraceList();
  const t = await fetch(`/traces/${runId}`).then((x) => x.json()).catch(() => null);
  const el = $("#trace-detail"); if (!el) return;
  if (!t || !t.steps) { el.innerHTML = `<div class="kpi-empty">트레이스를 불러올 수 없습니다.</div>`; return; }
  const flow = t.steps.map((s) =>
    `<div class="fstep"><div><span class="fs-node">${safeText(s.node)}</span><span class="fs-label">${safeText(s.label || "")}</span></div>
      <div class="fs-body">${renderStepBody(s)}</div></div>`).join("");
  el.innerHTML = `<div class="td-q">${safeText(t.query || "")}</div>
    <div class="td-sub">run ${safeText(t.run_id)} · ${safeText((t.created_at || "").replace("T", " ").slice(0, 16))}${t.total_tokens != null ? ` · ${t.total_tokens} 토큰 (LLM ${t.llm_calls || 0}콜)` : ""}</div>
    <div class="flow">${flow}</div>`;
}

function liveSummary(node, o) {
  o = o || {};
  switch (node) {
    case "Router": return `${safeText(o.intent || "-")}${o.confidence != null ? " · " + Number(o.confidence).toFixed(2) : ""}`;
    case "Param Extractor": return (o.missing_parameters || []).length ? "누락: " + o.missing_parameters.join(", ") : "필수값 충족";
    case "Planner": return (o.plan || []).join(", ") || "—";
    case "Tool Executor": return (o.tools || []).length ? o.tools.join(", ") : (o.error ? "오류" : "도구 없음");
    case "Verifier": return "정합성 확인";
    case "RAG Decision": return o.rag_required ? "검색 수행" : "검색 불필요";
    case "RAG Retriever": return `충분성 ${o.sufficiency_score != null ? Number(o.sufficiency_score).toFixed(2) : "—"} · 재검색 ${o.retries ?? 0}${o.abstain ? " · abstain" : ""}`;
    case "Response Generator": return "응답 생성";
    case "Approval Gate": return o.approval_required ? "승인 필요" : "승인 불필요";
    default: return "";
  }
}
function subSummary(ev) {
  switch (ev.kind) {
    case "search": return `검색 #${ev.attempt} · 후보 ${ev.candidates}개`;
    case "rerank": return `PRISM 리랭크 #${ev.attempt} · ` + ((ev.top || []).map((t) => `${t.source}(rel ${t.relevance})`).join(", ") || "후보 없음");
    case "sufficiency": return `충분성 #${ev.attempt} · ${ev.score} · ${ev.answerable ? "충분" : "부족"}` + ((ev.missing || []).length ? ` · 부족:${ev.missing.join(",")}` : "");
    case "retry": return `재검색 #${ev.attempt} · 질의 보강`;
    case "abstain": return "abstain — 근거 부족";
    default: return ev.kind || "";
  }
}
function handleChatEvent(ev, ui) {
  const ctx = ui.ctx;
  if (ev.type === "substep") {
    if (!ctx.steps || ev.kind === "tokens") return;   // 토큰은 라이브 미표시(총합은 done에서)
    const row = document.createElement("div");
    row.className = "lsub";
    row.innerHTML = `<span class="lsub-ic">↳</span><span class="lsub-text">${escapeHtml(subSummary(ev))}</span>`;
    ui.stepsEl.appendChild(row);
    chatScrollBottom(ctx);
    return;
  }
  if (ev.type === "step") {
    if (!ctx.steps) return;            // Agent Chat: 동작 스텝 숨김(AI 관측에서만)
    const detail = renderStepBody({ node: ev.node, out: ev.out });   // 우측 상세와 동일 렌더 재사용
    const row = document.createElement("div");
    row.className = "lstep done" + (detail ? " has-detail" : "");
    row.innerHTML = `<div class="lstep-head"><span class="ls-ic">✓</span>`
      + `<span class="ls-label">${escapeHtml(ev.label || ev.node)}</span>`
      + `<span class="ls-sum">${escapeHtml(liveSummary(ev.node, ev.out))}</span>`
      + (detail ? `<span class="ls-caret">▸</span>` : "") + `</div>`
      + (detail ? `<div class="lstep-detail">${detail}</div>` : "");
    if (detail) row.querySelector(".lstep-head").addEventListener("click", () => row.classList.toggle("open"));
    ui.stepsEl.appendChild(row);
    chatScrollBottom(ctx);
  } else if (ev.type === "done") {
    if (ui.runEl) ui.runEl.remove();
    if (ev.session_id) CHAT.sessionId = ev.session_id;
    if (ev.error) { ui.finalEl.innerHTML = `<span class="err">오류: ${escapeHtml(ev.error)}</span>`; return; }
    ui.finalEl.innerHTML = escapeHtml(ev.response || "(응답이 비어 있습니다)").replace(/\n/g, "<br>")
      + renderSources(ev.rag_sources)
      + (ev.approval_required ? renderApproval(ev.draft_actions, ev.tool_results) : "");
    if (ev.approval_required) wireApproval(ui.node, ev.tool_results);
    if (ctx.steps && ev.tokens) {
      const t = ev.tokens, row = document.createElement("div");
      row.className = "tok-total";
      row.textContent = `Σ 토큰 ${t.total || 0} · LLM ${t.calls || 0}콜 (입력 ${t.prompt || 0} / 출력 ${t.completion || 0})`;
      ui.stepsEl.appendChild(row);
    }
    if (ctx.steps) { TRACE.runId = null; loadTraces(CHAT.sessionId).catch(() => {}); }  // 새 run 목록·상세 갱신
    chatScrollBottom(ctx);
  } else if (ev.type === "error") {
    if (ui.runEl) ui.runEl.remove();
    ui.finalEl.innerHTML = `<span class="err">오류: ${escapeHtml(ev.message || "")}</span>`;
  }
}
async function streamChat(text, ctx) {
  ctx = ctx || CHAT_CTX;
  text = (text || "").trim(); if (!text) return;
  appendBubble("user", escapeHtml(text), ctx);
  const ta = document.getElementById(ctx.text); if (ta) { ta.value = ""; autoGrow(ta); }
  const send = document.getElementById(ctx.send); if (send) send.disabled = true;
  const node = appendBubble("bot",
    `<div class="live-steps"></div>`
    + `<div class="live-run"><span class="typing"><i></i><i></i><i></i></span> 처리 중…</div>`
    + `<div class="live-final"></div>`, ctx);
  const ui = { node, ctx, stepsEl: node.querySelector(".live-steps"),
               runEl: node.querySelector(".live-run"), finalEl: node.querySelector(".live-final") };
  try {
    const resp = await fetch("/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: text, user_id: "operator01", session_id: CHAT.sessionId }) });
    if (!resp.ok || !resp.body) throw new Error("스트림 연결 실패 " + resp.status);
    const reader = resp.body.getReader(), dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const dl = buf.slice(0, i).split("\n").find((l) => l.startsWith("data:"));
        buf = buf.slice(i + 2);
        if (!dl) continue;
        let ev; try { ev = JSON.parse(dl.slice(5).trim()); } catch (_) { continue; }
        handleChatEvent(ev, ui);
      }
    }
  } catch (e) {
    if (ui.runEl) ui.runEl.remove();
    ui.finalEl.innerHTML = `<span class="err">요청 실패: ${escapeHtml(String(e))}</span>`;
  } finally {
    if (send) send.disabled = false;
    const ta2 = document.getElementById(ctx.text); if (ta2) ta2.focus();
    setUpdated(); loadSessions().catch(() => {});
  }
}
function sendChat(text) { return streamChat(text, CHAT_CTX); }
function autoGrow(ta) { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 140) + "px"; }
function bindSuggests() {
  const sug = $("#chat-suggest"); if (!sug) return;
  sug.innerHTML = CHAT_SUGGESTS.map((s) => `<button class="sug">${escapeHtml(s)}</button>`).join("");
  sug.querySelectorAll(".sug").forEach((b) => b.addEventListener("click", () => sendChat(b.textContent)));
}
function resetChat() {
  CHAT.sessionId = null;                 // 새 대화 = 새 세션
  renderMessages(CHAT_CTX, []);          // 두 표면 모두 초기화
  renderMessages(TRACE_CTX, []);
  TRACE.runId = null; TRACE.items = []; renderTraceList();
  const td = $("#trace-detail"); if (td) td.innerHTML = `<div class="kpi-empty">새 대화입니다. 질문하면 동작이 그려집니다.</div>`;
  bindSuggests();
  const ta = $("#chat-text");
  if (ta) { ta.value = ""; autoGrow(ta); ta.focus(); }
  renderSessions();
}
function setupChat() {
  const ta = $("#chat-text"), send = $("#chat-send");
  if (ta && send) {
    send.addEventListener("click", () => sendChat(ta.value));
    ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(ta.value); } });
    ta.addEventListener("input", () => autoGrow(ta));
  }
  const plus = $("#cp-plus"); if (plus) plus.addEventListener("click", resetChat);
  // AI 관측 탭 입력창
  const tta = $("#trace-text"), tsend = $("#trace-send");
  if (tta && tsend) {
    tsend.addEventListener("click", () => streamChat(tta.value, TRACE_CTX));
    tta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); streamChat(tta.value, TRACE_CTX); } });
    tta.addEventListener("input", () => autoGrow(tta));
  }
  bindSuggests();
}

// ---------- 실시간 수요 발생 + Toast ----------
let LIVE = { running: false, es: null };

function showToast(ev) {
  const wrap = $("#toast-wrap"); if (!wrap) return;
  const kind = ev.kind || "outbound";
  const tag = kind === "inbound" ? "입고" : kind === "outbound" ? "출고" : "오류";
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<div class="t-head"><span class="t-tag">${tag}</span>${ev.id ? safeText(ev.id) : "실시간"}<span class="t-time">${safeText(ev.ts || "")}</span></div>
    <div class="t-body">${safeText(ev.message || "")}</div>`;
  wrap.appendChild(el);
  setTimeout(() => { el.classList.add("fade"); setTimeout(() => el.remove(), 300); }, 6000);
  while (wrap.children.length > 5) wrap.firstChild.remove();
}

function setupRealtime() {
  const btn = $("#live-toggle"); if (!btn) return;
  // SSE 구독은 항상 유지(수동 발생 1건도 수신)
  try {
    LIVE.es = new EventSource("/events");
    LIVE.es.onmessage = (e) => { try { showToast(JSON.parse(e.data)); } catch (_) {} };
  } catch (_) {}
  btn.addEventListener("click", async () => {
    LIVE.running = !LIVE.running;
    await fetch(`/realtime/${LIVE.running ? "start" : "stop"}`, { method: "POST" }).catch(() => {});
    btn.classList.toggle("on", LIVE.running);
    btn.innerHTML = `<i class="live-dot"></i>실시간 수요 ${LIVE.running ? "ON" : "OFF"}`;
  });
  setupLiveSettings();
}

async function openLiveSettings() {
  const s = await fetch("/realtime/status").then((x) => x.json()).catch(() => ({}));
  $("#cfg-interval").value = s.interval ?? 8;
  $("#cfg-ratio").value = Math.round((s.outbound_ratio ?? 0.5) * 100);
  $("#cfg-out-min").value = s.out_qty_min ?? 5;
  $("#cfg-out-max").value = s.out_qty_max ?? 40;
  $("#cfg-in-min").value = s.in_qty_min ?? 20;
  $("#cfg-in-max").value = s.in_qty_max ?? 120;
  $("#live-modal").classList.remove("hidden");
}
function closeLiveSettings() { $("#live-modal").classList.add("hidden"); }
async function saveLiveSettings() {
  const body = {
    interval: Number($("#cfg-interval").value),
    outbound_ratio: Math.min(100, Math.max(0, Number($("#cfg-ratio").value))) / 100,
    out_qty_min: Number($("#cfg-out-min").value), out_qty_max: Number($("#cfg-out-max").value),
    in_qty_min: Number($("#cfg-in-min").value), in_qty_max: Number($("#cfg-in-max").value),
  };
  await fetch("/realtime/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).catch(() => {});
  closeLiveSettings();
}
function setupLiveSettings() {
  const g = $("#live-settings"); if (!g) return;
  g.addEventListener("click", () => openLiveSettings().catch(() => {}));
  $("#live-modal-x").addEventListener("click", closeLiveSettings);
  $("#live-modal-cancel").addEventListener("click", closeLiveSettings);
  $("#live-modal-save").addEventListener("click", () => saveLiveSettings());
  $("#live-emit-now").addEventListener("click", () => fetch("/realtime/emit", { method: "POST" }).catch(() => {}));
  $("#live-modal").addEventListener("click", (e) => { if (e.target.id === "live-modal") closeLiveSettings(); });
}

/* ---------- 창고 자동운영 (블랙보드 대시보드) ---------- */
const AGENTS = [
  { id: "InboundAgent", label: "입고", emoji: "📥", kind: "dom" },
  { id: "PutawayAgent", label: "적치", emoji: "📦", kind: "dom" },
  { id: "PickingAgent", label: "피킹", emoji: "🛒", kind: "dom" },
  { id: "OutboundAgent", label: "출고", emoji: "🚚", kind: "dom" },
  { id: "ResourceAgent", label: "자원배정", emoji: "👷", kind: "dom" },
  { id: "AutoOrderAgent", label: "자동발주", emoji: "📦", kind: "dom" },
  { id: "ControlAgent", label: "컨트롤", emoji: "🧭", kind: "inf" },
  { id: "PolicyAgent", label: "정책", emoji: "🛡️", kind: "inf" },
  { id: "SimulationAgent", label: "시뮬레이션", emoji: "🧊", kind: "inf" },
  { id: "ExplanationAgent", label: "설명", emoji: "💬", kind: "inf" },
];
const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a]));
const AUTO = { on: false, seen: new Set(), flash: {}, poll: null, booted: false, renderedLogs: new Set(), manualSim: null, simRefreshing: false, requests: [], selectedReq: null, capacity: null, explaining: false };
const PHASE_LABEL = {
  EVENT_RECEIVED: "이벤트 수신", ACTION_CREATED: "Action 생성", POLICY_CHECK: "정책 검토",
  PRECHECK: "사전검증", LOCK_ACQUIRED: "락 확보", EXECUTE: "실행", POSTCHECK: "사후검증", FINISHED: "완료",
};

function agentForLog(l) {
  if (l.phase === "EVENT_RECEIVED") return "ControlAgent";
  if (l.phase === "POLICY_CHECK") return "PolicyAgent";
  if (l.agent_name === "SimulationAgent") return "SimulationAgent";
  if (l.phase === "ACTION_CREATED") return l.agent_name;
  if (AGENT_BY_ID[l.agent_name]) return l.agent_name;
  return "ControlAgent";
}

function statusBadge(st) {
  const m = {
    SUCCESS: ["성공", "ok"], POLICY_BLOCKED: ["차단", "blk"], FAILED: ["실패", "fail"],
    SKIPPED_DUPLICATE: ["중복생략", "mut"], PENDING: ["대기", "run"], READY: ["준비", "run"],
    RUNNING: ["실행중", "run"], COMPENSATED: ["보상", "mut"],
  };
  const [t, c] = m[st] || [st || "-", "mut"];
  return `<span class="ab ${c}">${t}</span>`;
}

// 그리드는 1회만 그리고(깜빡임 방지), 활성 표시는 클래스 토글로만 갱신
function buildAgents() {
  const el = $("#auto-agents"); if (!el || el.childElementCount) return;
  el.innerHTML = AGENTS.map((a) => `<div class="agent-cell ${a.kind}" data-agent="${a.id}">
      <span class="agent-badge" data-badge="${a.id}" hidden></span>
      <div class="agent-circle">${a.emoji}</div>
      <div class="agent-name">${a.label}</div>
      <div class="agent-sub">${a.id.replace("Agent", "")}</div></div>`).join("");
}
function renderAgentBadges() {
  // 자동발주 원에 '발주 대기(결품)' 건수를 상시 배지로 — 부족 백로그가 쌓여 있음을 한눈에
  const b = document.querySelector('[data-badge="AutoOrderAgent"]'); if (!b) return;
  const n = (AUTO.capacity && AUTO.capacity.awaiting_stock) || 0;
  if (n > 0) { b.textContent = n; b.title = `발주 대기 ${n}건`; b.hidden = false; }
  else { b.hidden = true; }
}
function updateAgentFlash() {
  const el = $("#auto-agents"); if (!el) return;
  const nowt = Date.now();
  el.querySelectorAll(".agent-cell").forEach((c) => {
    // 시뮬레이션은 DES가 도는 동안, 설명은 LLM 생성 중 계속 켜두고, 그 외는 로그 도착 후 2.4s 점멸
    const on = (c.dataset.agent === "SimulationAgent" && AUTO.simRefreshing)
      || (c.dataset.agent === "ExplanationAgent" && AUTO.explaining)
      || (AUTO.flash[c.dataset.agent] && (nowt - AUTO.flash[c.dataset.agent] < 2400));
    c.classList.toggle("active", !!on);
  });
}

function autoLogLine(l) {
  const t = (l.created_at || "").split(" ")[1] || "";
  const ag = AGENT_BY_ID[agentForLog(l)];
  const c = l.result === "OK" ? "ok" : (l.result === "BLOCKED" ? "blk" : (l.result === "FAIL" ? "fail" : "mut"));
  return `<div class="alog-line"><span class="alog-t">${t}</span>`
    + `<span class="alog-ag">${ag ? ag.emoji + " " + ag.label : (l.agent_name || "—")}</span>`
    + `<span class="alog-ph ${c}">${PHASE_LABEL[l.phase] || l.phase}</span>`
    + `<span class="alog-msg">${escapeHtml(l.message || "")}</span></div>`;
}

const hhmmss = (ts) => (ts ? String(ts).split(" ")[1] || String(ts) : "—");

/* ---------- 실시간 입/출고 요청 + 요청별 생애주기 ---------- */
const REQ_STATUS_CLS = { done: "ok", in_progress: "run", blocked: "blk", failed: "fail", pending: "mut" };
function renderRequests(list) {
  AUTO.requests = list;
  const el = $("#auto-requests"); if (!el) return;
  const meta = $("#auto-req-meta"); if (meta) meta.textContent = list.length ? `${list.length}건` : "";
  if (!list.length) {
    el.innerHTML = `<div class="auto-empty">‘실시간 수요’를 켜면 입/출고 요청이 실시간으로 쌓입니다.</div>`;
    return;
  }
  const sel = AUTO.selectedReq;
  el.innerHTML = list.map((r) => {
    const isOut = r.kind === "outbound";
    const active = sel && sel.id === r.id ? " active" : "";
    const cls = r.status === "AWAITING_STOCK" ? "blk" : (r.status === "SHIPPED" || r.status === "STOCKED" ? "ok" : "mut");
    return `<div class="req-row${active}" data-kind="${r.kind}" data-id="${escapeHtml(r.id)}">
      <span class="req-kind ${isOut ? "out" : "inb"}">${isOut ? "출고" : "입고"}</span>
      <span class="req-id">${escapeHtml(r.id)}</span>
      <span class="req-sub">${escapeHtml(r.sku || "")} ${r.qty != null ? r.qty + "개" : ""}</span>
      <span class="req-t"><span class="ab ${cls}">${escapeHtml(r.status_label || "—")}</span> · ${hhmmss(r.created_at)}</span></div>`;
  }).join("");
  el.querySelectorAll(".req-row").forEach((row) =>
    row.addEventListener("click", () => selectRequest(row.dataset.kind, row.dataset.id)));
}

async function selectRequest(kind, id) {
  AUTO.selectedReq = { kind, id };
  document.querySelectorAll("#auto-requests .req-row").forEach((r) =>
    r.classList.toggle("active", r.dataset.id === id));
  const sub = $("#auto-req-trace-sub"); if (sub) sub.textContent = `${kind === "outbound" ? "출고" : "입고"} ${id}`;
  const el = $("#auto-req-trace"); if (el) el.innerHTML = `<div class="auto-empty">불러오는 중…</div>`;
  await refreshTrace();
}
async function refreshTrace() {
  const s = AUTO.selectedReq; if (!s) return;
  const t = await fetch(`/api/blackboard/requests/${s.kind}/${encodeURIComponent(s.id)}/trace`)
    .then((r) => r.json()).catch(() => null);
  if (t && !t.error) renderReqTrace(t);
}
function renderReqTrace(t) {
  const el = $("#auto-req-trace"); if (!el) return;
  const badgeCls = t.awaiting_stock ? "blk" : "mut";
  const replBtn = !t.awaiting_stock ? ""
    : (AUTO.on
        ? `<button class="btn-ghost repl-now-btn" id="repl-now" data-order="${escapeHtml(t.id)}">🔁 바로 보충</button>`
        : `<button class="btn-ghost repl-now-btn" id="repl-now" disabled title="자동운영을 켜야 보충할 수 있습니다">🔁 바로 보충 (자동운영 OFF)</button>`);
  const head = `<div class="req-trace-head">${t.kind === "outbound" ? "🚚 출고" : "📥 입고"} ${escapeHtml(t.id)}
    <span class="ab ${badgeCls}">${escapeHtml(t.current_status_label || "—")}</span>${replBtn}</div>`;
  const steps = (t.milestones || []).map((m) => {
    const cls = REQ_STATUS_CLS[m.status] || "mut";
    const clickable = m.action_id ? " rt-clickable" : "";
    const hint = m.action_id ? `<span class="rt-why">왜?</span>` : "";
    return `<div class="rt-step ${m.status}${clickable}"${m.action_id ? ` data-action="${escapeHtml(m.action_id)}" data-label="${escapeHtml(m.label)}" data-status="${m.status}"` : ""}>
      <div class="rt-rail"><div class="rt-node ${m.status}"></div><div class="rt-line"></div></div>
      <div class="rt-body">
        <div class="rt-label">${escapeHtml(m.label)} <span class="ab ${cls}">${MS_LABEL[m.status] || m.status}</span>${hint}</div>
        <div class="rt-meta">${m.agent ? escapeHtml(m.agent) : "—"}${m.ts ? " · " + hhmmss(m.ts) : ""}</div>
        <div class="rt-detail">${escapeHtml(m.detail || "")}</div>
      </div></div>`;
  }).join("");
  el.innerHTML = head + `<div class="rt-timeline">${steps}</div>`;
  const btn = $("#repl-now");
  if (btn) btn.addEventListener("click", () => replenishNow(btn.dataset.order));
  el.querySelectorAll(".rt-step.rt-clickable").forEach((s) =>
    s.addEventListener("click", () => explainMilestone(
      s.dataset.action, s.dataset.label, { text: MS_LABEL[s.dataset.status] || "", cls: REQ_STATUS_CLS[s.dataset.status] || "mut" })));
}
const MS_LABEL = { done: "완료", in_progress: "진행", blocked: "보류", failed: "실패", pending: "대기" };

async function replenishNow(orderNo) {
  if (!AUTO.on) { showToast({ kind: "error", id: orderNo, message: "자동운영을 켜야 보충할 수 있습니다." }); return; }
  const btn = $("#repl-now"); if (btn) { btn.disabled = true; btn.textContent = "보충 중…"; }
  AUTO.flash.AutoOrderAgent = Date.now(); updateAgentFlash();   // 수동 보충도 자동발주 원 점멸
  try {
    const r = await fetch(`/api/blackboard/requests/${encodeURIComponent(orderNo)}/replenish-now`, { method: "POST" })
      .then((x) => x.json());
    if (r.error) { showToast({ kind: "error", id: orderNo, message: r.error }); if (btn) { btn.disabled = false; btn.textContent = "🔁 바로 보충"; } return; }
    const n = (r.stocked || []).reduce((s, x) => s + (x.qty || 0), 0);
    showToast({ kind: "ok", id: orderNo, message: `가상 보충 완료 — ${n}개 입고 반영, 주문 재개` });
    AUTO.flash.AutoOrderAgent = Date.now(); updateAgentFlash();
    await refreshTrace();
  } catch (_) {
    if (btn) { btn.disabled = false; btn.textContent = "🔁 바로 보충"; }
  }
}


function simCountdown(s) {
  if (!s || !s.refresh_seconds) return "";
  if (!s.ts) return ` · <span class="sim-cd">시뮬레이션 기동중…</span>`;
  const rem = Math.ceil(s.refresh_seconds - (Date.now() / 1000 - s.ts));
  return rem > 0
    ? ` · <span class="sim-cd">기준치 갱신까지 ${rem}s</span>`
    : ` · <span class="sim-cd">시뮬레이션 기동중…</span>`;
}
function laborBody() {   // 노동 신호 = 실시간 작업팀 가용 + 미처리 대기(적치/피킹 별도)
  const c = AUTO.capacity;
  if (!c) return `작업팀 <b>—</b>`;
  const shortCls = c.team_short ? "over" : "";
  const avail = `작업팀 <b class="${shortCls}">${c.available_teams}/${c.total_teams} 가용</b>${c.team_short ? " 부족" : ""}`;
  const wait = `대기 피킹 <b class="${c.waiting_picking ? "over" : ""}">${c.waiting_picking}건</b>·적치 <b class="${c.waiting_stocking ? "over" : ""}">${c.waiting_stocking}건</b>`;
  return `${avail} · ${wait} · 진행중 ${c.in_progress_total}건`;
}
function simBody(s) {   // 노동(팀가용)/공간/출고지연 문자열(카운트다운 제외)
  const k = s.kpis || {};
  const zb = s.zone_block != null ? s.zone_block : 1;
  const over = Object.entries(s.zone_peak || {}).filter(([, o]) => o >= zb).sort((a, b) => b[1] - a[1]);
  let spaceHtml;
  if (over.length) {
    const list = over.map(([z, o]) => `${escapeHtml(z)} ${Math.round(o * 100)}%`).join(" · ");
    spaceHtml = `공간 <b class="over">과부하 ${over.length}존</b> (${list})`;
  } else {
    const zone = s.worst_zone_occ != null ? Math.round(s.worst_zone_occ * 100) + "%" : "—";
    spaceHtml = `공간(최대존) <b>${zone}</b>${s.worst_zone ? " " + escapeHtml(s.worst_zone) : ""} 정상`;
  }
  return `${laborBody()} · ` + spaceHtml
    + ` · 출고지연 ${fmtNum(k.shipping_delay_count, 0)}건 · 적치지연 ${fmtNum(k.putaway_delay_count, 0)}건`;
}
function setSimbar(s) {
  const el = $("#auto-simbar"); if (!el) return;
  if (!AUTO.on) {   // OFF면 미가동 — 단, 수동 실행 결과가 최근(45초)이면 그걸 보여줌
    const m = AUTO.manualSim;
    if (m && m.s && m.s.ran && Date.now() - m.at < 45000) {
      el.className = "auto-simbar " + (m.s.ok ? "ok" : "blk");
      el.innerHTML = `<span class="sim-ic">🧊</span> ${simBody(m.s)} <span class="sim-cd">(수동 실행)</span>`;
      return;
    }
    el.className = "auto-simbar";
    const k = (s && s.kpis) || {};
    const ref = (s && s.ran && k.resource_utilization_team != null)
      ? ` <span class="sim-cd">(마지막 기준 · 가동률 ${Math.round(k.resource_utilization_team * 100)}%)</span>` : "";
    el.innerHTML = `<span class="sim-ic">🧊</span> 자동운영 OFF — 시뮬레이션 미가동${ref}`;
    return;
  }
  if (!s || s.ran === false) {
    el.className = "auto-simbar";
    el.innerHTML = `<span class="sim-ic">🧊</span> 배치 시뮬레이션 — ${s && s.reason ? escapeHtml(s.reason) : "대기"}` + simCountdown(s);
    return;
  }
  el.className = "auto-simbar " + (s.ok ? "ok" : "blk");
  el.innerHTML = `<span class="sim-ic">🧊</span> 배치 시뮬레이션 · ${simBody(s)}${simCountdown(s)}`;
}

function updateAutoToggle(enabled) {
  AUTO.on = enabled;
  const pill = $("#auto-pill"), btn = $("#auto-toggle");
  if (pill) { pill.textContent = enabled ? "ON" : "OFF"; pill.classList.toggle("on", enabled); }
  if (btn) { btn.textContent = enabled ? "■ 자동운영 중지" : "자동운영 시작"; btn.classList.toggle("running", enabled); }
}

async function pollAuto() {
  try {
    const [mode, logs, sim, reqs, cap] = await Promise.all([
      fetch("/api/auto-mode").then((r) => r.json()),
      fetch("/api/blackboard/audit-logs?limit=60").then((r) => r.json()),
      fetch("/api/blackboard/simulation").then((r) => r.json()).catch(() => null),
      fetch("/api/blackboard/requests?limit=30").then((r) => r.json()).catch(() => null),
      fetch("/api/blackboard/capacity").then((r) => r.json()).catch(() => null),
    ]);
    updateAutoToggle((mode.auto_mode_enabled || "false") === "true");
    AUTO.simRefreshing = !!(sim && sim.refreshing);   // DES 실행 중 — 시뮬레이션 원 지속 하이라이트
    AUTO.capacity = cap || null;                       // 실시간 작업팀 가용/백로그
    if (sim) setSimbar(sim);
    if (reqs) renderRequests(reqs.requests || []);
    if ($("#auto-cycle") && document.activeElement !== $("#auto-cycle")) {
      $("#auto-cycle").value = mode.auto_mode_cycle_interval_seconds || 15;
    }
    document.querySelectorAll("#auto-settings input[data-key]").forEach((inp) => {
      if (document.activeElement !== inp && mode[inp.dataset.key] != null) inp.value = mode[inp.dataset.key];
    });
    const all = logs.logs || [];                       // 서버는 최신순(DESC)
    const fresh = all.filter((l) => !AUTO.renderedLogs.has(l.log_id));
    if (fresh.length) {
      const box = $("#auto-log");
      const ph = box.querySelector(".auto-empty"); if (ph) ph.remove();
      // 오래된 것부터 afterbegin으로 넣으면 최종적으로 최신이 맨 위
      fresh.slice().reverse().forEach((l) => {
        AUTO.renderedLogs.add(l.log_id);
        AUTO.flash[agentForLog(l)] = Date.now();
        box.insertAdjacentHTML("afterbegin", autoLogLine(l));
      });
      while (box.childElementCount > 140) box.removeChild(box.lastElementChild);
      $("#auto-log-meta").textContent = `${box.childElementCount}건`;
      if (AUTO.renderedLogs.size > 4000) AUTO.renderedLogs = new Set([...AUTO.renderedLogs].slice(-2000));
    }
    if (AUTO.selectedReq) refreshTrace().catch(() => {});   // 선택 요청의 생애주기 라이브 갱신
    renderAgentBadges();
    updateAgentFlash();
  } catch (_) { /* noop */ }
}

async function refreshSimbar() {
  try { setSimbar(await fetch("/api/blackboard/simulation").then((r) => r.json())); }
  catch (_) { setSimbar(null); }
}

// 생애주기 단계(마일스톤) 클릭 → 그 단계 액션의 의사결정 사유(LLM)를 설명 패널에 표시
async function explainMilestone(actionId, label, statusLabel) {
  const det = $("#auto-detail"); if (!det) return;
  const head = `<div class="adet-head">${escapeHtml(label || "")} <span class="ab ${statusLabel && statusLabel.cls || "mut"}">${escapeHtml(statusLabel && statusLabel.text || "")}</span></div>`;
  det.innerHTML = head + `<div class="adet-ex muted">설명 생성 중…</div>`;
  AUTO.explaining = true; updateAgentFlash();   // 설명 원 하이라이트(생성 중 유지)
  try {
    const ex = await fetch(`/api/blackboard/actions/${actionId}/explanation`).then((r) => r.json());
    det.innerHTML = head
      + `<div class="adet-ex">${escapeHtml(ex.explanation || ex.error || "설명 없음")}</div>`
      + `<div class="adet-src">출처: ${escapeHtml(ex.source || "-")}</div>`;
  } catch (e) {
    det.innerHTML = head + `<div class="adet-ex">설명 조회 실패</div>`;
  } finally {
    AUTO.explaining = false; updateAgentFlash();
  }
}

async function toggleAuto() {
  const next = !AUTO.on;
  if (next && !LIVE.running) {
    showToast({ kind: "error", id: "", message: "‘실시간 수요’를 먼저 ON 한 뒤 자동운영을 시작하세요." });
    return;
  }
  updateAutoToggle(next);
  if (next) {
    await fetch("/api/auto-mode/on", { method: "POST" }).catch(() => {});
    await fetch("/api/auto-mode/loop/start", { method: "POST" }).catch(() => {});
    refreshSimbar().catch(() => {});
  } else {
    await fetch("/api/auto-mode/off", { method: "POST" }).catch(() => {});
    await fetch("/api/auto-mode/loop/stop", { method: "POST" }).catch(() => {});
  }
}

function setupAuto() {
  if (AUTO.booted) return; AUTO.booted = true;
  buildAgents();
  $("#auto-toggle").addEventListener("click", () => toggleAuto().catch(() => {}));
  $("#auto-runonce").addEventListener("click", async () => {
    $("#auto-runonce").disabled = true;
    try { await fetch("/api/blackboard/run-once?force=true", { method: "POST" }); await refreshSimbar(); await pollAuto(); }
    finally { $("#auto-runonce").disabled = false; }
  });
  $("#auto-simrun").addEventListener("click", async () => {
    const btn = $("#auto-simrun"); btn.disabled = true;
    const el = $("#auto-simbar"); if (el) { el.className = "auto-simbar"; el.innerHTML = `<span class="sim-ic">🧊</span> 시뮬레이션 기동중…`; }
    try {
      const s = await fetch("/api/blackboard/simulation/run", { method: "POST" }).then((r) => r.json());
      AUTO.manualSim = { s, at: Date.now() };
      setSimbar(s);
    } catch (_) { if (el) el.innerHTML = `<span class="sim-ic">🧊</span> 시뮬레이션 실행 실패`; }
    finally { btn.disabled = false; }
  });
  $("#auto-cycle").addEventListener("change", (e) => {
    const v = Math.max(2, Math.min(600, Number(e.target.value) || 15));
    fetch("/api/auto-mode/settings", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "auto_mode_cycle_interval_seconds", value: String(v) }) }).catch(() => {});
  });
  document.querySelectorAll("#auto-settings input[data-key]").forEach((inp) => {
    inp.addEventListener("change", () => {
      fetch("/api/auto-mode/settings", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: inp.dataset.key, value: String(inp.value) }) })
        .then(() => refreshSimbar()).catch(() => {});
    });
  });
  // 자동발주 원 클릭 → 발주 대기 주문 세부(배지 숫자의 근거)
  $("#auto-agents").addEventListener("click", (e) => {
    const c = e.target.closest(".agent-cell"); if (!c) return;
    if (c.dataset.agent === "AutoOrderAgent") showAwaitingOrders().catch(() => {});
  });
}

async function showAwaitingOrders() {
  const det = $("#auto-detail"); if (!det) return;
  const head = `<div class="adet-head">📦 자동발주 — 발주 대기 주문</div>`;
  det.innerHTML = head + `<div class="adet-ex muted">불러오는 중…</div>`;
  const r = await fetch("/api/blackboard/awaiting-orders").then((x) => x.json()).catch(() => null);
  const orders = (r && r.orders) || [];
  if (!orders.length) {
    det.innerHTML = `<div class="adet-head">📦 자동발주 — 발주 대기 주문</div><div class="adet-ex">발주 대기 주문이 없습니다.</div>`;
    return;
  }
  det.innerHTML = `<div class="adet-head">📦 자동발주 — 발주 대기 ${orders.length}건 <span class="head-sub">클릭하면 생애주기</span></div>`
    + `<div class="awo-list">` + orders.map((o) => {
      const inb = (o.replenishments || []).map((i) =>
        `${escapeHtml(i.sku)} ${i.qty}개 · 도착예정 ${escapeHtml(i.expected_date)} <span class="ab ${i.status === "STOCKED" ? "ok" : "blk"}">${escapeHtml(i.status)}</span>`).join("<br>");
      return `<div class="awo-row" data-order="${escapeHtml(o.order_no)}">
        <div class="awo-id">${escapeHtml(o.order_no)} <span class="req-t">${hhmmss(o.created_at)}</span></div>
        <div class="awo-inb">${inb || "발주분 없음"}</div></div>`;
    }).join("") + `</div>`;
  det.querySelectorAll(".awo-row").forEach((row) =>
    row.addEventListener("click", () => selectRequest("outbound", row.dataset.order)));
}

async function syncLive() {
  try { const s = await fetch("/realtime/status").then((r) => r.json()); LIVE.running = !!s.running; } catch (_) {}
}
function enterAuto() {
  setupAuto();
  // 로그를 새로 그려 깜빡임/잔재 없이 현재 상태부터 시작
  AUTO.renderedLogs = new Set();
  const box = $("#auto-log"); if (box) box.innerHTML = `<div class="auto-empty">동작 없음 — 자동운영을 시작하면 단계별로 표시됩니다.</div>`;
  syncLive().catch(() => {});
  pollAuto().catch(() => {});
  refreshSimbar().catch(() => {});
  if (AUTO.poll) clearInterval(AUTO.poll);
  AUTO.poll = setInterval(() => { updateAgentFlash(); pollAuto().catch(() => {}); }, 1000);
}
function leaveAuto() { if (AUTO.poll) { clearInterval(AUTO.poll); AUTO.poll = null; } }

async function init() {
  setupTabs(); setupChat(); setupDataBrowser(); setupRealtime();
  loadSessions().catch(() => {});
  const ss = document.querySelector(".side-search");
  if (ss) ss.addEventListener("input", (e) => { CHAT.filter = e.target.value; renderSessions(); });
  const nc = $("#new-chat"); if (nc) nc.addEventListener("click", () => { activateTab("chat"); resetChat(); });
  $("#run-sim").addEventListener("click", runSim);
  $("#refresh").addEventListener("click", refreshDashboard);
  $("#refresh-kpi").addEventListener("click", () => {
    loadKpiTargets().then(loadOperationKpis).catch(() => {});
    loadUtilizationTrend().catch(() => {});
    loadDelayTrend().catch(() => {});
  });
  const tz = $("#target-zone-occupancy"), tu = $("#target-utilization");
  if (tz) tz.addEventListener("change", () => saveKpiTarget("kpi_target_zone_occupancy", tz.value));
  if (tu) tu.addEventListener("change", () => saveKpiTarget("kpi_target_utilization", tu.value));
  $("#refresh-data").addEventListener("click", refreshDataBrowser);
  const ra = $("#refresh-approval"); if (ra) ra.addEventListener("click", () => loadApproval().catch(() => {}));
  const rt = $("#refresh-trace"); if (rt) rt.addEventListener("click", () => { TRACE.runId = null; loadTraces().catch(() => {}); });
  $("#commit-baseline").addEventListener("click", commitBaseline);
  $("#tw-play").addEventListener("click", twTogglePlay);
  $("#tw-range").addEventListener("input", (e) => { if (TW.timer) twTogglePlay(); twSetFrame(Number(e.target.value)); });
  await loadZoneTypes().catch(() => {});
  await loadResources();
  await loadKpiTargets().catch(() => {});
  await loadOperationKpis().catch(() => {});
  loadUtilizationTrend().catch(() => {});
  loadDelayTrend().catch(() => {});
  await refreshDataBrowser().catch(() => {});
  await runSim();
}
init();
