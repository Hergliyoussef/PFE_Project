"""
Sécurité — backend/services/auth.py

Authentification JWT complète :
- Vérification credentials via Redmine
- Génération token JWT signé
- Validation token sur chaque requête
- Refresh token pour renouveler la session
"""
from sqlalchemy.orm import Session
from db.models import User  # Assure-toi que le chemin est correct
from db.session import SessionLocal
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
    "Project Manager",
    "Chef de projet",
    "CEO",
    "Administrator",
    "Admin",
    "Gestionnaire",
}

ROLE_PRIORITY = {
    "CEO": 1,
    "Administrator": 1,
    "Admin": 1,
    "Manager": 2,
    "Project Manager": 2,
    "Chef de projet": 2,
    "Développeur": 10,
    "Developer": 10,
    "Rapporteur": 10,
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
        async with httpx.AsyncClient(timeout=50) as client:
            response = await client.get(
                f"{settings.redmine_url}/users/current.json",
                params={"include": "memberships"},   # ← récupère les rôles Redmine
                auth=(login, password),
            )

        if response.status_code != 200:
            logger.warning(f"[Auth] Échec connexion : {login} (HTTP {response.status_code})")
            return None

        user = response.json().get("user", {})
        logger.info(f"[Auth] Données Redmine reçues pour {login} : {user}")
        # L'admin Redmine (ID 1) est toujours considéré comme CEO/Admin
        is_admin = user.get("admin", False) or user.get("id") == 1

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

        # ── Récupération forcée de l'email via Clé API Admin si manquant ──
        email = user.get("mail") or user.get("email")
        if not email and settings.redmine_api_key:
            try:
                async with httpx.AsyncClient(timeout=50) as admin_client:
                    admin_resp = await admin_client.get(
                        f"{settings.redmine_url}/users/{user.get('id')}.json",
                        headers={"X-Redmine-API-Key": settings.redmine_api_key}
                    )
                    if admin_resp.status_code == 200:
                        full_user = admin_resp.json().get("user", {})
                        email = full_user.get("mail") or full_user.get("email")
                        if email:
                            logger.info(f"[Auth] Email récupéré via Admin API pour {login} : {email}")
            except Exception as e:
                logger.error(f"[Auth] Échec récupération email via Admin API : {e}")

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
            "email":     email,
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
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    # --- SYNCHRONISATION AUTOMATIQUE ---
    # On récupère les infos du token
    user_id = payload.get("user_id")
    username = payload.get("sub")
    email = payload.get("email")
    roles = payload.get("roles", [])

    # On appelle la fonction de synchro (que nous avons créée ensemble)
    # Elle vérifiera si l'ID existe, sinon elle le créera
    sync_user_to_db({
        "id": user_id,
        "login": username,
        "email": email,
        "roles": roles,
        "is_admin": payload.get("is_admin", False)
    })
    # -----------------------------------

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
    
    # Comparaison insensible à la casse
    user_roles = {r.lower().strip() for r in current_user.get("roles", [])}
    allowed_roles = {r.lower().strip() for r in AUTHORIZED_ROLES}
    
    if not (user_roles & allowed_roles):
        logger.warning(f"[Auth] Accès refusé pour {current_user.get('sub')}. Rôles détectés: {user_roles} | Rôles requis: {allowed_roles}")
        raise HTTPException(
            status_code = status.HTTP_403_FORBIDDEN,
            detail      = f"Accès réservé aux Chefs de Projet et CEO. (Rôles détectés : {list(user_roles)})",
        )
    return current_user
def sync_user_to_db(user_data: dict):
    """
    Synchronise l'utilisateur Redmine avec la base de données locale.
    Résout l'erreur ForeignKeyViolation en assurant que l'ID existe avant le chat.
    """
    db: Session = SessionLocal()
    try:
        # On vérifie si l'utilisateur existe déjà via son ID Redmine
        db_user = db.query(User).filter(User.id == user_data["id"]).first()

        # Déterminer le rôle principal pour notre DB (type user_role)
        # On prend le rôle le plus prioritaire de la liste triée
        primary_role = "PROJECT_MANAGER"
        if user_data.get("is_admin"):
            primary_role = "CEO"
        elif user_data.get("roles"):
            # Si le rôle 'CEO' est dans la liste Redmine, on lui donne
            primary_role = "CEO" if "CEO" in user_data["roles"] else "PROJECT_MANAGER"

        if not db_user:
            logger.info(f"[Auth] Nouveau profil détecté : {user_data['login']}. Création locale...")
            db_user = User(
                id=user_data["id"],
                username=user_data["login"],
                email=user_data.get("email") if user_data.get("email") else None,
                role=primary_role,
                hashed_password="redmine_external_auth" # Placeholder car auth via Redmine
            )
            db.add(db_user)
        else:
            # Mise à jour dynamique (rôle et email)
            db_user.role = primary_role
            if user_data.get("email"):
                db_user.email = user_data["email"]
            
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] Échec de la synchronisation PostgreSQL : {e}")
    finally:
        db.close()

def ensure_assistant_user():
    """Crée l'utilisateur virtuel 'assistant' s'il n'existe pas."""
    db: Session = SessionLocal()
    try:
        assistant = db.query(User).filter(User.username == "assistant").first()
        if not assistant:
            logger.info("[Auth] Création du profil système 'assistant' (ID: 999999)...")
            assistant = User(
                id=999999, # ID très haut pour éviter les conflits Redmine
                username="assistant",
                email=None,
                role="assistant",
                hashed_password="system_internal"
            )
            db.add(assistant)
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[Auth] Échec création assistant : {e}")
    finally:
        db.close()