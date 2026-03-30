import sys
import os
from pathlib import Path

# --- FIX DES IMPORTS (CRUCIAL POUR TON PFE) ---
# On ajoute le dossier 'backend' au PATH de recherche Python
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# On importe le router après avoir fixé le PATH
from api.chat import router as chat_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie du monitoring proactif."""
    from services.monitor import start_monitor, stop_monitor, check_all_projects

    logger.info("🚀 Démarrage du monitoring proactif...")
    try:
        # On lance le scheduler APScheduler
        start_monitor()
        # Première vérification immédiate des 21 alertes de ShopFlow
        await check_all_projects()
        logger.info("✅ Monitoring initialisé et première vérification terminée.")
    except Exception as e:
        logger.error(f"❌ Erreur au démarrage du monitoring : {e}")

    yield  # L'application FastAPI tourne ici

    # Arrêt propre du scheduler à la fermeture du serveur
    stop_monitor()
    logger.info("🛑 Monitoring arrêté proprement.")

app = FastAPI(
    title       = "PM Assistant API",
    description = "Chatbot IA Multi-Agents pour Redmine — Projet PFE Wassim/Youssef",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# Configuration CORS pour autoriser Streamlit (port 8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["http://localhost:8501"],
    allow_credentials = True,
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# Inclusion des routes de Chat
app.include_router(chat_router, prefix="/api/v1")

@app.get("/health")
def health():
    """Route de vérification pour le frontend."""
    return {
        "status": "ok", 
        "monitoring": "actif",
        "project": "PM Assistant"
    }

@app.get("/api/v1/alerts/{{project_id}}")
def get_alerts_endpoint(project_id: str):
    """Endpoint appelé par Streamlit pour récupérer les alertes détectées."""
    from services.monitor import get_alerts, clear_alerts
    alerts = get_alerts(project_id)
    # On vide les alertes après les avoir envoyées au Frontend
    clear_alerts(project_id) 
    return {"project_id": project_id, "alerts": alerts}