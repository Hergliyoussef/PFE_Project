"""
Agent Analyse — backend/agents/analyse_agent.py
100% LangChain — Pure LCEL + Manual Tool Loop (No LangGraph).
"""
import logging
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage
from agents.state import AgentState
from agents.tools import ANALYSE_TOOLS
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

# Map des outils pour exécution manuelle
TOOLS_MAP = {t.name: t for t in ANALYSE_TOOLS}

SYSTEM_TEMPLATE = """Tu es l'Agent Analyse expert des données Redmine du projet {project_id}.
Ton utilisateur actuel est : {user_role}.

RÈGLES CRITIQUES D'INTÉGRITÉ :
1. INTERDICTION FORMELLE d'inventer des noms de projets, des chiffres ou des dates.
2. Utilise UNIQUEMENT les noms de projets retournés par l'outil 'get_all_projects_status'.
3. Ne "traduis" pas les identifiants techniques (ex: si le projet s'appelle 'medicare', garde 'medicare', n'invente pas 'Sécurité médicale').
4. Si tu ne trouves pas de données via les outils pour une question spécifique, réponds explicitement que l'information n'est pas disponible dans Redmine au lieu d'imaginer une réponse.

CONSIGNES :
1. Utilise TOUJOURS project_id="{project_id}" dans tes appels d'outils.
2. Si l'utilisateur est CEO : Priorise les vues d'ensemble, les budgets et les risques stratégiques.
3. Si l'utilisateur est PROJECT_MANAGER : Sois précis, cite les numéros de tickets et la charge de travail.

Outils disponibles :
- get_project_metrics     → avancement global, retards
- get_overdue_issues      → tâches en retard
- get_not_started_issues   → tâches à 0%
- get_team_workload       → charge par membre
- get_sprint_status       → état des sprints
- classify_risk           → score de risque (0->1)
- get_all_projects_status → état de TOUS les projets (pour les vues d'ensemble)

5. MÉMOIRE : Utilise l'historique pour comprendre le contexte des questions de suivi (ex: "Pourquoi ?", "Détaille le premier").
Réponds en français avec des chiffres précis et utilise des indicateurs visuels (🔴🟡🟢).
Si on te demande un état des lieux de PLUSIEURS projets, utilise 'get_all_projects_status' et cite les noms EXACTS listés."""


FALLBACK = {
    "planning":   "⚠️ Analyse planning indisponible. Réessayez dans 1 minute.",
    "risques":    "⚠️ Analyse risques indisponible. Réessayez dans 1 minute.",
    "ressources": "⚠️ Analyse charge indisponible. Réessayez dans 1 minute.",
    "default":    "⚠️ Agent Analyse temporairement indisponible. Réessayez.",
}

def analyse_node(state: AgentState) -> dict:
    """
    Node LangChain pour l'analyse de données Redmine.
    Exécution manuelle des outils pour éviter la dépendance à LangGraph.
    """
    project_id = state.get("project_id", "default")
    user_role  = state.get("user_role", "PROJECT_MANAGER")
    
    llm = get_llm("analyse").bind_tools(ANALYSE_TOOLS)
    
    # Préparation des messages (System + Historique)
    working_messages = [
        SystemMessage(content=SYSTEM_TEMPLATE.format(project_id=project_id, user_role=user_role))
    ] + state["messages"]

    try:
        # Boucle ReAct manuelle
        for i in range(6):
            response = llm.invoke(working_messages)
            working_messages.append(response)
            
            if not response.tool_calls:
                break
                
            logger.info(f"[Analyse] Appel outils : {[t['name'] for t in response.tool_calls]}")
            
            for tool_call in response.tool_calls:
                tool = TOOLS_MAP.get(tool_call["name"])
                if tool:
                    result = tool.invoke(tool_call["args"])
                    working_messages.append(ToolMessage(
                        content=str(result), 
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"]
                    ))
                else:
                    working_messages.append(ToolMessage(
                        content=f"Erreur : Outil {tool_call['name']} non trouvé.",
                        tool_call_id=tool_call["id"]
                    ))

        final_content = working_messages[-1].content
        if not final_content:
            # Si le dernier message est un appel d'outil sans réponse texte, on force une synthèse
            final_content = "Voici les données collectées pour votre analyse."

        return {
            **state,
            "final_answer": final_content,
            "agent_status": "success",
            "messages": state["messages"] + [AIMessage(content=final_content)]
        }

    except Exception as e:
        logger.error(f"[Analyse] Erreur : {e}")
        err_msg = FALLBACK.get(state.get("intent", "default"), FALLBACK["default"])
        return {
            **state,
            "final_answer": err_msg,
            "agent_status": "error",
            "messages": state["messages"] + [AIMessage(content=err_msg)]
        }