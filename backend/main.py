"""
main.py sécurisé — backend/main.py
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from api.chat import router as chat_router
from api.auth import router as auth_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.monitor import start_monitor, stop_monitor, check_all_projects
    logger.info("Démarrage du monitoring proactif...")
    start_monitor()
    await check_all_projects()
    yield
    stop_monitor()


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

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")     # /api/v1/auth/login
app.include_router(chat_router, prefix="/api/v1")     # /api/v1/chat


@app.get("/health")
def health():
    return {"status": "ok", "monitoring": "actif"}