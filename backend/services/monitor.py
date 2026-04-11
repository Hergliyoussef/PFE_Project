"""
Monitor proactif — backend/services/monitor.py
Utilise Redis pour stocker les alertes (plus de store in-memory).
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import date
import logging, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

logger        = logging.getLogger(__name__)
SEUIL_RISQUE  = 0.65
SEUIL_CHARGE  = 85.0
INTERVALLE    = 30 # minute


async def check_project(project_id: str):
    from services.redmine_client import redmine
    from services.redis_client   import push_alert, cache_metrics, cache_risk

    try:
        today   = str(date.today())
        metrics = redmine.compute_project_metrics(project_id)
        issues  = redmine.get_issues(project_id, status="open")

        # Mettre en cache les métriques (incluant la charge max calculée par le client)
        metrics_to_cache = {k: v for k, v in metrics.items() if k != "time_by_user" and k != "overdue_list"}
        cache_metrics(project_id, metrics_to_cache)
        logger.info(f"[Monitor] Métriques en cache pour {project_id}: {metrics_to_cache}")

        # ── Alertes retard ────────────────────────────────────
        for issue in redmine.get_overdue_issues(project_id):
            due   = issue.get("due_date", "")
            delay = (date.today() - date.fromisoformat(due)).days if due else 0
            push_alert(project_id, {
                "type":    "retard",
                "level":   "critique" if delay >= 5 else "warning",
                "message": f"Tâche #{issue['id']} en retard de {delay}j : {issue['subject'][:50]}",
                "issue_id": issue["id"],
            })

        # ── Score de risque ───────────────────────────────────
        bugs = sum(1 for i in issues
                   if i.get("tracker", {}).get("name","").lower() in ("anomalie","bug")
                   and i.get("priority", {}).get("id", 0) >= 3)
        total = max(metrics["total_issues"], 1)
        score = round(min(
            (metrics["overdue_issues"] / total)         * 0.40 +
            (bugs / 10)                                 * 0.30 +
            ((100 - metrics["avg_progress"]) / 100)     * 0.30,
        1.0), 2)
        level = "faible" if score < 0.35 else "moyen" if score < 0.65 else "élevé"
        cache_risk(project_id, {"risk_level": level, "risk_score": score, "bugs": bugs})

        if score >= SEUIL_RISQUE:
            push_alert(project_id, {
                "type":    "risque",
                "level":   "critique" if score >= 0.80 else "warning",
                "message": f"Risque projet ÉLEVÉ — score {score}/1.0",
                "score":   score,
            })

        # ── Surcharge équipe ──────────────────────────────────
        for name, hours in redmine.get_time_by_user(project_id).items():
            load = min((hours / 40) * 100, 100)
            if load >= SEUIL_CHARGE:
                push_alert(project_id, {
                    "type":    "surcharge",
                    "level":   "critique" if load >= 95 else "warning",
                    "message": f"{name} surchargé à {load:.0f}% ({hours}h loguées)",
                    "member":  name,
                    "load":    load,
                })

        logger.info(f"[Monitor] {project_id} — score risque={score}")

    except Exception as e:
        logger.error(f"[Monitor] Erreur {project_id} : {e}")


async def check_all_projects():
    from services.redmine_client import redmine
    logger.info("[Monitor] Vérification automatique...")
    try:
        for project in redmine.get_projects():
            await check_project(project["identifier"])
    except Exception as e:
        logger.error(f"[Monitor] Erreur globale : {e}")


# Fonctions compatibles avec monitor.py original
def get_alerts(project_id: str) -> list:
    from services.redis_client import pop_alerts
    return pop_alerts(project_id)

def clear_alerts(project_id: str):
    pass  # pop_alerts vide déjà automatiquement


scheduler = AsyncIOScheduler()

def start_monitor():
    scheduler.add_job(
        check_all_projects,
        trigger=IntervalTrigger(minutes=INTERVALLE),
        id="monitor", replace_existing=True,
    )
    scheduler.start()
    logger.info(f"[Monitor] Démarré — Redis — toutes les {INTERVALLE} min")

def stop_monitor():
    if scheduler.running:
        scheduler.shutdown()