const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
p.author = "Smart WMS Agent";
p.title = "Smart WMS Agent — 진행 현황";

const NAVY = "1E2761", BLUE = "2F6BFF", ICE = "E8EEFC", INK = "20262F",
      SUB = "6B7480", GREEN = "16A34A", WHITE = "FFFFFF",
      BG = "F4F6FA", CARD = "FFFFFF", LINE = "E3E8F0", NODE2 = "2A3470";
const F = "Malgun Gothic";
const shadow = () => ({ type: "outer", color: "1E2761", blur: 7, offset: 2, angle: 90, opacity: 0.12 });

function title(s, t, sub) {
  s.addText(t, { x: 0.6, y: 0.4, w: 12.1, h: 0.6, fontFace: F, fontSize: 29, bold: true, color: INK, margin: 0 });
  if (sub) s.addText(sub, { x: 0.62, y: 1.0, w: 12.0, h: 0.4, fontFace: F, fontSize: 13.5, color: SUB, margin: 0 });
}
function star(s) { s.addText("★ 핵심", { x: 11.4, y: 0.46, w: 1.3, h: 0.4, fontFace: F, fontSize: 12, bold: true, color: BLUE, align: "right", margin: 0 }); }
function chip(s, x, y, txt, w) {
  s.addShape(p.shapes.OVAL, { x, y, w: 0.32, h: 0.32, fill: { color: GREEN }, line: { type: "none" } });
  s.addText("✓", { x, y: y - 0.01, w: 0.32, h: 0.32, fontFace: F, fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  s.addText(txt, { x: x + 0.44, y: y - 0.05, w: w || 5.4, h: 0.42, fontFace: F, fontSize: 13, color: INK, valign: "middle", margin: 0 });
}
function card(s, x, y, w, h, head, body, accent) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: CARD }, line: { color: LINE, width: 1 }, shadow: shadow() });
  s.addText(head, { x: x + 0.22, y: y + 0.15, w: w - 0.4, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: accent || NAVY, margin: 0 });
  s.addText(body, { x: x + 0.22, y: y + 0.6, w: w - 0.4, h: h - 0.74, fontFace: F, fontSize: 11.5, color: SUB, valign: "top", margin: 0, lineSpacingMultiple: 1.05 });
}
function box(s, x, y, w, h, t, dark) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: dark ? NAVY : CARD }, line: { color: dark ? NAVY : LINE, width: 1 }, shadow: shadow() });
  s.addText(t, { x: x + 0.05, y: y + 0.05, w: w - 0.1, h: h - 0.1, fontFace: F, fontSize: 10.5, bold: true, color: dark ? WHITE : INK, align: "center", valign: "middle", margin: 0 });
}
function arrow(s, x, y) { s.addText("›", { x, y, w: 0.2, h: 0.5, fontFace: F, fontSize: 20, color: SUB, align: "center", margin: 0 }); }

/* 1. Title */
let s = p.addSlide(); s.background = { color: NAVY };
s.addShape(p.shapes.OVAL, { x: 0.9, y: 2.3, w: 0.9, h: 0.9, fill: { color: BLUE }, line: { type: "none" } });
s.addText("📦", { x: 0.9, y: 2.3, w: 0.9, h: 0.9, fontSize: 30, align: "center", valign: "middle", margin: 0 });
s.addText("Smart WMS Agent", { x: 1.95, y: 2.35, w: 10.5, h: 0.95, fontFace: F, fontSize: 44, bold: true, color: WHITE, margin: 0 });
s.addText("진행 현황 보고 — POC 구현 & UI 리디자인", { x: 2.0, y: 3.35, w: 10.5, h: 0.5, fontFace: F, fontSize: 18, color: ICE, margin: 0 });
s.addText("문서 탐색(RAG) · AI 디자인 패턴 · LangGraph 아키텍처 + 운영 기능 확장 · 2026-06-25", { x: 2.0, y: 3.9, w: 10.5, h: 0.4, fontFace: F, fontSize: 12.5, color: "AEB9E6", margin: 0 });

