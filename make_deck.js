const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Smart WMS Agent 기획 요약";

// ---- palette (Charcoal + Teal, very simple) ----
const DARK = "263238";   // title/closing bg
const TEXT = "2B3A42";   // body text
const MUTED = "6B7A85";  // secondary text
const ACCENT = "028090"; // teal accent
const TINT = "EDF5F6";   // light teal tint for cards
const LIGHT = "F4F6F7";  // neutral card
const WHITE = "FFFFFF";
const F = "Malgun Gothic";

const shadow = () => ({ type: "outer", color: "000000", blur: 5, offset: 2, angle: 45, opacity: 0.10 });

function slideTitle(slide, label, title) {
  slide.addText(label, { x: 0.5, y: 0.32, w: 9, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: ACCENT, charSpacing: 2, margin: 0 });
  slide.addText(title, { x: 0.5, y: 0.58, w: 9, h: 0.6, fontFace: F, fontSize: 27, bold: true, color: TEXT, margin: 0 });
}

// =======================================================
// 1. Title (dark)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: DARK };

  s.addText("WAREHOUSE OPERATIONS COPILOT · POC", { x: 0.7, y: 1.35, w: 8.6, h: 0.35, fontFace: F, fontSize: 13, bold: true, color: "7FD1CD", charSpacing: 3, margin: 0 });
  s.addText("Smart WMS Agent", { x: 0.7, y: 1.75, w: 8.6, h: 1.0, fontFace: F, fontSize: 48, bold: true, color: WHITE, margin: 0 });
  s.addText("자연어로 묻고 · 데이터로 계산하고 · 승인으로 실행한다", { x: 0.7, y: 2.85, w: 8.6, h: 0.45, fontFace: F, fontSize: 17, color: "CFD8DC", margin: 0 });

  // simple chat bubble visual
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.7, y: 3.65, w: 2.6, h: 0.55, rectRadius: 0.12, fill: { color: ACCENT } });
  s.addText("“오늘 뭐 해야 돼?”", { x: 0.7, y: 3.65, w: 2.6, h: 0.55, fontFace: F, fontSize: 14, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  s.addText("→  피킹 · 적치 · 재고 리스크 · 출고확정까지 한 번에 답하는 Agentic AI", { x: 3.5, y: 3.65, w: 5.9, h: 0.55, fontFace: F, fontSize: 13, color: "B0BEC5", valign: "middle", margin: 0 });

  s.addText("창고 운영자를 위한 Agentic AI 서비스 기획  ·  2026.06", { x: 0.7, y: 4.95, w: 8.6, h: 0.3, fontFace: F, fontSize: 11, color: "78909C", margin: 0 });
}

// =======================================================
// 2. 어떤 서비스인가
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "OVERVIEW", "어떤 서비스인가");

  // left: chat mock
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.45, w: 4.1, h: 3.6, rectRadius: 0.08, fill: { color: LIGHT } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 1.9, y: 1.7, w: 2.4, h: 0.45, rectRadius: 0.1, fill: { color: ACCENT } });
  s.addText("오늘 뭐 해야 돼?", { x: 1.9, y: 1.7, w: 2.4, h: 0.45, fontFace: F, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.75, y: 2.35, w: 3.6, h: 2.45, rectRadius: 0.1, fill: { color: WHITE }, shadow: shadow() });
  s.addText([
    { text: "오늘 우선 처리할 업무는 3건입니다.", options: { bold: true, color: TEXT, breakLine: true } },
    { text: "", options: { breakLine: true, fontSize: 4 } },
    { text: "1. ORD001 피킹 지시 — 10:30 시작 권장", options: { color: MUTED, breakLine: true } },
    { text: "2. SKU_A001 재고 부족 예상 — HIGH", options: { color: MUTED, breakLine: true } },
    { text: "3. INB003 적치 필요 — Zone A 추천", options: { color: MUTED, breakLine: true } },
    { text: "", options: { breakLine: true, fontSize: 4 } },
    { text: "근거: 출고예정·재고·정책 문서 기반", options: { color: ACCENT, italic: true } },
  ], { x: 0.95, y: 2.5, w: 3.25, h: 2.2, fontFace: F, fontSize: 11, valign: "top", paraSpaceAfter: 4, margin: 0 });

  // right: 5 things agent aggregates
  s.addText("Agent가 한 번에 종합하는 5가지", { x: 5.05, y: 1.45, w: 4.4, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: TEXT, margin: 0 });
  const items = [
    ["피킹지시가 필요한 출고예정 건", "출고시간 기준 우선순위·시작시간 포함"],
    ["적치가 필요한 입고 건", "입고예정·적치대기 상태 기준"],
    ["재고 부족 예상 품목", "과거 출고이력 기반 소진일 예측"],
    ["출고확정대기 건", "피킹·패킹 완료 후 확정 대상"],
    ["SOP 기준 예외 상황 대응", "재고부족·CAPA부족 등 표준 대응안"],
  ];
  items.forEach((it, i) => {
    const y = 1.95 + i * 0.64;
    s.addShape(pres.shapes.OVAL, { x: 5.05, y: y + 0.04, w: 0.34, h: 0.34, fill: { color: ACCENT } });
    s.addText(String(i + 1), { x: 5.05, y: y + 0.04, w: 0.34, h: 0.34, fontFace: F, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText([
      { text: it[0], options: { bold: true, color: TEXT, fontSize: 13, breakLine: true } },
      { text: it[1], options: { color: MUTED, fontSize: 10.5 } },
    ], { x: 5.55, y: y - 0.05, w: 4.0, h: 0.62, fontFace: F, valign: "top", margin: 0 });
  });
}

// =======================================================
// 3. 핵심 기능
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "KEY FEATURES", "핵심 기능 6가지");

  const feats = [
    ["오늘 할 일 요약", "미지시 출고, 적치대기, 재고 위험, 출고확정대기를 한 번에 종합"],
    ["적치 추천", "동일 SKU · CAPA · 거리 · 고회전 기준으로 최적 Location 추천"],
    ["피킹 우선순위 추천", "출고시간 - 작업시간 - 버퍼로 피킹 시작시간과 순서 산출"],
    ["재고 리스크 예측", "선형회귀로 예상소진일 계산, HIGH/MEDIUM/LOW 등급 판정"],
    ["SOP 대응 추천", "재고부족, CAPA부족 등 예외 상황의 표준 대응 절차 제시"],
    ["근거 설명", "정책 문서 · 산식 · Tool 결과를 인용해 추천 이유를 설명"],
  ];
  const cw = 2.93, ch = 1.62, gx = 0.21, gy = 0.25, x0 = 0.5, y0 = 1.5;
  feats.forEach((f, i) => {
    const x = x0 + (i % 3) * (cw + gx);
    const y = y0 + Math.floor(i / 3) * (ch + gy);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.07, fill: { color: i === 0 ? TINT : LIGHT } });
    s.addText([
      { text: f[0], options: { bold: true, fontSize: 14.5, color: TEXT, breakLine: true } },
      { text: "", options: { breakLine: true, fontSize: 5 } },
      { text: f[1], options: { fontSize: 11, color: MUTED } },
    ], { x: x + 0.22, y: y + 0.16, w: cw - 0.44, h: ch - 0.32, fontFace: F, valign: "top", margin: 0 });
  });
}

