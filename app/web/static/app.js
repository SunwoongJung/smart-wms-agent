// Smart WMS Agent — SPA (P1~P5)
const $ = (s) => document.querySelector(s);
let META = { base_date: null };
let LAST = { result: null, forecast: null, comparison: null, insightTab: "inv", operationKpis: null };
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
  const so = earliestStockout(res), soDays = so ? daysFromBase(so.p50) : null;
  const cards = [
    { ico: "🕐", label: kpiLabel("shipping_delay_count"), val: fmtNum(sd.mean, 2), unit: "건", delta: deltaChip(cmpRow(comparison, "shipping_delay_count"), "mean") },
    { ico: "⏳", label: kpiLabel("picking_wait_minutes"), val: fmtNum(pw.p90, 1), unit: "분", delta: deltaChip(cmpRow(comparison, "picking_wait_minutes"), "p90") },
    { ico: "👥", label: kpiLabel("resource_utilization_team"), val: ut.mean != null ? fmtNum(ut.mean * 100, 1) : "—", unit: "%", delta: deltaChip(cmpRow(comparison, "resource_utilization_team"), "mean", false) },
    { ico: "📅", label: kpiLabel("expected_stockout_date"), val: soDays != null ? "D+" + soDays : "—", unit: "", delta: `<span class="kpi-delta flat">${so ? so.p50 : "소진 없음"}</span>` },
    { ico: "💰", label: "총 재고 비용", val: invValue != null ? "₩" + (invValue / 1e6).toFixed(1) + "M" : "—", unit: "", delta: `<span class="kpi-delta flat">예시 단가 기준</span>` },
  ];
  $("#kpi-row").innerHTML = cards.map((c) => `
    <div class="kpi"><div class="kpi-top"><span class="kpi-ico">${c.ico}</span>${c.label}</div>
      <div class="kpi-val">${c.val}<span class="unit">${c.unit}</span></div>${c.delta}</div>`).join("");
}

