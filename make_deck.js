const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "WOONG AI 기획 요약";

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
  s.addText("WOONG AI", { x: 0.7, y: 1.75, w: 8.6, h: 1.0, fontFace: F, fontSize: 48, bold: true, color: WHITE, margin: 0 });
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
  s.addText("WOONG AI", { x: 0.5, y: 5.05, w: 9.0, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", align: "center", margin: 0 });
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
  s.addText("WOONG AI", { x: 0.7, y: 5.28, w: 8.6, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", margin: 0 });
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
  slideTitle(s, "RAG · DESIGN", "RAG ① Adaptive vs Agentic — 검색 여부 + 품질 루프");
  pcard(s, 0.5, 1.5, 4.5, 1.95, "Adaptive RAG — 진입 게이트",
    "“검색을 할까?”를 결정\n· 단순 조회(입고예정·재고)는 검색 생략 → 비용·지연 ↓\n· 근거·정책·SOP·산식 질문만 검색\n· 구현: rag_decision_node (intent ∈ RAG_INTENTS)", false);
  pcard(s, 5.0, 1.5, 4.5, 1.95, "Agentic RAG — 품질 루프",
    "“이 근거로 충분한가?”를 반복\n· 검색 → 리랭크 → 충분성 판정, 부족 시 query rewrite 재검색(≤2)\n· 충분 근거 없으면 abstain(“문서 근거가 부족합니다”)\n· 구현: retriever.retrieve", true);
  s.addText("Adaptive = 문 앞에서 ‘들어갈지’ 결정  ·  Agentic = 안에서 ‘충분해질 때까지’ 반복",
    { x: 0.5, y: 3.56, w: 9.0, h: 0.32, fontFace: F, fontSize: 11.5, italic: true, color: ACCENT, align: "center", margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.0, w: 9.0, h: 1.25, rectRadius: 0.08, fill: { color: DARK } });
  s.addText("이 둘을 받치는 3가지 사상", { x: 0.75, y: 4.12, w: 8.5, h: 0.3, fontFace: F, fontSize: 12.5, bold: true, color: "7FD1CD", margin: 0 });
  s.addText([
    { text: "ALR ", options: { bold: true, color: WHITE } },
    { text: "근거 구조·사전 라우팅      ", options: { color: "CFD8DC" } },
    { text: "PRISM ", options: { bold: true, color: WHITE } },
    { text: "설명용 근거 추출      ", options: { color: "CFD8DC" } },
    { text: "Sufficient ", options: { bold: true, color: WHITE } },
    { text: "환각 차단 게이트", options: { color: "CFD8DC", breakLine: true } },
    { text: "→ 각각이 무엇이고, 어떤 장점 때문에 넣어 어떻게 결합했는지는 다음 장에서 설명", options: { color: "9FC7C4", italic: true } },
  ], { x: 0.75, y: 4.52, w: 8.5, h: 0.65, fontFace: F, fontSize: 11, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
}

// =======================================================
// [D1b] RAG · ALR·Sufficient·PRISM — 무엇이고, 왜 결합했나
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "RAG · WHY COMBINE", "RAG ② ALR · Sufficient · PRISM — 무엇이고, 왜 결합했나");
  s.addText("세 기법은 역할이 겹치지 않는다 — 질문 분석, 근거 정제, 생성 판단을 나눠 단일 RAG의 약점을 보완한다",
    { x: 0.5, y: 1.12, w: 9.33, h: 0.32, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });
  // 실행 흐름 (순차 파이프라인)
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.5, w: 9.33, h: 0.5, rectRadius: 0.08, fill: { color: TINT } });
  s.addText([
    { text: "질문 입력 ", options: { bold: true, color: TEXT } }, { text: "→  ", options: { color: MUTED } },
    { text: "ALR ", options: { bold: true, color: ACCENT } }, { text: "→  Retrieval  →  ", options: { color: MUTED } },
    { text: "PRISM ", options: { bold: true, color: ACCENT } }, { text: "→  ", options: { color: MUTED } },
    { text: "Sufficient Context ", options: { bold: true, color: ACCENT } }, { text: "→  ", options: { color: MUTED } },
    { text: "Answer / Re-search / Abstain", options: { bold: true, color: TEXT } },
  ], { x: 0.5, y: 1.5, w: 9.33, h: 0.5, fontFace: F, fontSize: 10.5, align: "center", valign: "middle", margin: 0 });
  function whyCard(x, name, tint, what, adv, role) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.15, w: 2.99, h: 2.45, rectRadius: 0.07, fill: { color: tint ? TINT : LIGHT }, shadow: shadow() });
    s.addText(name, { x: x + 0.18, y: 2.27, w: 2.63, h: 0.5, fontFace: F, fontSize: 10.5, bold: true, color: ACCENT, valign: "top", margin: 0 });
    s.addText([
      { text: "무엇  ", options: { bold: true, color: TEXT } }, { text: what, options: { color: MUTED, breakLine: true } },
      { text: "", options: { fontSize: 4, breakLine: true } },
      { text: "강점  ", options: { bold: true, color: TEXT } }, { text: adv, options: { color: MUTED, breakLine: true } },
      { text: "", options: { fontSize: 4, breakLine: true } },
      { text: "역할  ", options: { bold: true, color: ACCENT } }, { text: role, options: { color: MUTED } },
    ], { x: x + 0.18, y: 2.84, w: 2.63, h: 1.68, fontFace: F, fontSize: 8.8, valign: "top", margin: 0, lineSpacingMultiple: 1.04 });
  }
  whyCard(0.5, "ALR: Analysis–Localization–Reasoning", false,
    "DocSeeker의 구조화된 문서 추론 흐름. 질문 의도를 먼저 분석하고, 필요한 근거 위치를 문서에서 식별한 뒤 그 근거로 추론한다.",
    "검색과 추론을 분리해 ‘어디를 근거로 답했는지’가 명확. 긴 문서의 노이즈를 줄이고 근거 추적성을 높인다.",
    "DocSeeker 모델은 도입하지 않고 ALR 개념·흐름만 차용. RAG 파이프라인에서 질문 분석·근거 후보 라우팅 기준으로 사용.");
  whyCard(3.67, "PRISM: Evidence-aware Reranker", true,
    "유사도 점수만 쓰는 reranker가 아니라 relevance 판단·contribution·근거 구절(evidence passage)을 함께 생성하는 재랭킹.",
    "‘왜 근거인지’와 ‘답변 기여도’를 함께 제공 → 검색 결과를 그대로 넣지 않고 핵심 근거 중심으로 context를 정제.",
    "검색된 후보 청크를 재평가해 답변에 쓸 근거 구절과 설명 가능한 contribution을 생성.");
  whyCard(6.84, "Sufficient Context: Answerability Gate", false,
    "정제된 context만으로 질문에 답할 수 있는지 판단하는 품질 게이트.",
    "근거 부족 상태의 억지 답변을 차단. 불충분하면 추가 검색·재질문 또는 답변 보류(abstain).",
    "답변 생성 직전 근거 충분성을 판단 — 충분하면 답변, 부족하면 재검색하거나 ‘근거 부족으로 답변 불가’.");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.72, w: 9.33, h: 0.8, rectRadius: 0.07, fill: { color: DARK } });
  s.addText([
    { text: "결합  ", options: { bold: true, color: "7FD1CD" } },
    { text: "ALR은 질문 분석·근거 탐색을 구조화하고, PRISM은 후보를 근거 중심으로 재정렬·정제하며, Sufficient Context는 최종 답변 가능 여부를 판단한다. → 단순 유사도 RAG의 약점(잘못된 근거 선택·불충분한 context 답변·환각)을 함께 줄인다.", options: { color: "E6EDEF" } },
  ], { x: 0.72, y: 4.72, w: 8.9, h: 0.8, fontFace: F, fontSize: 9.5, valign: "middle", margin: 0, lineSpacingMultiple: 1.04 });
}

