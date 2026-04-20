"""
Client API sécurisé — frontend/utils/api_client.py
Envoie le JWT dans chaque requête FastAPI.
"""
import requests
import logging
import streamlit as st
logger = logging.getLogger(__name__)
FASTAPI_URL     = "http://localhost:8000/api/v1"
TIMEOUT_CHAT    = 90
TIMEOUT_METRICS = 20
TIMEOUT_ALERTS  = 5

from utils.cookies import cookie_manager


def _get_headers() -> dict:
    """Retourne les headers avec le JWT du session_state."""
    token = st.session_state.get("access_token", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


def _handle_401():
    """Si token expiré → déconnecter et rediriger."""
    st.warning("⚠️ Session expirée. Reconnectez-vous.")
    
    # Suppression des cookies
    try:
        cookie_manager.delete("access_token")
        cookie_manager.delete("refresh_token")
        cookie_manager.delete("user")
    except Exception:
        pass

    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.switch_page("pages/login.py") 


def ask_agent(question: str, project_id: str,
              project_name: str = "", user_id: str = "chef_projet",
              history: list = None, conversation_id: str = None) -> dict:
    try:
        payload = {
            "question": question,
            "project_id": str(project_id),
            "project_name": str(project_name),
            "user_id": user_id,
            "history": history or [],
            "conversation_id": conversation_id
        }
        resp = requests.post(
            f"{FASTAPI_URL}/chat",
            json=payload,
            headers=_get_headers(),
            timeout=TIMEOUT_CHAT,
        )
        if resp.status_code == 401:
            _handle_401()
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"answer": "⏱️ Timeout. Réessayez.", "intent": "error",
                "display_type": "text", "data": {}}
    except requests.exceptions.ConnectionError:
        return {"answer": "❌ Serveur inaccessible.", "intent": "error",
                "display_type": "text", "data": {}}
    except Exception as e:
        return {"answer": f"❌ Erreur : {e}", "intent": "error",
                "display_type": "text", "data": {}}


def get_metrics(project_id: str) -> dict:
    try:
        resp = requests.get(
            f"{FASTAPI_URL}/projects/{project_id}/metrics",
            headers=_get_headers(), timeout=TIMEOUT_METRICS,
        )
        if resp.status_code == 401: _handle_401()
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {"avancement": 0, "retard": 0, "risques": 0, "charge": 0, "delta": 0}


def get_alerts(project_id: str) -> list:
    try:
        resp = requests.get(
            f"{FASTAPI_URL}/alerts/{project_id}",
            headers=_get_headers(), timeout=TIMEOUT_ALERTS,
        )
        if resp.status_code == 401: _handle_401()
        resp.raise_for_status()
        return resp.json().get("alerts", [])
    except Exception:
        return []