/* 2. 제품 개요 */
s = p.addSlide(); s.background = { color: BG };
title(s, "제품 개요", "WMS 운영자를 위한 Agentic Copilot — 메인 기능은 SimPy DES 기반 창고상황 예측·What-if");
[["💬 오늘 할 일·승인 수행", "자연어로 당일 업무 종합, 적치·피킹지시·출고확정을 승인 하에 실행"],
 ["📦 적치·피킹 추천", "정규화 점수·우선순위 산식 추천 + 정책·산식 근거 설명"],
 ["🧊 창고상황 예측 (메인)", "DES로 인력·장비·공간 제약 하 처리가능성 검증 + What-if 비교"],
 ["📊 KPI·시각화", "운영 KPI + 재고추이·창고 디지털트윈·이벤트 타임라인"]
].forEach((c, i) => card(s, 0.6 + (i % 2) * 6.15, 1.65 + Math.floor(i / 2) * 2.55, 5.85, 2.3, c[0], c[1], i === 2 ? BLUE : NAVY));

/* 3. 시스템 구성 */
s = p.addSlide(); s.background = { color: BG };
title(s, "시스템 구성", "데이터 → Tool 엔진 → 예측/RAG → LangGraph 에이전트 → FastAPI → 웹 UI");
const flow = ["SQLite\n데이터·시드", "Tool 엔진\n조회·적치·피킹", "SimPy DES\n+ Regression", "RAG\nALR·충분성", "LangGraph\n에이전트", "FastAPI\n+ Web UI"];
flow.forEach((t, i) => { const x = 0.6 + i * 2.04; box(s, x, 2.3, 1.92, 1.4, t, i >= 4); if (i < 5) arrow(s, x + 1.9, 2.65); });
card(s, 0.6, 4.05, 12.13, 1.5, "모델 (회사 Azure OpenAI 호환 게이트웨이)",
  "생성·추론·Tool = gpt-5.4   ·   라우터·파라미터 추출 = gpt-4.1-mini   ·   임베딩 = text-embedding-3-small\n작업 모델: 2인1조(작업자 2 + 지게차 1) = 1팀, 동시 가용 팀 = min(작업자//2, 지게차)", BLUE);

/* 4. ★ 문서 탐색 (RAG) */
s = p.addSlide(); s.background = { color: BG }; star(s);
title(s, "문서 탐색 — RAG 구성", "임베딩 단순 검색이 아니라 '근거 우선 + 충분성 게이트' 파이프라인 (ALR + Sufficient Context + PRISM)");
const rag = ["질의", "필요 근거 정의\n(Analysis)", "FAISS 벡터검색\nTop-K", "PRISM 리랭크\n근거 passage 추출", "충분성 게이트\n(answerable?)", "근거 기반 답변"];
rag.forEach((t, i) => { const x = 0.6 + i * 2.04; box(s, x, 1.75, 1.92, 1.15, t, i === 4); if (i < 5) arrow(s, x + 1.9, 1.98); });
s.addText("↳ 부족 시: query rewrite·재검색(≤2회) / 한도 초과 시 “문서 근거가 부족합니다” abstain", { x: 0.7, y: 3.0, w: 12, h: 0.4, fontFace: F, fontSize: 12, italic: true, color: BLUE, margin: 0 });
card(s, 0.6, 3.55, 5.95, 2.0, "인덱싱 시점 근거 메타 (ALR Localization)",
  "정책 md 6종을 ## 헤딩 단위로 청킹 후 메타 부여:\n· document_type·domain·section\n· answerable_intents (이 chunk가 답할 intent)\n· evidence_summary (핵심 근거 한 줄)\n→ 추론을 인퍼런스가 아닌 인제스천에서 외부화", NAVY);
card(s, 6.78, 3.55, 5.95, 2.0, "차용한 설계 사상",
  "· DocSeeker(CVPR) ALR: 모델 도입 X, '근거 위치특정 후 추론' 흐름만 차용\n· Google Sufficient Context: 충분성 판정·abstain·재검색 게이트\n· PRISM: relevance + contribution + evidence_span 산출 리랭커\n→ 역할이 겹치지 않게 결합(구조 + 품질 게이트 + 부품)", BLUE);

/* 5. ★ AI 디자인 패턴 */
s = p.addSlide(); s.background = { color: BG }; star(s);
title(s, "적용한 AI 에이전트 디자인 패턴", "“LLM은 계산하지 않는다 · Tool이 계산하고 LLM은 설명한다”를 패턴으로 구현");
const rows = [
  ["Meta-Controller / Router", "질의 intent 분류 · 경로 결정"],
  ["Planning", "intent별 Tool 실행계획 수립(규칙 기반)"],
  ["Tool Use", "조회·점수·Forecast·DES·Draft (LLM 비계산)"],
  ["ReAct", "복합 질의에서 실행–관찰 반복"],
  ["PEV (Plan–Execute–Verify)", "Verifier 정합성 검증 + 재계획 루프(≤2)"],
  ["Dry-Run + Human-in-the-loop", "상태변경 전 미리보기 → 승인 게이트"],
  ["Adaptive RAG", "필요한 질의에만 문서 검색"],
  ["Agentic RAG", "ALR + Sufficient Context 재검색 루프"],
  ["Simulator", "SimPy DES · What-if 시나리오"],
  ["Loop / Harness", "검증 루프 + 평가 하네스(재현성·grounding)"],
];
const tbl = [[{ text: "패턴", options: { fill: { color: NAVY }, color: WHITE, bold: true, fontFace: F } },
              { text: "적용 위치", options: { fill: { color: NAVY }, color: WHITE, bold: true, fontFace: F } }]];
