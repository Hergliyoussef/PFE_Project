"""
Router Chat sécurisé — backend/api/chat.py
Toutes les routes nécessitent un JWT valide.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question:    str
    project_id:  str
    project_name: Optional[str] = ""
    user_id:     Optional[str] = "chef_projet"
    history:     Optional[list] = []

class ChatResponse(BaseModel):
    answer:       str
    intent:       str
    agent_used:   str
    project_id:   str
    display_type: str
    data:         dict


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),   # ← JWT requis
):
    """
    Route protégée — nécessite Authorization: Bearer <token>
    Le user_id est extrait du JWT, pas de la requête.
    """
    # Utiliser l'identité du token JWT (plus fiable que req.user_id)
    authenticated_user_id = current_user.get("sub", req.user_id)

    logger.info(
        f"[Chat] {authenticated_user_id} → projet {req.project_id} : "
        f"{req.question[:50]}"
    )

    try:
        from agents.supervisor_agent import run_agent

        result = run_agent(
            question    = req.question,
            project_id  = str(req.project_id),
            project_name = str(req.project_name),
            user_id     = authenticated_user_id,
            history     = req.history,
        )

        intent = result.get("intent", "general")

        # Court-circuit hors_sujet / clarification
        if intent in ("hors_sujet", "clarification"):
            return ChatResponse(
                answer       = result.get("answer", ""),
                intent       = intent,
                agent_used   = "supervisor",
                project_id   = req.project_id,
                display_type = "text",
                data         = {},
            )

        display_type = _get_display_type(intent, req.question)
        data         = _get_display_data(display_type, req.project_id)

        return ChatResponse(
            answer       = result.get("answer", "Pas de réponse."),
            intent       = intent,
            agent_used   = result.get("agent_used", "supervisor"),
            project_id   = req.project_id,
            display_type = display_type,
            data         = data,
        )

    except Exception as e:
        logger.error(f"[Chat] Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/metrics")
async def get_metrics(
    project_id: str,
    current_user: dict = Depends(get_current_user)  # ← JWT requis
):
    try:
        from services.redmine_client import redmine
        m = redmine.compute_project_metrics(project_id)
        return {
            "avancement": m.get("avg_progress", 0),
            "retard":     m.get("overdue_issues", 0),
            "risques":    m.get("critical_issues", 0),
            "charge":     87,
            "delta":      8,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{project_id}")
async def get_alerts(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        from services.monitor import get_alerts, clear_alerts
        alerts = get_alerts(project_id)
        clear_alerts(project_id)
        return {"project_id": project_id, "alerts": alerts}
    except Exception:
        return {"project_id": project_id, "alerts": []}


def _get_display_type(intent: str, question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["gantt", "planning", "sprint", "timeline"]):
        return "gantt"
    if any(k in q for k in ["risque", "risk", "danger"]):
        return "risk_table"
    if any(k in q for k in ["charge", "équipe", "workload", "surcharg"]):
        return "workload"
    if any(k in q for k in ["rapport", "synthèse", "résumé", "réunion"]):
        return "report"
    if any(k in q for k in ["retard", "bloqué", "overdue"]):
        return "issues_table"
    mapping = {
        "planning":   "gantt",
        "risques":    "risk_table",
        "ressources": "workload",
        "rapport":    "report",
    }
    return mapping.get(intent, "text")


def _get_display_data(display_type: str, project_id: str) -> dict:
    if display_type == "text":
        return {}
    try:
        from services.redmine_client import redmine
        if display_type == "gantt":
            return {"versions": redmine.get_versions(project_id),
                    "issues":   redmine.get_issues(project_id, status="*")}
        elif display_type == "risk_table":
            return {"issues":  redmine.get_issues(project_id, status="open"),
                    "metrics": redmine.compute_project_metrics(project_id)}
        elif display_type == "workload":
            return {"time_by_user": redmine.get_time_by_user(project_id),
                    "members":      redmine.get_project_members(project_id)}
        elif display_type == "report":
            return {"metrics":  redmine.compute_project_metrics(project_id),
                    "versions": redmine.get_versions(project_id),
                    "news":     redmine.get_news(project_id)}
        elif display_type == "issues_table":
            return {"issues": redmine.get_overdue_issues(project_id)}
        return {}
    except Exception as e:
        logger.warning(f"Données visuelles indisponibles : {e}")
        return {}