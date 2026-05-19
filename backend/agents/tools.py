"""
Outils LangChain optimisés pour le PFE - Gestion de Projet IA.
Ajoute l'analyse du chemin critique, de la vélocité et de la performance.
"""
from langchain_core.tools import tool
import json, sys, os
from datetime import date, datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.redmine_client import redmine, active_project_id_ctx, current_user_role_ctx

def resolve_authorized_project_id(project_id: str) -> str:
    """
    Vérifie et résout le project_id pour les outils.
    CEO -> Peut interroger n'importe quel projet (ex: gestpro depuis le chat de shopflow).
    PM/Autre -> Strictement restreint au projet de la session actuelle pour éviter les fuites.
    """
    import logging
    logger = logging.getLogger(__name__)
    role = current_user_role_ctx.get()
    active_project = active_project_id_ctx.get()
    
    logger.info(f"[Resolve Project ID] input project_id: {project_id}, role: {role}, active_project: {active_project}")
    
    if role == "CEO":
        return project_id
    
    # Restreindre strictement le PM à son projet actif pour éviter les fuites transverses
    if active_project:
        if project_id != active_project:
            raise PermissionError(f"Accès refusé. En tant que Chef de Projet, vous ne pouvez pas accéder aux données du projet '{project_id}'. Vos requêtes sont limitées au projet actif '{active_project}'.")
        return active_project
        
    return project_id

def is_authorized_project_manager(project_id: str) -> bool:
    """
    Vérifie si l'utilisateur actuel a le rôle de gestionnaire (Manager / Chef de projet...) sur le projet Redmine.
    """
    role = current_user_role_ctx.get()
    if role == "CEO":
        return True
        
    try:
        # Récupérer l'utilisateur actuel respectant l'impersonation
        curr = redmine._get("/users/current.json").get("user", {})
        user_id = curr.get("id")
        if not user_id:
            return False
            
        # Récupérer les membres du projet
        memberships = redmine.get_project_members(project_id)
        user_membership = next((m for m in memberships if m.get("user", {}).get("id") == user_id), None)
        if not user_membership:
            return False
            
        from services.auth import AUTHORIZED_ROLES
        allowed = {r.lower().strip() for r in AUTHORIZED_ROLES}
        user_roles = {r.get("name", "").lower().strip() for r in user_membership.get("roles", [])}
        return bool(user_roles & allowed)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Auth PM] Erreur vérification rôle sur {project_id}: {e}")
        return False
from db.session import SessionLocal
from db.models import Conversation as DBConv

# --- OUTILS DE BASE EXISTANTS ---

@tool
def get_project_metrics(project_id: str) -> str:
    """Retourne les métriques globales : avancement, retards, complétion.
    IMPORTANT : 'project_id' doit être l'identifiant technique (slug), ex: 'gestpro' et non 'GestPro'.
    """
    try:
        project_id = resolve_authorized_project_id(project_id)
        data = redmine.compute_project_metrics(project_id)
        # Ajout d'une note explicite contextuelle pour éviter que l'IA ne se trompe de métrique 
        # (ex: confondre completion_rate et avancement global)
        data["contexte_ia"] = "L'avancement général et officiel du projet est représenté UNIQUEMENT par la variable 'avg_progress'. Ne pas utiliser completion_rate comme avancement."
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_overdue_issues(project_id: str) -> str:
    """Liste les tâches dont la date d'échéance est dépassée.
    IMPORTANT : 'project_id' doit être l'identifiant technique (slug).
    """
    try:
        project_id = resolve_authorized_project_id(project_id)
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
        project_id = resolve_authorized_project_id(project_id)
        issues = redmine.get_issues(project_id, status="open")
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
        project_id = resolve_authorized_project_id(project_id)
        versions = redmine.get_versions(project_id)
        # On prend les 3 dernières versions fermées ou en cours
        history = []
        for v in versions[-3:]:
            # Récupérer les issues de cette version avec un filtre approprié
            all_version_issues = redmine.get_issues(project_id, status="*")
            # Filtrer manuellement par version_id
            issues = [i for i in all_version_issues if i.get("fixed_version", {}).get("id") == v["id"]]
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
        project_id = resolve_authorized_project_id(project_id)
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
        project_id = resolve_authorized_project_id(project_id)
        metrics = redmine.compute_project_metrics(project_id)
        
        # Récupération des données pour les nouveaux critères
        # BUG 7 — utiliser .invoke() pour appeler correctement les objets @tool LangChain
        path_data = json.loads(get_critical_path.invoke({"project_id": project_id}))
        velocity_data = json.loads(get_velocity_trend.invoke({"project_id": project_id}))
        
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

