"""중앙 설정 로더. .env에서 API 키·모델·경로를 읽는다.

모델 결정(docs/01·03): 생성/추론 = Claude, 임베딩 = OpenAI text-embedding-3.
실제 키는 Phase 4(DES)·5(RAG)부터 필요하며, Phase 1~3 스캐폴딩은 키 없이 동작한다.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent  # smart_wms_agent_docs (docs/ 와 rag/ 가 있는 루트)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=APP_DIR / ".env", extra="ignore")

    # --- API 키/엔드포인트 (.env에서 주입; 채팅/코드에 하드코딩 금지) ---
    # 회사 게이트웨이 = Azure OpenAI 호환 → AzureOpenAI 클라이언트 사용(app/llm.py)
    openai_api_key: str = ""       # 회사 제공 게이트웨이 키(atl- 접두사)
    openai_base_url: str = ""      # azure_endpoint (예: https://skax.ai-talentlab.com)
    openai_api_version: str = "2024-12-01-preview"
    # 모델명 = Azure deployment 이름(회사 허용 모델명과 동일 가정)

    # --- 모델: OpenAI 단일 공급자 (생성+임베딩 통일, 회사 제공 키) ---
    openai_chat_model: str = "gpt-5.4"                  # 생성/추론/Tool (메인, 게이트웨이 가용 최신)
    openai_router_model: str = "gpt-4.1-mini"           # 라우터/파라미터 추출 (경량·빠름)
    openai_embed_model: str = "text-embedding-3-small"  # 임베딩(한국어 극대화 필요 시 -large)

    # --- 경로 ---
    db_path: Path = APP_DIR / "db" / "wms.db"
    seed_dir: Path = APP_DIR / "seed"
    rag_docs_dir: Path = PROJECT_ROOT / "rag"           # 정책 마크다운(저장소 루트 rag/)
    faiss_index_dir: Path = APP_DIR / "rag" / "index"

    # --- 시뮬레이션 기준일('오늘'). seed의 BASE_DATE와 동일해야 함 ---
    base_date: str = "2026-06-15"

    # --- DES 기본값 (docs/07_FORECAST_AND_SIMULATION) ---
    des_replications: int = 200
    des_near_future_days: int = 3
    des_random_seed: int = 42


settings = Settings()
