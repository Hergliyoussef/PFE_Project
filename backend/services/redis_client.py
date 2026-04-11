"""
Client Redis — backend/services/redis_client.py

Gestion complète :
- Historique des conversations (LIST)
- Session utilisateur (HASH)
- Mémoire des agents (HASH)
- Cache métriques Redmine (HASH)
- Cache risques (HASH)
- Alertes proactives (LIST)
- Blacklist tokens JWT (STRING)
"""
import json
import logging
from datetime import datetime
from typing import Optional
import redis

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import settings

logger = logging.getLogger(__name__)

# ── Connexion Redis ───────────────────────────────────────────
try:
    r = redis.Redis(
        host     = settings.redis_host,
        port     = settings.redis_port,
        password = settings.redis_password or None,
        db       = 0,
        decode_responses = True,   # retourne des strings, pas des bytes
    )
    r.ping()
    logger.info("[Redis] Connexion établie")
except Exception as e:
    logger.error(f"[Redis] Connexion échouée : {e}")
    r = None


def _check() -> bool:
    """Vérifie que Redis est disponible."""
    return r is not None


# ══════════════════════════════════════════════════════════════
# 1. HISTORIQUE DES CONVERSATIONS
# Clé : conv:{user_id}:{project_id}  — LIST  — TTL 7 jours
# ══════════════════════════════════════════════════════════════
CONV_TTL = 7 * 24 * 3600   # 7 jours

def save_message(user_id: str, project_id: str,
                 role: str, content: str,
                 intent: str = "", agent: str = "") -> bool:
    """
    Sauvegarde un message dans l'historique Redis.
    Appelé après chaque échange dans le chat.
    """
    if not _check(): return False
    try:
        key = f"conv:{user_id}:{project_id}"
        msg = json.dumps({
            "role":      role,
            "content":   content,
            "intent":    intent,
            "agent":     agent,
            "timestamp": datetime.now().isoformat(),
        }, ensure_ascii=False)
        r.rpush(key, msg)
        r.expire(key, CONV_TTL)
        # Garder max 100 messages par conversation
        r.ltrim(key, -100, -1)
        return True
    except Exception as e:
        logger.error(f"[Redis] save_message : {e}")
        return False


def get_history(user_id: str, project_id: str,
                last_n: int = 10) -> list[dict]:
    """
    Récupère les N derniers messages de la conversation.
    Utilisé par les agents pour le contexte.
    """
    if not _check(): return []
    try:
        key  = f"conv:{user_id}:{project_id}"
        msgs = r.lrange(key, -last_n, -1)
        return [json.loads(m) for m in msgs]
    except Exception as e:
        logger.error(f"[Redis] get_history : {e}")
        return []


def clear_history(user_id: str, project_id: str) -> bool:
    """Vide l'historique d'une conversation."""
    if not _check(): return False
    try:
        r.delete(f"conv:{user_id}:{project_id}")
        return True
    except Exception as e:
        logger.error(f"[Redis] clear_history : {e}")
        return False


def get_all_conversations(user_id: str) -> list[str]:
    """Liste tous les projets avec lesquels l'utilisateur a conversé."""
    if not _check(): return []
    try:
        keys = r.keys(f"conv:{user_id}:*")
        return [k.split(":")[-1] for k in keys]
    except Exception as e:
        logger.error(f"[Redis] get_all_conversations : {e}")
        return []


# ══════════════════════════════════════════════════════════════
# 2. SESSION UTILISATEUR
# Clé : session:{user_id}  — HASH  — TTL 1 heure
# ══════════════════════════════════════════════════════════════
SESSION_TTL = 3600   # 1 heure (= durée du JWT access token)

