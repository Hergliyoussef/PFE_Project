"""
Agent Rapporteur — backend/agents/rapporteur_agent.py
100% LangChain — Pure LCEL + Manual Tool Loop (No LangGraph).
"""
import logging
from datetime import date
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from agents.state import AgentState
from agents.tools import RAPPORTEUR_TOOLS
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

# Map des outils pour exécution manuelle
TOOLS_MAP = {t.name: t for t in RAPPORTEUR_TOOLS}

RAPPORTEUR_SYSTEM = """Tu es l'Agent Rapporteur expert pour le projet : {project_id}.
NOM DU PROJET ACTIF : {project_name}
ID DU PROJET ACTIF : {project_id}
Date du jour : {today}

RÈGLES D'INTÉGRITÉ :
1. NE JAMAIS inventer de noms de projets, de noms de membres ou de chiffres.
2. Utilise UNIQUEMENT les informations extraites via les outils.
3. Si une donnée est manquante (ex: pas de tâches terminées), indique "Aucune donnée enregistrée sur Redmine" au lieu de simuler des réalisations.

MISSION :
Transformer les données techniques en une synthèse claire et actionnable pour le management.

STRUCTURE DE RÉPONSE OBLIGATOIRE (Markdown) :
📊 **TITRE DU RAPPORT**
---
✅ **RÉALISATIONS RÉCENTES**
(Liste des points positifs ou tâches terminées réellement trouvées dans Redmine)

⚠️ **POINTS DE VIGILANCE & ALERTES**
(Utilise 🔴 pour critique, 🟡 pour attention. Cite les noms de projets ou de tickets réels.)

📋 **PROCHAINES ÉTAPES & ACTIONS**
(Actions concrètes basées sur les données)

💡 **PRÉDICTION IA** : 
(Basé sur les retards réels, estime si la deadline est réaliste)
"""

FALLBACK_MESSAGES = {
    "rapport": "⚠️ Désolé, je n'ai pas pu générer le rapport complet. Redmine est peut-être inaccessible.",
    "default": "⚠️ L'Agent Rapporteur est momentanément indisponible. L'analyse technique reste fonctionnelle."
}

def rapporteur_node(state: AgentState) -> AgentState:
    """Agent Rapporteur — 100% LangChain sans LangGraph."""
    
    p_id = str(state.get("project_id", "Inconnu"))
    p_name = str(state.get("project_name", f"Projet {p_id}"))
    
    llm = get_llm("rapporteur").bind_tools(RAPPORTEUR_TOOLS)
    
    # Préparation des messages
    working_messages = [
        SystemMessage(content=RAPPORTEUR_SYSTEM.format(
            project_id=p_id, 
            project_name=p_name, 
            today=str(date.today())
        ))
    ] + state["messages"]

    try:
        # Boucle ReAct manuelle
        for i in range(5):
            response = llm.invoke(working_messages)
            working_messages.append(response)
            
            if not response.tool_calls:
                break
            
            logger.info(f"📝 Agent Rapporteur collecte des données (itération {i+1})")
            
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

        final_text = working_messages[-1].content
        if not final_text:
            final_text = "Synthèse indisponible pour le moment."

        return {
            **state,
            "agent_result": final_text,
            "final_answer": final_text,
            "agent_status": "success",
            "messages": state["messages"] + [AIMessage(content=final_text)]
        }

    except Exception as e:
        logger.error(f"❌ Erreur Agent Rapporteur : {e}")
        intent = state.get("intent", "default")
        fallback_txt = FALLBACK_MESSAGES.get(intent, FALLBACK_MESSAGES["default"])
        
        return {
            **state,
            "final_answer": fallback_txt,
            "agent_status": "error",
            "agent_error": str(e),
            "messages": state["messages"] + [AIMessage(content=fallback_txt)]
        }