rows.forEach((r, i) => tbl.push([
  { text: r[0], options: { fill: { color: i % 2 ? "EEF2FA" : WHITE }, color: INK, bold: true, fontFace: F } },
  { text: r[1], options: { fill: { color: i % 2 ? "EEF2FA" : WHITE }, color: SUB, fontFace: F } },
]));
s.addTable(tbl, { x: 0.6, y: 1.7, w: 12.13, colW: [4.6, 7.53], rowH: 0.37, fontSize: 11.5, border: { pt: 0.5, color: LINE }, valign: "middle" });

/* 6. ★ LangGraph 구성 */
s = p.addSlide(); s.background = { color: BG }; star(s);
title(s, "LangGraph 워크플로 구성", "조건 분기 그래프 — 단일 질의를 노드 파이프라인으로 처리");
const r1 = ["Router", "Parameter\nExtractor", "Planner", "Tool\nExecutor", "Verifier"];
const r2 = ["RAG\nDecision", "RAG Retriever\n(ALR)", "Sufficient\nContext", "Response\nGenerator", "Approval\nGate"];
r1.forEach((t, i) => { const x = 0.66 + i * 2.39; box(s, x, 1.7, 2.25, 0.95, t, false); if (i < 4) arrow(s, x + 2.22, 1.86); });
r2.forEach((t, i) => { const x = 0.66 + i * 2.39; box(s, x, 2.95, 2.25, 0.95, t, i >= 3); if (i < 4) arrow(s, x + 2.22, 3.11); });
s.addText("↩", { x: 11.2, y: 2.62, w: 0.4, h: 0.4, fontFace: F, fontSize: 16, color: SUB, align: "center", margin: 0 });
card(s, 0.6, 4.25, 7.4, 2.6, "조건 분기 (Conditional Edges)",
  "· 필수 파라미터 누락 → Clarification 후 종료\n· Verifier 실패 → 재계획(최대 2회)\n· RAG Decision → 불필요 시 검색 생략(Adaptive)\n· Sufficient Context 부족 → 재검색(≤2)·abstain\n· Approval Gate → 상태변경만 승인 요구 → State Update Tool", NAVY);
card(s, 8.2, 4.25, 4.53, 2.6, "상태 · 모델",
  "AgentState: intent·parameters·plan·tool_results·\nverification·rag_context·rag_retry·draft·approval\n\n2-tier 모델:\n· 라우터/추출 = gpt-4.1-mini\n· 응답/추론 = gpt-5.4", BLUE);

/* 7. 완료 ① 백엔드·엔진 */
s = p.addSlide(); s.background = { color: BG };
title(s, "완료 ① 백엔드 · 시뮬레이션 엔진", "Phase 1~9 구현 완료 · 평가 하네스 전체 통과");
["SQLite 스키마 + 일관성 시드(9 Zone·병목 시나리오)",
 "Tool 엔진: 조회·적치(정규화)·피킹·Draft/승인(HITL)",
 "Forecast(LR)+위험등급 · SimPy DES(4단계·팀·Monte Carlo)",
 "What-if + baseline/scenario 비교 · 버전 관리",
 "RAG: ALR + Sufficient Context + PRISM",
 "LangGraph 에이전트(라우터~승인) · FastAPI"
].forEach((t, i) => chip(s, 0.7, 1.85 + i * 0.66, t, 7.6));
function stat(x, y, num, label) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.9, h: 1.5, rectRadius: 0.08, fill: { color: ICE }, line: { type: "none" } });
  s.addText(num, { x, y: y + 0.2, w: 1.9, h: 0.7, fontFace: F, fontSize: 24, bold: true, color: NAVY, align: "center", valign: "middle", margin: 0 });
  s.addText(label, { x: x + 0.1, y: y + 0.92, w: 1.7, h: 0.5, fontFace: F, fontSize: 11, color: SUB, align: "center", margin: 0 });
}
stat(8.7, 1.95, "24/24", "평가 하네스 통과"); stat(10.8, 1.95, "9", "Zone(3×3)");
stat(8.7, 3.75, "P50/P90", "확률 KPI 분포"); stat(10.8, 3.75, "50", "SKU 시드");