def save_session(user_id: str, project_id: str,
                 user_data: dict) -> bool:
    """
    Sauvegarde la session active de l'utilisateur.
    Appelé au login.
    """
    if not _check(): return False
    try:
        key = f"session:{user_id}"
        r.hset(key, mapping={
            "project_id":    project_id,
            "user_login":    user_data.get("login", ""),
            "user_email":    user_data.get("email", ""),
            "is_admin":      str(user_data.get("is_admin", False)),
            "last_activity": datetime.now().isoformat(),
        })
        r.expire(key, SESSION_TTL)
        return True
    except Exception as e:
        logger.error(f"[Redis] save_session : {e}")
        return False


def get_session(user_id: str) -> Optional[dict]:
    """Récupère la session active."""
    if not _check(): return None
    try:
        key  = f"session:{user_id}"
        data = r.hgetall(key)
        return data if data else None
    except Exception as e:
        logger.error(f"[Redis] get_session : {e}")
        return None


def update_session_project(user_id: str, project_id: str) -> bool:
    """Met à jour le projet actif dans la session."""
    if not _check(): return False
    try:
        key = f"session:{user_id}"
        r.hset(key, mapping={
            "project_id":    project_id,
            "last_activity": datetime.now().isoformat(),
        })
        r.expire(key, SESSION_TTL)
        return True
    except Exception as e:
        logger.error(f"[Redis] update_session_project : {e}")
        return False


def delete_session(user_id: str) -> bool:
    """Supprime la session (logout)."""
    if not _check(): return False
    try:
        r.delete(f"session:{user_id}")
        return True
    except Exception as e:
        logger.error(f"[Redis] delete_session : {e}")
        return False


# ══════════════════════════════════════════════════════════════
# 3. MÉMOIRE DES AGENTS
# Clé : memory:{agent}:{project_id}  — HASH  — TTL 30 min
# ══════════════════════════════════════════════════════════════
MEMORY_TTL = 30 * 60   # 30 minutes

def save_agent_memory(agent: str, project_id: str,
                      data: dict) -> bool:
    """
    Sauvegarde la mémoire d'un agent pour un projet.
    Appelé à la fin de chaque traitement d'agent.
    """
    if not _check(): return False
    try:
        key     = f"memory:{agent}:{project_id}"
        mapping = {k: str(v) for k, v in data.items()}
        mapping["updated_at"] = datetime.now().isoformat()
        r.hset(key, mapping=mapping)
        r.expire(key, MEMORY_TTL)
        return True
    except Exception as e:
        logger.error(f"[Redis] save_agent_memory : {e}")
        return False


def get_agent_memory(agent: str, project_id: str) -> Optional[dict]:
    """
    Récupère la mémoire d'un agent.
    Permet aux agents de se souvenir de leurs analyses précédentes.
    """
    if not _check(): return None
    try:
        key  = f"memory:{agent}:{project_id}"
        data = r.hgetall(key)
        return data if data else None
    except Exception as e:
        logger.error(f"[Redis] get_agent_memory : {e}")
        return None


# ══════════════════════════════════════════════════════════════
# 4. CACHE MÉTRIQUES REDMINE
# Clé : metrics:{project_id}  — HASH  — TTL 15 min
# ══════════════════════════════════════════════════════════════
METRICS_TTL = 15 * 60   # 15 minutes

def cache_metrics(project_id: str, metrics: dict) -> bool:
    """
    Met en cache les métriques Redmine.
    Évite d'appeler Redmine à chaque requête Streamlit.
    """
    if not _check(): return False
    try:
        key     = f"metrics:{project_id}"
        mapping = {k: str(v) for k, v in metrics.items()}
        mapping["computed_at"] = datetime.now().isoformat()
        r.hset(key, mapping=mapping)
        r.expire(key, METRICS_TTL)
        return True
    except Exception as e:
        logger.error(f"[Redis] cache_metrics : {e}")
        return False


def get_cached_metrics(project_id: str) -> Optional[dict]:
    """
    Récupère les métriques depuis le cache.
    Retourne None si cache expiré → appel Redmine nécessaire.
    """
    if not _check(): return None
    try:
        key  = f"metrics:{project_id}"
        data = r.hgetall(key)
        return data if data else None
    except Exception as e:
        logger.error(f"[Redis] get_cached_metrics : {e}")
        return None