// =======================================================
// 4. 동작 구조
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "HOW IT WORKS", "동작 구조 — LangGraph Workflow");

  const steps = [
    ["Router", "질문 의도 분류"],
    ["Planner", "Tool 실행 계획"],
    ["Tool 실행", "조회·계산·예측"],
    ["Verifier", "결과 정합성 검증"],
    ["RAG", "정책·산식 검색"],
    ["응답·승인", "설명 + 승인 요청"],
  ];
  const bw = 1.32, bh = 1.05, gap = 0.21, x0 = 0.5, y0 = 1.55;
  steps.forEach((st, i) => {
    const x = x0 + i * (bw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y0, w: bw, h: bh, rectRadius: 0.08, fill: { color: i === 5 ? ACCENT : LIGHT } });
    s.addText([
      { text: st[0], options: { bold: true, fontSize: 13, color: i === 5 ? WHITE : TEXT, breakLine: true } },
      { text: st[1], options: { fontSize: 9.5, color: i === 5 ? "D6EFEE" : MUTED } },
    ], { x: x + 0.08, y: y0 + 0.12, w: bw - 0.16, h: bh - 0.24, fontFace: F, align: "center", valign: "middle", margin: 0 });
    if (i < 5) {
      s.addText("→", { x: x + bw - 0.03, y: y0, w: gap + 0.06, h: bh, fontFace: F, fontSize: 14, bold: true, color: MUTED, align: "center", valign: "middle", margin: 0 });
    }
  });

  // principle callout
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.0, w: 9.0, h: 1.0, rectRadius: 0.08, fill: { color: TINT } });
  s.addText([
    { text: "설계 원칙 — LLM은 계산하지 않는다", options: { bold: true, fontSize: 14, color: ACCENT, breakLine: true } },
    { text: "모든 수치는 Tool이 계산하고, LLM은 결과를 해석·설명한다. 상태 변경은 반드시 사용자 승인 후에만 수행한다.", options: { fontSize: 11.5, color: TEXT } },
  ], { x: 0.78, y: 3.16, w: 8.45, h: 0.7, fontFace: F, valign: "top", paraSpaceAfter: 4, margin: 0 });

  s.addText("적용 패턴   Router · Planning · ReAct · PEV · Adaptive RAG · Dry-Run · Human-in-the-loop · Simulator", { x: 0.5, y: 4.35, w: 9.0, h: 0.35, fontFace: F, fontSize: 11, color: MUTED, margin: 0 });
}

