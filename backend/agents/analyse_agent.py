from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode
import logging, time, sys, os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.tools import ANALYSE_TOOLS
from agents.state import AgentState

logger = logging.getLogger(__name__)

ANALYSE_SYSTEM = """Tu es l'Agent Analyse du projet Redmine.

NOM DU PROJET ACTIF : {project_name}
ID DU PROJET ACTIF : {project_id}

IMPORTANT : Utilise TOUJOURS le nom du projet "{project_name}" dans tes phrases au lieu de son ID technique.
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
    """Agent Analyse — Corrigé pour utiliser project_name et éviter les crashs."""
    from services.llm_client import get_llm

    # 🔑 Extraction sécurisée des données du projet
    project_id = str(state.get("project_id", "Inconnu"))
    project_name = str(state.get("project_name", f"Projet {project_id}"))

    last_question = next(
        (m.content for m in reversed(state["messages"])
         if isinstance(m, HumanMessage)), ""
    )

    for attempt in range(3):
        try:
            llm = get_llm("analyse")
            llm_with_tools = llm.bind_tools(ANALYSE_TOOLS)
            tool_node = ToolNode(ANALYSE_TOOLS)

            # 🛠️ Correction du formatage (project_name est maintenant inclus)
            messages = [
                SystemMessage(content=ANALYSE_SYSTEM.format(
                    project_id=project_id,
                    project_name=project_name
                )),
                HumanMessage(content=(
                    f"Nom du projet : {project_name}\n"
                    f"ID projet : {project_id}\n"
                    f"Intention : {state.get('intent', '')}\n"
                    f"Question : {last_question}\n\n"
                    f"Utilise le project_id='{project_id}' pour tes outils."
                )),
            ]

            # Boucle ReAct (Max 6 étapes)
            for _ in range(6):
                response = llm_with_tools.invoke(messages)
                messages.append(response)

                if response.tool_calls:
                    tool_results = tool_node.invoke({"messages": messages})
                    messages.extend(tool_results["messages"])
                else:
                    break

            final = messages[-1].content or ""
            if not final:
                raise ValueError("Réponse vide du LLM")

            logger.info(f"Agent Analyse — succès (tentative {attempt+1})")
            return {
                **state,
                "agent_result": final,
                "final_answer": final,
                "agent_status": "success",
                "agent_error":  "",
                "retry_count":  attempt + 1,
                "messages":     state["messages"] + [AIMessage(content=final)],
            }

        except Exception as e:
            err = str(e)
            logger.warning(f"Agent Analyse tentative {attempt+1} : {err[:100]}")
            
            # Gestion du Rate Limit (429)
            if "429" in err or "rate" in err.lower():
                wait = (attempt + 1) * 5
                time.sleep(wait)
                continue
            elif attempt < 2:
                continue
            break

    # 🚨 Gestion du Fallback si échec total
    intent = state.get("intent", "default")
    fallback = FALLBACK_MSG.get(intent, FALLBACK_MSG["default"])
    logger.error(f"Agent Analyse — échec critique : {err if 'err' in dir() else 'inconnu'}")

    return {
        **state,
        "agent_result": fallback,
        "final_answer": fallback,
        "agent_status": "error",
        "agent_error":  err if 'err' in dir() else "erreur inconnue",
        "retry_count":  3,
        "messages":     state["messages"] + [AIMessage(content=fallback)],
    }