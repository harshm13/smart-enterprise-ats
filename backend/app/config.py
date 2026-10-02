from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://ats:ats@localhost:5432/ats"

    # ── Redis / Celery ──────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Qdrant Vector DB ────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # ── AWS ─────────────────────────────────────────────────────────────────
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "ats-resumes-dev"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # ── Auth0 ────────────────────────────────────────────────────────────────
    AUTH0_DOMAIN: str = ""
    AUTH0_AUDIENCE: str = ""
    AUTH0_ALGORITHMS: list[str] = ["RS256"]

    # ── OpenAI ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""

    # ── App ─────────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SECRET_KEY: str = "change-me-in-production"

    # ── Celery ──────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── NLP ─────────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-mpnet-base-v2"
    SPACY_MODEL: str = "en_core_web_sm"
    PARSE_TIMEOUT_SECONDS: int = 60
    MAX_RESUME_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


settings = Settings()