// =======================================================
// 5. 승인 기반 실행
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "HUMAN-IN-THE-LOOP", "승인 없이는 아무것도 바꾸지 않는다");

  const steps = [
    ["추천", "Tool이 적치·피킹·출고확정 대상을 계산"],
    ["Draft 생성", "실행 전 초안을 만들어 보관"],
    ["Dry Run", "변경될 상태·재고를 미리보기로 제시"],
    ["사용자 승인", "운영자가 확인 후 승인 또는 거부"],
    ["실행", "승인된 Draft만 실제 DB 상태 변경"],
  ];
  const cw = 1.66, ch = 1.7, gap = 0.17, x0 = 0.5, y0 = 1.6;
  steps.forEach((st, i) => {
    const x = x0 + i * (cw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y0, w: cw, h: ch, rectRadius: 0.08, fill: { color: i === 3 ? ACCENT : LIGHT } });
    s.addText(String(i + 1), { x: x + 0.18, y: y0 + 0.14, w: 0.5, h: 0.4, fontFace: F, fontSize: 20, bold: true, color: i === 3 ? WHITE : ACCENT, margin: 0 });
    s.addText([
      { text: st[0], options: { bold: true, fontSize: 13.5, color: i === 3 ? WHITE : TEXT, breakLine: true } },
      { text: st[1], options: { fontSize: 10, color: i === 3 ? "D6EFEE" : MUTED } },
    ], { x: x + 0.16, y: y0 + 0.6, w: cw - 0.32, h: ch - 0.75, fontFace: F, valign: "top", paraSpaceAfter: 3, margin: 0 });
  });

  s.addText([
    { text: "대상 작업  ", options: { bold: true, color: TEXT } },
    { text: "적치지시 생성 · 피킹지시 발행 · 출고확정     ", options: { color: MUTED } },
    { text: "원칙  ", options: { bold: true, color: TEXT } },
    { text: "승인 없는 상태 변경 0건", options: { bold: true, color: ACCENT } },
  ], { x: 0.5, y: 3.75, w: 9.0, h: 0.4, fontFace: F, fontSize: 13, margin: 0 });

  s.addText("거부된 Draft는 REJECTED로 보관되어 언제든 추적 가능 — 모든 추천은 Tool Trace로 재현된다.", { x: 0.5, y: 4.2, w: 9.0, h: 0.35, fontFace: F, fontSize: 11, color: MUTED, margin: 0 });
}

// =======================================================
// 6. Agent 페르소나 & 대화 메모리
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AGENT IDENTITY & MEMORY", "Agent 페르소나와 대화 관리");

  // left: persona
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.45, w: 4.4, h: 3.55, rectRadius: 0.08, fill: { color: LIGHT } });
  s.addText("페르소나 · 톤앤매너", { x: 0.78, y: 1.63, w: 3.9, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: ACCENT, margin: 0 });
  s.addText([
    { text: "간결한 존댓말, 결론 → 수치 → 근거 → 조치 순", options: { bullet: true, breakLine: true } },
    { text: "수치는 Tool 결과만 인용 — 추측 표현 금지", options: { bullet: true, breakLine: true } },
    { text: "HIGH 위험·출고 임박 건은 응답 첫머리에 배치", options: { bullet: true, breakLine: true } },
    { text: "상태변경은 항상 “승인이 필요합니다” 명시", options: { bullet: true, breakLine: true } },
    { text: "금지: 수치 임의 생성 · 문서에 없는 정책 설명 · 업무 범위 밖 답변", options: { bullet: true } },
  ], { x: 0.78, y: 2.08, w: 3.9, h: 2.75, fontFace: F, fontSize: 12, color: TEXT, paraSpaceAfter: 9, valign: "top", margin: 0 });

  // right: memory
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.1, y: 1.45, w: 4.4, h: 3.55, rectRadius: 0.08, fill: { color: TINT } });
  s.addText("대화 메모리 전략", { x: 5.38, y: 1.63, w: 3.9, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: ACCENT, margin: 0 });
  s.addText([
    { text: "최근 10턴 윈도우 버퍼 + 세션 슬롯", options: { bullet: true, breakLine: true } },
    { text: "“승인해줘” → 직전 Draft, “그 제품은?” → 최근 SKU 참조", options: { bullet: true, breakLine: true } },
    { text: "30분 무활동 시 세션 종료", options: { bullet: true, breakLine: true } },
    { text: "승인 대기 Draft는 DB 영속 — 세션 만료 후에도 승인 가능", options: { bullet: true, breakLine: true } },
    { text: "장기 메모리는 POC 범위 제외 (모든 기록은 DB)", options: { bullet: true } },
  ], { x: 5.38, y: 2.08, w: 3.9, h: 2.75, fontFace: F, fontSize: 12, color: TEXT, paraSpaceAfter: 9, valign: "top", margin: 0 });

  s.addText("LLM·임베딩 모델은 사내 제공 예정(미정) — 교체 가능한 model-agnostic 구조로 설계", { x: 0.5, y: 5.12, w: 9.0, h: 0.3, fontFace: F, fontSize: 11, italic: true, color: MUTED, margin: 0 });
}

