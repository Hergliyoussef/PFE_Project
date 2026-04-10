"""
Superviseur — backend/agents/supervisor_agent.py
Architecture LangGraph corrigée et synchronisée avec FastAPI
"""
import json
import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Prompt NLP — Classification sémantique
# ──────────────────────────────────────────────────────────────
NLP_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Tu es un classificateur NLP expert en gestion de projet.
Ton rôle UNIQUE : analyser la SÉMANTIQUE de la question et la classer.

Projet actif : {project_id}
Nom du projet: {project_name}

═══════ RÈGLES DE CLASSIFICATION ═══════
[hors_sujet] — Santé, météo, cuisine, sport, personnel, politique
[clarification] — Concerne le projet mais trop vague.
[analyse] — Demande des DONNÉES, métriques, délais, retards ou KPIs.
[rapporteur] — Demande une SYNTHÈSE, un document ou des news générales.

FORMAT JSON STRICT :
{{
  "action": "hors_sujet" | "clarification" | "analyse" | "rapporteur",
  "intent": "planning" | "risques" | "rapport" | "hors_sujet" | "general",
  "confidence": 0.0 à 1.0,
  "message": "réponse directe si hors_sujet, sinon vide",
  "semantic_reason": "explication brève"
}}"""),
    ("human", "Question à classifier : {question}")
])

def _parse_llm_response(content: str) -> dict:
    """Parse la réponse JSON du LLM avec nettoyage robuste."""
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    start = content.find("{")
    end = content.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("Format JSON non trouvé")
    
    return json.loads(content[start:end])

# ──────────────────────────────────────────────────────────────
# NŒUD 1 : Superviseur NLP
# ──────────────────────────────────────────────────────────────
def supervisor_node(state: AgentState) -> AgentState:
    llm = get_llm("supervisor")

    # Initialisation de sécurité (évite UnboundLocalError)
    action = "rapporteur"
    intent = "general"
    confidence = 1.0
    message = ""

    last_question = next(
        (m.content for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)), ""
    )

    try:
        prompt_messages = NLP_CLASSIFICATION_PROMPT.format_messages(
            project_id=state.get("project_id", "inconnu"),
            project_name=state.get("project_name", "Projet"), 
            question=last_question,
        )
        response = llm.invoke(prompt_messages)
        parsed = _parse_llm_response(response.content)

        action = parsed.get("action", "rapporteur")
        intent = parsed.get("intent", "general")
        confidence = float(parsed.get("confidence", 0.5))
        message = parsed.get("message", "")

    except Exception as e:
        logger.warning(f"[Superviseur] Erreur parsing : {e}. Fallback rapporteur.")

    # Logique de filtrage / Court-circuit
    if action == "hors_sujet" or confidence < 0.3:
        reply = "Je suis votre assistant de gestion de projet. Je ne peux pas répondre à ce genre de question"
        return {
            **state, 
            "next_agent": "end", 
            "final_answer": reply, 
            "intent": "hors_sujet",
            "messages": state.get("messages", []) + [AIMessage(content=reply)]
        }

    return {
        **state,
        "next_agent": action,
        "intent": intent
    }

# ──────────────────────────────────────────────────────────────
# ROUTAGE ET CONSTRUCTION
# ──────────────────────────────────────────────────────────────
def route_after_supervisor(state: AgentState) -> Literal["analyse", "rapporteur", "end"]:
    next_agent = state.get("next_agent", "rapporteur")
    if next_agent == "end":
        return END
    return next_agent if next_agent in ["analyse", "rapporteur"] else "rapporteur"

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("analyse",    analyse_node)
    workflow.add_node("rapporteur", rapporteur_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"analyse": "analyse", "rapporteur": "rapporteur", END: END}
    )

    workflow.add_edge("analyse", END)
    workflow.add_edge("rapporteur", END)

    return workflow.compile()

graph = build_graph()

# ──────────────────────────────────────────────────────────────
# POINT D'ENTRÉE — Signature synchronisée avec FastAPI
# ──────────────────────────────────────────────────────────────
def run_agent(question: str, project_id: str, project_name: str = "Projet", user_id: str = "chef_projet", history: list = None) -> dict:
    """Lance le graphe avec la signature attendue par api/chat.py."""
    messages = list(history or [])
    messages.append(HumanMessage(content=question))

    initial_state: AgentState = {
        "messages": messages,
        "project_id": str(project_id),
        "project_name": str(project_name),
        "user_id": user_id,
        "intent": "general",
        "next_agent": "rapporteur",
        "final_answer": "",
        "agent_result": "",
        "agent_status": "pending",
        "agent_error": "",
        "retry_count": 0
    }

    try:
        result = graph.invoke(initial_state)
        
        # Récupération de la réponse filtrée ou du résultat agent
        answer = result.get("final_answer") or result.get("agent_result") or result.get("answer")
        
        if not answer:
            answer = "Désolé, je n'ai pas pu traiter votre demande concernant ce projet."

        intent = result.get("intent", "general")
        agent_used = "supervisor" if result.get("next_agent") == "end" else result.get("next_agent")

        logger.info(f"[LangGraph] Résultat : intent={intent}, agent={agent_used}")

        return {
            "answer": answer,
            "intent": intent,
            "agent_used": agent_used,
            "project_id": str(project_id),
            "display_type": "text" if intent == "hors_sujet" else "auto"
        }

    except Exception as e:
        logger.error(f"[LangGraph] Crash : {e}")
        return {"answer": f"Erreur système : {e}", "intent": "error", "agent_used": "none", "project_id": str(project_id)}