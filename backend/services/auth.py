"""
Sécurité — backend/services/auth.py

Authentification JWT complète :
- Vérification credentials via Redmine
- Génération token JWT signé
- Validation token sur chaque requête
- Refresh token pour renouveler la session
"""
from datetime import datetime, timedelta
from typing import Optional
import httpx
import logging
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import settings

logger = logging.getLogger(__name__)

# ── Configuration JWT ─────────────────────────────────────────
ALGORITHM          = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES  = 60        # 1 heure
REFRESH_TOKEN_EXPIRE_DAYS    = 7         # 7 jours

# ── Schéma Bearer Token ───────────────────────────────────────
bearer_scheme = HTTPBearer()

# ── Contexte hachage mot de passe (optionnel) ─────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ──────────────────────────────────────────────────────────────
# AUTHENTIFICATION VIA REDMINE
# ──────────────────────────────────────────────────────────────
async def authenticate_with_redmine(login: str, password: str) -> Optional[dict]:
    """
    Vérifie les credentials directement via l'API Redmine.
    Retourne les infos utilisateur si succès, None sinon.
    """
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                f"{settings.redmine_url}/users/current.json",
                auth=(login, password),
            )

        if response.status_code == 200:
            user = response.json().get("user", {})
            logger.info(f"[Auth] Connexion réussie : {login}")
            return {
                "id":        user.get("id"),
                "login":     user.get("login"),
                "firstname": user.get("firstname", ""),
                "lastname":  user.get("lastname", ""),
                "email":     user.get("mail", ""),
                "is_admin":  user.get("admin", False),
                "api_key":   user.get("api_key", ""),
            }

        logger.warning(f"[Auth] Échec connexion : {login} (HTTP {response.status_code})")
        return None

    except Exception as e:
        logger.error(f"[Auth] Erreur Redmine : {e}")
        return None


# ──────────────────────────────────────────────────────────────
# GÉNÉRATION DES TOKENS JWT
# ──────────────────────────────────────────────────────────────
def create_access_token(user_data: dict) -> str:
    """
    Génère un JWT access token signé avec SECRET_KEY.
    Expire dans ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    payload = {
        "sub":       user_data["login"],
        "user_id":   user_data["id"],
        "email":     user_data["email"],
        "is_admin":  user_data["is_admin"],
        "api_key":   user_data["api_key"],
        "type":      "access",
        "exp":       datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat":       datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    logger.info(f"[Auth] Access token créé pour : {user_data['login']}")
    return token


def create_refresh_token(user_data: dict) -> str:
    """
    Génère un JWT refresh token.
    Expire dans REFRESH_TOKEN_EXPIRE_DAYS.
    Utilisé pour renouveler l'access token sans re-login.
    """
    payload = {
        "sub":     user_data["login"],
        "user_id": user_data["id"],
        "type":    "refresh",
        "exp":     datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat":     datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


# ──────────────────────────────────────────────────────────────
# VALIDATION DU TOKEN JWT
# ──────────────────────────────────────────────────────────────
def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Vérifie et décode un JWT token.
    Lève HTTPException 401 si invalide ou expiré.
    """
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail      = "Token invalide ou expiré. Reconnectez-vous.",
        headers     = {"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )

        # Vérifier le type de token
        if payload.get("type") != token_type:
            raise credentials_exception

        # Vérifier que le sujet est présent
        if not payload.get("sub"):
            raise credentials_exception

        return payload

    except JWTError as e:
        logger.warning(f"[Auth] Token invalide : {e}")
        raise credentials_exception


# ──────────────────────────────────────────────────────────────
# DÉPENDANCE FASTAPI — protège les routes
# ──────────────────────────────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Dépendance FastAPI à injecter dans les routes protégées.
    Extrait et valide le JWT du header Authorization: Bearer <token>

    Usage dans une route :
        @router.get("/protected")
        async def route(user = Depends(get_current_user)):
            return {"user": user["sub"]}
    """
    token   = credentials.credentials
    payload = verify_token(token, token_type="access")
    return payload


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dépendance pour les routes admin uniquement.
    Lève 403 si l'utilisateur n'est pas admin.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Accès réservé aux administrateurs.",
        )
    return current_user