// =======================================================
// 7. 기술 구성 & 데이터
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "TECH & DATA", "기술 구성과 지식 기반");

  // left: tech stack
  s.addText("기술 스택", { x: 0.5, y: 1.42, w: 4.4, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: TEXT, margin: 0 });
  const tech = [
    ["LLM · 임베딩", "사내 제공 모델 (미정) · 교체 가능 설계"],
    ["LangGraph", "Agent 워크플로우 · 조건 분기 · 상태 관리"],
    ["Tool Engine", "조회·추천·Forecast·Draft 등 표준 Tool 23종"],
    ["RAG (FAISS)", "정책 6종 검색 · 필요할 때만 수행"],
    ["SQLite", "POC용 WMS 데이터 저장소 (13개 테이블)"],
    ["Linear Regression", "소진일 예측 · 이동평균 Fallback"],
    ["FastAPI · Streamlit", "API와 운영자용 대시보드 UI"],
  ];
  tech.forEach((t, i) => {
    const y = 1.82 + i * 0.47;
    s.addShape(pres.shapes.OVAL, { x: 0.5, y: y + 0.08, w: 0.12, h: 0.12, fill: { color: ACCENT } });
    s.addText([
      { text: t[0] + "  ", options: { bold: true, color: TEXT, fontSize: 12.5 } },
      { text: t[1], options: { color: MUTED, fontSize: 10.5 } },
    ], { x: 0.78, y: y - 0.08, w: 4.3, h: 0.5, fontFace: F, valign: "top", margin: 0 });
  });

  // right: RAG knowledge
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.35, y: 1.42, w: 4.15, h: 3.55, rectRadius: 0.08, fill: { color: TINT } });
  s.addText("RAG 지식 문서 6종", { x: 5.62, y: 1.6, w: 3.6, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: ACCENT, margin: 0 });
  const docs = [
    ["적치 정책", "동일 SKU 우선 · CAPA · 거리 · 고회전"],
    ["피킹 정책", "시작시간 산정 · 우선순위 기준"],
    ["재고 리스크 정책", "소진일 · 위험등급 · Fallback"],
    ["운영 SOP", "재고부족 등 예외 상황 대응 8종"],
    ["산식 문서", "적치 점수 · 피킹 점수 · Forecast 산식"],
    ["용어 사전", "WMS 용어 정의"],
  ];
  docs.forEach((d, i) => {
    const y = 2.05 + i * 0.47;
    s.addText([
      { text: d[0] + "   ", options: { bold: true, color: TEXT, fontSize: 11.5 } },
      { text: d[1], options: { color: MUTED, fontSize: 10 } },
    ], { x: 5.62, y, w: 3.7, h: 0.44, fontFace: F, valign: "top", margin: 0 });
  });

  s.addText("의사결정은 Tool이, 그 근거 설명은 RAG가 담당한다.", { x: 0.5, y: 5.18, w: 9.0, h: 0.3, fontFace: F, fontSize: 11, italic: true, color: MUTED, margin: 0 });
}

// =======================================================
// 7. 성공 기준
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "SUCCESS CRITERIA", "무엇으로 성공을 판단하는가");

  const stats = [
    ["95%", "Intent 분류 정확도", "질문 100건 기준 의도 분류"],
    ["85%+", "RAG Recall@3", "근거 문서 검색 정확도"],
    ["90%+", "Groundedness", "문서에 근거한 답변 비율"],
    ["0건", "무승인 상태 변경", "승인 없는 지시·확정 차단"],
  ];
  const cw = 2.16, ch = 2.0, gap = 0.12, x0 = 0.5, y0 = 1.7;
  stats.forEach((st, i) => {
    const x = x0 + i * (cw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y0, w: cw, h: ch, rectRadius: 0.08, fill: { color: LIGHT } });
    s.addText(st[0], { x, y: y0 + 0.22, w: cw, h: 0.7, fontFace: F, fontSize: 38, bold: true, color: ACCENT, align: "center", margin: 0 });
    s.addText([
      { text: st[1], options: { bold: true, fontSize: 12.5, color: TEXT, breakLine: true } },
      { text: st[2], options: { fontSize: 10, color: MUTED } },
    ], { x: x + 0.12, y: y0 + 1.05, w: cw - 0.24, h: 0.85, fontFace: F, align: "center", valign: "top", paraSpaceAfter: 3, margin: 0 });
  });

  s.addText("그 외 — 적치 규칙 위반 추천 0건 · 피킹 시작시간 계산 정확도 100% · Forecast 위험등급 분류 정확도 평가", { x: 0.5, y: 4.1, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, align: "center", margin: 0 });
}