@tool
def get_project_issues(project_id: str, status: str = "open") -> str:
    """Liste les tickets (tâches) d'un projet avec la possibilité de filtrer par statut.
    'status' peut être 'open' (tous les tickets ouverts), 'closed' (fermés), '*' (tous), ou un nom de statut spécifique (ex: 'Nouveau', 'En cours', 'Résolu', 'Fermé').
    IMPORTANT : 'project_id' doit être l'identifiant technique (slug).
    """
    try:
        project_id = resolve_authorized_project_id(project_id)
        import logging
        logger = logging.getLogger(__name__)
        
        status_param = status
        normalized_status = str(status).lower().strip()
        
        if normalized_status not in ["open", "closed", "*"]:
            try:
                data = redmine._get("/issue_statuses.json")
                statuses = data.get("issue_statuses", [])
                found = False
                for s in statuses:
                    if s.get("name", "").lower().strip() == normalized_status:
                        status_param = str(s["id"])
                        found = True
                        break
                if not found:
                    for s in statuses:
                        if normalized_status in s.get("name", "").lower().strip():
                            status_param = str(s["id"])
                            found = True
                            break
            except Exception as exc:
                logger.error(f"Erreur lors de la récupération des statuts : {exc}")
                
        issues = redmine.get_issues(project_id, status=status_param)
        result = [{
            "id": i["id"],
            "subject": i["subject"],
            "status": i.get("status"),
            "assignee": i.get("assigned") or "Non assigné",
            "priority": i.get("priority") or "Normal",
            "progress": i.get("done_ratio", 0),
            "due_date": i.get("due_date")
        } for i in issues]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def get_all_projects_status() -> str:
    """Retourne l'état de TOUS les projets : avancement, retards, et alertes."""
    try:
        projects = redmine.get_projects()
        results = []
        for p in projects:
            try:
                # Filtrer les projets pour lesquels l'utilisateur n'est pas un Manager autorisé
                if not is_authorized_project_manager(p["identifier"]):
                    continue
                # Calcul rapide des métriques pour chaque projet
                m = redmine.compute_project_metrics(p["identifier"])
                results.append({
                    "id": p["id"],
                    "identifier": p["identifier"],
                    "name": p["name"],
                    "progress": m["avg_progress"],
                    "overdue_issues": m["overdue_issues"],
                    "critical_issues": m.get("critical_issues_count", 0)
                })
            except Exception:
                continue
        # Trier par nombre de retards
        results.sort(key=lambda x: x["overdue_issues"], reverse=True)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})



@tool
def delete_project_conversations(project_id: str, user_id: int) -> str:
    """
    Supprime définitivement TOUTES les conversations de l'utilisateur pour un projet spécifique.
    À utiliser uniquement si l'utilisateur demande explicitement de 'supprimer', 'effacer' ou 'nettoyer' son historique.
    """
    db = SessionLocal()
    try:
        project_id = resolve_authorized_project_id(project_id)
        query = db.query(DBConv).filter(
            DBConv.user_id == user_id,
            DBConv.id.like(f"conv_{user_id}_{project_id}_%")
        )
        count = query.count()
        if count == 0:
            return f"Aucune conversation trouvée pour le projet '{project_id}'."
        
        query.delete(synchronize_session=False)
        db.commit()
        return f"Succès : {count} conversation(s) supprimée(s) pour le projet '{project_id}'."
    except Exception as e:
        db.rollback()
        return f"Erreur lors de la suppression : {str(e)}"
    finally:
        db.close()


