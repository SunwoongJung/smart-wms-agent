"""Blackboard Auto Execution Layer — 기존 LangGraph 대화 에이전트와 분리된 자율 운영 레이어.

지식원(도메인 에이전트) = 블랙보드(DB) 상태를 보고 Action을 '제안'만 하고, 실제 상태 변경은
Action Executor 한 곳에서 정책·예약·락·트랜잭션·감사로그를 거쳐 수행한다.
"""