// =======================================================
// 8. 로드맵 (dark closing)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: DARK };

  s.addText("ROADMAP", { x: 0.5, y: 0.42, w: 9, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", charSpacing: 2, margin: 0 });
  s.addText("구현 로드맵 — 10 Phase, 4단계", { x: 0.5, y: 0.68, w: 9, h: 0.6, fontFace: F, fontSize: 27, bold: true, color: WHITE, margin: 0 });

  const phases = [
    ["STEP 1", "기반 구축", "프로젝트 셋업\nDB 스키마 · Seed Data", "Phase 1–2"],
    ["STEP 2", "계산 엔진", "Tool 23종 구현\nForecast · What-if", "Phase 3–4"],
    ["STEP 3", "Agent 조립", "RAG 인덱싱\nLangGraph 워크플로우", "Phase 5–6"],
    ["STEP 4", "서비스화", "API · Streamlit UI\n평가 · 데모", "Phase 7–9"],
  ];
  const cw = 2.16, ch = 2.45, gap = 0.12, x0 = 0.5, y0 = 1.65;
  phases.forEach((p, i) => {
    const x = x0 + i * (cw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: y0, w: cw, h: ch, rectRadius: 0.08, fill: { color: "324148" } });
    s.addText(p[0], { x: x + 0.2, y: y0 + 0.2, w: cw - 0.4, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", charSpacing: 1, margin: 0 });
    s.addText(p[1], { x: x + 0.2, y: y0 + 0.5, w: cw - 0.4, h: 0.4, fontFace: F, fontSize: 17, bold: true, color: WHITE, margin: 0 });
    s.addText(p[2], { x: x + 0.2, y: y0 + 0.98, w: cw - 0.4, h: 0.95, fontFace: F, fontSize: 11, color: "B0BEC5", valign: "top", margin: 0 });
    s.addText(p[3], { x: x + 0.2, y: y0 + ch - 0.42, w: cw - 0.4, h: 0.3, fontFace: F, fontSize: 10, color: "78909C", margin: 0 });
  });

  s.addText("이후 확장 — Hybrid Search · Reranker · PostgreSQL 전환 · 실제 WMS API 연동", { x: 0.5, y: 4.45, w: 9.0, h: 0.35, fontFace: F, fontSize: 12, color: "90A4AE", align: "center", margin: 0 });
  s.addText("Smart WMS Agent", { x: 0.5, y: 5.05, w: 9.0, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", align: "center", margin: 0 });
}

// #######################################################
// ##  진행 업데이트 누적 섹션 (이 파일에 날짜 단위로 append)
// ##  디자인: 위 기획요약과 동일 토큰(Charcoal+Teal, 16:9, Malgun Gothic)
// ##  이후 새 진행분은 "날짜 구분 슬라이드 + 내용"을 아래에 이어 붙인다.
// #######################################################
const MONO = "Courier New";

function pcard(s, x, y, w, h, head, body, tint) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07, fill: { color: tint ? TINT : LIGHT }, shadow: shadow() });
  s.addText(head, { x: x + 0.2, y: y + 0.14, w: w - 0.4, h: 0.32, fontFace: F, fontSize: 12.5, bold: true, color: TEXT, margin: 0 });
  s.addText(body, { x: x + 0.2, y: y + 0.52, w: w - 0.4, h: h - 0.66, fontFace: F, fontSize: 10.2, color: MUTED, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
}

function codeCard(s, x, y, w, h, head, code) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: DARK } });
  if (head) s.addText(head, { x: x + 0.16, y: y + 0.1, w: w - 0.32, h: 0.26, fontFace: F, fontSize: 9.5, bold: true, color: "7FD1CD", margin: 0 });
  s.addText(code, { x: x + 0.16, y: y + (head ? 0.4 : 0.12), w: w - 0.32, h: h - (head ? 0.5 : 0.24), fontFace: MONO, fontSize: 8.3, color: "E6EDEF", valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
}

// =======================================================
// [A] 날짜 구분 (dark divider)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: DARK };
  s.addText("PROGRESS UPDATE · 2026.06.17", { x: 0.7, y: 1.2, w: 8.6, h: 0.35, fontFace: F, fontSize: 13, bold: true, color: "7FD1CD", charSpacing: 3, margin: 0 });
  s.addText("구현 진행 업데이트", { x: 0.7, y: 1.62, w: 8.6, h: 0.9, fontFace: F, fontSize: 44, bold: true, color: WHITE, margin: 0 });
  s.addText("기획요약 + 진행현황을 병합했습니다. 이후 진행사항은 이 파일에 날짜 단위로 누적합니다.",
    { x: 0.7, y: 2.66, w: 8.6, h: 0.45, fontFace: F, fontSize: 14, color: "CFD8DC", margin: 0 });
  const batch = [
    "POC 구현 완료 현황",
    "AI 디자인 패턴 — 정의와 코드 구현",
    "RAG 심화 — Adaptive/Agentic · ALR+Sufficient · Vector DB 구성",
    "향후 — 실시간 수요 발생 시뮬레이션 (Toast · 긴급 처리)",
  ];
  batch.forEach((t, i) => {
    const y = 3.42 + i * 0.46;
    s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.02, w: 0.32, h: 0.32, fill: { color: ACCENT } });
    s.addText(String(i + 1), { x: 0.7, y: y + 0.02, w: 0.32, h: 0.32, fontFace: F, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: 1.18, y: y - 0.03, w: 8.0, h: 0.42, fontFace: F, fontSize: 13, color: "ECEFF1", valign: "middle", margin: 0 });
  });
  s.addText("Smart WMS Agent", { x: 0.7, y: 5.28, w: 8.6, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", margin: 0 });
}

// =======================================================
// [B] 현재 구현된 내용 — POC
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "IMPLEMENTATION STATUS", "현재 구현된 내용 — POC");
  s.addText("설계 문서(docs 12종)대로 app/ 전 계층 구현 — 자연어 질의 → Tool 계산 → 근거 설명 → 승인 실행이 end-to-end로 동작",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });
  const mods = [
    ["DB · Seed", "SQLite 15테이블 스키마 + 일관성 시드\ndb/schema.sql · seed/generate.py · wms.db"],
    ["Tools", "조회 · 적치(0~1 정규화 점수) · 피킹(우선순위·시작시간) · Draft/Dry-Run\ntools/"],
    ["Forecast · DES", "LR·MA 소진예측·위험등급 · SimPy 3인1조 DES · Monte Carlo P50/P90 · What-if\nsim/"],
    ["RAG", "ALR 메타 청킹 · FAISS · PRISM 리랭크 · 충분성 게이트\nrag/"],
    ["Agent", "LangGraph 9노드 조건분기 그래프 + AgentState\nagent/graph.py · nodes.py"],
    ["API · UI", "FastAPI · 무프레임워크 웹 SPA(시뮬레이션·디지털트윈·타임라인)\napi/ · web/"],
  ];
  const cw = 2.93, ch = 1.5, gx = 0.21, gy = 0.2, x0 = 0.5, y0 = 1.6;
  mods.forEach((m, i) => {
    const x = x0 + (i % 3) * (cw + gx);
    const y = y0 + Math.floor(i / 3) * (ch + gy);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.07, fill: { color: i === 2 ? TINT : LIGHT } });
    s.addText([
      { text: m[0], options: { bold: true, fontSize: 13.5, color: i === 2 ? ACCENT : TEXT, breakLine: true } },
      { text: "", options: { breakLine: true, fontSize: 4 } },
      { text: m[1], options: { fontSize: 9.8, color: MUTED } },
    ], { x: x + 0.2, y: y + 0.15, w: cw - 0.4, h: ch - 0.3, fontFace: F, valign: "top", margin: 0 });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.95, w: 9.0, h: 0.55, rectRadius: 0.07, fill: { color: TINT } });
  s.addText([
    { text: "평가 하네스  ", options: { bold: true, color: ACCENT } },
    { text: "7종 · 24체크 — Tool 결정성 · 적치 정규화 · DES 재현성(seed 고정) · Forecast · Intent · RAG/Abstain · Answer Grounding (eval/harness.py)", options: { color: TEXT } },
  ], { x: 0.72, y: 4.95, w: 8.6, h: 0.55, fontFace: F, fontSize: 10.5, valign: "middle", margin: 0 });
}

