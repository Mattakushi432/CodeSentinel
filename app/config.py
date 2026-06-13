from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/codesentinel.db"
    secret_key: str = "change-me-in-production"
    base_url: str = "http://localhost:8000"

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5-coder:7b-instruct"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@codesentinel.dev"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""

    max_diff_lines: int = 500
    worker_poll_interval: int = 10
    llm_timeout: int = 300

    magic_link_expiry: int = 900  # 15 minutes in seconds

    # Fernet key for encrypting access tokens at rest (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    encryption_key: str = ""

    # Opt-in anonymous telemetry ping (set to "true" to enable)
    telemetry_enabled: bool = False

    llm_retry_attempts: int = 3
    llm_retry_backoff: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
