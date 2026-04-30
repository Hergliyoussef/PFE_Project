"""
main.py— backend/main.py
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
    from db.session import engine
    from db.models import Base
    from services.monitor import start_monitor, stop_monitor, check_all_projects
    
    logger.info("Initialisation de la base de données...")
    Base.metadata.create_all(bind=engine) # Crée les tables Postgres si elles n'existent pas
    
    from services.auth import ensure_assistant_user
    ensure_assistant_user()
    
    logger.info("Démarrage du monitoring proactif...")
    start_monitor()
    # await check_all_projects() # Ne pas bloquer le démarrage si Redmine est lent/down
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
    allow_origins      = [
        "http://localhost:8501", 
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "http://localhost:5174", 
        "http://127.0.0.1:5174",
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://pm_frontend"
    ],
    allow_methods      = ["*"],
    allow_headers      = ["*"],
    allow_credentials  = True,   # BUG 11 — nécessaire pour le header Authorization: Bearer
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")     # /api/v1/auth/login
app.include_router(chat_router, prefix="/api/v1")     # /api/v1/chat


from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    """Redirige vers la documentation Swagger."""
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return {"status": "ok", "monitoring": "actif"}