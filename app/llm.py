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


def chat(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """간단 채팅 호출 → 응답 텍스트."""
    resp = get_client().chat.completions.create(
        model=model or settings.openai_chat_model, messages=messages, **kwargs)
    return resp.choices[0].message.content
