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

# ── Contrôle d'accès basé sur les rôles ───────────────────────
# Rôles Redmine autorisés à accéder à l'application
# ✅ Manager, CEO  →  accès accordé
# ❌ Développeur, Rapporteur  →  accès refusé (HTTP 403)
AUTHORIZED_ROLES = {
    "Manager",
    "CEO",
}

ROLE_PRIORITY = {
    "CEO": 1,
    "Manager": 2,
    "D développeur": 10,  # Gestion de l'encodage Redmine probable
    "Développeur": 10,
    "Developer": 10,
    "Rapporteur": 20,
}


# ──────────────────────────────────────────────────────────────
# AUTHENTIFICATION VIA REDMINE
# ──────────────────────────────────────────────────────────────
async def authenticate_with_redmine(login: str, password: str) -> Optional[dict]:
    """
    Vérifie les credentials Redmine ET les rôles de l'utilisateur.

    Retourne :
        dict          — credentials valides ET rôle autorisé
        {"role_denied": True, ...} — credentials valides MAIS rôle non autorisé
        None          — mauvais identifiants ou erreur réseau
    """
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                f"{settings.redmine_url}/users/current.json",
                params={"include": "memberships"},   # ← récupère les rôles Redmine
                auth=(login, password),
            )

        if response.status_code != 200:
            logger.warning(f"[Auth] Échec connexion : {login} (HTTP {response.status_code})")
            return None

        user = response.json().get("user", {})
        is_admin = user.get("admin", False)

        # ── Extraction des rôles et projets autorisés ──────────────────────
        memberships = user.get("memberships", [])
        user_roles: set[str] = set()
        authorized_projects = []
        
        # Résolution des identifiants (Redmine ne les donne pas dans memberships)
        try:
            from services.redmine_client import redmine
            all_p = redmine.get_projects()
            id_to_ident = {p["id"]: p.get("identifier") for p in all_p}
        except:
            id_to_ident = {}

        for membership in memberships:
            proj = membership.get("project", {})
            p_id = proj.get("id")
            p_ident = id_to_ident.get(p_id) or str(p_id) # Fallback sur l'ID si slug inconnu
            
            m_roles = [r.get("name", "") for r in membership.get("roles", [])]
            
            # On stocke tous les rôles pour le JWT
            for r_name in m_roles:
                user_roles.add(r_name)
            
            # Filtre : Est-ce que l'utilisateur est PM/CEO sur CE projet ?
            is_authorized_on_proj = any(r in AUTHORIZED_ROLES for r in m_roles)
            if is_authorized_on_proj or is_admin:
                authorized_projects.append({
                    "id": p_id,
                    "name": proj.get("name"),
                    "identifier": p_ident
                })

        # ── Contrôle d'accès ────────────────────────────────────────
        has_authorized_role = is_admin or len(authorized_projects) > 0

        if not has_authorized_role:
            logger.warning(
                f"[Auth] Accès refusé pour {login} — "
                f"aucun rôle autorisé (Manager/CEO) sur les projets détectés."
            )
            return {"role_denied": True, "roles": sorted(user_roles)}

        # ── Priorisation du rôle (pour l'affichage) ─────────────────
        sorted_roles = sorted(
            list(user_roles),
            key=lambda r: ROLE_PRIORITY.get(r, 99)
        )

        logger.info(f"[Auth] Connexion réussie : {login} — {len(authorized_projects)} projets autorisés")
        
        return {
            "id":        user.get("id"),
            "login":     user.get("login"),
            "firstname": user.get("firstname", ""),
            "lastname":  user.get("lastname", ""),
            "email":     user.get("mail", ""),
            "is_admin":  is_admin,
            "api_key":   user.get("api_key", ""),
            "roles":     sorted_roles,   # Le premier est le plus prioritaire
            "authorized_projects": authorized_projects,
        }

    except Exception as e:
        logger.error(f"[Auth] Erreur Redmine : {e}")
        return None


# ──────────────────────────────────────────────────────────────
# GÉNÉRATION DES TOKENS JWT
# ──────────────────────────────────────────────────────────────
def create_access_token(user_data: dict) -> str:
    """
    Génère un JWT access token signé avec SECRET_KEY.
    Inclut les rôles pour le contrôle d'accès backend.
    """
    payload = {
        "sub":       user_data["login"],
        "user_id":   user_data["id"],
        "email":     user_data["email"],
        "is_admin":  user_data["is_admin"],
        "api_key":   user_data["api_key"],
        "roles":     user_data.get("roles", []),   # ← rôles inclus dans le token
        "type":      "access",
        "exp":       datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat":       datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    logger.info(f"[Auth] Access token créé pour : {user_data['login']}")
    return token


def create_refresh_token(user_data: dict) -> str:
    """
    Génère un JWT refresh token (7 jours).
    Inclut les rôles pour les conserver lors du renouvellement.
    """
    payload = {
        "sub":      user_data["login"],
        "user_id":  user_data["id"],
        "roles":    user_data.get("roles", []),    # ← conservés lors du refresh
        "type":     "refresh",
        "exp":      datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat":      datetime.utcnow(),
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


async def require_authorized_role(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dépendance de protection des routes sensibles.
    Accepte uniquement : Chefs de Projet, CEO et admins Redmine.
    Constitue une deuxième couche de sécurité après le login.
    """
    if current_user.get("is_admin"):
        return current_user
    user_roles = set(current_user.get("roles", []))
    if not user_roles & AUTHORIZED_ROLES:
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = "Accès réservé aux Chefs de Projet et CEO.",
        )
    return current_user