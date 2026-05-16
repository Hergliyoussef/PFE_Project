import logging
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import settings

# ── Langfuse ──────────────────────────────────────────────────
import os
os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url

from langfuse.langchain import CallbackHandler
langfuse_handler = CallbackHandler() 


logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
GROQ_BASE       = "https://api.groq.com/openai/v1"


def _openrouter(model: str):
    """Client OpenRouter."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model       = model,
        api_key     = settings.openrouter_api_key,
        base_url    = OPENROUTER_BASE,
        temperature = 0.1,
        default_headers = {
            "HTTP-Referer": "http://localhost:8501",
            "X-Title":      settings.app_name,
        },
        callbacks=[langfuse_handler]
    )


def _groq(model: str):
    """Client Groq — 14400 req/jour gratuit."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model       = model,
        api_key     = settings.groq_api_key,
        base_url    = GROQ_BASE,
        temperature = 0.1,
        callbacks=[langfuse_handler]
    )


def get_llm(agent: str = "supervisor"):
    """
    Retourne le bon LLM selon l'agent.
    """
    model_map = {
        "supervisor": settings.llm_supervisor,
        "analyse":    settings.llm_analyse,
        "planning":   settings.llm_planning,
        "rapporteur": settings.llm_rapporteur,
        "fallback":   settings.llm_fallback
    }
    
    model = model_map.get(agent, settings.llm_fallback)
    
    def _get_client(m: str):
        # Si le modèle contient un '/' ou n'est pas un modèle Groq connu, on passe par OpenRouter
       
        is_groq_model = any(kw in m.lower() for kw in ["llama", "mixtral", "gemma"]) and "/" not in m
        
        if is_groq_model:
            logger.info(f"[LLM] {agent} -> Groq '{m}'")
            return _groq(m)
        else:
            logger.info(f"[LLM] {agent} -> OpenRouter '{m}'")
            return _openrouter(m)

    try:
        return _get_client(model)
    except Exception as e:
        logger.warning(f"[LLM] Agent '{agent}' échoue ({str(e)[:50]}), bascule sur fallback")
        return _get_client(settings.llm_fallback)