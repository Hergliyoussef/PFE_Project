"""
Router Auth — backend/api/auth.py

Endpoints d'authentification :
POST /auth/login   → credentials → JWT tokens
POST /auth/refresh → refresh token → nouvel access token
POST /auth/logout  → invalider la session
GET  /auth/me      → infos utilisateur connecté
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
import logging

from services.auth import (
    authenticate_with_redmine,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentification"])


# ── Modèles Pydantic ──────────────────────────────────────────
class LoginRequest(BaseModel):
    login:    str
    password: str

class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = 3600       # secondes
    user:          dict

class RefreshRequest(BaseModel):
    refresh_token: str


# ──────────────────────────────────────────────────────────────
# POST /auth/login
# ──────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """
    Authentification via Redmine.
    1. Vérifie les credentials sur Redmine
    2. Génère access_token (1h) + refresh_token (7j)
    3. Retourne les tokens + infos utilisateur
    """
    # Vérification Redmine
    user = await authenticate_with_redmine(req.login, req.password)

    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Identifiant ou mot de passe incorrect.",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

    # Génération des tokens
    access_token  = create_access_token(user)
    refresh_token = create_refresh_token(user)

    logger.info(f"[Login] Connexion réussie : {req.login}")

    return TokenResponse(
        access_token  = access_token,
        refresh_token = refresh_token,
        user          = {
            "id":        user["id"],
            "login":     user["login"],
            "firstname": user["firstname"],
            "lastname":  user["lastname"],
            "email":     user["email"],
            "is_admin":  user["is_admin"],
            "api_key":   user["api_key"],
        },
    )


# ──────────────────────────────────────────────────────────────
# POST /auth/refresh
# ──────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest):
    """
    Renouvelle l'access token via le refresh token.
    Évite de demander les credentials à chaque heure.
    """
    payload = verify_token(req.refresh_token, token_type="refresh")

    # Reconstruire les données utilisateur depuis le token
    user_data = {
        "id":       payload.get("user_id"),
        "login":    payload.get("sub"),
        "email":    "",
        "is_admin": False,
        "api_key":  "",
    }

    new_access  = create_access_token(user_data)
    new_refresh = create_refresh_token(user_data)

    logger.info(f"[Refresh] Token renouvelé pour : {payload.get('sub')}")

    return TokenResponse(
        access_token  = new_access,
        refresh_token = new_refresh,
        user          = user_data,
    )


# ──────────────────────────────────────────────────────────────
# GET /auth/me
# ──────────────────────────────────────────────────────────────
@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Retourne les infos de l'utilisateur connecté.
    Route protégée — nécessite Authorization: Bearer <token>
    """
    return {
        "login":    current_user.get("sub"),
        "user_id":  current_user.get("user_id"),
        "email":    current_user.get("email"),
        "is_admin": current_user.get("is_admin"),
    }


# ──────────────────────────────────────────────────────────────
# POST /auth/logout
# ──────────────────────────────────────────────────────────────
@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Déconnexion — côté client le token doit être supprimé.
    JWT est stateless donc on ne peut pas l'invalider côté serveur
    sans une blacklist (non implémentée ici pour simplifier).
    """
    logger.info(f"[Logout] Déconnexion : {current_user.get('sub')}")
    return {"message": "Déconnexion réussie. Supprimez le token côté client."}