import logging
from datetime import date
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.prebuilt import ToolNode
from agents.tools import RAPPORTEUR_TOOLS
from agents.state import AgentState

logger = logging.getLogger(__name__)

# Prompt orienté communication et synthèse managériale
RAPPORTEUR_SYSTEM = """Tu es l'Agent Rapporteur expert pour le projet : {project_id}.
NOM DU PROJET ACTIF : {project_name}
ID DU PROJET ACTIF : {project_id}
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

💡 **PRÉDICTION IA** : 
(Basé sur les retards actuels, estime si la deadline du prochain sprint est réaliste)
"""

FALLBACK_MESSAGES = {
    "rapport": "⚠️ Désolé, je n'ai pas pu générer le rapport complet. Redmine est peut-être inaccessible.",
    "default": "⚠️ L'Agent Rapporteur est momentanément indisponible. L'analyse technique reste fonctionnelle."
}
def rapporteur_node(state: AgentState) -> AgentState:
    """Agent Rapporteur — Corrigé pour inclure project_name et éviter le crash."""
    from services.llm_client import get_llm
    from datetime import date

    # 🔑 1. Extraction sécurisée des données du state
    p_id = str(state.get("project_id", "Inconnu"))
    p_name = str(state.get("project_name", f"Projet {p_id}"))
    
    llm = get_llm("rapporteur")
    llm_with_tools = llm.bind_tools(RAPPORTEUR_TOOLS)
    tool_node = ToolNode(RAPPORTEUR_TOOLS)

    last_question = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), 
        "Générer un rapport d'activité"
    )

    # 🔑 2. CORRECTION DU FORMAT (On ajoute project_name ici)
    working_messages = [
        SystemMessage(content=RAPPORTEUR_SYSTEM.format(
            project_id=p_id, 
            project_name=p_name, 
            today=str(date.today())
        )),
        HumanMessage(content=f"Demande de synthèse pour {p_name} (ID: {p_id}) : {last_question}")
    ]

    attempt = 0
    max_retries = 2
    last_error = None  # BUG 2 — variable dédiée pour éviter NameError
    
    while attempt < max_retries:
        attempt += 1
        try:
            # Cycle Tool-Calling
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
            last_error = e  # BUG 2 — capturer l'erreur ici
            logger.error(f"❌ Erreur Agent Rapporteur (Tentative {attempt}/{max_retries}) : {e}")
            if attempt < max_retries:
                import time
                time.sleep(2)
                continue
            break

    # Gestion du Fallback
    intent = state.get("intent", "default")
    fallback_txt = FALLBACK_MESSAGES.get(intent, FALLBACK_MESSAGES["default"])
    
    return {
        **state,
        "final_answer": fallback_txt,
        "agent_status": "error",
        "agent_error": str(last_error) if last_error else "Timeout",  # BUG 2 — was: str(e) if 'e' in locals()
        "messages": state["messages"] + [AIMessage(content=fallback_txt)]
    }