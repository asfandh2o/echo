from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    REDIS_URL: str

    SECRET_KEY: str
    ENCRYPTION_KEY: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    FRONTEND_URL: str = "http://localhost:3003"

    LLM_PROVIDER: str = "groq"
    OPENAI_API_KEY: str = ""
    OPENAI_ORG_ID: str = ""
    GROQ_API_KEY: str = ""

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str | List[str] = '["http://localhost:3000"]'

    CLASSIFICATION_MODEL: str = "gpt-4o-mini"
    DRAFTING_MODEL: str = "gpt-4o"
    SUMMARIZATION_MODEL: str = "gpt-4o"
    MAX_TOKENS_PER_USER_DAILY: int = 100000

    # HERA integration (for syncing tasks back)
    HERA_API_URL: str = "http://host.docker.internal:8001"
    HERA_API_KEY: str = ""

    AUTO_SEND_THRESHOLD: float = 0.95
    APPROVAL_THRESHOLD: float = 0.70
    SUGGESTION_THRESHOLD: float = 0.50

    EMAIL_FETCH_INTERVAL_MINUTES: int = 5
    MAX_EMAILS_PER_FETCH: int = 50
    STYLE_PROFILE_SAMPLE_SIZE: int = 200

    # Google Drive document indexing
    DRIVE_SCAN_INTERVAL_HOURS: int = 2
    DRIVE_MAX_FILE_SIZE_MB: int = 25
    DRIVE_CHUNK_SIZE_TOKENS: int = 800
    DRIVE_CHUNK_OVERLAP_TOKENS: int = 100

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v


settings = Settings()
