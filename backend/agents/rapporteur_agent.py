"""
Agent Rapporteur — backend/agents/rapporteur_agent.py

Résilience :
- Si Redmine est inaccessible → rapport partiel avec données disponibles
- Si le LLM échoue → retry automatique (max 2 fois)
- Si retry échoue → message d'erreur propre sans crasher
- Totalement indépendant de l'Agent Analyse
"""
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode
from datetime import date
import logging, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.tools import RAPPORTEUR_TOOLS
from agents.state import AgentState

logger = logging.getLogger(__name__)

RAPPORTEUR_SYSTEM = """Tu es l'Agent Rapporteur du projet {project_id}.
Aujourd'hui : {today}

Spécialisé dans : rapports de statut, synthèses, tableaux de bord.

Outils disponibles :
- get_project_metrics → métriques globales
- get_sprint_status   → état des sprints
- get_project_news    → actualités
- get_overdue_issues  → tâches en retard

Format de réponse :
📊 RAPPORT DE STATUT — {project_id} — {today}

Avancement global : X%
Sprint en cours : [nom] — X% complété

✅ Réalisations
⚠️  Points d'attention
🔴 Blocages critiques
👥 Équipe
📋 Actions prioritaires
"""

FALLBACK_RESPONSES = {
    "rapport":  "⚠️ Impossible de générer le rapport complet pour l'instant. "
                "Redmine est peut-être inaccessible. "
                "Vérifiez que http://localhost:3000 est accessible et réessayez.",

    "general":  "⚠️ Impossible de récupérer les informations du projet. "
                "Vérifiez la connexion à Redmine et réessayez.",

    "default":  "⚠️ L'Agent Rapporteur a rencontré une erreur. "
                "Le reste du système fonctionne normalement. "
                "Essayez de reformuler votre question.",
}

MAX_RETRIES = 2


def _run_rapporteur(state: AgentState, llm_with_tools, tool_node) -> str:
    """Exécute la boucle ReAct de l'agent rapporteur."""
    last_question = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_question = msg.content
            break

    today  = str(date.today())
    system = RAPPORTEUR_SYSTEM.format(
        project_id = state["project_id"],
        today      = today,
    )

    messages = [
        SystemMessage(content=system),
        HumanMessage(
            content=f"Projet : {state['project_id']}\n"
                    f"Intention : {state['intent']}\n"
                    f"Demande : {last_question}"
        ),
    ]

    for _ in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)
        if response.tool_calls:
            tool_results = tool_node.invoke({"messages": messages})
            messages.extend(tool_results["messages"])
        else:
            break

    return messages[-1].content if messages else ""


def rapporteur_node(state: AgentState) -> AgentState:
    """
    Nœud Agent Rapporteur avec résilience complète.
    Totalement indépendant de l'Agent Analyse —
    une erreur ici n'affecte pas l'Agent Analyse et vice versa.
    """
    from services.llm_client import get_llm

    attempt    = 0
    last_error = ""

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            logger.info(f"Agent Rapporteur — tentative {attempt}/{MAX_RETRIES}")

            llm            = get_llm()
            llm_with_tools = llm.bind_tools(RAPPORTEUR_TOOLS)
            tool_node      = ToolNode(RAPPORTEUR_TOOLS)

            final = _run_rapporteur(state, llm_with_tools, tool_node)

            if not final:
                raise ValueError("Réponse vide de l'agent")

            # ✅ Succès
            logger.info("Agent Rapporteur — succès")
            return {
                **state,
                "agent_result":  final,
                "final_answer":  final,
                "agent_status":  "success",
                "agent_error":   "",
                "retry_count":   attempt,
                "messages":      state["messages"] + [AIMessage(content=final)],
            }

        except ConnectionError as e:
            last_error = f"Redmine inaccessible : {str(e)}"
            logger.warning(f"Agent Rapporteur — {last_error}")
            break

        except Exception as e:
            last_error = str(e)
            logger.error(f"Agent Rapporteur — erreur tentative {attempt} : {e}")
            if attempt < MAX_RETRIES:
                logger.info("Agent Rapporteur — nouvelle tentative...")
                continue
            break

    # ❌ Toutes les tentatives ont échoué → réponse dégradée
    intent   = state.get("intent", "default")
    fallback = FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES["default"])
    error_msg = f"{fallback}\n\n_Erreur technique : {last_error}_"

    logger.error(f"Agent Rapporteur — abandon après {attempt} tentatives : {last_error}")

    return {
        **state,
        "agent_result":  error_msg,
        "final_answer":  error_msg,
        "agent_status":  "error",
        "agent_error":   last_error,
        "retry_count":   attempt,
        "messages":      state["messages"] + [AIMessage(content=error_msg)],
    }