// =======================================================
// [D2] RAG ② Vector DB 구성 & 검색 파이프라인
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "RAG · VECTOR DB", "RAG ③ Vector DB 구성과 검색 파이프라인");
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

// #######################################################
// ##  2026-06-30 누적분 — 창고 자동운영(블랙보드 멀티에이전트)
// #######################################################

// =======================================================
// [F0] 날짜 구분 (dark divider)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: DARK };
  s.addText("PROGRESS UPDATE · 2026.06.30", { x: 0.7, y: 1.2, w: 8.6, h: 0.35, fontFace: F, fontSize: 13, bold: true, color: "7FD1CD", charSpacing: 3, margin: 0 });
  s.addText("창고 자동운영 — 블랙보드 멀티에이전트", { x: 0.7, y: 1.62, w: 8.6, h: 0.9, fontFace: F, fontSize: 38, bold: true, color: WHITE, margin: 0 });
  s.addText("실시간 이벤트를 10개 에이전트가 블랙보드(DB)로 협업해 자동 처리하는 구조와 동작 원리",
    { x: 0.7, y: 2.62, w: 8.6, h: 0.45, fontFace: F, fontSize: 14, color: "CFD8DC", margin: 0 });
  const batch = [
    "구조 — 10개 에이전트(도메인 6 · 인프라 4)와 블랙보드",
    "핵심 — 에이전트는 어떻게 협력하나 (주기 · 신호 · 데이터 읽기)",
    "연쇄 — 데이터로 흐르는 이벤트 체이닝 (입고→적치→자원)",
    "의사결정 1 사이클 — 8단계 실행과 가드레일",
    "대시보드 — ‘창고자동운영’ 탭 동작 가시화",
  ];
  batch.forEach((t, i) => {
    const y = 3.3 + i * 0.42;
    s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.02, w: 0.3, h: 0.3, fill: { color: ACCENT } });
    s.addText(String(i + 1), { x: 0.7, y: y + 0.02, w: 0.3, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: 1.16, y: y - 0.04, w: 8.1, h: 0.4, fontFace: F, fontSize: 12.5, color: "ECEFF1", valign: "middle", margin: 0 });
  });
  s.addText("WOONG AI · Blackboard Auto-Execution Layer", { x: 0.7, y: 5.3, w: 8.6, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: "7FD1CD", margin: 0 });
}

