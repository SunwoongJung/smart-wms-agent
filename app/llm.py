"""OpenAI(회사 Azure OpenAI 호환 게이트웨이) 클라이언트 헬퍼.

회사 게이트웨이는 Azure OpenAI 호환(경로 /openai/deployments/{deployment}/...,
api-version 필요)이므로 AzureOpenAI 클라이언트를 사용한다. 모델명 = Azure deployment 이름.
표준 OpenAI 엔드포인트(base_url 미설정)면 일반 OpenAI 클라이언트로 폴백한다.
"""
from functools import lru_cache

from config import settings


@lru_cache(maxsize=1)
def get_client():
    if settings.openai_base_url:
        from openai import AzureOpenAI
        return AzureOpenAI(
            api_key=settings.openai_api_key,
            azure_endpoint=settings.openai_base_url,
            api_version=settings.openai_api_version,
        )
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)


def embed(texts: list[str]) -> list[list[float]]:
    """문자열 리스트 → 임베딩 벡터 리스트."""
    resp = get_client().embeddings.create(model=settings.openai_embed_model, input=texts)
    return [d.embedding for d in resp.data]


def complete(messages: list[dict], model: str | None = None, node: str | None = None, **kwargs):
    """채팅 completion 단일 진입점 — 응답 객체 반환 + 토큰 usage를 트레이스에 기록.

    모든 LLM 호출이 이 래퍼를 거치게 해 토큰 계측을 한 곳에서 한다(게이트웨이가 usage를
    안 주면 조용히 건너뜀).
    """
    resp = get_client().chat.completions.create(
        model=model or settings.openai_chat_model, messages=messages, **kwargs)
    try:
        import trace_store
        u = getattr(resp, "usage", None)
        if u is not None:
            trace_store.record_tokens(node,
                                      int(getattr(u, "prompt_tokens", 0) or 0),
                                      int(getattr(u, "completion_tokens", 0) or 0),
                                      int(getattr(u, "total_tokens", 0) or 0))
    except Exception:
        pass
    return resp


def chat(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """간단 채팅 호출 → 응답 텍스트."""
    return complete(messages, model=model, **kwargs).choices[0].message.content
