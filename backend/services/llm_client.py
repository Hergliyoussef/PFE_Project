"""
Client LLM — backend/services/llm_client.py

Architecture 3 providers :
- Superviseur  → OpenRouter (modèle léger)
- Analyse      → Groq       (Llama 70B, 14400 req/jour)
- Rapporteur   → OpenRouter (génération texte)
- Fallback     → OpenRouter (gpt-oss-120b)

Zéro 429 pour l'Agent Analyse grâce à Groq.
"""
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
    """Client Groq — 14400 req/jour gratuit."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model       = model,
        api_key     = settings.groq_api_key,
        base_url    = GROQ_BASE,
        temperature = 0.1,
    )


def get_llm(agent: str = "supervisor"):
    """
    Retourne le bon LLM selon l'agent.

    supervisor  → OpenRouter léger
    analyse     → Groq Llama 70B (zéro 429)
    rapporteur  → OpenRouter
    fallback    → OpenRouter gpt-oss-120b
    """
    try:
        if agent == "analyse":
            # ── Groq pour l'Agent Analyse ─────────────────────
            # 14400 req/jour gratuites → zéro 429
            logger.info(f"[LLM] Agent Analyse → Groq '{settings.llm_analyse}'")
            return _groq(settings.llm_analyse)

        elif agent == "supervisor":
            logger.info(f"[LLM] Superviseur → OpenRouter '{settings.llm_supervisor}'")
            return _openrouter(settings.llm_supervisor)

        elif agent == "rapporteur":
            logger.info(f"[LLM] Rapporteur → OpenRouter '{settings.llm_rapporteur}'")
            return _openrouter(settings.llm_rapporteur)

        else:
            logger.info(f"[LLM] Fallback → OpenRouter '{settings.llm_fallback}'")
            return _openrouter(settings.llm_fallback)

    except Exception as e:
        # Si Groq échoue → fallback OpenRouter gpt-oss-120b
        logger.warning(
            f"[LLM] Agent '{agent}' échoue ({str(e)[:50]}), "
            f"bascule sur gpt-oss-120b"
        )
        return _openrouter(settings.llm_fallback)