// =======================================================
// [C1] AI 패턴 — 정의와 코드 구현 위치 (table)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AI PATTERNS", "적용한 에이전트 패턴 — 정의와 코드 구현");
  s.addText("설계 원칙 — LLM은 계산하지 않는다 · Tool이 계산하고 LLM은 설명한다 (agent/nodes.py)",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, italic: true, color: ACCENT, margin: 0 });
  const hd = (t) => ({ text: t, options: { fill: { color: ACCENT }, color: WHITE, bold: true, fontFace: F, valign: "middle" } });
  const rows = [
    ["Router / Meta-Controller", "질의 intent·파라미터 분류", "router_node · gpt-4.1-mini JSON"],
    ["Planning", "intent → Tool 실행계획(규칙)", "planner_node"],
    ["Tool Use", "조회·점수·예측·Draft 계산", "tool_executor_node + _HANDLERS"],
    ["PEV / Verify", "결과 정합성 검증(점수 0~1 범위)", "verifier_node"],
    ["Dry-Run · HITL", "상태변경 미리보기 → 사용자 승인", "approval_gate_node · drafts.dry_run"],
    ["Adaptive RAG", "필요한 질의에만 검색", "rag_decision_node (RAG_INTENTS)"],
    ["Agentic RAG", "충분성 루프 · 재검색 · abstain", "retriever.retrieve"],
    ["Simulator", "SimPy DES · What-if 시나리오", "des.run_des_simulation · whatif"],
  ];
  const body = rows.map((r, i) => r.map((c, j) => ({
    text: c, options: { fill: { color: i % 2 ? "EDF5F6" : WHITE }, color: j === 0 ? TEXT : MUTED, bold: j === 0, fontFace: j === 2 ? MONO : F, fontSize: j === 2 ? 9.5 : 10.5, valign: "middle" },
  })));
  s.addTable([[hd("패턴"), hd("정의 (역할)"), hd("구현 (파일 · 함수)")], ...body],
    { x: 0.5, y: 1.6, w: 9.0, colW: [2.5, 3.35, 3.15], rowH: 0.4, fontSize: 10.5, fontFace: F, border: { pt: 0.5, color: "D6E2E4" }, valign: "middle" });
}

// =======================================================
// [C2] AI 패턴 — 핵심 코드로 보는 구현 (snippets)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AI PATTERNS · CODE", "핵심 코드로 보는 패턴 구현");
  codeCard(s, 0.5, 1.55, 4.55, 3.55, "Agentic RAG — 충분성 루프 (rag/retriever.py)",
    "def retrieve(query, intent, k=5):\n"
    + "  q, retries = query, 0\n"
    + "  while True:\n"
    + "    cands  = search(q, k, intent)    # FAISS\n"
    + "    ranked = prism_rerank(query, cands)\n"
    + "    judge  = sufficient_context(query, ranked)\n"
    + "    if judge[\"answerable\"] or retries>=2:\n"
    + "      break\n"
    + "    # 부족한 근거유형을 질의에 보강 후 재검색\n"
    + "    q = f\"{query} {missing}\"\n"
    + "    retries += 1\n"
    + "  # 충분: 근거 반환 / 부족: abstain");
  codeCard(s, 5.25, 1.55, 4.25, 1.68, "Tool Use — 계산은 Tool (agent/nodes.py)",
    "_HANDLERS = {\n"
    + "  \"inventory_risk\": _h_inventory_risk,\n"
    + "  \"stocking_recommendation\": _h_stocking, ...}\n"
    + "def tool_executor_node(state):\n"
    + "  h = _HANDLERS[state[\"intent\"]]\n"
    + "  return {\"tool_results\": h(state[\"params\"])}");
  codeCard(s, 5.25, 3.42, 4.25, 1.68, "Adaptive RAG — 진입 게이트 (agent/nodes.py)",
    "RAG_INTENTS = {\"policy_question\",\n"
    + "  \"stocking_recommendation\", \"inventory_risk\"...}\n"
    + "def rag_decision_node(state):\n"
    + "  # 단순 조회는 검색 생략(비용·지연 ↓)\n"
    + "  return {\"rag_required\":\n"
    + "          state[\"intent\"] in RAG_INTENTS}");
}