/* 8. 완료 ② UI 리디자인 */
s = p.addSlide(); s.background = { color: BG };
title(s, "완료 ② UI 리디자인 (커스텀 웹 SPA)", "FastAPI 서빙 · 외부 라이브러리 없이 자체 SVG로 구현 (P1~P6)");
[["P1 디자인 토큰·테마", "블루 액센트·카드·소프트 섀도우 통일"],
 ["P2 레이아웃 셸", "헤더·탭·좌측 대화이력·본문 그리드"],
 ["P3 KPI 카드 5종", "출고지연·피킹P90·팀가동률·소진일·재고비용 + delta"],
 ["P4 예측 인사이트 차트", "재고추이/출고지연 탭 · 자체 SVG · 툴팁"],
 ["P5 Agent Copilot", "병목 자원 자동 판별 → 권장 시나리오·개선율"],
 ["P6 2D 디지털 트윈 + 타임라인", "점유율 heatmap·지게차 이동·재생/스크럽·이벤트"]
].forEach((c, i) => card(s, 0.6 + (i % 3) * 4.08, 1.7 + Math.floor(i / 3) * 2.45, 3.85, 2.2, c[0], c[1], BLUE));

/* 8.5 완료 ③ 이번 추가 구현 (이전 대비) */
s = p.addSlide(); s.background = { color: BG };
title(s, "완료 ③ — 이번 추가 구현 (이전 보고 대비)",
  "운영 흐름 현실화 + 대화/관측 기능 + 실시간 시뮬레이션 — 전 항목 평가 하네스 40/40 통과");
[
  ["출고 할당 단계 · 예상 결품", "예정→할당→피킹→확정 수량 세분화. ATP(현재고+입고예정) 기반 예상 결품 KPI. 승인형 할당.", NAVY],
  ["체화재고 · 재고 보충", "EXPIRING/DEAD/SLOW 등급화·처분(HOLD). PICK/RESERVE 2단 재고 → 피킹면 보충 추천·이동.", "0B7A75"],
  ["실시간 수요 발생", "가상 입·출고 주기 생성 → DB 저장 후 SSE Toast. 설정 모달(주기·출고비율·수량). LLM 즉시 인지.", BLUE],
  ["대화 메모리", "세션 저장·복원(사이드바) + 멀티턴 맥락(대명사·생략 해소). 화자 라벨(user/ai).", "9B2D8F"],
  ["Approval 탭 · AI 관측", "상태변경 승인 통합 화면. LangGraph 노드 흐름·RAG(PRISM·충분성) 트레이스(Phoenix식).", NAVY],
  ["냉장·고회전·지연비용", "냉장/일반 2종+냉장존 격리·트윈 표현. 고회전 입구 슬로팅. 납기초과 비용 고회전 10배.", "C2410C"],
].forEach((c, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  card(s, 0.6 + col * 6.18, 1.55 + row * 1.78, 5.95, 1.6, c[0], c[1], c[2]);
});

/* 9. 남은 작업 */
s = p.addSlide(); s.background = { color: NAVY };
s.addText("남은 작업 & 다음 단계", { x: 0.6, y: 0.5, w: 12, h: 0.7, fontFace: F, fontSize: 29, bold: true, color: WHITE, margin: 0 });
s.addText("문서 마무리 → 기능 확장 → 운영 고도화", { x: 0.62, y: 1.18, w: 12, h: 0.4, fontFace: F, fontSize: 14, color: ICE, margin: 0 });
[["문서 마무리 (단기)", "기능 시연 시나리오 · 사용자 매뉴얼 (후반부 문서 작업)"],
 ["기능 확장 (중기)", "총 재고 비용 실단가 연동 · ABC 슬로팅 고도화 · 반응형·시각 디테일"],
 ["운영 고도화 (Phase 10)", "Dreaming Memory(장기기억) · Hybrid Search · PostgreSQL 전환 · 실 WMS API 연동 · DES 처리시간 실측 분포"]
].forEach((c, i) => {
  const y = 1.9 + i * 1.7;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 12.13, h: 1.5, rectRadius: 0.08, fill: { color: NODE2 }, line: { color: "3C4790", width: 1 } });
  s.addText(c[0], { x: 0.85, y: y + 0.18, w: 3.4, h: 1.1, fontFace: F, fontSize: 16, bold: true, color: WHITE, valign: "middle", margin: 0 });
  s.addText(c[1], { x: 4.3, y: y + 0.18, w: 8.2, h: 1.1, fontFace: F, fontSize: 13, color: ICE, valign: "middle", margin: 0, lineSpacingMultiple: 1.05 });
});

