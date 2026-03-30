from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Les noms doivent être identiques au .env (en minuscules ou majuscules)
    openrouter_api_key: str
    redmine_url: str
    redmine_api_key: str
    
    # Modèles LLM
    llm_supervisor: str
    llm_analyse: str
    llm_rapporteur: str
    llm_fallback: str
    
    # Autres paramètres
    app_name: str = "PM Assistant"
    database_url: Optional[str] = None
    debug: bool = True

    # Configuration du chargement
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Pour ne pas planter avec les commentaires ou variables en trop
    )

settings = Settings()