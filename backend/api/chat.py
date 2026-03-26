"""
Router FastAPI — backend/api/chat.py
Retourne maintenant answer + display_type + data
pour que Streamlit sache quoi afficher.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

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
    display_type: str   # "text" | "gantt" | "risk_table" | "workload" | "report"
    data:         dict  # données brutes pour le composant Streamlit


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        from agents.supervisor import run_agent
        result = run_agent(
            question   = req.question,
            project_id = req.project_id,
            user_id    = req.user_id,
            history    = req.history,
        )

        # Déterminer le display_type selon l'intention
        intent       = result.get("intent", "general")
        display_type = _get_display_type(intent, req.question)
        data         = _get_display_data(display_type, req.project_id)

        return ChatResponse(
            answer       = result["answer"],
            intent       = intent,
            agent_used   = result.get("agent_used", ""),
            project_id   = req.project_id,
            display_type = display_type,
            data         = data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_display_type(intent: str, question: str) -> str:
    """Détermine le type d'affichage selon l'intention et les mots-clés."""
    q = question.lower()

    # Mots-clés graphique / visuel
    if any(k in q for k in ["graphique", "gantt", "planning", "sprint", "timeline", "calendrier"]):
        return "gantt"

    if any(k in q for k in ["risque", "risk", "score", "danger", "critique"]):
        return "risk_table"

    if any(k in q for k in ["charge", "surcharge", "équipe", "workload", "ressource"]):
        return "workload"

    if any(k in q for k in ["rapport", "report", "statut", "synthèse", "résumé", "réunion"]):
        return "report"

    if any(k in q for k in ["retard", "en retard", "bloqué", "tâche"]):
        return "issues_table"

    # Par défaut selon l'intention
    mapping = {
        "planning":   "gantt",
        "risques":    "risk_table",
        "ressources": "workload",
        "rapport":    "report",
        "general":    "text",
    }
    return mapping.get(intent, "text")


def _get_display_data(display_type: str, project_id: str) -> dict:
    """Récupère les données brutes pour le composant Streamlit."""
    try:
        from services.redmine_client import redmine

        if display_type == "gantt":
            versions = redmine.get_versions(project_id)
            issues   = redmine.get_issues(project_id, status="*")
            return {"versions": versions, "issues": issues}

        elif display_type == "risk_table":
            issues  = redmine.get_issues(project_id, status="open")
            metrics = redmine.compute_project_metrics(project_id)
            return {"issues": issues, "metrics": metrics}

        elif display_type == "workload":
            time_by_user = redmine.get_time_by_user(project_id)
            members      = redmine.get_project_members(project_id)
            return {"time_by_user": time_by_user, "members": members}

        elif display_type == "report":
            metrics  = redmine.compute_project_metrics(project_id)
            versions = redmine.get_versions(project_id)
            news     = redmine.get_news(project_id)
            return {"metrics": metrics, "versions": versions, "news": news}

        elif display_type == "issues_table":
            overdue = redmine.get_overdue_issues(project_id)
            return {"issues": overdue}

        return {}
    except Exception:
        return {}


@router.get("/projects/{project_id}/metrics")
async def get_metrics(project_id: str):
    try:
        from services.redmine_client import redmine
        metrics = redmine.compute_project_metrics(project_id)
        return {
            "avancement": metrics["avg_progress"],
            "retard":     metrics["overdue_issues"],
            "risques":    3,
            "charge":     87,
            "delta":      8,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{project_id}")
async def get_alerts(project_id: str):
    from services.monitor import get_alerts, clear_alerts
    alerts = get_alerts(project_id)
    clear_alerts(project_id)
    return {"project_id": project_id, "alerts": alerts}