import logging
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

# --- SCHÉMAS ET CONFIGURATION ---

class RouterDecision(BaseModel):
    """Décision du superviseur sur l'agent à appeler."""
    action: Literal["analyse", "rapporteur", "hors_sujet"] = Field(description="L'agent spécialisé ou hors_sujet.")
    intent: str = Field(description="L'intention détectée.")
    message: str = Field(default="", description="Réponse directe si hors_sujet.")

parser = PydanticOutputParser(pydantic_object=RouterDecision)

SYSTEM_PROMPT = """Tu es l'intelligence centrale d'un chatbot de gestion de projet.
Ton rôle est UNIQUEMENT de choisir l'agent spécialisé (analyse, rapporteur) ou de BLOQUER le hors-sujet.

RÈGLE ABSOLUE POUR HORS-SUJET : 
Si la question ne concerne pas Redmine ou la gestion de projet, ne réponds JAMAIS à la question posée.
Ton seul message doit être : "Je suis un assistant spécialisé uniquement dans la gestion de projet et Redmine. Je ne peux pas répondre à cette demande." """

def get_router_chain():
    llm = get_llm("supervisor")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT + "\n{format_instructions}"),
        ("human", "Question : {question}"),
    ]).partial(format_instructions=parser.get_format_instructions())
    return prompt | llm | parser

# --- LOGIQUE DE ROUTAGE 100% LANGCHAIN (LCEL) ---

def _execute_routing(inputs: Dict[str, Any]) -> Dict[str, Any]:
    decision = inputs["decision"]
    state = inputs["state"]
    
    # On met à jour l'intention dans le state
    state["intent"] = decision.intent
    state["next_agent"] = decision.action
    
    if decision.action == "analyse":
        return analyse_node(state)
    elif decision.action == "rapporteur":
        return rapporteur_node(state)
    else:
        # Hors-sujet : l'IA répond elle-même
        return {
            **state, 
            "next_agent": "end", 
            "final_answer": decision.message or "Désolé, ce sujet n'est pas lié à la gestion de projet."
        }

# La chaîne maîtresse qui orchestre tout
master_chain = (
    RunnablePassthrough.assign(
        decision=lambda x: get_router_chain().invoke({"question": x["last_msg"]})
    ) 
    | RunnableLambda(_execute_routing)
)

def run_agent(question: str, project_id: str, user_id: str, user_role: str = "PROJECT_MANAGER", history: list = None, project_name: str = "") -> dict:
    """Point d'entrée unique utilisant la master_chain LangChain."""
    
    # Initialisation du State
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
        "last_msg": question # Pour la chaîne
    }

    try:
        # On laisse LangChain orchestrer le flux via la master_chain
        final_state = master_chain.invoke({"last_msg": question, "state": state})
        
        return {
            "answer": final_state.get("final_answer"),
            "intent": final_state.get("intent"),
            "agent_used": final_state.get("next_agent"),
            "data": final_state.get("data", {})
        }
    except Exception as e:
        logger.error(f"[MasterChain] Erreur : {e}")
        return {"answer": "Erreur technique, réessayez.", "intent": "error", "agent_used": "none", "data": {}}