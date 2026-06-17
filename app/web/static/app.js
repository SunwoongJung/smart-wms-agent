// Smart WMS Agent — SPA (P1~P5)
const $ = (s) => document.querySelector(s);
let META = { base_date: null };
let LAST = { result: null, forecast: null, comparison: null, insightTab: "inv" };

const kpi = (res, name) => (res.kpis || []).find((k) => k.kpi_name === name) || {};
const fmtNum = (v, d = 1) => (v == null ? "—" : Number(v).toFixed(d));

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
    { ico: "🕐", label: "출고지연 (mean)", val: fmtNum(sd.mean, 2), unit: "분", delta: deltaChip(cmpRow(comparison, "shipping_delay_count"), "mean") },
    { ico: "⏳", label: "피킹처리 P90(분)", val: fmtNum(pw.p90, 1), unit: "분", delta: deltaChip(cmpRow(comparison, "picking_wait_minutes"), "p90") },
    { ico: "👥", label: "팀 가동률", val: ut.mean != null ? fmtNum(ut.mean * 100, 1) : "—", unit: "%", delta: deltaChip(cmpRow(comparison, "resource_utilization_team"), "mean", false) },
    { ico: "📅", label: "예상소진일", val: soDays != null ? "D+" + soDays : "—", unit: "", delta: `<span class="kpi-delta flat">${so ? so.p50 : "소진 없음"}</span>` },
    { ico: "💰", label: "총 재고 비용", val: invValue != null ? "₩" + (invValue / 1e6).toFixed(1) + "M" : "—", unit: "", delta: `<span class="kpi-delta flat">예시 단가 기준</span>` },
  ];
  $("#kpi-row").innerHTML = cards.map((c) => `
    <div class="kpi"><div class="kpi-top"><span class="kpi-ico">${c.ico}</span>${c.label}</div>
      <div class="kpi-val">${c.val}<span class="unit">${c.unit}</span></div>${c.delta}</div>`).join("");
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

async function runSim() {
  const btn = $("#run-sim"); btn.disabled = true; btn.textContent = "실행 중...";
  const body = { horizon_days: Number($("#horizon").value), replications: Number($("#reps").value) };
  const wd = Number($("#worker-delta").value), fd = Number($("#forklift-delta").value);
  if (wd !== 0 || fd !== 0) body.scenario = { worker_delta: wd, forklift_delta: fd };
  try {
    const resp = await fetch("/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((x) => x.json());
    const result = resp.scenario || resp;
    LAST.result = result; LAST.comparison = resp.comparison || null;
    renderKpis(result, LAST.comparison, META.inventory_value);
    $("#version-badge").textContent = `저장된 버전: ${result.version_name} (${result.run_type})`;
    window.__lastParams = result.params;
    setUpdated();
    const so = earliestStockout(result);
    LAST.forecast = await fetchForecast(so ? so.sku : "SKU_A001");
    renderInsight();
    renderTwin(result.movement, result.zone_occupancy_timeseries);
    renderTimeline(result.bottleneck_events);
    if (result.run_type === "BASELINE") loadCopilot(result.params).catch(() => {});
  } catch (e) {
    $("#version-badge").textContent = "실행 오류: " + e;
  } finally {
    btn.disabled = false; btn.textContent = "▶ 시뮬레이션 실행";
  }
}

async function commitBaseline() {
  const p = window.__lastParams; if (!p) return;
  await fetch("/resources/update?worker=" + p.worker_count + "&forklift=" + p.forklift_count, { method: "POST" }).catch(() => {});
  await loadResources();
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    $("#panel-" + t.dataset.tab).classList.remove("hidden");
  }));
  document.querySelectorAll("#insight-tabs .seg-btn").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#insight-tabs .seg-btn").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); LAST.insightTab = b.dataset.it; renderInsight();
  }));
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

function renderChatStub() {
  const items = [["재고 소진 예측", "오늘 10:12"], ["작업자 증원 시나리오", "오늘 09:48"], ["Zone B 병목 분석", "어제 16:32"],
    ["출고지연 원인", "어제 14:05"], ["피킹 효율 개선 방안", "어제 11:20"], ["시뮬레이션 비교 분석", "05-20 17:22"]];
  $("#chat-list").innerHTML = items.map(([t, m]) => `<div class="chat-item"><div class="ci-title">💬 ${t}</div><div class="ci-meta">${m}</div></div>`).join("");
}

async function init() {
  setupTabs(); renderChatStub();
  $("#run-sim").addEventListener("click", runSim);
  $("#refresh").addEventListener("click", runSim);
  $("#commit-baseline").addEventListener("click", commitBaseline);
  $("#tw-play").addEventListener("click", twTogglePlay);
  $("#tw-range").addEventListener("input", (e) => { if (TW.timer) twTogglePlay(); twSetFrame(Number(e.target.value)); });
  await loadResources();
  await runSim();
}
init();
