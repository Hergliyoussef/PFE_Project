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
    password: str = Field(default="PFE@2024", description="Mot de passe initial de l'utilisateur (pour create_user). Défaut: PFE@2024")
    utilisateur: str = Field(default="", description="Nom ou login de l'utilisateur (pour suppression ou ajout au projet)")
    user_id: str = Field(default="", description="ID ou Nom de l'utilisateur (pour delete_user, add_project_member ou create_issue)")
    project_id: str = Field(default="", description="ID du projet (pour add_project_member)")
    role_ids: list[int] = Field(default_factory=list, description="Liste des IDs de rôles (ex: [3] pour Project Manager)")
    role: str = Field(default="", description="Nom du rôle (ex: Manager, Developpeur, Rapporteur)")
    copy_roles_from: str = Field(default="", description="Nom ou ID de l'utilisateur dont on doit copier les rôles (pour 'à sa place')")
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
    action_type: Literal["create_project", "create_user", "update_user", "delete_user", "delete_project", "add_project_member", "remove_project_member", "create_issue", "update_issue", "delete_issue", "unknown"] = Field(
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

# Format compact pour éviter l'erreur "looping content" de Groq
# (le format_instructions auto-généré est trop verbeux et répétitif)
COMPACT_FORMAT = """Réponds UNIQUEMENT avec ce JSON (sans markdown, sans explication) :
{"actions": [{"action_type": "<type>", "parameters": {"project_id": "", "user_id": "", "login": "", "firstname": "", "lastname": "", "mail": "", "password": "PFE@2024", "role": "", "role_ids": [], "subject": "", "description": "", "tracker_id": null, "priority_id": null, "estimated_hours": null, "done_ratio": null, "issue_id": null, "status_id": null, "notes": null, "identifier": "", "name": "", "utilisateur": "", "copy_roles_from": ""}, "description": "<description courte>"}], "summary": "<résumé>"}
Types valides: create_project, create_user, update_user, delete_user, delete_project, add_project_member, remove_project_member, create_issue, update_issue, delete_issue"""

SYSTEM_PROMPT = """Tu es un Agent de Planification spécialisé dans la préparation d'opérations d'écriture sur Redmine.
Ton rôle est de comprendre l'intention de l'utilisateur (ex: créer un projet, ajouter un utilisateur, supprimer un projet, assigner un chef de projet) et d'en extraire les paramètres nécessaires.

RÈGLES DE SÉCURITÉ ET RÔLES (TRÈS IMPORTANT) :
Tu dois respecter les permissions de l'utilisateur actuel. Son rôle est : {user_role}
1. CEO : A tous les droits. Peut créer/modifier/supprimer des projets, des utilisateurs et gérer n'importe quel membre.
2. PROJECT_MANAGER :
   - Peut créer, modifier ou supprimer des TÂCHES (tickets) uniquement sur son projet.
   - Peut ajouter ou modifier des MEMBRES uniquement sur son projet.
   - NE PEUT PAS supprimer de projet.
   - NE PEUT PAS créer ou modifier d'utilisateur global.
Si l'utilisateur demande une action non autorisée pour son rôle, réponds poliment que son rôle ({user_role}) ne lui permet pas de faire cela.

RÈGLE D'AMBIGUÏTÉ :
Si l'utilisateur exprime une intention d'action mais que des informations essentielles sont manquantes, génère quand même l'action avec des paramètres vides ("" ou null) pour afficher un formulaire interactif.

RÈGLES IMPORTANTES :
1. MULTI-ACTIONS : Prépare une liste complète si nécessaire (ex: Création projet + Membres).
2. UTILISATEURS : Création=create_user, Modification=update_user, Suppression=delete_user.
3. MEMBRES DU PROJET : Ajout=add_project_member (project_id + user_id), Retrait=remove_project_member.
4. TÂCHES : Création=create_issue, Modification=update_issue, Suppression=delete_issue (issue_id obligatoire).
5. tracker_id : 1=Anomalie, 2=Evolution, 3=Assistance.
6. priority_id : 1=Bas, 2=Normal, 3=Haut, 4=Urgent, 5=Immédiat.
7. GESTION UTILISATEURS : Pour add_project_member, mets simplement le nom/login dans `user_id`. Le backend cherchera automatiquement l'utilisateur dans Redmine et ne le créera QUE s'il n'existe pas. Ne génère create_user que si l'utilisateur demande EXPLICITEMENT de créer un nouveau compte.
8. RÔLES : Utilise le champ 'role' ("CEO", "Chef de projet", "Développeur", "Rapporteur"). IDs: CEO=6, Chef de projet=3, Developpeur=4, Rapporteur=5.
9. PROJET ACTUEL : Si non précisé, utilise : {current_project_id} ({current_project_name}).

{format_instructions}
"""

def get_planning_chain():
    llm = get_llm("planning")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}")
    ]).partial(format_instructions=COMPACT_FORMAT)
    
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
            "current_project_name": project_name,
            "user_role": state.get("user_role", "PROJECT_MANAGER")
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
            
        # Injection automatique du projet actif si manquant dans les actions (sauf actions globales)
        for action in decision.actions:
            if action.action_type not in ["create_user", "delete_user", "update_user"]:
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
        err_str = str(e)
        logger.error(f"[Planning Node] Erreur : {err_str}")
        
        # Détection spécifique de l'erreur "looping content" de Groq
        if "looping content" in err_str or "model output error" in err_str:
            logger.warning("[Planning Node] Erreur de contenu répétitif détectée par Groq. Reformulation du prompt...")
            return {
                **state,
                "next_agent": "end",
                "intent": "planning",
                "final_answer": (
                    "Le modèle IA a détecté une répétition dans sa réponse et a refusé de générer le plan. "
                    "Veuillez reformuler votre demande de façon plus concise (ex: 'Ajoute ismail au projet shopflow en tant que développeur')."
                )
            }
        
        return {
            **state,
            "next_agent": "end",
            "final_answer": "Désolé, je n'ai pas pu planifier cette action. Erreur de compréhension."
        }
