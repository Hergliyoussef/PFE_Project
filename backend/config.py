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

    # ── Local LLM (Société / Ollama) ──────────────────────────
    local_llm_url:   str = "http://192.168.130.177:11434/v1"
    local_llm_model: str = "gemma4:26b"

    # ── Modèles par agent ─────────────────────────────────────
    # Déclarés vides par défaut pour forcer leur lecture exclusive depuis le .env
    llm_supervisor:  str = ""
    llm_analyse:     str = ""
    llm_planning:    str = ""
    llm_rapporteur:  str = ""
    llm_fallback:    str = ""

    # ── Redmine ───────────────────────────────────────────────
    redmine_url:     str = "http://127.0.0.1:3000"
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

    class Config:
        from pathlib import Path
        env_file          = Path(__file__).resolve().parent / ".env"
        env_file_encoding = "utf-8"
        extra             = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