// =======================================================
// [F1] 구조 — 10개 에이전트 & 블랙보드
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AUTO-OPERATION · ARCHITECTURE", "10개 에이전트와 블랙보드");
  s.addText("에이전트는 서로를 모른다. 공유 게시판(블랙보드=DB)의 상태 변화에만 반응하는 ‘지식원(knowledge source)’이다.",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });

  s.addText("도메인 에이전트 6 — Action을 ‘제안’만 (DB write 없음)", { x: 0.5, y: 1.62, w: 4.5, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: TEXT, margin: 0 });
  const dom = [
    ["Inbound", "입고 도착 → 입고작업"], ["Putaway", "입고완료 → 적치 위치 배정"],
    ["Picking", "출고주문 → 예약 + 피킹작업"], ["Outbound", "임박 → 우선순위 / 출고준비"],
    ["Resource", "작업 발생 → 작업자 배정"], ["InventoryRisk", "결품 위험 → 경보(자동실행 금지)"],
  ];
  dom.forEach((d, i) => {
    const x = 0.5 + (i % 2) * 2.32, y = 1.98 + Math.floor(i / 2) * 0.66;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.22, h: 0.56, rectRadius: 0.06, fill: { color: LIGHT } });
    s.addText([
      { text: d[0] + "  ", options: { bold: true, color: ACCENT, fontSize: 10.5 } },
      { text: d[1], options: { color: MUTED, fontSize: 8.6, breakLine: true } },
    ], { x: x + 0.12, y: y + 0.07, w: 2.0, h: 0.44, fontFace: F, valign: "middle", margin: 0, lineSpacingMultiple: 0.96 });
  });

  s.addText("인프라 에이전트 4 — 공통(cross-cutting)", { x: 5.2, y: 1.62, w: 4.3, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: TEXT, margin: 0 });
  const inf = [
    ["Control", "유일한 주기 스케줄러 — 이벤트를 읽어 에이전트에 분배"],
    ["Policy", "자동실행 가부 게이트(위험 Action 차단)"],
    ["Simulation", "배치 What-if(DES)로 KPI 과부하 판정 — 백그라운드 캐시"],
    ["Explanation", "각 Action의 한국어 사유 생성(LLM + 템플릿 폴백)"],
  ];
  inf.forEach((d, i) => {
    const y = 1.98 + i * 0.62;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.2, y, w: 4.3, h: 0.54, rectRadius: 0.06, fill: { color: TINT } });
    s.addText([
      { text: d[0] + "  ", options: { bold: true, color: ACCENT, fontSize: 10.5 } },
      { text: d[1], options: { color: MUTED, fontSize: 9 } },
    ], { x: 5.34, y: y + 0.05, w: 4.05, h: 0.44, fontFace: F, valign: "middle", margin: 0, lineSpacingMultiple: 0.96 });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.62, w: 9.0, h: 0.92, rectRadius: 0.07, fill: { color: DARK } });
  s.addText([
    { text: "블랙보드 = DB 테이블  ", options: { bold: true, color: "7FD1CD" } },
    { text: "blackboard_events · blackboard_actions · audit_logs · inventory_reservations. ", options: { color: "E6EDEF" } },
    { text: "모든 협업은 이 게시판을 ‘읽고 쓰는’ 것으로만 이뤄진다 — 에이전트 간 직접 호출은 없다.", options: { color: "B9C6CB" } },
  ], { x: 0.72, y: 4.62, w: 8.6, h: 0.92, fontFace: F, fontSize: 10.5, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });
}

