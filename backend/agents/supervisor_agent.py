import json
import logging
import traceback
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM = """Tu es le Superviseur IA expert. Projet : {project_id}
Réponds EXCLUSIVEMENT avec ce JSON :
{{
  "intent": "planning" ou "risques" ou "rapport" ou "ressources" ou "general",
  "next_agent": "analyse" ou "rapporteur",
  "reasoning": "pourquoi"
}}
Routage : 
- Choisis "analyse" si la question demande des chiffres, des tickets ou des données Redmine.
- Choisis "rapporteur" pour les salutations ou les résumés simples."""
def supervisor_node(state: AgentState) -> AgentState:
    llm = get_llm("supervisor")
    
    last_question = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            last_question = msg.content
            break

    try:
        response = llm.invoke([
            SystemMessage(content=SUPERVISOR_SYSTEM.format(
                user_id=state.get("user_id", "chef_projet"),
                project_id=state.get("project_id", "inconnu")
            )),
            HumanMessage(content=last_question),
        ])
        
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        parsed = json.loads(content)
        intent = parsed.get("intent", "general")
        next_agent = parsed.get("next_agent", "rapporteur")
        
        logger.info(f"🎯 Superviseur a décidé : {next_agent} (Intention: {intent})")
        
    except Exception as e:
        logger.error(f"⚠️ Erreur Parsing Superviseur : {e}")
        intent = "general"
        next_agent = "rapporteur"

    return {**state, "intent": intent, "next_agent": next_agent}

def route_after_supervisor(state: AgentState) -> Literal["analyse", "rapporteur"]:
    return state.get("next_agent", "rapporteur")

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("analyse", analyse_node)
    workflow.add_node("rapporteur", rapporteur_node)
    
    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor", 
        route_after_supervisor,
        {"analyse": "analyse", "rapporteur": "rapporteur"}
    )
    workflow.add_edge("analyse", END)
    workflow.add_edge("rapporteur", END)
    return workflow.compile()

graph = build_graph()

def run_agent(question: str, project_id: str, user_id: str = "chef_projet", history: list = None):
    # On force le project_id en string (très important pour Redmine)
    p_id = str(project_id)
    messages = list(history or [])
    messages.append(HumanMessage(content=question))
    
    # ⚠️ INITIALISATION COMPLÈTE DU STATE ⚠️
    # Toutes les clés définies dans ton AgentState DOIVENT être ici
    initial_state = {
        "messages": messages,
        "project_id": p_id,
        "user_id": user_id,
        "intent": "general",
        "next_agent": "rapporteur", # Valeur par défaut sécurisée
        "agent_result": "",
        "final_answer": "", 
        "agent_status": "pending",
        "agent_error": "",
        "retry_count": 0
    }

    try:
        # On lance le graphe
        result = graph.invoke(initial_state)
        
        # On vérifie que final_answer contient quelque chose
        answer = result.get("final_answer")
        if not answer:
            answer = "L'analyse est terminée, mais je n'ai pas pu formuler de texte. Vérifiez les logs."

        return {
            "answer": answer,
            "intent": result.get("intent"),
            "agent_used": result.get("next_agent"),
            "project_id": p_id
        }
    except Exception as e:
        # Capture l'erreur réelle dans le terminal pour ton diagnostic
        print(f"❌ CRASH DU GRAPHE : {str(e)}")
        import traceback
        traceback.print_exc() 
        return {
            "answer": f"Désolé Youssef, une erreur interne est survenue : {str(e)}",
            "intent": "error"
        }

    try:
        result = graph.invoke(initial_state)
        
        print(f"✅ RÉPONSE GÉNÉRÉE : {result.get('next_agent')}")
        
        return {
            "answer": result.get("final_answer") or "L'agent a terminé mais n'a pas produit de texte final.",
            "intent": result.get("intent", "general"),
            "agent_used": result.get("next_agent", "unknown"),
            "project_id": p_id,
        }
    except Exception as e:
        print(f"❌ CRASH DANS LE GRAPHE :")
        traceback.print_exc() # Affiche l'erreur exacte dans le terminal
        return {
            "answer": f"Erreur système : {str(e)}", 
            "intent": "error", 
            "agent_used": "none"
        }