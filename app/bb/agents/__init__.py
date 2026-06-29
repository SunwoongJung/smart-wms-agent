"""도메인 에이전트(지식원) — 블랙보드 이벤트/상태를 보고 Action을 '제안'만 한다(DB write 없음).

각 에이전트: handles(event_type)->bool, propose(event)->list[action_spec].
action_spec = bb.actions.create(**spec)에 그대로 넘길 kwargs.

연쇄는 executor가 성공 후 발생시키는 체인 이벤트(NEED_PUTAWAY, TASK_CREATED)로 이루어진다:
  입고 이벤트 → Inbound → (RECEIVED) → NEED_PUTAWAY → Putaway → (적치작업) → TASK_CREATED → Resource → 작업자 배정.
"""
from bb.agents import (inbound_agent, inventory_risk_agent, outbound_agent,
                       picking_agent, putaway_agent, resource_agent)

# 컨트롤 루프가 순회하는 등록 순서(의존 흐름: 입고→적치→피킹→출고→자원→위험).
REGISTRY = [inbound_agent, putaway_agent, picking_agent, outbound_agent, resource_agent, inventory_risk_agent]
