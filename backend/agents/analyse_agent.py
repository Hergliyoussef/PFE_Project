"""
Agent Analyse — backend/agents/analyse_agent.py
Corrigé : utilise ToolNode de langgraph (pas execute_tools)
"""
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode   # ← correct
import logging, time, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.tools import ANALYSE_TOOLS   # ← pas execute_tools
from agents.state import AgentState

logger = logging.getLogger(__name__)

ANALYSE_SYSTEM = """Tu es l'Agent Analyse du projet Redmine.

PROJET ACTIF : {project_id}

IMPORTANT : Tu connais déjà le projet actif — c'est "{project_id}".
NE DEMANDE JAMAIS l'identifiant du projet à l'utilisateur.
Utilise DIRECTEMENT "{project_id}" dans tous tes appels d'outils.

Outils disponibles :
- get_project_metrics("{project_id}")    → métriques globales
- get_overdue_issues("{project_id}")     → tâches en retard
- get_not_started_issues("{project_id}") → tâches à 0%
- get_team_workload("{project_id}")      → charge équipe
- get_sprint_status("{project_id}")      → état des sprints
- classify_risk("{project_id}")          → score de risque

Réponds en français avec chiffres précis + recommandations + 🔴🟡🟢
"""

FALLBACK_MSG = {
    "planning":   "⚠️ Analyse planning indisponible. Réessayez dans 1 minute.",
    "risques":    "⚠️ Analyse risques indisponible. Réessayez dans 1 minute.",
    "ressources": "⚠️ Analyse charge indisponible. Réessayez dans 1 minute.",
    "default":    "⚠️ Agent Analyse indisponible. Réessayez dans 1 minute.",
}


def analyse_node(state: AgentState) -> AgentState:
    """Agent Analyse — corrigé avec ToolNode."""
    from services.llm_client import get_llm

    project_id = state["project_id"]

    last_question = next(
        (m.content for m in reversed(state["messages"])
         if isinstance(m, HumanMessage)), ""
    )

    for attempt in range(3):
        try:
            llm            = get_llm("analyse")
            llm_with_tools = llm.bind_tools(ANALYSE_TOOLS)
            tool_node      = ToolNode(ANALYSE_TOOLS)   # ← ToolNode correct

            messages = [
                SystemMessage(content=ANALYSE_SYSTEM.format(
                    project_id=project_id
                )),
                HumanMessage(content=(
                    f"Projet actif : {project_id}\n"
                    f"Intention : {state.get('intent', '')}\n"
                    f"Question : {last_question}\n\n"
                    f"Utilise le project_id='{project_id}' "
                    f"dans tous tes appels d'outils."
                )),
            ]

            # Boucle ReAct
            for _ in range(6):
                response = llm_with_tools.invoke(messages)
                messages.append(response)

                if response.tool_calls:
                    # Exécuter les outils via ToolNode
                    tool_results = tool_node.invoke({"messages": messages})
                    messages.extend(tool_results["messages"])
                else:
                    break

            final = messages[-1].content or ""
            if not final:
                raise ValueError("Réponse vide")

            logger.info(f"Agent Analyse — succès (tentative {attempt+1})")
            return {
                **state,
                "agent_result":  final,
                "final_answer":  final,
                "agent_status":  "success",
                "agent_error":   "",
                "retry_count":   attempt + 1,
                "messages":      state["messages"] + [AIMessage(content=final)],
            }

        except Exception as e:
            err = str(e)
            logger.warning(f"Agent Analyse tentative {attempt+1} : {err[:100]}")

            if "429" in err or "rate" in err.lower():
                wait = (attempt + 1) * 5
                logger.info(f"Attente {wait}s avant retry...")
                time.sleep(wait)
                continue
            elif attempt < 2:
                continue
            break

    intent   = state.get("intent", "default")
    fallback = FALLBACK_MSG.get(intent, FALLBACK_MSG["default"])
    logger.error("Agent Analyse — abandon après 3 tentatives")

    return {
        **state,
        "agent_result":  fallback,
        "final_answer":  fallback,
        "agent_status":  "error",
        "agent_error":   err if 'err' in dir() else "erreur inconnue",
        "retry_count":   3,
        "messages":      state["messages"] + [AIMessage(content=fallback)],
    }