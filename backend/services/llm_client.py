import os
import httpx
from langchain_openai import ChatOpenAI
from config import settings

def get_llm():
    """
    Client LLM ultra-robuste.
    On utilise un client HTTP standard pour éviter les erreurs de bibliothèque.
    """
    # Ce client ignore les erreurs de certificats SSL locales fréquentes sur Windows
    http_client = httpx.Client(verify=False)

    return ChatOpenAI(
        model=settings.llm_model_name,
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        http_client=http_client, # On injecte le client qui ignore le SSL
        max_retries=3,
        timeout=30.0,
        default_headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": settings.app_name,
        }
    )