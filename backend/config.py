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
    llm_supervisor:  str = "liquid/lfm-2.5-1.2b-thinking:free"
    llm_analyse:     str = "llama-3.3-70b-versatile"
    llm_rapporteur:  str = "arcee-ai/trinity-mini:free"
    llm_fallback:    str = "openai/gpt-oss-120b:free"

    # ── Redmine ───────────────────────────────────────────────
    redmine_url:     str = "http://localhost:3000"
    redmine_api_key: str = ""

    # ── PostgreSQL ────────────────────────────────────────────
    database_url: str = "postgresql://postgres:password@localhost:5432/pm_chatbot"

    # ── App ───────────────────────────────────────────────────
    app_name:   str  = "PM Assistant - Youssef"
    secret_key: str  = "pmassistant_secret_key_2024"
    debug:      bool = True

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        extra             = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()