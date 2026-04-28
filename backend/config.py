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
    llm_supervisor:  str = "llama-3.3-70b-versatile"
    llm_analyse:     str = "llama-3.3-70b-versatile"
    llm_planning:    str = "llama-3.3-70b-versatile"
    llm_rapporteur:  str = "z-ai/glm-4.5-air:free"
    llm_fallback:    str = "openai/gpt-oss-120b:free"

    # ── Redmine ───────────────────────────────────────────────
    redmine_url:     str = "http://redmine:3000"
    redmine_api_key: str = ""
    
    # ── Redis ────────────────────────────────────────────────
    redis_host:     str = "redis"
    redis_port:     int = 6379
    redis_password: str = ""

    # ── PostgreSQL ────────────────────────────────────────────
    database_url: str = "postgresql://postgres:pfe_password_2026@db:5432/pm_chatbot"
    # ── App ───────────────────────────────────────────────────
    app_name:   str  = "PM Assistant - Youssef"
    secret_key: str  = "pmassistant_secret_key_2024"
    debug:      bool = True

    # ── Langfuse ──────────────────────────────────────────────
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url:   str = "https://cloud.langfuse.com"

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        extra             = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
