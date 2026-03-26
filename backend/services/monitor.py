"""
Monitoring proactif — backend/services/monitor.py

Tourne en arrière-plan toutes les 30 minutes.
Vérifie automatiquement Redmine SANS attendre une question.
Génère des alertes si :
  - Une tâche dépasse son échéance (retard)
  - Le score de risque dépasse 0.65 (risque élevé)
  - Un membre dépasse 85% de charge (surcharge)

Démarré automatiquement au lancement de FastAPI dans main.py
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, date
import logging, json, sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

logger = logging.getLogger(__name__)

# ── Seuils d'alerte configurables ─────────────────────────────
SEUIL_RISQUE_ELEVE   = 0.65   # score > 0.65 → alerte risque
SEUIL_SURCHARGE      = 85.0   # charge > 85% → alerte surcharge
INTERVALLE_MINUTES   = 30     # vérification toutes les 30 min


# ── Stockage en mémoire des alertes actives ───────────────────
# Structure : { project_id: [{"type", "message", "level", "ts"}] }
_alerts_store: dict[str, list] = {}


def get_alerts(project_id: str) -> list:
    """Retourne les alertes actives pour un projet."""
    return _alerts_store.get(project_id, [])


def clear_alerts(project_id: str):
    """Vide les alertes d'un projet (après lecture)."""
    _alerts_store[project_id] = []


# ──────────────────────────────────────────────────────────────
# Vérification d'un projet
# ──────────────────────────────────────────────────────────────
async def check_project(project_id: str):
    """
    Vérifie un projet et génère les alertes nécessaires.
    Appelé automatiquement par le scheduler.
    """
    from services.redmine_client import redmine
    alerts = []
    today  = str(date.today())

    try:
        # ── 1. Vérifier les retards ───────────────────────────
        overdue = redmine.get_overdue_issues(project_id)
        for issue in overdue:
            delay = (
                date.today() - date.fromisoformat(issue["due_date"])
            ).days if issue.get("due_date") else 0

            level = "critique" if delay >= 5 else "warning"
            alerts.append({
                "type":    "retard",
                "level":   level,
                "message": (
                    f"Tâche #{issue['id']} en retard de {delay} jour(s) : "
                    f"{issue['subject'][:50]} "
                    f"(assigné à {issue.get('assigned_to', {}).get('name', '?')})"
                ),
                "issue_id": issue["id"],
                "ts":      datetime.now().isoformat(),
            })

        # ── 2. Vérifier le risque global ──────────────────────
        issues  = redmine.get_issues(project_id, status="open")
        metrics = redmine.compute_project_metrics(project_id)

        bugs_urgent = sum(
            1 for i in issues
            if i.get("tracker", {}).get("name","").lower() in ("anomalie","bug")
            and i.get("priority", {}).get("id", 0) >= 3
        )
        total    = max(metrics["total_issues"], 1)
        score    = (
            (metrics["overdue_issues"] / total)         * 0.40 +
            (bugs_urgent / 10)                          * 0.30 +
            ((100 - metrics["avg_progress"]) / 100)     * 0.30
        )
        score = round(min(score, 1.0), 2)

        if score >= SEUIL_RISQUE_ELEVE:
            alerts.append({
                "type":    "risque",
                "level":   "critique" if score >= 0.80 else "warning",
                "message": (
                    f"Risque projet ÉLEVÉ — score {score}/1.0 "
                    f"({metrics['overdue_issues']} retards, "
                    f"{bugs_urgent} bugs critiques, "
                    f"avancement {metrics['avg_progress']}%)"
                ),
                "score": score,
                "ts":    datetime.now().isoformat(),
            })

        # ── 3. Vérifier la surcharge équipe ───────────────────
        time_by_user  = redmine.get_time_by_user(project_id)
        issues_open   = redmine.get_issues(project_id, status="open")
        issues_by_user: dict[str, int] = {}
        for i in issues_open:
            name = i.get("assigned_to", {}).get("name", "Non assigné")
            issues_by_user[name] = issues_by_user.get(name, 0) + 1

        for name, hours in time_by_user.items():
            load = min((hours / 40) * 100, 100)
            if load >= SEUIL_SURCHARGE:
                nb = issues_by_user.get(name, 0)
                alerts.append({
                    "type":    "surcharge",
                    "level":   "critique" if load >= 95 else "warning",
                    "message": (
                        f"{name} surchargé à {load:.0f}% "
                        f"({hours}h loguées, {nb} tâches ouvertes)"
                    ),
                    "member": name,
                    "load":   load,
                    "ts":     datetime.now().isoformat(),
                })

        # ── Sauvegarder les alertes ───────────────────────────
        _alerts_store[project_id] = alerts

        if alerts:
            logger.warning(
                f"[Monitor] {project_id} — "
                f"{len(alerts)} alerte(s) détectée(s) : "
                f"{[a['type'] for a in alerts]}"
            )
        else:
            logger.info(f"[Monitor] {project_id} — aucune alerte")

    except Exception as e:
        logger.error(f"[Monitor] Erreur sur {project_id} : {e}")


# ──────────────────────────────────────────────────────────────
# Vérification de tous les projets
# ──────────────────────────────────────────────────────────────
async def check_all_projects():
    """
    Tâche principale du scheduler.
    Récupère tous les projets Redmine et les vérifie un par un.
    """
    from services.redmine_client import redmine
    logger.info(f"[Monitor] Vérification automatique — {datetime.now().strftime('%H:%M')}")
    try:
        projects = redmine.get_projects()
        for project in projects:
            await check_project(project["identifier"])
    except Exception as e:
        logger.error(f"[Monitor] Erreur globale : {e}")


# ──────────────────────────────────────────────────────────────
# Démarrage / arrêt du scheduler
# ──────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()

def start_monitor():
    """
    Démarre le monitoring proactif.
    Appelé dans main.py au démarrage de FastAPI.
    """
    scheduler.add_job(
        check_all_projects,
        trigger  = IntervalTrigger(minutes=INTERVALLE_MINUTES),
        id       = "proactive_monitor",
        name     = "Monitoring proactif Redmine",
        replace_existing = True,
    )
    scheduler.start()
    logger.info(
        f"[Monitor] Démarré — vérification toutes les "
        f"{INTERVALLE_MINUTES} minutes"
    )


def stop_monitor():
    """Arrête le scheduler proprement."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Monitor] Arrêté")