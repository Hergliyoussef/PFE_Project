"""
Agent Analyse — backend/agents/analyse_agent.py

Résilience :
- Si Redmine est inaccessible → réponse dégradée claire
- Si le LLM échoue → retry automatique (max 2 fois)
- Si retry échoue → message d'erreur propre sans crasher
- Les erreurs de cet agent n'affectent pas le Rapporteur
"""
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode
import logging, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.tools import ANALYSE_TOOLS
from agents.state import AgentState

logger = logging.getLogger(__name__)

ANALYSE_SYSTEM = """Tu es l'Agent Analyse du projet {project_id}.

Spécialisé dans : retards, risques, charge équipe, sprints.

Outils disponibles :
- get_project_metrics    → métriques globales
- get_overdue_issues     → tâches en retard
- get_not_started_issues → tâches à 0%
- get_team_workload      → charge par membre
- get_sprint_status      → état des sprints
- classify_risk          → score de risque

Instructions :
1. Utilise les outils pour collecter les données
2. Analyse et réponds en français avec chiffres + recommandations
3. Utilise 🔴 🟡 🟢 pour les niveaux de criticité
"""

# ── Réponses de secours si l'agent échoue ─────────────────────
FALLBACK_RESPONSES = {
    "planning":   "⚠️ Impossible d'analyser le planning pour l'instant. "
                  "Redmine est peut-être inaccessible. "
                  "Vérifiez que http://localhost:3000 est accessible et réessayez.",

    "risques":    "⚠️ L'analyse des risques est temporairement indisponible. "
                  "Impossible de contacter Redmine ou le modèle IA. "
                  "Réessayez dans quelques instants.",

    "ressources": "⚠️ Impossible de calculer la charge de l'équipe. "
                  "Vérifiez la connexion à Redmine et réessayez.",

    "default":    "⚠️ L'Agent Analyse a rencontré une erreur. "
                  "Le reste du système fonctionne normalement. "
                  "Essayez de reformuler votre question.",
}

MAX_RETRIES = 2


def _run_analyse(state: AgentState, llm_with_tools, tool_node) -> str:
    """Exécute la boucle ReAct de l'agent analyse."""
    last_question = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_question = msg.content
            break

    messages = [
        SystemMessage(content=ANALYSE_SYSTEM.format(
            project_id=state["project_id"]
        )),
        HumanMessage(
            content=f"Projet : {state['project_id']}\n"
                    f"Intention : {state['intent']}\n"
                    f"Question : {last_question}"
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


def analyse_node(state: AgentState) -> AgentState:
    """
    Nœud Agent Analyse avec résilience complète.
    Si cet agent échoue, l'erreur est capturée proprement
    et n'affecte pas les autres agents ni le superviseur.
    """
    from services.llm_client import get_llm

    attempt = 0
    last_error = ""

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            logger.info(f"Agent Analyse — tentative {attempt}/{MAX_RETRIES}")

            llm            = get_llm()
            llm_with_tools = llm.bind_tools(ANALYSE_TOOLS)
            tool_node      = ToolNode(ANALYSE_TOOLS)

            final = _run_analyse(state, llm_with_tools, tool_node)

            if not final:
                raise ValueError("Réponse vide de l'agent")

            # ✅ Succès
            logger.info("Agent Analyse — succès")
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
            # Redmine inaccessible
            last_error = f"Redmine inaccessible : {str(e)}"
            logger.warning(f"Agent Analyse — {last_error}")
            break  # Inutile de retry si Redmine est down

        except Exception as e:
            last_error = str(e)
            logger.error(f"Agent Analyse — erreur tentative {attempt} : {e}")
            if attempt < MAX_RETRIES:
                logger.info("Agent Analyse — nouvelle tentative...")
                continue
            break

    # ❌ Toutes les tentatives ont échoué → réponse dégradée
    intent   = state.get("intent", "default")
    fallback = FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES["default"])
    error_msg = f"{fallback}\n\n_Erreur technique : {last_error}_"

    logger.error(f"Agent Analyse — abandon après {attempt} tentatives : {last_error}")

    return {
        **state,
        "agent_result":  error_msg,
        "final_answer":  error_msg,
        "agent_status":  "error",
        "agent_error":   last_error,
        "retry_count":   attempt,
        "messages":      state["messages"] + [AIMessage(content=error_msg)],
    }
