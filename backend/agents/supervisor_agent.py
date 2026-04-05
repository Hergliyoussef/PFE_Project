"""
Agent Superviseur — backend/agents/supervisor_agent.py
"""
import json
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM = """Tu es le Superviseur IA d'un assistant de gestion de projet.
NOM DU PROJET ACTIF : {project_name}
ID DU PROJET ACTIF : {project_id}

Analyse la question et retourne UN JSON avec "action" parmi :

1. "hors_sujet" → Uniquement si la question n'a AUCUN rapport avec le travail, Redmine ou le projet (ex: météo, cuisine , santé). 
   Retourne STRICTEMENT : "Je suis un assistant spécialisé en gestion de projet. Posez-moi une question à propos du projet."

2. "clarification" → La question concerne le projet mais est trop vague (ex: "fais quelque chose").
   NOTE : Si l'utilisateur demande le NOM ou l'ID du projet, RÉPONDS DIRECTEMENT dans "message" avec l'action "clarification" (ex: "Nous travaillons sur le projet {project_name}").

3. "analyse" → Demandes de données chiffrées : retards, risques, charge équipe, sprints, métriques.

4. "rapporteur" → Demandes de synthèse : rapport de statut, résumé, préparation de réunion.

JSON attendu :
{{
  "action": "hors_sujet|clarification|analyse|rapporteur",
  "intent": "hors_sujet|clarification|planning|risques|ressources|rapport|general",
  "message": "Ta réponse si l'action est hors_sujet ou clarification, sinon vide",
  "reasoning": "Pourquoi as-tu choisi cette action ?"
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

    # ── Hors sujet → réponse directe immédiate ────────────────
    if action == "hors_sujet":
        reply = message if message else (
            "Je suis votre assistant de gestion de projet. "
            "Je ne peux pas répondre à des questions non liées au projet. "
            "Posez-moi des questions sur le planning, les risques, "
            "l'équipe ou l'avancement du projet."
        )
        return {
            **state,
            "intent":       "hors_sujet",
            "next_agent":   "end",
            "final_answer": reply,
            "agent_result": reply,
            "agent_status": "success",
            "agent_error":  "",
            "retry_count":  0,
            "messages":     state["messages"] + [AIMessage(content=reply)],
        }

    # ── Clarification → demande précision ────────────────────
    if action == "clarification":
        reply = message if message else (
            "Pourriez-vous préciser votre demande ?\n"

        )
        return {
            **state,
            "intent":       "clarification",
            "next_agent":   "end",
            "final_answer": reply,
            "agent_result": reply,
            "agent_status": "success",
            "agent_error":  "",
            "retry_count":  0,
            "messages":     state["messages"] + [AIMessage(content=reply)],
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