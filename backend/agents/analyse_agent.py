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
# --- DANS agents/analyse_agent.py ---

def analyse_node(state: AgentState) -> AgentState:
    from services.llm_client import get_llm
    
    project_id = str(state.get("project_id", "Inconnu"))
    project_name = str(state.get("project_name", f"Projet {project_id}"))
    intent = state.get("intent", "default")

    # On récupère la dernière question utilisateur
    last_question = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), 
        ""
    )

    for attempt in range(3):
        try:
            llm = get_llm("analyse")
            llm_with_tools = llm.bind_tools(ANALYSE_TOOLS)
            tool_node = ToolNode(ANALYSE_TOOLS)

            # 📋 Construction du contexte de l'agent
            messages = [
                SystemMessage(content=ANALYSE_SYSTEM.format(
                    project_id=project_id,
                    project_name=project_name
                )),
                HumanMessage(content=(
                    f"CONTEXTE PROJET : {project_name} (ID: {project_id})\n"
                    f"INTENTION : {intent}\n"
                    f"QUESTION : {last_question}"
                )),
            ]

            # 🔄 Boucle de Raisonnement (ReAct)
            for step in range(6):
                response = llm_with_tools.invoke(messages)
                
                # Si l'agent décide d'utiliser un outil
                if response.tool_calls:
                    # LOG DE DEBUG : Voir quel outil l'IA choisit
                    for call in response.tool_calls:
                        logger.info(f"🛠️ Agent Analyse utilise : {call['name']} avec {call['args']}")
                    
                    messages.append(response)
                    tool_results = tool_node.invoke({"messages": messages})
                    messages.extend(tool_results["messages"])
                else:
                    # L'IA a fini de réfléchir, elle donne sa réponse finale
                    messages.append(response)
                    break

            final_answer = messages[-1].content or "Désolé, je n'ai pas pu formuler de réponse."

            return {
                **state,
                "agent_result": final_answer,
                "final_answer": final_answer,
                "agent_status": "success",
                "messages": state["messages"] + [AIMessage(content=final_answer)],
            }

        except Exception as e:
            logger.error(f"❌ Erreur tentative {attempt+1} : {str(e)}")
            if attempt < 2: time.sleep(2)
            continue

    # 🚨 FALLBACK
    fallback = FALLBACK_MSG.get(intent, FALLBACK_MSG["default"])
    return {
        **state,
        "final_answer": fallback,
        "agent_status": "error",
        "messages": state["messages"] + [AIMessage(content=fallback)],
    }