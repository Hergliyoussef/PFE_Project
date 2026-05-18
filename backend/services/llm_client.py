import logging
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import settings

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
    )


def _groq(model: str):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model       = model,
        api_key     = settings.groq_api_key,
        base_url    = GROQ_BASE,
        temperature = 0.1,
    )


def _local(model: str):
    """Client Local Société (Ollama / Gateway compatible OpenAI)."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model       = model,
        api_key     = "not-needed",
        base_url    = settings.local_llm_url,
        temperature = 0.1,
    )


def get_llm(agent: str = "supervisor"):
    """
    Retourne le bon LLM selon l'agent (supporte OpenRouter, Groq ou Local Société).
    """
    # ── Option 1 : Mode Local Société ──────────────────────────
    if settings.llm_provider == "local":
        # En mode local, on force TOUS les agents à utiliser le modèle local de la société (gemma4:26b)
        # pour éviter d'essayer d'interroger Ollama avec des noms de modèles cloud LLaMA.
        model = settings.local_llm_model
        logger.info(f"[LLM-LOCAL] Agent '{agent}' -> Modèle Société '{model}' sur {settings.local_llm_url}")
        return _local(model)

    # ── Option 2 : Mode Standard (OpenRouter / Groq) ───────────
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