from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, date
import logging
import sys
import os

# Configuration du chemin pour les imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
SEUIL_RISQUE_ELEVE = 0.65
SEUIL_SURCHARGE = 85.0
INTERVALLE_MINUTES = 10  # Garde 10 minutes

# --- STORE ---
# Utilisation d'un dictionnaire global pour stocker les alertes en mémoire
_alerts_store = {}

def get_alerts(project_id: str):
    """Récupère les alertes sans les effacer immédiatement pour le frontend."""
    return _alerts_store.get(str(project_id), [])

def clear_alerts(project_id: str):
    """Nettoie manuellement si besoin."""
    if str(project_id) in _alerts_store:
        _alerts_store[str(project_id)] = []

async def check_project(project_id: str):
    """Vérifie un projet et remplit le store d'alertes."""
    # Import local pour éviter les imports circulaires
    from services.redmine_client import redmine
    
    project_id = str(project_id)
    alerts = []
    
    try:
        logger.info(f"🔍 [Monitor] Analyse du projet : {project_id}")
        
        # 1. RETARDS (La base des alertes)
        overdue = redmine.get_overdue_issues(project_id)
        for issue in overdue:
            # Calcul du délai
            due_date = issue.get("due_date")
            delay = 0
            if due_date:
                delay = (date.today() - date.fromisoformat(due_date)).days
            
            # On génère l'alerte dès que delay >= 0 pour le test
            if delay >= 5:
                alerts.append({
                    "type": "retard",
                    "level": "critique" if delay >= 3 else "warning",
                    "message": f"🚨 Retard ({delay}j) : {issue['subject'][:50]}",
                    "issue_id": issue["id"],
                    "ts": datetime.now().isoformat()
                })

        # 2. RISQUE GLOBAL (Calcul composite)
        metrics = redmine.compute_project_metrics(project_id)
        issues_open = redmine.get_issues(project_id, status="open")
        
        bugs_urgent = sum(1 for i in issues_open 
                         if i.get("priority", {}).get("id", 0) >= 3)
        
        total = max(metrics.get("total_issues", 1), 1)
        score = (
            (metrics.get("overdue_issues", 0) / total) * 0.50 +
            (bugs_urgent / 10) * 0.25 +
            ((100 - metrics.get("avg_progress", 0)) / 100) * 0.25
        )
        score = round(min(score, 1.0), 2)

        if score >= SEUIL_RISQUE_ELEVE:
            alerts.append({
                "type": "risque",
                "level": "critique" if score >= 0.8 else "warning",
                "message": f"⚠️ Risque élevé ({score}/1.0) sur le projet.",
                "ts": datetime.now().isoformat()
            })

        # --- MISE À JOUR DU STORE ---
        _alerts_store[project_id] = alerts
        
        if alerts:
            logger.warning(f"🔔 [Monitor] {len(alerts)} alertes détectées pour {project_id}")
        else:
            logger.info(f"✅ [Monitor] Projet {project_id} sain.")

    except Exception as e:
        logger.error(f"❌ [Monitor] Erreur sur projet {project_id} : {str(e)}")

# backend/services/monitor.py

async def check_all_projects():
    from services.redmine_client import redmine
    try:
        projects = redmine.get_projects()
        for p in projects:
            # On récupère les deux types d'ID
            p_id = str(p.get("id"))          # Ex: "3"
            p_slug = str(p.get("identifier")) # Ex: "shopflow"
            
            # On lance l'analyse
            await check_project(p_slug)
            
            # CRUCIAL : On copie les alertes pour que l'API les trouve peu importe l'appel
            if p_slug in _alerts_store:
                _alerts_store[p_id] = _alerts_store[p_slug]
                
        logger.info(f"✅ [Monitor] Store mis à jour : {list(_alerts_store.keys())}")
    except Exception as e:
        logger.error(f"❌ [Monitor] Erreur check_all : {e}")
# --- SCHEDULER ---
scheduler = AsyncIOScheduler()

def start_monitor():
    if not scheduler.running:
        scheduler.add_job(
            check_all_projects,
            trigger=IntervalTrigger(minutes=INTERVALLE_MINUTES),
            id="proactive_monitor",
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"🚀 [Monitor] Service démarré (Intervalle: {INTERVALLE_MINUTES} min)")

def stop_monitor():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 [Monitor] Service arrêté.")