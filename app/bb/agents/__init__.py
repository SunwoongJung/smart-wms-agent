"""도메인 에이전트(지식원) — 블랙보드 이벤트/상태를 보고 Action을 '제안'만 한다(DB write 없음).

각 에이전트는 handles(event_type)->bool, propose(event)->list[action_spec]를 제공.
action_spec = bb.actions.create(**spec)에 그대로 넘길 kwargs.
"""
from bb.agents import picking_agent

# 컨트롤 루프가 순회하는 등록 순서(의존 흐름: 입고→적치→피킹→출고→자원). 빌드 6~8은 Picking만.
REGISTRY = [picking_agent]
