"""
Monitor proactif — backend/services/monitor.py
Utilise Redis pour stocker les alertes (plus de store in-memory).
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import date
import logging, sys, os, asyncio
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

logger        = logging.getLogger(__name__)
SEUIL_RISQUE  = 0.65
SEUIL_CHARGE  = 85.0
INTERVALLE    = 1 # minute (Monitoring plus réactif)


async def check_project(project_id: str):
    from services.redmine_client import redmine
    from services.redis_client   import push_alert, cache_metrics, cache_risk
    from services.websocket_manager import manager

    try:
        today   = str(date.today())
        metrics = await asyncio.to_thread(redmine.compute_project_metrics, project_id)
        issues  = await asyncio.to_thread(redmine.get_issues, project_id, status="open")

        # Récupération du nom réel du projet
        try:
            p_raw = await asyncio.to_thread(redmine._get, f"/projects/{project_id}.json", cache_ttl=3600)
            p_data = p_raw.get("project", {})
            project_name = p_data.get("name", project_id)
        except:
            project_name = project_id

        # Mettre en cache les métriques (incluant la charge max calculée par le client)
        metrics_to_cache = {k: v for k, v in metrics.items() if k != "time_by_user" and k != "overdue_list"}
        cache_metrics(project_id, metrics_to_cache)
        logger.info(f"[Monitor] Métriques en cache pour {project_id}: {metrics_to_cache}")
        
        # Broadcast temps réel pour rafraîchir l'interface
        await manager.broadcast_to_project(project_id, {
            "type": "metrics_updated",
            "project_id": project_id
        })

        # ── Alertes retard (Détection de changement d'état) ──────────────────
        from services.redis_client import r as redis_conn
        overdue_issues = await asyncio.to_thread(redmine.get_overdue_issues, project_id)
        for issue in overdue_issues:
            due   = issue.get("due_date", "")
            delay = (date.today() - date.fromisoformat(due)).days if due else 0
            
            alert_key = f"alert_sent:{project_id}:retard:{issue['id']}"
            if not redis_conn.exists(alert_key):
                assigned_name = issue.get("assigned") or "Non assigné"
                msg_retard = f"NOUVEAU : Tâche #{issue['id']} en retard de {delay}j : {issue['subject'][:50]} (Assigné à : {assigned_name})"
                
                alert_id = f"{project_id}:retard:{issue['id']}"
                push_alert(project_id, {
                    "id":            alert_id,
                    "type":          "retard",
                    "level":         "critique" if delay >= 5 else "warning",
                    "message":       msg_retard,
                    "issue_id":      issue["id"],
                    "project_id":    project_id,
                    "project_name":  project_name,
                })
                # On expire l'alerte après 24h pour permettre un rappel si pas résolu le lendemain
                redis_conn.setex(alert_key, 86400, "1")
                # Broadcast temps réel !
                await manager.broadcast_to_project(project_id, {
                    "type": "new_alert",
                    "alert": {
                        "id":            alert_id,
                        "type":          "retard",
                        "level":         "critique" if delay >= 5 else "warning",
                        "message":       msg_retard,
                        "issue_id":      issue["id"],
                        "project_id":    project_id,
                        "project_name":  project_name,
                    }
                })

        # ── Alertes Priorité Haute (NOUVEAU) ──────────────────────────
        for issue in issues:
            prio_id = issue.get("priority_id", 0)
            prio_val = issue.get("priority", "")
            prio_name = prio_val.get("name", "") if isinstance(prio_val, dict) else str(prio_val)
            
            # 3 = Haut, 4 = Urgent, 5 = Immédiat
            if prio_id >= 3 or prio_name.lower() in ["haut", "high", "urgent", "immédiat", "immediate"]:
                alert_key = f"alert_sent:{project_id}:priority:{issue['id']}"
                if not redis_conn.exists(alert_key):
                    assigned_name = issue.get("assigned") or "Non assigné"
                    is_critical = prio_id >= 4 or prio_name.lower() in ["urgent", "immédiat", "immediate"]
                    prio_level = "critique" if is_critical else "warning"
                    prio_label = "URGENT" if is_critical else "HAUT"
                    
                    msg_urgent = f"ALERTE : Nouveau ticket {prio_label} #{issue['id']} : {issue['subject'][:50]} (Assigné à : {assigned_name})"
                    
                    alert_id = f"{project_id}:priority:{issue['id']}"
                    push_alert(project_id, {
                        "id":            alert_id,
                        "type":          "priorité",
                        "level":         prio_level,
                        "message":       msg_urgent,
                        "issue_id":      issue["id"],
                        "project_id":    project_id,
                        "project_name":  project_name,
                    })
                    redis_conn.setex(alert_key, 86400, "1") # Une fois par jour
                    await manager.broadcast_to_project(project_id, {
                        "type": "new_alert",
                        "alert": {
                            "id":            alert_id,
                            "type":          "priorité",
                            "level":         prio_level,
                            "message":       msg_urgent,
                            "issue_id":      issue["id"],
                            "project_id":    project_id,
                            "project_name":  project_name,
                        }
                    })

        # ── Score de risque ───────────────────────────────────
        bugs = sum(1 for i in issues
                   if (i.get("tracker") if isinstance(i.get("tracker"), str) else i.get("tracker", {}).get("name", "")).lower() in ("anomalie", "bug")
                   and i.get("priority_id", 0) >= 3)
        total = max(metrics["total_issues"], 1)
        score = round(min(
            (metrics["overdue_issues"] / total)         * 0.40 +
            (bugs / 10)                                 * 0.30 +
            ((100 - metrics["avg_progress"]) / 100)     * 0.30,
        1.0), 2)
        level = "faible" if score < 0.35 else "moyen" if score < 0.65 else "élevé"
        cache_risk(project_id, {"risk_level": level, "risk_score": score, "bugs": bugs})

        if score >= SEUIL_RISQUE:
            alert_key = f"alert_sent:{project_id}:risque"
            if not redis_conn.exists(alert_key):
                push_alert(project_id, {
                    "type":    "risque",
                    "level":   "critique" if score >= 0.80 else "warning",
                    "message": f"ATTENTION : Risque projet ÉLEVÉ — score {score}/1.0",
                    "score":   score,
                })
                # On garde l'alerte active pendant 4h (on ne prévient pas toutes les minutes)
                redis_conn.setex(alert_key, 14400, "1")
                # Broadcast temps réel !
                await manager.broadcast_to_project(project_id, {
                    "type": "new_alert",
                    "alert": {
                        "type": "risque",
                        "level": "critique" if score >= 0.80 else "warning",
                        "message": f"ATTENTION : Risque projet ÉLEVÉ — score {score}/1.0",
                        "score": score
                    }
                })

        # ── Surcharge équipe ──────────────────────────────────
        time_by_user = await asyncio.to_thread(redmine.get_time_by_user, project_id)
        for name, hours in time_by_user.items():
            load = min((hours / 40) * 100, 100)
            if load >= SEUIL_CHARGE:
                alert_key = f"alert_sent:{project_id}:surcharge:{name}"
                if not redis_conn.exists(alert_key):
                    push_alert(project_id, {
                        "type":    "surcharge",
                        "level":   "critique" if load >= 95 else "warning",
                        "message": f"SURCHARGE : {name} est à {load:.0f}% de charge",
                        "member":  name,
                        "load":    load,
                    })
                    # On évite de répéter l'alerte de surcharge pendant 8h
                    redis_conn.setex(alert_key, 28800, "1")
                    # Broadcast temps réel !
                    await manager.broadcast_to_project(project_id, {
                        "type": "new_alert",
                        "alert": {
                            "type": "surcharge",
                            "level": "critique" if load >= 95 else "warning",
                            "message": f"SURCHARGE : {name} est à {load:.0f}% de charge",
                            "member": name,
                            "load": load
                        }
                    })

        logger.info(f"[Monitor] {project_id} — score risque={score}")

    except Exception as e:
        logger.error(f"[Monitor] Erreur {project_id} : {e}")


async def check_all_projects():
    from services.redmine_client import redmine
    logger.info("[Monitor] Vérification automatique...")
    try:
        projects = await asyncio.to_thread(redmine.get_projects)
        for project in projects:
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
    # Désactivé car remplacé par le monitoring événementiel via Webhooks
    logger.info("[Monitor] Démarrage ignoré (le timer périodique est désactivé au profit des webhooks)")

def stop_monitor():
    if scheduler.running:
        scheduler.shutdown()