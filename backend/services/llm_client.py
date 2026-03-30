import logging
import sys
import os
from langchain_openai import ChatOpenAI

# --- CORRECTIF DYNAMIQUE DES CHEMINS ---
# On s'assure que le dossier parent (backend) est dans le path pour trouver 'core'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# REMPLACE : from core.config import settings
# PAR :
try:
    from config import settings
except ImportError:
    import sys
    import os
    # On force Python à regarder dans le dossier parent (backend)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

def _build_llm(model: str) -> ChatOpenAI:
    """Construit un client ChatOpenAI avec vérification de sécurité."""
    api_key = settings.openrouter_api_key
    
    # Vérification stricte de la clé pour éviter l'erreur 500 silencieuse
    if not api_key or not str(api_key).startswith("sk-or"):
        logger.error("❌ Clé API OpenRouter invalide ou absente dans le .env")
        raise ValueError("API_KEY_MISSING")

    return ChatOpenAI(
        model           = model,
        api_key         = api_key,
        base_url        = OPENROUTER_BASE_URL,
        temperature     = 0.1,
        default_headers = {
            "HTTP-Referer": "http://localhost:8501",
            "X-Title":      settings.app_name,
        },
    )

def get_llm(agent: str = "supervisor") -> ChatOpenAI:
    """Retourne le LLM spécifique à l'agent demandé."""
    try:
        if agent == "analyse":
            model = settings.llm_analyse
        elif agent == "rapporteur":
            model = settings.llm_rapporteur
        else:
            model = settings.llm_supervisor
            
        logger.info(f"🤖 [LLM] Agent='{agent}' utilise modèle='{model}'")
        return _build_llm(model)
        
    except Exception as e:
        logger.error(f"❌ Erreur LLM pour {agent}: {e}. Bascule sur Fallback.")
        return _build_llm(settings.llm_fallback)