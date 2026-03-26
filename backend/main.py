"""
main.py — backend/main.py
Point d'entrée FastAPI avec monitoring proactif intégré.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from api.chat import router as chat_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarre et arrête le monitoring au lancement/arrêt de FastAPI."""
    from services.monitor import start_monitor, stop_monitor, check_all_projects

    # Démarrage
    logger.info("Démarrage du monitoring proactif...")
    start_monitor()

    # Première vérification immédiate au démarrage
    await check_all_projects()

    yield  # L'app tourne ici

    # Arrêt propre
    stop_monitor()
    logger.info("Monitoring arrêté")


app = FastAPI(
    title       = "PM Assistant API",
    description = "Chatbot IA pour chefs de projet — Redmine",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["http://localhost:8501"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

app.include_router(chat_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok", "monitoring": "actif"}


@app.get("/api/v1/alerts/{project_id}")
def get_alerts(project_id: str):
    """
    Retourne les alertes proactives d'un projet.
    Appelé par Streamlit toutes les 60 secondes.
    """
    from services.monitor import get_alerts, clear_alerts
    alerts = get_alerts(project_id)
    clear_alerts(project_id)  # vide après lecture
    return {"project_id": project_id, "alerts": alerts}