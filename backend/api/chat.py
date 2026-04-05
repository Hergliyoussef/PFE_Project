from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 1. SCHÉMAS DE DONNÉES ─────────────────────────────────────

class ChatRequest(BaseModel):
    question:   str
    project_id: str
    project_name: str  # Pour l'affichage convivial dans l'IA
    user_id:    Optional[str] = "chef_projet"
    history:    Optional[list] = []

class ChatResponse(BaseModel):
    answer:       str
    intent:       str
    agent_used:   str
    project_id:   str
    display_type: str
    data:         dict

# ── 2. FONCTIONS UTILITAIRES (À définir AVANT les routes) ──────

def _get_display_type(intent: str, question: str) -> str:
    """Détermine quel composant graphique afficher selon l'intention."""
    q = question.lower()
    if any(k in q for k in ["graphique", "gantt", "planning", "sprint", "timeline"]):
        return "gantt"
    if any(k in q for k in ["risque", "risk", "danger", "critique"]):
        return "risk_table"
    if any(k in q for k in ["charge", "équipe", "workload", "ressource", "surcharg"]):
        return "workload"
    if any(k in q for k in ["rapport", "report", "synthèse", "résumé", "réunion"]):
        return "report"
    if any(k in q for k in ["retard", "bloqué", "tâche", "overdue"]):
        return "issues_table"
    
    mapping = {
        "planning":      "gantt",
        "risques":       "risk_table",
        "ressources":    "workload",
        "rapport":       "report",
        "hors_sujet":    "text",
        "clarification": "text",
        "general":       "text",
    }
    return mapping.get(intent, "text")


def _get_display_data(display_type: str, project_id: str) -> dict:
    """Récupère les données Redmine nécessaires pour le graphique."""
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
        logger.warning(f"Données visuelles indisponibles ({display_type}): {e}")
        return {}

# ── 3. ROUTES API ─────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        from agents.supervisor_agent import run_agent

        logger.info(f"Question reçue pour le projet {req.project_name} (ID: {req.project_id})")

        # Appel du moteur multi-agents
        result = run_agent(
            question   = req.question,
            project_id = str(req.project_id),
            project_name = str(req.project_name), 
            user_id    = req.user_id,
            history    = req.history,
        )

        intent     = result.get("intent",     "general")
        agent_used = result.get("agent_used", "supervisor")
        answer     = result.get("answer",     "")

        # Court-circuit pour réponses directes
        if intent in ("hors_sujet", "clarification") or agent_used == "supervisor":
            if answer and intent in ("hors_sujet", "clarification"):
                return ChatResponse(
                    answer       = answer,
                    intent       = intent,
                    agent_used   = "supervisor",
                    project_id   = req.project_id,
                    display_type = "text",
                    data         = {},
                )

        # Logique de routing visuel
        d_type = _get_display_type(intent, req.question)
        d_data = _get_display_data(d_type, req.project_id)

        return ChatResponse(
            answer       = answer or "Désolé, pas de réponse.",
            intent       = intent,
            agent_used   = agent_used,
            project_id   = req.project_id,
            display_type = d_type,
            data         = d_data,
        )

    except Exception as e:
        logger.error(f"Erreur critique dans /chat : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {str(e)}")

@router.get("/projects/{project_id}/metrics")
async def get_metrics(project_id: str):
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
async def get_alerts_endpoint(project_id: str):
    try:
        from services.monitor import get_alerts, clear_alerts
        alerts = get_alerts(project_id)
        clear_alerts(project_id)
        return {"project_id": project_id, "alerts": alerts}
    except Exception:
        return {"project_id": project_id, "alerts": []}