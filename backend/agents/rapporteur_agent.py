import logging
from datetime import date
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode
from agents.tools import RAPPORTEUR_TOOLS
from agents.state import AgentState

logger = logging.getLogger(__name__)

# Prompt orienté communication et synthèse managériale
RAPPORTEUR_SYSTEM = """Tu es l'Agent Rapporteur expert pour le projet : {project_id}.
Date du jour : {today}

MISSION :
Transformer les données techniques en une synthèse claire et actionnable pour le management.

STRUCTURE DE RÉPONSE OBLIGATOIRE (Markdown) :
📊 **TITRE DU RAPPORT**
---
✅ **RÉALISATIONS RÉCENTES**
(Liste des points positifs ou tâches terminées)

⚠️ **POINTS DE VIGILANCE & ALERTES**
(Utilise 🔴 pour critique, 🟡 pour attention)

📋 **PROCHAINES ÉTAPES & ACTIONS**
(Ce qu'il faut faire maintenant)

---
*Note : Sois diplomate mais direct. Si les données manquent, mentionne-le clairement.*
"""

FALLBACK_MESSAGES = {
    "rapport": "⚠️ Désolé, je n'ai pas pu générer le rapport complet. Redmine est peut-être inaccessible.",
    "default": "⚠️ L'Agent Rapporteur est momentanément indisponible. L'analyse technique reste fonctionnelle."
}

def rapporteur_node(state: AgentState) -> AgentState:
    """Noeud de synthèse utilisant un modèle fluide (Mistral 7B / Trinity Mini)."""
    from services.llm_client import get_llm
    
    llm = get_llm("rapporteur")
    llm_with_tools = llm.bind_tools(RAPPORTEUR_TOOLS)
    tool_node = ToolNode(RAPPORTEUR_TOOLS)

    last_question = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), 
        "Générer un rapport d'activité"
    )

    # Contexte de travail local pour éviter de polluer l'historique global
    working_messages = [
        SystemMessage(content=RAPPORTEUR_SYSTEM.format(
            project_id=state["project_id"], 
            today=str(date.today())
        )),
        HumanMessage(content=f"Demande de synthèse pour {state['project_id']} : {last_question}")
    ]

    attempt = 0
    max_retries = 2
    
    while attempt < max_retries:
        attempt += 1
        try:
            # Cycle Tool-Calling (max 5 itérations pour collecter les infos de synthèse)
            for i in range(5):
                response = llm_with_tools.invoke(working_messages)
                working_messages.append(response)
                
                if response.tool_calls:
                    logger.info(f"📝 Agent Rapporteur collecte des données (itération {i+1})")
                    tool_output = tool_node.invoke({"messages": working_messages})
                    working_messages.extend(tool_output["messages"])
                else:
                    break

            final_text = working_messages[-1].content or ""
            if not final_text:
                raise ValueError("Réponse vide générée par le Rapporteur.")

            return {
                **state,
                "agent_result": final_text,
                "final_answer": final_text,
                "agent_status": "success",
                "retry_count": attempt,
                "messages": state["messages"] + [AIMessage(content=final_text)]
            }

        except Exception as e:
            logger.error(f"❌ Erreur Agent Rapporteur (Tentative {attempt}/{max_retries}) : {e}")
            if attempt < max_retries:
                continue
            break

    # Gestion du Fallback contextuel
    intent = state.get("intent", "default")
    fallback_txt = FALLBACK_MESSAGES.get(intent, FALLBACK_MESSAGES["default"])
    
    return {
        **state,
        "final_answer": fallback_txt,
        "agent_status": "error",
        "agent_error": str(e) if 'e' in locals() else "Timeout",
        "messages": state["messages"] + [AIMessage(content=fallback_txt)]
    }