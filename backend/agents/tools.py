"""
Outils LangChain utilisés par les agents.
Chaque outil appelle redmine_client et retourne un JSON string.
"""
from langchain_core.tools import tool
import json, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.redmine_client import redmine


@tool
def get_project_metrics(project_id: str) -> str:
    """
    Retourne les métriques globales d'un projet :
    avancement, issues en retard, issues non démarrées,
    taux de complétion, temps logué par membre.
    """
    try:
        data = redmine.compute_project_metrics(project_id)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_overdue_issues(project_id: str) -> str:
    """
    Retourne la liste des tâches ouvertes dont la date
    d'échéance est dépassée, avec le nombre de jours de retard.
    """
    try:
        issues = redmine.get_overdue_issues(project_id)
        result = []
        for i in issues:
            result.append({
                "id":        i["id"],
                "subject":   i["subject"],
                "due_date":  i.get("due_date"),
                "assignee":  i.get("assigned_to", {}).get("name", "Non assigné"),
                "priority":  i.get("priority", {}).get("name", ""),
                "progress":  i.get("done_ratio", 0),
                "tracker":   i.get("tracker", {}).get("name", ""),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_not_started_issues(project_id: str) -> str:
    """
    Retourne les tâches ouvertes à 0% d'avancement.
    Utile pour détecter les tâches bloquées ou oubliées.
    """
    try:
        issues = redmine.get_not_started_issues(project_id)
        result = []
        for i in issues:
            result.append({
                "id":       i["id"],
                "subject":  i["subject"],
                "due_date": i.get("due_date"),
                "assignee": i.get("assigned_to", {}).get("name", "Non assigné"),
                "priority": i.get("priority", {}).get("name", ""),
                "version":  i.get("fixed_version", {}).get("name", "Sans sprint"),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_team_workload(project_id: str) -> str:
    """
    Analyse la charge de travail par membre de l'équipe :
    heures loguées, nombre d'issues assignées, estimation surcharge.
    """
    try:
        time_by_user  = redmine.get_time_by_user(project_id)
        issues        = redmine.get_issues(project_id, status="open")
        members       = redmine.get_project_members(project_id)

        issues_by_user: dict[str, int] = {}
        for i in issues:
            name = i.get("assigned_to", {}).get("name", "Non assigné")
            issues_by_user[name] = issues_by_user.get(name, 0) + 1

        result = []
        for m in members:
            name  = m.get("user", {}).get("name", "?")
            hours = time_by_user.get(name, 0)
            nb    = issues_by_user.get(name, 0)
            load  = min(round((hours / 40) * 100, 1), 100)
            result.append({
                "name":          name,
                "hours_logged":  hours,
                "open_issues":   nb,
                "load_percent":  load,
                "status": "surchargé" if load > 85 else "normal" if load > 50 else "disponible",
            })
        result.sort(key=lambda x: x["load_percent"], reverse=True)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_project_news(project_id: str) -> str:
    """
    Retourne les dernières nouvelles et annonces du projet.
    """
    try:
        news = redmine.get_news(project_id)
        result = [{"title": n["title"], "summary": n.get("summary",""),
                   "created_on": n.get("created_on","")} for n in news[:5]]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_sprint_status(project_id: str) -> str:
    """
    Retourne l'état de chaque sprint/version du projet :
    issues terminées, en cours, en retard par sprint.
    """
    try:
        versions = redmine.get_versions(project_id)
        all_issues = redmine.get_issues(project_id, status="*")
        from datetime import date
        today = str(date.today())

        result = []
        for v in versions:
            vid   = v["id"]
            vname = v["name"]
            v_issues = [i for i in all_issues
                        if i.get("fixed_version", {}).get("id") == vid]
            done    = [i for i in v_issues if i.get("done_ratio", 0) == 100]
            overdue = [i for i in v_issues
                       if i.get("due_date","") < today
                       and i.get("done_ratio", 0) < 100]
            avg = (sum(i.get("done_ratio",0) for i in v_issues) / len(v_issues)
                   if v_issues else 0)
            result.append({
                "sprint":        vname,
                "status":        v.get("status","open"),
                "due_date":      v.get("due_date",""),
                "total_issues":  len(v_issues),
                "done":          len(done),
                "overdue":       len(overdue),
                "avg_progress":  round(avg, 1),
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def classify_risk(project_id: str) -> str:
    """
    Calcule et classifie le niveau de risque global du projet
    (faible / moyen / élevé) avec un score entre 0 et 1.
    """
    try:
        metrics = redmine.compute_project_metrics(project_id)
        issues  = redmine.get_issues(project_id, status="open")

        bugs_urgent = sum(
            1 for i in issues
            if i.get("tracker", {}).get("name","").lower() in ("anomalie","bug")
            and i.get("priority", {}).get("id", 0) >= 3
        )

        total    = max(metrics["total_issues"], 1)
        overdue  = metrics["overdue_issues"]
        progress = metrics["avg_progress"]

        score = (
            (overdue / total)         * 0.40 +
            (bugs_urgent / 10)        * 0.30 +
            ((100 - progress) / 100)  * 0.30
        )
        score = round(min(score, 1.0), 2)

        level = "faible" if score < 0.35 else "moyen" if score < 0.65 else "élevé"

        return json.dumps({
            "risk_level":    level,
            "risk_score":    score,
            "overdue_issues":  overdue,
            "critical_bugs":   bugs_urgent,
            "avg_progress":    progress,
            "details": {
                "retards_weight":  round((overdue / total) * 0.40, 3),
                "bugs_weight":     round((bugs_urgent / 10) * 0.30, 3),
                "progress_weight": round(((100 - progress) / 100) * 0.30, 3),
            }
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Liste de tous les outils disponibles
ALL_TOOLS = [
    get_project_metrics,
    get_overdue_issues,
    get_not_started_issues,
    get_team_workload,
    get_project_news,
    get_sprint_status,
    classify_risk,
]

ANALYSE_TOOLS    = [get_project_metrics, get_overdue_issues,
                    get_not_started_issues, get_team_workload,
                    get_sprint_status, classify_risk]

RAPPORTEUR_TOOLS = [get_project_metrics, get_sprint_status,
                    get_project_news, get_overdue_issues] 
