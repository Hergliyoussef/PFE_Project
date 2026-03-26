import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

# Chemin absolu du dossier backend
BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # On définit juste les types. Pydantic remplira les valeurs depuis le .env automatiquement.
    
    # ── LLM OpenRouter ────────────────────────────────────────
    llm_provider: str
    openrouter_api_key: str
    llm_model_name: str

    # ── Redmine ───────────────────────────────────────────────
    redmine_url: str
    redmine_api_key: str

    # ── PostgreSQL ────────────────────────────────────────────
    database_url: str

    # ── App ───────────────────────────────────────────────────
    app_name: str
    secret_key: str
    debug: bool = True # On peut laisser une valeur par défaut non sensible

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    try:
        s = Settings()
        # On ne print plus la clé, juste un message de succès
        print(f"✅ Configuration chargée avec succès pour : {s.app_name}")
        return s
    except Exception as e:
        print(f"❌ ERREUR de configuration : {e}")
        # Ceci s'affichera si une variable manque dans ton .env
        raise e

settings = get_settings()