// =======================================================
// [F2] 핵심 — 에이전트는 어떻게 협력하나 (centerpiece)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AUTO-OPERATION · MECHANISM", "에이전트는 어떻게 협력하나");
  s.addText("주기적으로 파일을 읽지도, 서로를 직접 부르지도 않는다 — 가운데 블랙보드(이벤트 테이블)를 통해 간접 신호를 주고받는다.",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });
  pcard(s, 0.5, 1.6, 2.95, 2.25, "① 유일한 ‘주기적’ 주체 = 컨트롤 루프 1개",
    "· 1개 스레드가 cycle_seconds(기본 15초)\n   마다 깨어난다.\n· 하는 일: blackboard_events 테이블에서\n   status='NEW' 이벤트만 읽기.\n· 파일을 폴링하는 게 아니라 DB 한\n   테이블을 읽는다.", false);
  pcard(s, 3.58, 1.6, 2.95, 2.25, "② 에이전트 = ‘수동’ 함수",
    "· handles(event_type) / propose(event)\n   두 함수뿐 — 타이머·루프 없음.\n· 컨트롤 루프가 이벤트 종류를 보고\n   해당 에이전트를 호출할 때만 동작.\n· 깨워진 그 순간 운영 테이블을 1회\n   조회해 판단(주기 폴링 아님).", true);
  pcard(s, 6.66, 1.6, 2.84, 2.25, "③ ‘다음 에이전트’ 신호",
    "· 직접 호출 ✕\n· Executor가 Action을 성공시킨 뒤\n   후속 이벤트 행을 블랙보드에 INSERT.\n· 컨트롤 루프가 그 새 이벤트를 읽어\n   다음 에이전트를 깨운다.\n   → data-driven 연쇄.", false);
  codeCard(s, 0.5, 4.05, 9.0, 1.45, "control_loop.py — 유일한 주기 주체가 이벤트 테이블을 읽어 분배",
    "while _running:\n"
    + "    if settings.enabled():\n"
    + "        run_once()                 # blackboard_events 읽어 처리\n"
    + "    time.sleep(cycle_seconds())    # ← 유일한 ‘주기적’ 부분 (기본 15초)\n"
    + "\n"
    + "def run_once():\n"
    + "    for ev in events.new_events():            # status='NEW' 이벤트만\n"
    + "        for agent in REGISTRY:\n"
    + "            if agent.handles(ev.type):        # 이 이벤트 담당?\n"
    + "                for spec in agent.propose(ev):    # Action 제안(읽기 1회)\n"
    + "                    executor.execute(create(spec))");
}

