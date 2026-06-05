from fastapi import APIRouter, Request, BackgroundTasks
import logging
from services.monitor import check_project

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/webhooks/redmine")
async def redmine_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Reçoit les notifications d'événements de Redmine (créations/mises à jour de tickets, etc.).
    Déclenche l'analyse de projet check_project en arrière-plan sans bloquer Redmine.
    """
    try:
        payload = await request.json()
        logger.info(f"[Webhook Redmine] Payload reçu : {payload}")
        
        project_id = None
        
        # 1. Extraction depuis l'issue s'il s'agit d'un webhook de ticket
        # Structure : {"issue": {"project": {"identifier": "shopflow", "id": 1}}}
        if "issue" in payload and isinstance(payload["issue"], dict):
            project = payload["issue"].get("project")
            if isinstance(project, dict):
                project_id = project.get("identifier") or project.get("id")
        
        # 2. Extraction directe du projet (si l'événement concerne directement un projet)
        # Structure : {"project": {"identifier": "shopflow", "id": 1}}
        if not project_id and "project" in payload and isinstance(payload["project"], dict):
            project_id = payload["project"].get("identifier") or payload["project"].get("id")
            
        # 3. Fallback au premier niveau du JSON
        if not project_id:
            project_id = payload.get("project_id") or payload.get("project_identifier")
            
        if project_id:
            project_id_str = str(project_id)
            logger.info(f"[Webhook Redmine] Déclenchement de check_project pour le projet : '{project_id_str}'")
            # Exécuter l'analyse en arrière-plan pour répondre immédiatement 200 OK à Redmine
            background_tasks.add_task(check_project, project_id_str)
            return {
                "status": "success",
                "message": f"Analyse planifiée pour le projet '{project_id_str}'"
            }
        else:
            logger.warning("[Webhook Redmine] Aucun identifiant de projet trouvé dans le payload.")
            return {
                "status": "ignored",
                "message": "Aucun identifiant de projet trouvé."
            }
            
    except Exception as e:
        logger.error(f"[Webhook Redmine] Erreur lors du traitement : {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }
