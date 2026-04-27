import logging
import json
from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from services.llm_client import get_llm
from agents.state import AgentState

logger = logging.getLogger(__name__)

class ActionParams(BaseModel):
    name: str = Field(default="", description="Nom du projet (pour create_project)")
    identifier: str = Field(default="", description="Identifiant unique court, sans espaces ni caractères spéciaux (ex: mon-projet)")
    description: str = Field(default="", description="Description du projet")
    login: str = Field(default="", description="Login de l'utilisateur (pour create_user)")
    firstname: str = Field(default="", description="Prénom de l'utilisateur")
    lastname: str = Field(default="", description="Nom de famille de l'utilisateur")
    mail: str = Field(default="", description="Email de l'utilisateur")
    user_id: str = Field(default="", description="ID de l'utilisateur (pour delete_user ou add_project_member)")
    project_id: str = Field(default="", description="ID du projet (pour add_project_member)")
    role_ids: list[int] = Field(default_factory=list, description="Liste des IDs de rôles (ex: [3] pour Project Manager)")

class PlanningDecision(BaseModel):
    """La décision de l'agent de planification pour une opération d'écriture."""
    action_type: Literal["create_project", "create_user", "delete_user", "add_project_member", "unknown"] = Field(
        description="Le type d'action à effectuer sur Redmine."
    )
    parameters: ActionParams = Field(
        description="Les paramètres extraits de la demande de l'utilisateur."
    )
    description: str = Field(
        description="Une phrase explicative de l'action qui sera affichée à l'utilisateur."
    )

parser = PydanticOutputParser(pydantic_object=PlanningDecision)

SYSTEM_PROMPT = """Tu es un Agent de Planification spécialisé dans la préparation d'opérations d'écriture sur Redmine.
Ton rôle est de comprendre l'intention de l'utilisateur (ex: créer un projet, ajouter un utilisateur, supprimer un utilisateur, assigner un chef de projet) et d'en extraire les paramètres nécessaires.

RÈGLES IMPORTANTES :
1. Si l'utilisateur demande de créer un projet (ex: "Crée un projet Alpha"), génère un `identifier` en minuscules, sans espaces (ex: "alpha").
2. Si l'utilisateur demande de créer un utilisateur, invente un login/mail par défaut s'ils manquent (basé sur le nom/prénom).
3. Assure-toi de toujours répondre STRICTEMENT avec le format JSON demandé.

{format_instructions}
"""

def get_planning_chain():
    llm = get_llm("planning")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}")
    ]).partial(format_instructions=parser.get_format_instructions())
    
    return prompt | llm

def planning_node(state: AgentState) -> dict:
    """Nœud LangGraph/LangChain pour l'agent de planification."""
    logger.info("[Planning Node] Démarrage de la planification d'action...")
    last_msg = state.get("last_msg", "")
    chain = get_planning_chain()
    
    try:
        response = chain.invoke({"question": last_msg})
        content = response.content if hasattr(response, "content") else str(response)
        
        # Tentative de parsing
        try:
            decision = parser.parse(content)
        except Exception:
            import re
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                cleaned = match.group(0)
                decision = parser.parse(cleaned)
            else:
                raise
            
        return {
            **state,
            "next_agent": "end",
            "intent": "planning",
            # On renvoie la décision sérialisée dans final_answer (qui sera transformée en data par chat.py)
            "final_answer": decision.model_dump_json(),
            "data": decision.model_dump()
        }
        
    except Exception as e:
        logger.error(f"[Planning Node] Erreur : {e}")
        return {
            **state,
            "next_agent": "end",
            "final_answer": "Désolé, je n'ai pas pu planifier cette action. Erreur de compréhension."
        }
