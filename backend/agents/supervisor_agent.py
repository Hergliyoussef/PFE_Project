"""
Agent Superviseur — backend/agents/supervisor_agent.py
"""
import json
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typer.cli import state

from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM = """Tu es le Superviseur IA d'un assistant de gestion de projet.
NOM DU PROJET ACTIF : {project_name}
ID DU PROJET ACTIF : {project_id}

CONSIGNE CRITIQUE :
- Ton unique but est de classer la requête. 
- Si l'utilisateur parle de lui (santé, humeur, vie privée) ou de sujets hors-travail -> ACTION "hors_sujet".
- INTERDICTION ABSOLUE de compatir ou de répondre au message de l'utilisateur (ex: ne dis pas "soignez-vous bien").
- Tu dois être un robot froid qui ne connaît que la gestion de projet.

PROJET ACTUEL : {project_name} (ID: {project_id})

JSON attendu :
{{
  "action": "hors_sujet",
  "intent": "hors_sujet",
  "message": "Je suis un assistant spécialisé en gestion de projet. Je ne peux pas traiter les demandes personnelles ou médicales.",
  "reasoning": "L'utilisateur parle de sa santé (hors-sujet)."
}}"""
def supervisor_node(state: AgentState) -> AgentState:
    llm = get_llm("supervisor")

    last_question = next(
        (m.content for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)), ""
    )

    try:
        response = llm.invoke([
            SystemMessage(content=SUPERVISOR_SYSTEM.format(
                project_id=state.get("project_id", "inconnu"),
                project_name=state.get("project_name", "Projet Actuel")
            )),
            HumanMessage(content=last_question),
        ])

        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed    = json.loads(content)
        action    = parsed.get("action",    "rapporteur")
        intent    = parsed.get("intent",    "general")
        message   = parsed.get("message",  "")
        reasoning = parsed.get("reasoning","")

        logger.info(f"Superviseur → action={action}, intent={intent} | {reasoning}")

    except Exception as e:
        logger.error(f"Superviseur erreur : {e}")
        action  = "rapporteur"
        intent  = "general"
        message = ""

   # ── 1. ON TESTE D'ABORD SI ON PEUT CLARIFIER (MÊME SI LE LLM DIT HORS_SUJET) ──
    # On vérifie si des mots-clés du projet sont présents
    keywords = ["membre", "projet", "tâche", "retard", "qui", "equipe", "équipe"]
    is_project_related = any(word in last_question.lower() for word in keywords)

    if action == "clarification" or (action == "hors_sujet" and is_project_related):
        reply = message if message else (
            f"Je suis prêt à vous aider sur le projet **{state.get('project_name')}**.\n"
            "Pourriez-vous préciser votre demande ? (ex: 'Quels sont les membres de l'équipe ?')"
        )
        return {
            **state,
            "intent": "clarification",
            "next_agent": "end",
            "final_answer": reply,
            "agent_result": reply,
            "agent_status": "success",
            "messages": state["messages"] + [AIMessage(content=reply)],
        }

    # ── 2. ENSUITE SEULEMENT, ON APPLIQUE LE HORS-SUJET STRICT ─────────────────
    if action == "hors_sujet":
        # Réponse de sécurité pour les vrais hors-sujets (Madrid, météo, etc.)
        reply = "Je suis votre assistant spécialisé en gestion de projet (Redmine). Je ne peux répondre qu'aux questions liées au projet, au planning ou à l'équipe."
        
        logger.warning(f"🛑 Accès hors-sujet bloqué définitivement : {last_question[:50]}...")
        
        return {
            **state,
            "intent": "hors_sujet",
            "next_agent": "end",
            "final_answer": reply,
            "agent_result": reply,
            "agent_status": "success",
            "messages": state["messages"] + [AIMessage(content=reply)],
        }
    # ── Routing normal ────────────────────────────────────────
    next_agent = action if action in ("analyse", "rapporteur") else "rapporteur"
    return {
        **state,
        "intent":     intent,
        "next_agent": next_agent,
    }


def route_after_supervisor(state: AgentState) -> Literal["analyse", "rapporteur"]:
    next_agent = state.get("next_agent", "rapporteur")
    if next_agent == "end":
        return END
    return next_agent


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor",  supervisor_node)
    workflow.add_node("analyse",     analyse_node)
    workflow.add_node("rapporteur",  rapporteur_node)
    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"analyse": "analyse", "rapporteur": "rapporteur", END: END}
    )
    workflow.add_edge("analyse",    END)
    workflow.add_edge("rapporteur", END)
    return workflow.compile()


graph = build_graph()


def run_agent(
    question:   str,
    project_id: str,
    project_name: str,
    user_id:    str  = "chef_projet",
    history:    list = None,
) -> dict:
    messages = list(history or [])
    messages.append(HumanMessage(content=question))

    initial_state: AgentState = {
        "messages":    messages,
        "project_id":  str(project_id),
        "user_id":     user_id,
        "project_name": str(project_name),
        "intent":      "general",
        "next_agent":  "rapporteur",
        "agent_result": "",
        "final_answer": "",
        "agent_status": "pending",
        "agent_error":  "",
        "retry_count":  0,
    }

    try:
        result = graph.invoke(initial_state)

        intent     = result.get("intent", "general")
        answer     = result.get("final_answer", "")
        agent_used = result.get("next_agent", "unknown")

        # Si hors_sujet ou clarification → agent_used = "supervisor"
        if intent in ("hors_sujet", "clarification"):
            agent_used = "supervisor"

        return {
            "answer":       answer or "Analyse terminée sans réponse.",
            "intent":       intent,
            "agent_used":   agent_used,
            "agent_status": result.get("agent_status", "success"),
            "project_id":   str(project_id),
        }

    except Exception as e:
        logger.error(f"Crash du graphe : {e}")
        import traceback; traceback.print_exc()
        return {
            "answer":     f"Erreur système : {str(e)}",
            "intent":     "error",
            "agent_used": "none",
            "project_id": str(project_id),
        }