# ══════════════════════════════════════════════════════════════
# 5. CACHE RISQUES
# Clé : risk:{project_id}  — HASH  — TTL 30 min
# ══════════════════════════════════════════════════════════════
RISK_TTL = 30 * 60   # 30 minutes

def cache_risk(project_id: str, risk_data: dict) -> bool:
    """Cache le score de risque calculé."""
    if not _check(): return False
    try:
        key     = f"risk:{project_id}"
        mapping = {k: str(v) for k, v in risk_data.items()}
        mapping["computed_at"] = datetime.now().isoformat()
        r.hset(key, mapping=mapping)
        r.expire(key, RISK_TTL)
        return True
    except Exception as e:
        logger.error(f"[Redis] cache_risk : {e}")
        return False


def get_cached_risk(project_id: str) -> Optional[dict]:
    """Récupère le score de risque depuis le cache."""
    if not _check(): return None
    try:
        key  = f"risk:{project_id}"
        data = r.hgetall(key)
        return data if data else None
    except Exception as e:
        logger.error(f"[Redis] get_cached_risk : {e}")
        return None


# ══════════════════════════════════════════════════════════════
# 6. ALERTES PROACTIVES
# Clé : alerts:{project_id}  — LIST  — TTL 30 min
# ══════════════════════════════════════════════════════════════
ALERTS_TTL = 30 * 60

def push_alert(project_id: str, alert: dict) -> bool:
    """
    Ajoute une alerte dans la liste Redis.
    Appelé par monitor.py quand une anomalie est détectée.
    """
    if not _check(): return False
    try:
        key = f"alerts:{project_id}"
        r.rpush(key, json.dumps(alert, ensure_ascii=False))
        r.expire(key, ALERTS_TTL)
        return True
    except Exception as e:
        logger.error(f"[Redis] push_alert : {e}")
        return False


def pop_alerts(project_id: str) -> list[dict]:
    """
    Récupère ET vide les alertes d'un projet.
    Appelé par Streamlit toutes les 60 secondes.
    """
    if not _check(): return []
    try:
        key    = f"alerts:{project_id}"
        alerts = r.lrange(key, 0, -1)
        r.delete(key)
        return [json.loads(a) for a in alerts]
    except Exception as e:
        logger.error(f"[Redis] pop_alerts : {e}")
        return []


# ══════════════════════════════════════════════════════════════
# 7. BLACKLIST JWT (révocation tokens après logout)
# Clé : blacklist:token:{jti}  — STRING  — TTL = expiration JWT
# ══════════════════════════════════════════════════════════════
def blacklist_token(jti: str, expires_in: int) -> bool:
    """
    Révoque un token JWT après logout.
    jti = JWT ID unique dans le payload du token.
    expires_in = secondes avant expiration du token.
    """
    if not _check(): return False
    try:
        key = f"blacklist:token:{jti}"
        r.setex(key, expires_in, "revoked")
        return True
    except Exception as e:
        logger.error(f"[Redis] blacklist_token : {e}")
        return False


def is_token_blacklisted(jti: str) -> bool:
    """
    Vérifie si un token est révoqué.
    Appelé dans get_current_user() à chaque requête.
    """
    if not _check(): return False
    try:
        return r.exists(f"blacklist:token:{jti}") == 1
    except Exception as e:
        logger.error(f"[Redis] is_token_blacklisted : {e}")
        return False


# ══════════════════════════════════════════════════════════════
# 8. UTILITAIRES
# ══════════════════════════════════════════════════════════════
def health_check() -> bool:
    """Vérifie que Redis est accessible."""
    try:
        return r.ping()
    except Exception:
        return False


def get_stats() -> dict:
    """Statistiques Redis pour le monitoring."""
    if not _check(): return {}
    try:
        info = r.info()
        return {
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_keys":        r.dbsize(),
            "uptime_days":       info.get("uptime_in_days"),
        }
    except Exception as e:
        logger.error(f"[Redis] get_stats : {e}")
        return {}