"""Tool 공통 유틸 — DB 조회 헬퍼, 실행 래퍼(tool_logs 기록), 산식 상수."""
import json
import uuid

from db.database import get_connection

# 피킹 산식 기본값 (rag/scoring_formula.md)
BASE_PICKING_MINUTES = 15
BUFFER_MINUTES = 10

# 적치 가중치 (rag/scoring_formula.md — 동일 SKU 가중치 우선)
W_SAME_SKU = 0.30
W_CAPACITY = 0.25
W_DISTANCE = 0.20
W_TURNOVER = 0.15
W_CONGESTION = 0.10


def q(sql: str, params: tuple = ()) -> list[dict]:
    """SELECT 실행 → dict 리스트."""
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def new_run_id() -> str:
    return "RUN-" + uuid.uuid4().hex[:8]


def run_tool(tool_name: str, fn, run_id: str | None = None, **kwargs):
    """Tool 실행을 tool_logs에 기록하며 호출(Phase 6 Agent에서 사용)."""
    run_id = run_id or new_run_id()
    try:
        out = fn(**kwargs)
        _log(run_id, tool_name, kwargs, out, True, None)
        return out
    except Exception as e:  # noqa: BLE001
        _log(run_id, tool_name, kwargs, None, False, str(e))
        raise


def _log(run_id, name, inp, out, success, err):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO tool_logs(run_id,tool_name,input_json,output_json,success,error_message)"
            " VALUES(?,?,?,?,?,?)",
            (run_id, name,
             json.dumps(inp, ensure_ascii=False, default=str),
             json.dumps(out, ensure_ascii=False, default=str) if out is not None else None,
             1 if success else 0, err),
        )
        conn.commit()
    finally:
        conn.close()
