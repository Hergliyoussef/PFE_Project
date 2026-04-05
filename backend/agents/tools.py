"""
Outils LangChain optimisés pour le PFE - Gestion de Projet IA.
Ajoute l'analyse du chemin critique, de la vélocité et de la performance.
"""
from langchain_core.tools import tool
import json, sys, os
from datetime import date, datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.redmine_client import redmine

# --- OUTILS DE BASE EXISTANTS ---

@tool
def get_project_metrics(project_id: str) -> str:
    """Retourne les métriques globales : avancement, retards, complétion."""
    try:
        data = redmine.compute_project_metrics(project_id)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_overdue_issues(project_id: str) -> str:
    """Liste les tâches dont la date d'échéance est dépassée."""
    try:
        issues = redmine.get_overdue_issues(project_id)
        result = [{
            "id": i["id"], "subject": i["subject"], "due_date": i.get("due_date"),
            "assignee": i.get("assigned_to", {}).get("name", "Non assigné"),
            "priority": i.get("priority", {}).get("name", ""),
            "progress": i.get("done_ratio", 0)
        } for i in issues]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- PRIORITÉ 1 : NOUVEAUX OUTILS STRATÉGIQUES ---

@tool
def get_critical_path(project_id: str) -> str:
    """
    Identifie le chemin critique : les tâches bloquantes qui retardent le projet.
    Analyse les relations 'precedes/follows' de Redmine.
    """
    try:
        issues = redmine.get_issues(project_id, status="open", include="relations")
        # On filtre les tâches qui ont des relations bloquantes
        critical_tasks = []
        for i in issues:
            relations = i.get("relations", [])
            is_blocking = any(rel["relation_type"] == "precedes" for rel in relations)
            if is_blocking and i.get("done_ratio", 0) < 100:
                critical_tasks.append({
                    "id": i["id"],
                    "subject": i["subject"],
                    "impact": "Bloque d'autres tâches",
                    "due_date": i.get("due_date"),
                    "assignee": i.get("assigned_to", {}).get("name", "?")
                })
        return json.dumps(critical_tasks, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_velocity_trend(project_id: str) -> str:
    """
    Analyse la tendance de vélocité sur les 3 derniers sprints.
    Prédit si le projet accélère ou ralentit.
    """
    try:
        versions = redmine.get_versions(project_id)
        # On prend les 3 dernières versions fermées ou en cours
        history = []
        for v in versions[-3:]:
            issues = redmine.get_issues(project_id, status="*", fixed_version_id=v["id"])
            total = len(issues)
            done = len([i for i in issues if i.get("done_ratio") == 100])
            velocity = (done / total * 100) if total > 0 else 0
            history.append({"sprint": v["name"], "completion_rate": round(velocity, 1)})
        
        # Calcul de la tendance
        trend = "stable"
        if len(history) >= 2:
            if history[-1]["completion_rate"] < history[-2]["completion_rate"]:
                trend = "décroissante (Alerte)"
            elif history[-1]["completion_rate"] > history[-2]["completion_rate"]:
                trend = "croissante (Optimisation)"
                
        return json.dumps({"history": history, "trend": trend}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_member_performance(project_id: str) -> str:
    """
    Compare le temps estimé vs temps passé par membre.
    Identifie les membres les plus efficaces ou ceux en difficulté.
    """
    try:
        issues = redmine.get_issues(project_id, status="*")
        performance = {}
        for i in issues:
            assignee = i.get("assigned_to", {}).get("name")
            if not assignee: continue
            
            estimated = i.get("estimated_hours", 0) or 0
            spent = i.get("spent_hours", 0) or 0
            
            if assignee not in performance:
                performance[assignee] = {"total_est": 0, "total_spent": 0, "tasks": 0}
            
            performance[assignee]["total_est"] += estimated
            performance[assignee]["total_spent"] += spent
            performance[assignee]["tasks"] += 1

        result = []
        for name, stats in performance.items():
            ratio = round(stats["total_est"] / stats["total_spent"], 2) if stats["total_spent"] > 0 else 1.0
            result.append({
                "name": name,
                "efficiency_ratio": ratio,
                "tasks_count": stats["tasks"],
                "status": "Haute performance" if ratio > 1.1 else "Sous-estimé" if ratio < 0.8 else "Nominal"
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- PRIORITÉ 2 : CLASSIFY_RISK AMÉLIORÉ ---

@tool
def classify_risk(project_id: str) -> str:
    """
    Calcule le risque avec les nouveaux critères PFE :
    Retards + Bugs + Vélocité + Chemin Critique.
    """
    try:
        metrics = redmine.compute_project_metrics(project_id)
        
        # Récupération des données pour les nouveaux critères
        path_data = json.loads(get_critical_path(project_id))
        velocity_data = json.loads(get_velocity_trend(project_id))
        
        # Calcul du score (Base 0.0 à 1.0)
        overdue_ratio = metrics["overdue_issues"] / max(metrics["total_issues"], 1)
        critical_penalty = 0.2 if len(path_data) > 0 else 0
        velocity_penalty = 0.15 if velocity_data.get("trend") == "décroissante (Alerte)" else 0
        
        score = (overdue_ratio * 0.4) + (critical_penalty) + (velocity_penalty) + ((100 - metrics["avg_progress"])/100 * 0.25)
        score = round(min(score, 1.0), 2)
        
        level = "faible" if score < 0.35 else "moyen" if score < 0.70 else "élevé"
        
        return json.dumps({
            "risk_level": level,
            "risk_score": score,
            "factors": {
                "critical_path_blocked": len(path_data) > 0,
                "velocity_trend": velocity_data.get("trend"),
                "overdue_count": metrics["overdue_issues"]
            }
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- LISTES D'OUTILS MISES À JOUR ---

ALL_TOOLS = [
    get_project_metrics, get_overdue_issues, get_critical_path,
    get_velocity_trend, get_member_performance, classify_risk
]

ANALYSE_TOOLS = ALL_TOOLS
DECISION_TOOLS = [get_critical_path, get_velocity_trend, classify_risk, get_member_performance]

# Liste pour l'agent Rapporteur (Synthèse et métriques)
RAPPORTEUR_TOOLS = [get_project_metrics, get_overdue_issues, get_velocity_trend, classify_risk]