// =======================================================
// [D1] RAG ① Adaptive vs Agentic + 결합 사상
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "RAG · DESIGN", "RAG ① Adaptive vs Agentic · ALR+Sufficient 결합");
  pcard(s, 0.5, 1.5, 4.5, 1.95, "Adaptive RAG — 진입 게이트",
    "“검색을 할까?”를 결정\n· 단순 조회(입고예정·재고)는 검색 생략 → 비용·지연 ↓\n· 근거·정책·SOP·산식 질문만 검색\n· 구현: rag_decision_node (intent ∈ RAG_INTENTS)", false);
  pcard(s, 5.0, 1.5, 4.5, 1.95, "Agentic RAG — 품질 루프",
    "“이 근거로 충분한가?”를 반복\n· 검색 → 리랭크 → 충분성 판정, 부족 시 query rewrite 재검색(≤2)\n· 충분 근거 없으면 abstain(“문서 근거가 부족합니다”)\n· 구현: retriever.retrieve", true);
  s.addText("Adaptive = 문 앞에서 ‘들어갈지’ 결정  ·  Agentic = 안에서 ‘충분해질 때까지’ 반복",
    { x: 0.5, y: 3.56, w: 9.0, h: 0.32, fontFace: F, fontSize: 11.5, italic: true, color: ACCENT, align: "center", margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.95, w: 9.0, h: 1.55, rectRadius: 0.08, fill: { color: DARK } });
  s.addText("ALR + Sufficient Context + PRISM — 역할이 겹치지 않게 결합", { x: 0.75, y: 4.06, w: 8.5, h: 0.3, fontFace: F, fontSize: 12.5, bold: true, color: "7FD1CD", margin: 0 });
  s.addText([
    { text: "ALR(DocSeeker 개념)  ", options: { bold: true, color: WHITE } },
    { text: "인덱싱 때 근거 메타(answerable_intents·evidence_summary) 사전부여 = 근거 구조·사전 라우팅 (chunker.py)", options: { color: "CFD8DC", breakLine: true } },
    { text: "PRISM  ", options: { bold: true, color: WHITE } },
    { text: "relevance+contribution+evidence_span 리랭커 = 설명용 근거 span 추출 (prism_rerank)", options: { color: "CFD8DC", breakLine: true } },
    { text: "Sufficient(Google)  ", options: { bold: true, color: WHITE } },
    { text: "‘답해도 되나’ 게이트 = 환각 차단·abstain. ALR만으론 멈추는 규칙이 없어 환각 위험 → 보완 (sufficient_context)", options: { color: "CFD8DC" } },
  ], { x: 0.75, y: 4.38, w: 8.5, h: 1.08, fontFace: F, fontSize: 9.6, valign: "top", margin: 0, lineSpacingMultiple: 1.04 });
}

// =======================================================
// [D2] RAG ② Vector DB 구성 & 검색 파이프라인
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "RAG · VECTOR DB", "RAG ② Vector DB 구성과 검색 파이프라인");
  pcard(s, 0.5, 1.55, 4.35, 3.55, "Vector DB · 인덱스 구성",
    "· Vector DB: FAISS IndexFlatIP\n   (L2 정규화 → 코사인 유사도)\n· 임베딩: text-embedding-3-small\n· 청킹: 정책 md 6종 · ## 헤딩 단위\n   (LLM 없이 결정적 메타 부여)\n· 메타: source·document_type·domain·\n   section·answerable_intents·evidence_summary\n· 인덱스: faiss.index + chunks.json\n   정책 변경 시 전체 재인덱싱\n· 향후: PostgreSQL/pgvector 전환", false);
  pcard(s, 5.05, 1.55, 4.45, 1.95, "검색 파이프라인 (rag/retriever.py)",
    "① 질의 임베딩 → ② FAISS top-(k×3)\n③ intent 메타 필터 → top-k\n④ PRISM 리랭크(relevance·contribution·span)\n⑤ Sufficient 판정\n   충분 → 근거 답변 / 부족 → 재검색(≤2)·abstain", true);
  codeCard(s, 5.05, 3.7, 4.45, 1.4, "인덱스 빌드 (rag/index.py)",
    "vecs = embed([c.text for c in chunks])\n"
    + "faiss.normalize_L2(vecs)        # → 코사인\n"
    + "index = faiss.IndexFlatIP(dim)\n"
    + "index.add(vecs)");
}

