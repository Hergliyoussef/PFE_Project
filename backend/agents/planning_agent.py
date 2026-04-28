import logging
import json
from typing import Dict, Any, Literal, Optional
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
    utilisateur: str = Field(default="", description="Nom ou login de l'utilisateur (pour suppression ou ajout au projet)")
    user_id: str = Field(default="", description="ID ou Nom de l'utilisateur (pour delete_user, add_project_member ou create_issue)")
    project_id: str = Field(default="", description="ID du projet (pour add_project_member)")
    role_ids: list[int] = Field(default_factory=list, description="Liste des IDs de rôles (ex: [3] pour Project Manager)")
    subject: str = Field(default="", description="Sujet ou titre de la tâche (pour create_issue). Laisse vide si non précisé.")
    tracker_id: Optional[int] = Field(default=None, description="ID du Tracker (1=Anomalie, 2=Evolution, 3=Assistance). Laisse null si non précisé.")
    priority_id: Optional[int] = Field(default=None, description="ID de Priorité (1=Bas, 2=Normal, 3=Haut, 4=Urgent, 5=Immédiat). Laisse null si non précisé.")
    estimated_hours: Optional[float] = Field(default=None, description="Temps estimé en heures pour la tâche. Laisse null si non précisé.")
    done_ratio: Optional[int] = Field(default=None, description="Pourcentage d'avancement (0 à 100). Laisse null si non précisé.")
    issue_id: Optional[int] = Field(default=None, description="ID de la tâche à modifier (pour update_issue)")
    status_id: Optional[int] = Field(default=None, description="ID du statut (1=Nouveau, 2=En cours, 3=Résolu, 4=Commentaire, 5=Fermé, 6=Rejeté)")
    notes: Optional[str] = Field(default=None, description="Commentaire à ajouter sur la tâche (pour update_issue)")


class SingleAction(BaseModel):
    """Une action individuelle planifiée."""
    action_type: Literal["create_project", "create_user", "delete_user", "delete_project", "add_project_member", "create_issue", "update_issue", "unknown"] = Field(
        description="Le type d'action à effectuer sur Redmine."
    )
    parameters: ActionParams = Field(
        description="Les paramètres extraits pour cette action."
    )
    description: str = Field(
        description="Description courte de l'action (ex: 'Création du projet Alpha')."
    )

class PlanningDecision(BaseModel):
    """La décision globale de l'agent (peut contenir plusieurs actions)."""
    actions: list[SingleAction] = Field(description="Liste des actions à effectuer séquentiellement.")
    summary: str = Field(description="Résumé global de ce qui va être fait.")

parser = PydanticOutputParser(pydantic_object=PlanningDecision)

SYSTEM_PROMPT = """Tu es un Agent de Planification spécialisé dans la préparation d'opérations d'écriture sur Redmine.
Ton rôle est de comprendre l'intention de l'utilisateur (ex: créer un projet, ajouter un utilisateur, supprimer un projet, assigner un chef de projet) et d'en extraire les paramètres nécessaires.

RÈGLES IMPORTANTES :
1. MULTI-ACTIONS : Prépare une liste complète (actions) si nécessaire (ex: Création projet + Membres).
3. SUPPRESSION : Pour supprimer un projet, utilise `action_type="delete_project"` et mets l'identifiant dans `project_id`.
4. TÂCHES : Pour créer une tâche, utilise `action_type="create_issue"`. 
   - SI L'UTILISATEUR NE PRÉCISE PAS UNE INFORMATION, LAISSE LA VALEUR À `null` OU `""`. NE L'INVENTE PAS.
   - Le champ `subject` est le titre. 
   - Utilise le champ `user_id` pour la personne assignée.
   - `tracker_id` : 1 (Anomalie/Bug), 2 (Evolution/Feature), 3 (Assistance/Support).
   - `priority_id` : 1 (Bas), 2 (Normal), 3 (Haut), 4 (Urgent), 5 (Immédiat).
   - `estimated_hours` : Nombre d'heures estimées (ex: 2.5).
   - `description` : Description détaillée.
5. PROJETS : Utilise un `identifier` court (minuscules, sans espaces).
6. MODIFICATION DE TÂCHE : Utilise `action_type="update_issue"`. 
   - NE METS PAS de `project_id` sauf si l'utilisateur demande explicitement de changer le projet de la tâche.
   - L'utilisateur DOIT fournir le numéro du ticket (extrait-le dans `issue_id`).
   - S'il veut changer le pourcentage d'avancement (% réalisé), met la valeur dans `done_ratio` (ex: 50).
   - S'il veut changer le statut, met `status_id`.
   - S'il veut ajouter un commentaire, met `notes`.
7. GESTION DES UTILISATEURS (CRUCIAL) : 
   - NE PLANIFIE JAMAIS de `create_user` à moins que l'utilisateur ne demande EXPLICITEMENT de "créer un compte" ou "créer un utilisateur".
   - Si l'utilisateur donne un nom (ex: "Amira", "Jean") pour l'ajouter à un projet ou lui assigner une tâche, SUPPOSE QU'IL EXISTE DÉJÀ. Passe directement à `add_project_member` ou `create_issue` avec ce nom dans `user_id`.
7. CHAMPS OBLIGATOIRES : Ne laisse JAMAIS le champ `utilisateur` vide dans `add_project_member`. Utilise toujours le login ou le prénom de la personne.
8. RÔLES : Utilise STRICTEMENT ces IDs : 
   - Project Manager = 3
   - CEO = 6
   - Developpeur = 4
   - Rapporteur = 5
   - Non membre = 1
   - Anonyme = 2
6. PROJET ACTUEL : Si l'utilisateur ne précise pas de projet, utilise IMPÉRATIVEMENT l'identifiant suivant : {current_project_id}
7. Assure-toi de toujours répondre STRICTEMENT avec le format JSON demandé.

PROJET ACTUEL : {current_project_id} ({current_project_name})

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
    """LangChain pour l'agent de planification."""
    logger.info("[Planning Node] Démarrage de la planification d'action...")
    last_msg = state.get("last_msg", "")
    project_id = state.get("project_id", "inconnu")
    project_name = state.get("project_name", "")
    chain = get_planning_chain()
    
    try:
        response = chain.invoke({
            "question": last_msg,
            "current_project_id": project_id,
            "current_project_name": project_name
        })
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
            
        # Injection automatique du projet actif si manquant dans les actions
        for action in decision.actions:
            if not action.parameters.project_id:
                action.parameters.project_id = project_id
                logger.info(f"[Planning Node] Injection auto du projet '{project_id}' dans l'action {action.action_type}")

        return {
            **state,
            "next_agent": "end",
            "intent": "planning",
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
