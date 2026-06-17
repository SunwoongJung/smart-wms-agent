"""정책 md 청킹 + 메타데이터 부여 (docs/03_RAG_DESIGN.md §4~5).

## 헤딩 단위로 청크를 만들고, 인덱싱 시점 근거 메타(ALR Localization 사전기록)인
answerable_intents / evidence_summary 를 부여한다(결정적, LLM 호출 없음).
"""
import re
from pathlib import Path

from config import settings

# 파일 → (document_type, domain, answerable_intents)
FILE_META = {
    "stocking_policy.md": ("policy", "stocking", ["stocking_recommendation", "policy_question"]),
    "picking_policy.md": ("policy", "picking", ["picking_recommendation", "policy_question"]),
    "inventory_risk_policy.md": ("policy", "inventory", ["inventory_risk", "risk_response_recommendation", "policy_question"]),
    "warehouse_operation_sop.md": ("sop", "common", ["risk_response_recommendation", "policy_question"]),
    "scoring_formula.md": ("formula", "common", ["policy_question"]),
    "wms_terms.md": ("glossary", "common", ["policy_question"]),
}

# 헤딩 부분문자열 → section id (docs/03 §5)
SECTION_MAP = {
    "동일 SKU": "same_sku_policy", "잔여용량": "capacity_policy", "거리": "distance_policy", "고회전": "fast_moving_policy",
    "피킹 시작": "picking_start_time", "예상 피킹": "picking_time_estimation", "우선순위": "picking_priority_policy",
    "위험등급": "risk_level", "Fallback": "forecast_fallback", "데이터 부족": "forecast_fallback",
    "재고 부족": "sop_stock_shortage", "CAPA": "sop_capacity_shortage", "Location 없음": "sop_no_available_location",
    "피킹지시 미발행": "sop_picking_not_issued", "입고 지연": "sop_inbound_delay", "출고확정 지연": "sop_shipping_confirm_delay",
    "적치 점수": "stocking_score_formula", "예상소진일": "stockout_formula",
}


def _section_id(domain: str, heading: str, idx: int) -> str:
    for key, sid in SECTION_MAP.items():
        if key in heading:
            return sid
    return f"{domain}_sec{idx}"


def load_chunks() -> list[dict]:
    docs_dir = Path(settings.rag_docs_dir)
    chunks = []
    for fname, (dtype, domain, intents) in FILE_META.items():
        fp = docs_dir / fname
        if not fp.exists():
            continue
        parts = re.split(r"(?m)^##\s+", fp.read_text(encoding="utf-8"))
        for idx, part in enumerate(parts[1:], 1):  # parts[0] = 제목(스킵)
            lines = part.strip().split("\n")
            heading = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            if not heading and not body:
                continue
            sid = _section_id(domain, heading, idx)
            summary = next((ln.strip() for ln in lines[1:]
                            if ln.strip() and not ln.strip().startswith(("```", "|", "-", "#"))), heading)
            chunks.append({
                "id": f"{fname}#{sid}", "source": fname, "document_type": dtype, "domain": domain,
                "section": sid, "answerable_intents": intents, "evidence_summary": summary[:120],
                "heading": heading, "text": f"[{fname} / {heading}]\n{body}",
            })
    return chunks