// =======================================================
// [E1] 향후 ① 실시간 수요 발생 (Runtime Demand Stream)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "ROADMAP · NEXT", "향후 ① 실시간 수요 발생 (Runtime Demand Stream)");
  s.addText("현재 DES의 확률 수요생성(Poisson, λ=fit_demand)을 런타임 이벤트 스트림으로 확장",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });
  pcard(s, 0.5, 1.6, 4.5, 1.95, "실시간 발생 개념",
    "· 앱 실행(runtime) 중 확률분포로 입고요청/출고요청이 실시간 생성\n· 발생 시점: 보유 데이터 대비 미래 / 중간 / 근미래(실시간)\n· 생성기: 현재 DES Poisson 수요(λ) 로직 재사용", false);
  pcard(s, 0.5, 3.7, 4.5, 1.4, "발생 흐름",
    "확률 스트림 발생기 → 요청 row 생성\n→ Toast 알림 → [탭 이동] 또는 [닫기]", true);
  // toast mock
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y: 1.6, w: 4.3, h: 1.55, rectRadius: 0.1, fill: { color: WHITE }, line: { color: ACCENT, width: 1.25 }, shadow: shadow() });
  s.addText("🔔  신규 출고요청 발생 — ORD-RT-014", { x: 5.42, y: 1.74, w: 3.9, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: TEXT, margin: 0 });
  s.addText([
    { text: "오늘 16:00 마감 · ", options: { color: MUTED } },
    { text: "긴급", options: { bold: true, color: "C0392B" } },
  ], { x: 5.42, y: 2.08, w: 3.9, h: 0.3, fontFace: F, fontSize: 11, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.42, y: 2.5, w: 1.9, h: 0.42, rectRadius: 0.1, fill: { color: ACCENT } });
  s.addText("입·출고 요청 데이터로 이동", { x: 5.42, y: 2.5, w: 1.9, h: 0.42, fontFace: F, fontSize: 9, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.45, y: 2.5, w: 0.95, h: 0.42, rectRadius: 0.1, fill: { color: LIGHT }, line: { color: "C9D6D8", width: 1 } });
  s.addText("닫기", { x: 7.45, y: 2.5, w: 0.95, h: 0.42, fontFace: F, fontSize: 9, bold: true, color: MUTED, align: "center", valign: "middle", margin: 0 });
  // timeline mock
  s.addText("발생 시점 분포", { x: 5.2, y: 3.55, w: 4.3, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: TEXT, margin: 0 });
  s.addShape(pres.shapes.LINE, { x: 5.4, y: 4.35, w: 3.9, h: 0, line: { color: "C9D6D8", width: 1.5 } });
  [["now", 5.4, ACCENT], ["근미래", 6.55, "1C7293"], ["중간", 7.6, "8AA0A6"], ["미래", 8.95, "8AA0A6"]].forEach(([t, x, c]) => {
    s.addShape(pres.shapes.OVAL, { x: x, y: 4.27, w: 0.16, h: 0.16, fill: { color: c } });
    s.addText(t, { x: x - 0.45, y: 4.5, w: 1.05, h: 0.3, fontFace: F, fontSize: 9.5, color: TEXT, align: "center", margin: 0 });
  });
  s.addText("실시간 요청은 now 이후 어느 시점에도 발생 가능 — 근미래 건은 즉시 처리 압박",
    { x: 5.2, y: 4.92, w: 4.3, h: 0.5, fontFace: F, fontSize: 9.5, italic: true, color: MUTED, valign: "top", margin: 0 });
}

// =======================================================
// [E2] 향후 ② 긴급 처리 판정 & 입·출고 요청 데이터 탭
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "ROADMAP · NEXT", "향후 ② 긴급 처리 판정 · 입·출고 요청 데이터 탭");
  pcard(s, 0.5, 1.55, 4.5, 1.72, "긴급여부 판정",
    "· 정의: now 기준 오늘(영업일) 내 처리해야 하면 긴급\n· 판정: due_datetime ≤ 오늘 마감(EOD) → urgent = true\n· 연계: 피킹 우선순위(deadline_urgency)·DES 부하에 즉시 반영", false);
  pcard(s, 0.5, 3.42, 4.5, 1.78, "데이터 모델 변경",
    "· inbound_orders / outbound_orders에\n   urgent 파생 컬럼(또는 뷰) 추가\n· 실시간 생성 요청은 row append (source=REALTIME)\n· 신규 탭: 입·출고 요청 데이터", true);
  pcard(s, 5.15, 1.55, 4.35, 1.25, "UI 탭 구성 (신규 탭 추가)",
    "현재: Agent Chat · KPI · Simulation · Approval\n추가: ★ 입·출고 요청 데이터 (실시간 요청·긴급 표시)", false);
  // data table mock
  const hd = (t) => ({ text: t, options: { fill: { color: ACCENT }, color: WHITE, bold: true, fontFace: F, fontSize: 9.5, valign: "middle", align: "center" } });
  const cell = (t, urgent) => ({ text: t, options: { fill: { color: urgent ? "FBE9E7" : WHITE }, color: urgent ? "C0392B" : TEXT, bold: !!urgent, fontFace: F, fontSize: 9.5, valign: "middle", align: "center" } });
  s.addText("입·출고 요청 데이터 (예시)", { x: 5.15, y: 2.95, w: 4.35, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: TEXT, margin: 0 });
  s.addTable([
    [hd("요청번호"), hd("유형"), hd("마감"), hd("긴급여부")],
    [cell("ORD-RT-014"), cell("출고"), cell("오늘 16:00"), cell("긴급", true)],
    [cell("INB-209"), cell("입고"), cell("내일"), cell("일반")],
    [cell("ORD-188"), cell("출고"), cell("오늘 18:00"), cell("긴급", true)],
  ], { x: 5.15, y: 3.3, w: 4.35, colW: [1.45, 0.8, 1.15, 0.95], rowH: 0.38, border: { pt: 0.5, color: "D6E2E4" }, valign: "middle" });
}

pres.writeFile({ fileName: "Smart_WMS_Agent_기획요약.pptx" }).then(() => console.log("done"));