/* 10. 설계 사상 종합 */
function phiCard(s, x, y, w, h, head, strength, intent, how, accent) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: CARD }, line: { color: LINE, width: 1 }, shadow: shadow() });
  s.addText(head, { x: x + 0.22, y: y + 0.13, w: w - 0.4, h: 0.36, fontFace: F, fontSize: 13.5, bold: true, color: accent, margin: 0 });
  s.addText([
    { text: "강점  ", options: { bold: true, color: GREEN } }, { text: strength, options: { color: SUB, breakLine: true } },
    { text: "의도  ", options: { bold: true, color: BLUE } }, { text: intent, options: { color: SUB, breakLine: true } },
    { text: "동작  ", options: { bold: true, color: NAVY } }, { text: how, options: { color: SUB } },
  ], { x: x + 0.22, y: y + 0.52, w: w - 0.4, h: h - 0.62, fontFace: F, fontSize: 10.3, valign: "top", margin: 0, lineSpacingMultiple: 1.02 });
}
s = p.addSlide(); s.background = { color: BG };
title(s, "설계 사상 — 왜 섞었나 · 어떻게 동작하나",
  "단일 기법의 한계를 상호 보완: 요건 위에 ‘기술 컴포넌트 장단점 분석 + 도메인 지식’으로 차별화");
phiCard(s, 0.6, 1.6, 5.95, 1.95, "① SimPy DES (확률적 분포)",
  "자원·제약 하 동적 흐름과 불확실성을 분포로 모사",
  "회귀 점추정은 ‘언제’만 답하고 ‘처리 가능?·병목’은 못 봄(과적합 위험)",
  "처리시간·수요를 분포에서 샘플링 → N회 반복 → P50/P90·발생확률", NAVY);
phiCard(s, 6.78, 1.6, 5.95, 1.95, "② ALR — DocSeeker (개념만)",
  "근거를 먼저 위치특정 후 추론 → 설명력·노이즈 강건성↑",
  "추천 ‘근거 설명’이 제품 차별점, 추론을 인제스천에 외부화해 효율↑",
  "인덱싱 시 근거 메타 부여 + 질의 시 분석→위치확인→추론", BLUE);
phiCard(s, 0.6, 3.7, 5.95, 1.95, "③ Sufficient Context (Google)",
  "‘답해도 되나’ 게이트로 환각 차단·복구",
  "ALR만으론 근거가 없을 때 멈추는 규칙이 없어 환각 위험",
  "충분성 판정 → 부족 시 재검색(≤2)·query rewrite / abstain", "0B7A75");
phiCard(s, 6.78, 3.7, 5.95, 1.95, "④ Agentic 패턴 + 하네스",
  "계획–실행–검증 루프 자기검증 + 사람 승인 안전장치",
  "LLM 단독 생성은 신뢰성↓ → 계산은 Tool, 설명은 LLM, 변경은 승인",
  "Verifier 재계획·Dry-Run·승인 게이트·평가 하네스(재현성·grounding)", "9B2D8F");
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.82, w: 12.13, h: 1.4, rectRadius: 0.08, fill: { color: NAVY }, line: { type: "none" } });
s.addText([
  { text: "결합 의도  ", options: { bold: true, color: "9FB3F2" } },
  { text: "역할이 겹치지 않게 — DES=현실성 · ALR=근거 구조/설명 · Sufficient Context=품질 게이트 · Agentic/하네스=안전·검증.", options: { color: WHITE, breakLine: true } },
  { text: "단일 기법의 약점을 서로의 강점으로 메워 ‘근거 있고(RAG) · 검증되며(루프·하네스) · 현실적인(DES)’ 운영 의사결정 지원을 만든다.", options: { color: ICE } },
], { x: 0.85, y: 5.96, w: 11.6, h: 1.15, fontFace: F, fontSize: 12.5, valign: "middle", margin: 0, lineSpacingMultiple: 1.08 });

p.writeFile({ fileName: "Smart_WMS_Agent_진행현황.pptx" }).then((f) => console.log("written:", f));