// =======================================================
// [F3] 연쇄 — 이벤트 체이닝 (입고→적치→자원)
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AUTO-OPERATION · CHAINING", "데이터로 흐르는 연쇄 — 입고 → 적치 → 자원");
  s.addText("한 에이전트의 실행 결과(=새 이벤트)가 다음 에이전트를 깨운다. 같은 사이클 안에서 이벤트가 빌 때까지 이어진다.",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });

  function stageCard(x, name, trig, act, emit) {
    const y = 1.66, w = 2.86, h = 2.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07, fill: { color: LIGHT }, shadow: shadow() });
    s.addText(name, { x: x + 0.16, y: y + 0.13, w: w - 0.32, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: ACCENT, margin: 0 });
    s.addText([
      { text: "트리거  ", options: { bold: true, color: TEXT } }, { text: trig, options: { color: MUTED, breakLine: true } },
      { text: "", options: { fontSize: 5, breakLine: true } },
      { text: "Action  ", options: { bold: true, color: TEXT } }, { text: act, options: { color: MUTED, breakLine: true } },
      { text: "", options: { fontSize: 5, breakLine: true } },
      { text: "→ 발생  ", options: { bold: true, color: ACCENT } }, { text: emit, options: { color: MUTED } },
    ], { x: x + 0.16, y: y + 0.5, w: w - 0.32, h: h - 0.6, fontFace: F, fontSize: 9, valign: "top", margin: 0, lineSpacingMultiple: 1.04 });
  }
  stageCard(0.5, "InboundAgent", "NEW_INBOUND_ARRIVAL", "CREATE_INBOUND_TASK (입고=RECEIVED)", "NEED_PUTAWAY");
  stageCard(3.58, "PutawayAgent", "NEED_PUTAWAY", "CREATE_PUTAWAY_TASK (적치작업 생성)", "TASK_CREATED");
  stageCard(6.66, "ResourceAgent", "TASK_CREATED", "ALLOCATE_WORKER (작업자 배정)", "(완료)");
  [3.46, 6.54].forEach((x) => s.addText("→", { x, y: 1.66, w: 0.16, h: 2.0, fontFace: F, fontSize: 18, bold: true, color: ACCENT, align: "center", valign: "middle", margin: 0 }));

  codeCard(s, 0.5, 3.86, 5.55, 1.6, "executor.py — 성공 후 ‘다음 에이전트’ 신호 = 이벤트 INSERT",
    "def _emit_followups(action, result):\n"
    + "  if at == 'CREATE_INBOUND_TASK':\n"
    + "    events.add_event('NEED_PUTAWAY','inbound', inbound_no)\n"
    + "  elif at == 'CREATE_PUTAWAY_TASK':\n"
    + "    events.add_event('TASK_CREATED','task', stocking_task_id)\n"
    + "  elif at == 'CREATE_PICKING_TASK':\n"
    + "    events.add_event('TASK_CREATED','task', picking_task_id)");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.2, y: 3.86, w: 3.3, h: 1.6, rectRadius: 0.07, fill: { color: TINT } });
  s.addText([
    { text: "출고 흐름도 동일\n", options: { bold: true, color: TEXT } },
    { text: "NEW_OUTBOUND_ORDER → PickingAgent\n(예약 + 피킹작업) →〔TASK_CREATED〕→\nResourceAgent(작업자 배정).\n\n", options: { color: MUTED } },
    { text: "에이전트는 서로 모른 채, 블랙보드에 쌓인 이벤트만 보고 자기 일을 한다.", options: { color: ACCENT, italic: true } },
  ], { x: 6.4, y: 4.0, w: 2.95, h: 1.34, fontFace: F, fontSize: 9.2, valign: "top", margin: 0, lineSpacingMultiple: 1.04 });
}

// =======================================================
// [F4] 의사결정 1 사이클 — 8단계 & 가드레일
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AUTO-OPERATION · DECISION CYCLE", "의사결정 1 사이클 — 실행 8단계와 가드레일");
  s.addText("이벤트가 Action으로 실행되기까지 — 자동 상태변경의 유일한 경로(Executor)는 매 단계를 검증·감사한다.",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 1.6, w: 9.0, h: 0.62, rectRadius: 0.08, fill: { color: TINT } });
  s.addText([
    { text: "이벤트 수집 ", options: { bold: true, color: TEXT } }, { text: "→ ", options: { color: MUTED } },
    { text: "배치 시뮬 게이트 ", options: { bold: true, color: ACCENT } }, { text: "→ ", options: { color: MUTED } },
    { text: "정책 ", options: { bold: true, color: ACCENT } }, { text: "→ 사전검증 → 락 → ", options: { color: MUTED } },
    { text: "트랜잭션 실행 ", options: { bold: true, color: TEXT } }, { text: "→ 사후검증 → ", options: { color: MUTED } },
    { text: "감사 · 후속이벤트", options: { bold: true, color: TEXT } },
  ], { x: 0.6, y: 1.6, w: 8.8, h: 0.62, fontFace: F, fontSize: 11, align: "center", valign: "middle", margin: 0 });

  const guards = [
    ["멱등성(Idempotency)", "idempotency_key UNIQUE → 같은 작업 중복 시 SKIPPED_DUPLICATE"],
    ["예약 단일출처", "가용 = 보유(AVAILABLE) − 예약. 예측·할당·자동운영이 같은 수치 사용"],
    ["정책 게이트", "위험 Action(재고보정·취소·출고확정 등)은 자동실행 금지 → POLICY_BLOCKED"],
    ["시뮬 게이트", "배치 What-if 팀 가동률이 임계 이상이면 sim-required Action 보류"],
  ];
  guards.forEach((g, i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 2.45 + Math.floor(i / 2) * 1.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.4, h: 0.92, rectRadius: 0.07, fill: { color: LIGHT }, shadow: shadow() });
    s.addText([
      { text: g[0] + "\n", options: { bold: true, color: ACCENT, fontSize: 11 } },
      { text: g[1], options: { color: MUTED, fontSize: 9.5 } },
    ], { x: x + 0.18, y: y + 0.12, w: 4.04, h: 0.68, fontFace: F, valign: "top", margin: 0, lineSpacingMultiple: 1.04 });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.68, w: 9.0, h: 0.82, rectRadius: 0.07, fill: { color: DARK } });
  s.addText([
    { text: "원칙  ", options: { bold: true, color: "7FD1CD" } },
    { text: "‘무승인 상태변경 0건(HITL)’을 Auto Mode가 위 가드레일과 함께 대체한다. 모든 실행은 8단계 감사로그(EVENT_RECEIVED→…→FINISHED)로 추적된다.", options: { color: "E6EDEF" } },
  ], { x: 0.72, y: 4.68, w: 8.6, h: 0.82, fontFace: F, fontSize: 10, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });
}

