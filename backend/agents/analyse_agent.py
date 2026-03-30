import logging
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode
from agents.tools import ANALYSE_TOOLS
from agents.state import AgentState

logger = logging.getLogger(__name__)

# Prompt Système orienté KPI et Décision
ANALYSE_SYSTEM = """Tu es l'Agent Analyse expert pour le projet Redmine : {project_id}.
Ta mission : Extraire des données précises et fournir un diagnostic technique.

DOMAINES D'EXPERTISE :
1. Retards (Tickets Overdue)
2. Risques (Bloquants, priorités hautes)
3. Charge équipe (Workload par utilisateur)
4. Sprints et Versions (Respect des échéances)

CONSIGNES :
- Utilise TOUJOURS les outils pour obtenir des chiffres réels.
- Structure ta réponse : Faits -> Analyse -> Recommandation.
- Utilise des indicateurs visuels : 🔴 (Critique), 🟡 (Attention), 🟢 (OK).
- Réponds en français de manière concise et professionnelle.
"""

FALLBACK_MESSAGES = {
    "planning":   "⚠️ Analyse du planning indisponible. Veuillez vérifier les échéances directement sur Redmine.",
    "risques":    "⚠️ Analyse des risques en échec. Impossible de récupérer les tickets critiques actuellement.",
    "ressources": "⚠️ Analyse de charge indisponible. Les entrées de temps ne répondent pas.",
    "default":    "⚠️ L'Agent Analyse rencontre des difficultés techniques. Les données brutes restent accessibles via les graphiques."
}

def analyse_node(state: AgentState) -> AgentState:
    from services.llm_client import get_llm
    
    llm = get_llm("analyse")
    # Vérifie si ton LLM supporte bien bind_tools (certains modèles free ne le font pas)
    llm_with_tools = llm.bind_tools(ANALYSE_TOOLS)
    
    # Récupération de la question
    last_msg = state["messages"][-1].content
    
    working_messages = [
        SystemMessage(content=ANALYSE_SYSTEM.format(project_id=state["project_id"])),
        HumanMessage(content=last_msg)
    ]

    try:
        # On limite à 2-3 itérations pour éviter le timeout en mode "Free"
        for i in range(3):
            response = llm_with_tools.invoke(working_messages)
            working_messages.append(response)
            
            if response.tool_calls:
                # Exécution manuelle simplifiée pour le debug
                from agents.tools import execute_tools # Assure-toi d'avoir une fonction qui execute
                tool_results = execute_tools(response.tool_calls) 
                working_messages.extend(tool_results)
            else:
                break

        # CRUCIAL : Si le dernier message est un appel d'outil sans texte, 
        # on force une dernière réponse textuelle
        if not working_messages[-1].content:
            final_resp = llm.invoke(working_messages)
            final_content = final_resp.content
        else:
            final_content = working_messages[-1].content

        return {
            **state,
            "final_answer": final_content,
            "agent_status": "success",
            "messages": state["messages"] + [AIMessage(content=final_content)]
        }

    except Exception as e:
        logger.error(f"❌ Erreur critique Analyse : {e}")
        # On renvoie le fallback mais AVEC l'erreur pour débugger pendant ta démo
        intent = state.get("intent", "default")
        error_msg = FALLBACK_MESSAGES.get(intent, FALLBACK_MESSAGES["default"])
        return {
            **state,
            "final_answer": f"{error_msg} (Détail: {str(e)[:50]})",
            "agent_status": "error"
        }