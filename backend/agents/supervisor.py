"""
Agent Superviseur — backend/agents/supervisor.py

Résilience :
- Si le LLM de classification échoue → routage par défaut (rapporteur)
- Si un agent tombe → l'autre continue normalement
- Chaque agent est isolé dans son propre try/except
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
import json, logging, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM = """Tu es le Superviseur IA de {user_id}.
Projet actif : {project_id}

Détecte l'intention et retourne un JSON strict :
{{
  "intent":     "planning|risques|rapport|ressources|general",
  "next_agent": "analyse|rapporteur",
  "reasoning":  "explication courte"
}}

Règles :
  planning   → analyse
  risques    → analyse
  ressources → analyse
  rapport    → rapporteur
  general    → rapporteur

Réponds UNIQUEMENT avec le JSON."""


def supervisor_node(state: AgentState) -> AgentState:
    """
    Détecte l'intention et route vers le bon agent.
    Si le LLM échoue → routage par défaut vers rapporteur.
    """
    from services.llm_client import get_llm

    last_question = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_question = msg.content
            break

    try:
        llm    = get_llm()
        system = SUPERVISOR_SYSTEM.format(
            user_id    = state.get("user_id", "chef_projet"),
            project_id = state["project_id"],
        )
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=last_question),
        ])
        parsed     = json.loads(response.content)
        intent     = parsed.get("intent",     "general")
        next_agent = parsed.get("next_agent", "rapporteur")
        logger.info(f"Superviseur → intent={intent}, agent={next_agent}")

    except Exception as e:
        # ❌ LLM ou JSON échoue → fallback par défaut
        logger.error(f"Superviseur — erreur classification : {e}")
        intent     = "general"
        next_agent = "rapporteur"

    return {**state, "intent": intent, "next_agent": next_agent}


def route_after_supervisor(
    state: AgentState,
) -> Literal["analyse", "rapporteur"]:
    return state.get("next_agent", "rapporteur")


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor",  supervisor_node)
    workflow.add_node("analyse",     analyse_node)
    workflow.add_node("rapporteur",  rapporteur_node)
    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"analyse": "analyse", "rapporteur": "rapporteur"}
    )
    workflow.add_edge("analyse",    END)
    workflow.add_edge("rapporteur", END)
    return workflow.compile()


graph = build_graph()


def run_agent(
    question:   str,
    project_id: str,
    user_id:    str  = "chef_projet",
    history:    list = None,
) -> dict:
    """Point d'entrée appelé par FastAPI."""
    from langchain_core.messages import HumanMessage
    messages = list(history or [])
    messages.append(HumanMessage(content=question))

    initial_state: AgentState = {
        "messages":    messages,
        "project_id":  project_id,
        "user_id":     user_id,
        "intent":      "",
        "next_agent":  "",
        "agent_result": "",
        "final_answer": "",
        "agent_status": "",
        "agent_error":  "",
        "retry_count":  0,
    }

    result = graph.invoke(initial_state)

    return {
        "answer":       result["final_answer"],
        "intent":       result["intent"],
        "agent_used":   result["next_agent"],
        "agent_status": result.get("agent_status", "success"),
        "project_id":   project_id,
    } 
