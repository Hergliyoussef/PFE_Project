from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    question:   str
    project_id: str
    user_id:    Optional[str] = "chef_projet"
    history:    Optional[list] = []

class ChatResponse(BaseModel):
    answer:       str
    intent:       str
    agent_used:   str
    project_id:   str
    display_type: str
    data:         dict
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        try:
            from agents.supervisor_agent import run_agent
        except ImportError:
            # Fallback si lancé d'un autre dossier
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from agents.supervisor_agent import run_agent
        
        # 2. APPEL DE L'AGENT
        logger.info(f"🚀 Question reçue pour le projet {req.project_id}: {req.question}")
        
        result = run_agent(
            question=req.question,
            project_id=str(req.project_id),
            user_id=req.user_id,
            history=req.history
        )
        
        # 3. ANALYSE ET AFFICHAGE
        intent = result.get("intent", "general")
        display_type = _get_display_type(intent, req.question)
        data = _get_display_data(display_type, req.project_id)

        return ChatResponse(
            answer       = result.get("answer", "Désolé, l'agent n'a pas pu formuler de réponse."),
            intent       = intent,
            agent_used   = result.get("agent_used", "supervisor"),
            project_id   = req.project_id,
            display_type = display_type,
            data         = data,
        )

    except Exception as e:
        logger.error(f"❌ Erreur critique dans /chat : {str(e)}")
        import traceback
        logger.error(traceback.format_exc()) 
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")
    
def _get_display_type(intent: str, question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["graphique", "gantt", "planning", "sprint", "timeline"]):
        return "gantt"
    if any(k in q for k in ["risque", "risk", "danger", "critique"]):
        return "risk_table"
    if any(k in q for k in ["charge", "équipe", "workload", "ressource"]):
        return "workload"
    if any(k in q for k in ["rapport", "report", "synthèse", "résumé"]):
        return "report"
    if any(k in q for k in ["retard", "bloqué", "tâche", "overdue"]):
        return "issues_table"

    mapping = {
        "planning":   "gantt",
        "risques":    "risk_table",
        "ressources": "workload",
        "rapport":    "report",
        "general":    "text",
    }
    return mapping.get(intent, "text")


def _get_display_data(display_type: str, project_id: str) -> dict:
    try:
        from services.redmine_client import redmine

        if display_type == "gantt":
            return {
                "versions": redmine.get_versions(project_id),
                "issues": redmine.get_issues(project_id, status="*")
            }
        elif display_type == "risk_table":
            return {
                "issues": redmine.get_issues(project_id, status="open"),
                "metrics": redmine.compute_project_metrics(project_id)
            }
        elif display_type == "workload":
            return {
                "time_by_user": redmine.get_time_by_user(project_id),
                "members": redmine.get_project_members(project_id)
            }
        elif display_type == "report":
            return {
                "metrics": redmine.compute_project_metrics(project_id),
                "versions": redmine.get_versions(project_id),
                "news": redmine.get_news(project_id)
            }
        elif display_type == "issues_table":
            return {"issues": redmine.get_overdue_issues(project_id)}
            
        return {}
    except Exception as e:
        logger.warning(f"⚠️ Impossible de charger les data visuelles ({display_type}): {e}")
        return {}

@router.get("/projects/{project_id}/metrics")
async def get_metrics(project_id: str):
    try:
        from services.redmine_client import redmine
        m = redmine.compute_project_metrics(project_id)
        return {
            "avancement": m.get("avg_progress", 0),
            "retard":     m.get("overdue_issues", 0),
            "risques":    m.get("critical_issues", 3),
            "charge":     87,
            "delta":      8,
        }
    except Exception as e:
        logger.error(f"❌ Erreur GET /metrics : {e}")
        raise HTTPException(status_code=500, detail=str(e))