@tool
def get_sprint_status(project_id: str) -> str:
    """Retourne l'état d'avancement de chaque sprint/version du projet,
    avec le nombre de tâches totales, fermées, et ouvertes pour chaque sprint.
    IMPORTANT : 'project_id' doit être l'identifiant technique (slug).
    """
    try:
        project_id = resolve_authorized_project_id(project_id)
        versions = redmine.get_versions(project_id)
        issues = redmine.get_issues(project_id, status="*")
        
        closed_ids = redmine.get_closed_status_ids()
        def is_issue_closed(i):
            s_id = i.get("status_id")
            if s_id in closed_ids: return True
            name = str(i.get("status", "")).lower()
            return any(x in name for x in ["clos", "fermé", "resolv", "résolu", "termin", "rejet", "fini"])

        result = []
        for v in versions:
            v_issues = [i for i in issues if i.get("fixed_version", {}).get("id") == v["id"]]
            total = len(v_issues)
            closed = len([i for i in v_issues if is_issue_closed(i)])
            opened = total - closed
            
            # Calcul de la progression moyenne
            avg_progress = 0.0
            if total > 0:
                progress_sum = sum(100 if is_issue_closed(i) else i.get("done_ratio", 0) for i in v_issues)
                avg_progress = round(progress_sum / total, 1)
            else:
                if v["status"] == "closed":
                    avg_progress = 100.0
            
            result.append({
                "id": v["id"],
                "name": v["name"],
                "status": v["status"],
                "due_date": v.get("due_date"),
                "description": v.get("description", ""),
                "total_tasks": total,
                "closed_tasks": closed,
                "open_tasks": opened,
                "progress": avg_progress
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_team_workload(project_id: str) -> str:
    """Retourne la répartition de la charge de travail et la surcharge par membre de l'équipe du projet.
    IMPORTANT : 'project_id' doit être l'identifiant technique (slug).
    """
    try:
        project_id = resolve_authorized_project_id(project_id)
        metrics = redmine.compute_project_metrics(project_id)
        result = {
            "workload": metrics.get("team_workload", []),
            "bottleneck_alert": metrics.get("bottleneck_alert", "")
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_not_started_issues(project_id: str) -> str:
    """Liste les tâches du projet qui n'ont pas encore commencé (progression à 0%).
    IMPORTANT : 'project_id' doit être l'identifiant technique (slug).
    """
    try:
        project_id = resolve_authorized_project_id(project_id)
        issues = redmine.get_not_started_issues(project_id)
        result = [{
            "id": i["id"],
            "subject": i["subject"],
            "assignee": i.get("assigned_to", {}).get("name", "Non assigné"),
            "priority": i.get("priority", {}).get("name", ""),
            "due_date": i.get("due_date")
        } for i in issues]
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


ALL_TOOLS = [
    get_project_metrics, get_overdue_issues, get_critical_path,
    get_velocity_trend, get_member_performance, classify_risk,
    delete_project_conversations, get_all_projects_status, get_project_issues,
    get_sprint_status, get_team_workload, get_not_started_issues
]

ANALYSE_TOOLS = ALL_TOOLS
DECISION_TOOLS = [get_critical_path, get_velocity_trend, classify_risk, get_member_performance, get_sprint_status, get_team_workload]

# Liste pour l'agent Rapporteur (Synthèse et métriques)
RAPPORTEUR_TOOLS = [
    get_project_metrics, get_overdue_issues, get_velocity_trend, classify_risk,
    delete_project_conversations, get_all_projects_status, get_project_issues,
    get_sprint_status, get_team_workload, get_not_started_issues
]
