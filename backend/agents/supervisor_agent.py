import logging
import json
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from agents.planning_agent import planning_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

REFUSAL_MSG = "Je suis un assistant spécialisé uniquement dans la gestion de projet et Redmine. Je ne peux pas répondre à cette demande."

# --- SCHÉMAS ET CONFIGURATION ---

class RouterDecision(BaseModel):
    """Décision du superviseur sur l'agent à appeler."""
    action: Literal["analyse", "rapporteur", "planning", "hors_sujet"] = Field(description="L'agent spécialisé ou hors_sujet.")
    intent: str = Field(description="L'intention détectée.")
    message: str = Field(default="", description="Réponse directe si hors_sujet.")

parser = PydanticOutputParser(pydantic_object=RouterDecision)

SYSTEM_PROMPT = f"""Tu es l'intelligence centrale d'un chatbot de gestion de projet.
Ton rôle est de choisir l'agent spécialisé (analyse, rapporteur) ou de gérer la conversation générale liée au projet.

RÈGLES DE CONVERSATION :
1. SALUTATIONS : Si l'utilisateur te dit bonjour ou te salue, réponds poliment (ex: "Bonjour ! Comment puis-je vous aider avec vos projets aujourd'hui ?") en utilisant l'action "hors_sujet".
2. ANALYSE : Pour les questions sur les données, les retards, les risques ou les calculs, utilise "analyse".
3. RAPPORT : Pour les résumés, les comptes-rendus ou les synthèses, utilise "rapporteur".
4. PLANIFICATION : Pour toute action de CRÉATION, AJOUT, SUPPRESSION, MODIFICATION (ex: "Crée un projet", "Ajoute un utilisateur"), utilise "planning".
5. HORS-SUJET TOTAL : Si la question n'a aucun lien avec le travail (ex: sport, cuisine), utilise "hors_sujet" et réponds : "{REFUSAL_MSG}"

Tu dois TOUJOURS répondre au format JSON."""

def get_router_chain():
    llm = get_llm("supervisor")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n{format_instructions}"),
        ("human", "Question : {question}"),
    ]).partial(format_instructions=parser.get_format_instructions())
    # On retire le parser de la chaîne brute pour gérer les erreurs manuellement
    return prompt | llm

# --- LOGIQUE DE ROUTAGE SÉCURISÉE ---

def _get_decision(question: str) -> RouterDecision:
    """Invoque l'LLM et tente de parser le JSON, avec repli sécurisé."""
    chain = get_router_chain()
    try:
        response = chain.invoke({"question": question})
        # Si la réponse est déjà un objet (certains LLMs le font avec bind_tools), on l'utilise
        content = response.content if hasattr(response, "content") else str(response)
        
        try:
            return parser.parse(content)
        except Exception:
            # Si le parsing échoue mais que le message a l'air d'une salutation ou d'une réponse textuelle, on le garde
            # Sinon, si c'est un refus connu ou un bug, on utilise le REFUSAL_MSG
            if "assistant spécialisé" in content or "pas répondre" in content:
                return RouterDecision(action="hors_sujet", intent="off_topic", message=REFUSAL_MSG)
            
            # Cas par défaut : on fait confiance au texte de l'IA s'il n'est pas trop long
            if len(content) < 200:
                return RouterDecision(action="hors_sujet", intent="general", message=content)
            
            return RouterDecision(action="hors_sujet", intent="off_topic", message=REFUSAL_MSG)
    except Exception as e:
        logger.error(f"[Router] Erreur invocation : {e}")
        return RouterDecision(action="hors_sujet", intent="error", message="Une erreur technique est survenue.")

def _execute_routing(inputs: Dict[str, Any]) -> Dict[str, Any]:
    decision = inputs["decision"]
    state = inputs["state"]
    
    state["intent"] = decision.intent
    state["next_agent"] = decision.action
    
    if decision.action == "analyse":
        return analyse_node(state)
    elif decision.action == "rapporteur":
        return rapporteur_node(state)
    elif decision.action == "planning":
        return planning_node(state)
    else:
        return {
            **state, 
            "next_agent": "end", 
            "final_answer": decision.message or "Désolé, ce sujet n'est pas lié à la gestion de projet."
        }

# La chaîne maîtresse
master_chain = (
    RunnablePassthrough.assign(
        decision=lambda x: _get_decision(x["last_msg"])
    ) 
    | RunnableLambda(_execute_routing)
)

def run_agent(question: str, project_id: str, user_id: str, user_role: str = "PROJECT_MANAGER", history: list = None, project_name: str = "") -> dict:
    state: AgentState = {
        "messages": list(history or []) + [HumanMessage(content=question)],
        "project_id": str(project_id),
        "project_name": project_name,
        "user_id": user_id,
        "user_role": user_role,
        "next_agent": "supervisor",
        "final_answer": "",
        "data": {},
        "intent": "general",
        "last_msg": question
    }

    try:
        final_state = master_chain.invoke({"last_msg": question, "state": state})
        return {
            "answer": final_state.get("final_answer"),
            "intent": final_state.get("intent"),
            "agent_used": final_state.get("next_agent"),
            "data": final_state.get("data", {})
        }
    except Exception as e:
        logger.error(f"[MasterChain] Erreur critique : {e}")
        return {"answer": "Erreur système, veuillez reformuler.", "intent": "error", "agent_used": "none", "data": {}}