function opKpi(name) { return ((LAST.operationKpis && LAST.operationKpis.kpis) || []).find((x) => x.name === name) || {}; }
function pct(v, d = 1) { return v == null ? "—" : (Number(v) * 100).toFixed(d) + "%"; }
function metric(label, value, note = "") {
  return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div>${note ? `<div class="metric-note">${note}</div>` : ""}</div>`;
}

async function loadOperationKpis() {
  const body = { kpis: ["zone_occupancy", "saturated_zone_count", "safety_stock_below_count", "stocking_completion_rate", "expected_shortage_count", "dead_stock_count", "replenishment_needed_count"] };
  LAST.operationKpis = await fetch("/kpi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((x) => x.json());
  renderKpiDashboard();
  return LAST.operationKpis;
}

function renderOpsKpis() {
  const zones = opKpi("zone_occupancy").value || [];
  const worst = zones.slice().sort((a, b) => Number(b.occupancy || 0) - Number(a.occupancy || 0))[0];
  const saturated = opKpi("saturated_zone_count");
  const safety = opKpi("safety_stock_below_count");
  const stocking = opKpi("stocking_completion_rate");
  const shortage = opKpi("expected_shortage_count");
  const dead = opKpi("dead_stock_count");
  const replenish = opKpi("replenishment_needed_count");
  $("#ops-kpi-row").innerHTML = [
    { ico: "▦", label: kpiLabel("zone_occupancy"), val: worst ? pct(worst.occupancy) : "—", delta: `<span class="kpi-delta flat">${worst ? worst.zone_id : "데이터 없음"}</span>` },
    { ico: "!", label: kpiLabel("saturated_zone_count"), val: saturated.value ?? "—", unit: "개", delta: `<span class="kpi-delta flat">점유율 90% 초과</span>` },
    { ico: "↓", label: kpiLabel("safety_stock_below_count"), val: safety.value ?? "—", unit: "개", delta: `<span class="kpi-delta flat">현재 재고 기준</span>` },
    { ico: "✓", label: kpiLabel("stocking_completion_rate"), val: pct(stocking.value), unit: "", delta: `<span class="kpi-delta flat">STOCKED / 입고 대상</span>` },
    { ico: "⚠", label: kpiLabel("expected_shortage_count"), val: shortage.value ?? "—", unit: "건", delta: `<span class="kpi-delta ${shortage.value ? "up" : "flat"}">가용재고 기준 할당</span>` },
    { ico: "🐌", label: kpiLabel("dead_stock_count"), val: dead.value ?? "—", unit: "개", delta: `<span class="kpi-delta ${dead.value ? "up" : "flat"}">저회전·임박·무동</span>` },
    { ico: "🔁", label: kpiLabel("replenishment_needed_count"), val: replenish.value ?? "—", unit: "개", delta: `<span class="kpi-delta ${replenish.value ? "up" : "flat"}">피킹면 보충 대상</span>` },
  ].map((c) => `
    <div class="kpi"><div class="kpi-top"><span class="kpi-ico">${c.ico}</span>${c.label}</div>
      <div class="kpi-val">${c.val}<span class="unit">${c.unit || ""}</span></div>${c.delta}</div>`).join("");

  if (!zones.length) {
    $("#zone-kpi-chart").innerHTML = `<div class="kpi-empty">Zone 점유율 데이터 없음</div>`;
  } else {
    svgBars($("#zone-kpi-chart"), zones.map((z) => ({
      label: z.zone_id,
      bars: [{ name: "점유율", value: Math.round(Number(z.occupancy || 0) * 100), color: Number(z.occupancy || 0) > 0.9 ? "#e1483b" : "#2f6bff" }],
    })));
  }

  $("#ops-kpi-table").innerHTML = `
    <table><thead><tr><th>KPI</th><th>값</th><th>설명</th></tr></thead><tbody>
      <tr><td>${kpiLabel("zone_occupancy")}</td><td>${zones.map((z) => `${z.zone_id} ${pct(z.occupancy)}`).join("<br>") || "—"}</td><td>${kpiDesc("zone_occupancy")}</td></tr>
      <tr><td>${kpiLabel("saturated_zone_count")}</td><td class="num">${saturated.value ?? "—"}</td><td>${kpiDesc("saturated_zone_count")}</td></tr>
      <tr><td>${kpiLabel("safety_stock_below_count")}</td><td class="num">${safety.value ?? "—"}</td><td>${kpiDesc("safety_stock_below_count")}</td></tr>
      <tr><td>${kpiLabel("stocking_completion_rate")}</td><td class="num">${pct(stocking.value)}</td><td>${kpiDesc("stocking_completion_rate")}</td></tr>
      <tr><td>${kpiLabel("expected_shortage_count")}</td><td class="num">${shortage.value ?? "—"}</td><td>${kpiDesc("expected_shortage_count")}</td></tr>
      <tr><td>${kpiLabel("dead_stock_count")}</td><td class="num">${dead.value ?? "—"}</td><td>${kpiDesc("dead_stock_count")}</td></tr>
      <tr><td>${kpiLabel("replenishment_needed_count")}</td><td class="num">${replenish.value ?? "—"}</td><td>${kpiDesc("replenishment_needed_count")}</td></tr>
    </tbody></table>`;
}

function renderSimKpiDashboard() {
  const r = LAST.result;
  if (!r || !r.kpis) {
    $("#sim-kpi-grid").innerHTML = `<div class="kpi-empty">시뮬레이션 실행 후 표시됩니다.</div>`;
    $("#sim-kpi-table").innerHTML = `<div class="kpi-empty">시뮬레이션 실행 후 표시됩니다.</div>`;
    return;
  }
  const sd = kpi(r, "shipping_delay_count");
  const pw = kpi(r, "picking_wait_minutes");
  const ut = kpi(r, "resource_utilization_team");
  const zoneRows = (r.kpis || []).filter((x) => x.kpi_name === "zone_max_occupancy");
  const worstZone = zoneRows.slice().sort((a, b) => Number(b.p90 || b.mean || 0) - Number(a.p90 || a.mean || 0))[0];
  const so = earliestStockout(r);
  $("#sim-kpi-grid").innerHTML = [
    metric(kpiLabel("shipping_delay_count"), fmtNum(sd.mean, 2), `평균 · 지연 발생확률 ${pct(sd.occurrence_prob)}`),
    metric(kpiLabel("picking_wait_minutes"), fmtNum(pw.p90, 1), "P90 기준"),
    metric(kpiLabel("resource_utilization_team"), pct(ut.mean), "평균 가동률"),
    metric(kpiLabel("zone_max_occupancy"), worstZone ? pct(worstZone.p90 ?? worstZone.mean) : "—", worstZone ? `${worstZone.zone_id} · P90 기준` : "Zone 데이터 없음"),
    metric(kpiLabel("expected_stockout_date"), so ? so.p50 : "소진 없음", so ? `${so.sku} · 발생확률 ${pct(so.occurrence_prob)}` : ""),
  ].join("");

  const rows = (r.kpis || []).map((x) => {
    const target = x.zone_id || x.sku || "";
    const vals = [];
    if (x.mean != null) vals.push(`mean ${x.unit === "percent" ? pct(x.mean) : fmtNum(x.mean, 2)}`);
    if (x.p50 != null) vals.push(`p50 ${typeof x.p50 === "number" && x.unit === "percent" ? pct(x.p50) : x.p50}`);
    if (x.p90 != null) vals.push(`p90 ${typeof x.p90 === "number" && x.unit === "percent" ? pct(x.p90) : x.p90}`);
    if (x.occurrence_prob != null) vals.push(`prob ${pct(x.occurrence_prob)}`);
    return `<tr><td>${kpiLabel(x.kpi_name)}<div class="metric-note">${kpiDesc(x.kpi_name)}</div></td><td>${target}</td><td>${vals.join("<br>") || "—"}</td><td>${KPI_META[x.kpi_name]?.unit || x.unit || ""}</td></tr>`;
  }).join("");
  $("#sim-kpi-table").innerHTML = `
    <table><thead><tr><th>KPI</th><th>대상</th><th>값</th><th>단위</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderKpiDashboard() {
  const sub = $("#kpi-board-sub");
  if (sub) {
    const v = LAST.result ? `${LAST.result.version_name} · ${LAST.result.run_type}` : "시뮬레이션 미실행";
    sub.textContent = `운영 KPI와 최신 시뮬레이션 KPI를 함께 확인합니다. 현재 시뮬레이션: ${v}`;
  }
  if (LAST.operationKpis) renderOpsKpis();
  renderSimKpiDashboard();
}

function setupDataBrowser() {
  const sel = $("#data-dataset");
  if (!sel) return;
  sel.innerHTML = DATASET_ORDER.map((id) => `<option value="${id}">${DATASET_META[id][0]}</option>`).join("");
  ["data-dataset", "data-status", "data-sku", "data-zone", "data-date"].forEach((id) => {
    const el = $("#" + id);
    if (el) el.addEventListener("change", loadRawData);
  });
  const qInput = $("#data-q");
  if (qInput) qInput.addEventListener("keydown", (e) => { if (e.key === "Enter") loadRawData(); });
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
  $("#data-table-meta").textContent = `${meta[1]} · ${data.total}건`;
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
  const dataset = $("#data-dataset")?.value || "snapshot";
  if (dataset === "snapshot") {
    const s = await loadDataSnapshot();
    renderRawTable({
      dataset: "snapshot",
      total: 1,
      rows: [{ ...s, counts: JSON.stringify(s.counts), latest_simulation: JSON.stringify(s.latest_simulation) }],
    });
    return;
  }
  const params = new URLSearchParams({ limit: "200", offset: "0" });
  const filters = [
    ["status", $("#data-status")?.value],
    ["sku", $("#data-sku")?.value],
    ["zone_id", $("#data-zone")?.value],
    ["date", $("#data-date")?.value],
    ["qtext", $("#data-q")?.value],
  ];
  filters.forEach(([k, v]) => { if (v) params.set(k, v); });
  const data = await fetch(`/data/${encodeURIComponent(dataset)}?${params.toString()}`).then((x) => x.json());
  renderRawTable(data);
}

async function refreshDataBrowser() {
  await loadDataSnapshot().catch(() => {});
  await loadRawData().catch(() => {});
}

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

function svgBars(el, groups) {
  const W = 560, H = 250, pl = 46, pr = 14, pt = 16, pb = 36, gap = 40;
  const allv = groups.flatMap((g) => g.bars.map((b) => b.value));
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
  svg += `</svg>`;
  const names = groups[0].bars.map((b) => `<span><i style="border-color:${b.color};border-top-width:8px"></i>${b.name}</span>`).join("");
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
  if (name === "approval") loadApproval().catch(() => {});
  if (name === "trace") loadTraces().catch(() => {});
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
const TW = { frames: [], occByDay: {}, zpos: {}, entrance: [1, -0.5], idx: 0, timer: null };
const TW_W = 560, TW_H = 300, TW_XMIN = -1, TW_XMAX = 3, TW_YMIN = -1.2, TW_YMAX = 2.8, ZH = 0.4;
const txc = (x) => ((x - TW_XMIN) / (TW_XMAX - TW_XMIN)) * TW_W;
const tyc = (y) => (1 - (y - TW_YMIN) / (TW_YMAX - TW_YMIN)) * TW_H;
const STATE_COLOR = { MOVING: "#1f77b4", WORKING: "#d62728", IDLE: "#999999" };
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
    s += `<rect x="${x0}" y="${y0}" width="${w}" height="${h}" rx="6" fill="${occColor(ratio)}" stroke="#c7d2e6"/>`;
    s += `<text x="${txc(p[0])}" y="${tyc(p[1]) - 4}" font-size="11" font-weight="600" fill="#33415a" text-anchor="middle">${z.replace("ZONE_", "")}</text>`;
    s += `<text x="${txc(p[0])}" y="${tyc(p[1]) + 11}" font-size="9" fill="#5d6573" text-anchor="middle">${Math.round(ratio * 100)}%</text>`;
  }
  // entrance
  s += `<text x="${txc(TW.entrance[0])}" y="${tyc(TW.entrance[1]) + 16}" font-size="10" fill="#333" text-anchor="middle">입구</text>`;
  s += `<polygon points="${txc(TW.entrance[0])},${tyc(TW.entrance[1]) - 2} ${txc(TW.entrance[0]) - 6},${tyc(TW.entrance[1]) + 8} ${txc(TW.entrance[0]) + 6},${tyc(TW.entrance[1]) + 8}" fill="#333"/>`;
  // teams
  (f.teams || []).forEach((m) => {
    const cx = txc(m.x), cy = tyc(m.y), col = STATE_COLOR[m.state] || "#999";
    s += `<circle cx="${cx}" cy="${cy}" r="12" fill="${col}" fill-opacity="0.16" stroke="${col}" stroke-width="1.6"/>`;
    s += `<text x="${cx}" y="${cy + 5}" font-size="14" text-anchor="middle">🚜</text>`;
    s += `<text x="${cx}" y="${cy - 14}" font-size="12" fill="${col}" text-anchor="middle">${dirArrow(m.heading)}</text>`;
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
  activateTab("chat");
  CHAT.sessionId = sid;
  const r = await fetch(`/sessions/${sid}`).then((x) => x.json()).catch(() => null);
  const msgs = (r && r.messages) || [];
  chatThread().innerHTML = "";
  const root = $("#chat-root"); if (root) root.classList.remove("is-empty");
  msgs.forEach((m) => {
    if (m.role === "user") appendBubble("user", escapeHtml(m.content));
    else {
      let sources = []; try { sources = JSON.parse(m.sources_json || "[]"); } catch (_) {}
      appendBubble("bot", escapeHtml(m.content).replace(/\n/g, "<br>") + renderSources(sources));
    }
  });
  if (!msgs.length) chatThread().innerHTML = CHAT_EMPTY_HTML;
  renderSessions();
}

/* ---------- Agent Chat ---------- */
const CHAT_SUGGESTS = ["오늘 뭐 해야 돼?", "SKU_A001 언제 소진돼?", "왜 Zone A를 추천했어?", "이번 주 창고 상황 예측해줘"];
const CHAT_EMPTY_HTML = `<div class="chat-empty" id="chat-empty">
  <div class="ce-title">무엇을 도와드릴까요?</div>
  <div class="ce-sub">오늘 할 일, 적치·피킹 추천, 재고 소진 예측, 시뮬레이션을 자연어로 물어보세요.</div>
</div>`;
const escapeHtml = (s) => (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const chatScrollBottom = () => { const el = $("#chat-scroll"); el.scrollTop = el.scrollHeight; };
const chatThread = () => $("#thread-inner") || $("#chat-scroll");

function appendBubble(role, inner) {
  const empty = $("#chat-empty"); if (empty) empty.remove();
  const root = $("#chat-root"); if (root) root.classList.remove("is-empty");
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  const who = role === "user" ? "user" : "ai";
  wrap.innerHTML = `<div class="role-tag">${who} :</div><div class="bubble">${inner}</div>`;
  chatThread().appendChild(wrap); chatScrollBottom();
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

async function loadTraces() {
  try { TRACE.items = (await fetch("/traces?limit=40").then((x) => x.json())).traces || []; }
  catch (_) { TRACE.items = []; }
  renderTraceList();
  if (TRACE.items.length && !TRACE.runId) openTrace(TRACE.items[0].run_id);
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
    <div class="td-sub">run ${safeText(t.run_id)} · ${safeText((t.created_at || "").replace("T", " ").slice(0, 16))}</div>
    <div class="flow">${flow}</div>`;
}

async function sendChat(text) {
  text = (text || "").trim(); if (!text) return;
  appendBubble("user", escapeHtml(text));
  const ta = $("#chat-text"); ta.value = ""; autoGrow(ta);
  const send = $("#chat-send"); send.disabled = true;
  const typing = appendBubble("bot", `<span class="typing"><i></i><i></i><i></i></span>`);
  try {
    const r = await fetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: text, user_id: "operator01", session_id: CHAT.sessionId }) }).then((x) => x.json());
    typing.remove();
    if (r.session_id) CHAT.sessionId = r.session_id;
    if (r.error) {
      appendBubble("bot", `<span class="err">오류: ${escapeHtml(r.error)}</span>`);
    } else {
      const body = escapeHtml(r.response || "(응답이 비어 있습니다)").replace(/\n/g, "<br>")
        + renderSources(r.rag_sources)
        + (r.approval_required ? renderApproval(r.draft_actions, r.tool_results) : "");
      const node = appendBubble("bot", body);
      if (r.approval_required) wireApproval(node, r.tool_results);
    }
  } catch (e) {
    typing.remove();
    appendBubble("bot", `<span class="err">요청 실패: ${escapeHtml(String(e))}</span>`);
  } finally {
    send.disabled = false; $("#chat-text").focus(); setUpdated();
    loadSessions().catch(() => {});   // 사이드바 이력 갱신(새 세션·제목·시각)
  }
}
function autoGrow(ta) { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 140) + "px"; }
function bindSuggests() {
  const sug = $("#chat-suggest"); if (!sug) return;
  sug.innerHTML = CHAT_SUGGESTS.map((s) => `<button class="sug">${escapeHtml(s)}</button>`).join("");
  sug.querySelectorAll(".sug").forEach((b) => b.addEventListener("click", () => sendChat(b.textContent)));
}
function resetChat() {
  CHAT.sessionId = null;                 // 새 대화 = 새 세션
  const root = $("#chat-root"); if (root) root.classList.add("is-empty");
  chatThread().innerHTML = CHAT_EMPTY_HTML;
  bindSuggests();
  const ta = $("#chat-text");
  if (ta) { ta.value = ""; autoGrow(ta); ta.focus(); }
  renderSessions();
}
function setupChat() {
  const ta = $("#chat-text"), send = $("#chat-send"); if (!ta) return;
  send.addEventListener("click", () => sendChat(ta.value));
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(ta.value); } });
  ta.addEventListener("input", () => autoGrow(ta));
  const plus = $("#cp-plus"); if (plus) plus.addEventListener("click", resetChat);
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

async function init() {
  setupTabs(); setupChat(); setupDataBrowser(); setupRealtime();
  loadSessions().catch(() => {});
  const ss = document.querySelector(".side-search");
  if (ss) ss.addEventListener("input", (e) => { CHAT.filter = e.target.value; renderSessions(); });
  const nc = $("#new-chat"); if (nc) nc.addEventListener("click", () => { activateTab("chat"); resetChat(); });
  $("#run-sim").addEventListener("click", runSim);
  $("#refresh").addEventListener("click", refreshDashboard);
  $("#refresh-kpi").addEventListener("click", () => loadOperationKpis().catch(() => {}));
  $("#refresh-data").addEventListener("click", refreshDataBrowser);
  const ra = $("#refresh-approval"); if (ra) ra.addEventListener("click", () => loadApproval().catch(() => {}));
  const rt = $("#refresh-trace"); if (rt) rt.addEventListener("click", () => { TRACE.runId = null; loadTraces().catch(() => {}); });
  $("#commit-baseline").addEventListener("click", commitBaseline);
  $("#tw-play").addEventListener("click", twTogglePlay);
  $("#tw-range").addEventListener("input", (e) => { if (TW.timer) twTogglePlay(); twSetFrame(Number(e.target.value)); });
  await loadResources();
  await loadOperationKpis().catch(() => {});
  await refreshDataBrowser().catch(() => {});
  await runSim();
}
init();