// =======================================================
// [F5] 대시보드 — ‘창고자동운영’ 탭 가시화
// =======================================================
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  slideTitle(s, "AUTO-OPERATION · DASHBOARD", "‘창고자동운영’ 탭 — 동작 가시화");
  s.addText("10개 에이전트가 동작할 때 원이 점등되고, 단계별 로그·Action·LLM 사유가 실시간으로 쌓인다.",
    { x: 0.5, y: 1.16, w: 9.0, h: 0.35, fontFace: F, fontSize: 11.5, color: MUTED, margin: 0 });

  // agent grid mock (2 x 5)
  s.addText("에이전트 보드 (도메인 6 · 인프라 4)", { x: 0.5, y: 1.58, w: 5.0, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: TEXT, margin: 0 });
  const grid = [["입고", 0], ["적치", 0], ["피킹", 1], ["출고", 0], ["자원", 0], ["위험", 0], ["컨트롤", 0], ["정책", 0], ["시뮬", 0], ["설명", 0]];
  grid.forEach((g, i) => {
    const x = 0.5 + (i % 5) * 0.92, y = 1.95 + Math.floor(i / 5) * 0.95;
    const hot = g[1] === 1;
    s.addShape(pres.shapes.OVAL, { x, y, w: 0.62, h: 0.62, fill: { color: hot ? ACCENT : LIGHT }, line: { color: hot ? ACCENT : "C9D6D8", width: hot ? 2 : 1 } });
    s.addText(g[0], { x: x - 0.12, y: y + 0.62, w: 0.86, h: 0.26, fontFace: F, fontSize: 8.5, color: hot ? ACCENT : MUTED, align: "center", bold: hot, margin: 0 });
  });

  pcard(s, 5.2, 1.58, 4.3, 1.5, "실시간 동작 로그",
    "· 감사 8단계를 에이전트·결과 색상으로 표시\n· 신규 줄만 증분 추가(깜빡임 없음)\n· 동작한 에이전트 원이 1.2초 점등", true);
  pcard(s, 5.2, 3.18, 4.3, 1.05, "Action 타임라인",
    "· 처리 시각 · 에이전트 · 상태 배지(성공/차단/실패)\n· 클릭 → 하단에 LLM 한국어 사유", false);

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 4.4, w: 4.45, h: 1.1, rectRadius: 0.07, fill: { color: DARK } });
  s.addText([
    { text: "한 건씩 가시화\n", options: { bold: true, color: "7FD1CD" } },
    { text: "Action 간 step_delay(기본 1.2초)로 흐름을 눈으로 확인. 시뮬 DES(수 초)는 백그라운드 캐시라 사이클을 막지 않음.", options: { color: "E6EDEF" } },
  ], { x: 0.72, y: 4.52, w: 4.05, h: 0.92, fontFace: F, fontSize: 9.5, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.05, y: 4.4, w: 4.45, h: 1.1, rectRadius: 0.07, fill: { color: TINT } });
  s.addText([
    { text: "안전 가동 조건\n", options: { bold: true, color: ACCENT } },
    { text: "‘실시간 수요’ ON 일 때만 자동운영 시작 가능. Auto Mode는 기본 OFF — 켜야 컨트롤 루프가 돈다.", options: { color: MUTED } },
  ], { x: 5.27, y: 4.52, w: 4.05, h: 0.92, fontFace: F, fontSize: 9.5, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
}

pres.writeFile({ fileName: "Smart_WMS_Agent_기획요약.pptx" }).then(() => console.log("done"));
