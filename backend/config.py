"""
Configuration — backend/config.py
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── OpenRouter ────────────────────────────────────────────
    llm_provider:       str = "openrouter"
    openrouter_api_key: str = ""

    # ── Groq ──────────────────────────────────────────────────
    groq_api_key: str = ""

    # ── Modèles par agent ─────────────────────────────────────
    # Déclarés vides par défaut pour forcer leur lecture exclusive depuis le .env
    llm_supervisor:  str = ""
    llm_analyse:     str = ""
    llm_planning:    str = ""
    llm_rapporteur:  str = ""
    llm_fallback:    str = ""

    # ── Redmine ───────────────────────────────────────────────
    redmine_url:     str = "http://redmine:3000"
    redmine_api_key: str = ""
    
    # ── Redis ────────────────────────────────────────────────
    redis_host:     str = "redis"
    redis_port:     int = 6379
    redis_password: str = ""

    # ── PostgreSQL ────────────────────────────────────────────
    # Valeur par défaut générique (sera écrasée par la valeur de DATABASE_URL dans votre .env)
    database_url: str = "postgresql://postgres:postgres@localhost:5432/pm_chatbot"
    # ── App ───────────────────────────────────────────────────
    app_name:   str  = "PM Assistant"
    secret_key: str  = "dev_default_secret_key_change_me_in_env"
    debug:      bool = True

    # ── Langfuse ──────────────────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url:   str = "https://cloud.langfuse.com"

    class Config:
        from pathlib import Path
        env_file          = Path(__file__).resolve().parent / ".env"
        env_file_encoding = "utf-8"
        extra             = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
