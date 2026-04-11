"""
Garde d'authentification & Sidebar — frontend/utils/auth_guard.py

Fonctionnalités du sidebar :
  - Profil utilisateur avec avatar initiales
  - Sélecteur de projet
  - Bouton "Nouvelle conversation"
  - Liste des conversations récentes (avec aperçu du dernier message)
  - Bouton de déconnexion
"""
import streamlit as st
import requests

FASTAPI_URL = "http://localhost:8000/api/v1"


# ── Helpers internes ───────────────────────────────────────────

def _get_headers() -> dict:
    """Retourne les headers JWT pour les appels API."""
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _load_conversations() -> list:
    """
    Charge les conversations depuis le cache session_state ou l'API.
    """
    needs_refresh = st.session_state.get("refresh_conversations", True)
    if needs_refresh or "conversations_list" not in st.session_state:
        try:
            resp = requests.get(
                f"{FASTAPI_URL}/conversations",
                headers=_get_headers(),
                timeout=8,
            )
            if resp.status_code == 200:
                st.session_state["conversations_list"] = resp.json().get("conversations", [])
            else:
                st.session_state.setdefault("conversations_list", [])
        except Exception:
            st.session_state.setdefault("conversations_list", [])
        st.session_state["refresh_conversations"] = False

    return st.session_state.get("conversations_list", [])


def _select_conversation(conv: dict):
    """
    Sélectionne une conversation existante.
    """
    project_list = st.session_state.get("projects", [])
    target = next((p for p in project_list if p.get("identifier") == conv["project_id"]), None)
    if target:
        st.session_state["active_project"] = target
        st.session_state["last_project_id"] = target["identifier"]
    
    st.session_state["active_conv_id"] = conv["id"]
    st.session_state.messages = []
    st.rerun()


def _new_conversation():
    """
    Démarre une nouvelle conversation en réinitialisant l'ID actif.
    L'historique Postgres est préservé.
    """
    st.session_state["active_conv_id"] = None
    st.session_state.messages = []
    st.session_state["refresh_conversations"] = True
    st.rerun()


# ── API publique ───────────────────────────────────────────────

def require_login():
    """Point d'entrée : vérifie l'auth et affiche le sidebar."""
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        st.warning("Veuillez vous connecter.")
        st.switch_page("pages/login.py")
        st.stop()
    render_sidebar()


def get_active_project():
    """Retourne l'objet projet actif depuis la session."""
    return st.session_state.get("active_project")


def render_sidebar():
    """Affiche le sidebar complet avec conversations et navigation."""
    with st.sidebar:
        # CSS (De-indented)
        st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f172a 0%, #1a2236 60%, #1e293b 100%);
    border-right: 1px solid rgba(99,102,241,0.18);
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span:not(.stSelectbox *), [data-testid="stSidebar"] div[class*="caption"], [data-testid="stSidebar"] small {
    color: #94a3b8 !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.07) !important;
    margin: 10px 0 !important;
}
div[data-testid="stSidebar"] div[data-conv-new="1"] button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 16px !important;
    letter-spacing: 0.3px;
    box-shadow: 0 2px 8px rgba(99,102,241,0.3);
}
div[data-testid="stSidebar"] div[data-conv-item="1"] button {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #cbd5e1 !important;
    border-radius: 9px !important;
    text-align: left !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
}
div[data-testid="stSidebar"] div[data-conv-active="1"] button {
    background: rgba(99,102,241,0.18) !important;
    border: 1px solid rgba(99,102,241,0.45) !important;
    color: #a5b4fc !important;
    border-radius: 9px !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
    font-weight: 600 !important;
}
div[data-testid="stSidebar"] div[data-logout="1"] button {
    background: rgba(239,68,68,0.1) !important;
    border: 1px solid rgba(239,68,68,0.25) !important;
    color: #fca5a5 !important;
    border-radius: 9px !important;
    font-size: 13px !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(99,102,241,0.25) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}
</style>
""", unsafe_allow_html=True)

        # Branding
        st.markdown("""
<div style="text-align:center; padding:20px 0 14px 0;">
<div style="font-size:38px; line-height:1; margin-bottom:6px;">🤖</div>
<div style="font-size:17px; font-weight:700; color:#818cf8; letter-spacing:0.4px;">PM Assistant</div>
<div style="font-size:11px; color:#475569; margin-top:3px; letter-spacing:0.5px;">Gestion de projet</div>
</div>
""", unsafe_allow_html=True)

        if "user" in st.session_state:
            user  = st.session_state.get("user", {})
            fn    = user.get("firstname", "")
            ln    = user.get("lastname", "")
            full  = f"{fn} {ln}".strip() or user.get("login", "Utilisateur")
            inits = (fn[:1] + ln[:1]).upper() if fn and ln else full[:2].upper()
            roles = user.get("roles", [])
            role_display = roles[0] if roles else "Utilisateur"

            st.markdown(f"""
<div style="display:flex; align-items:center; gap:10px; background:rgba(99,102,241,0.09); border:1px solid rgba(99,102,241,0.2); border-radius:10px; padding:10px 12px; margin-bottom:4px;">
<div style="width:36px; height:36px; border-radius:50%; flex-shrink:0; background:linear-gradient(135deg,#6366f1,#8b5cf6); display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; color:#fff;">{inits}</div>
<div style="overflow:hidden;">
<div style="font-size:13px; font-weight:600; color:#e2e8f0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{full}</div>
<div style="font-size:11px; color:#64748b;">{role_display}</div>
</div>
</div>
""", unsafe_allow_html=True)

        st.divider()

        if "projects" in st.session_state and st.session_state["projects"]:
            project_names = [p["name"] for p in st.session_state["projects"]]
            if "active_project" not in st.session_state:
                st.session_state["active_project"] = st.session_state["projects"][0]
            current_proj = st.session_state["active_project"]
            try:
                current_index = project_names.index(current_proj["name"])
            except ValueError:
                current_index = 0

            def on_project_change():
                new_name = st.session_state["project_selector_sidebar"]
                new_proj = next(p for p in st.session_state["projects"] if p["name"] == new_name)
                st.session_state["active_project"] = new_proj
                st.session_state["active_conv_id"] = None
                st.session_state.messages = []
                st.session_state["refresh_conversations"] = True

            st.markdown("""
<div style="font-size:10px; color:#475569; text-transform:uppercase; letter-spacing:1.2px; margin-bottom:6px; font-weight:600;">📁 PROJET ACTIF</div>
""", unsafe_allow_html=True)
            st.selectbox("Projet", options=project_names, index=current_index, key="project_selector_sidebar", on_change=on_project_change, label_visibility="collapsed")

        st.divider()

        st.markdown("""
<div style="font-size:10px; color:#475569; text-transform:uppercase; letter-spacing:1.2px; margin-bottom:10px; font-weight:600;">💬 CONVERSATIONS</div>
""", unsafe_allow_html=True)

        st.markdown('<div data-conv-new="1">', unsafe_allow_html=True)
        if st.button("✏️  Nouvelle conversation", key="new_conv_btn", use_container_width=True):
            _new_conversation()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

        conversations = _load_conversations()
        active_proj_id = st.session_state.get("active_project", {}).get("identifier", "")
        active_conv_id = st.session_state.get("active_conv_id")

        if conversations:
            for conv in conversations:
                # Filtrer les conversations par projet actif
                if conv["project_id"] != active_proj_id:
                    continue
                
                is_active = (conv["id"] == active_conv_id)
                attr = 'data-conv-active="1"' if is_active else 'data-conv-item="1"'
                icon = "🔵" if is_active else "💬"
                label = f"{icon}  {conv['title']}"
                preview = (conv.get("last_message", "")[:45] + "…") if len(conv.get("last_message", "")) > 45 else conv.get("last_message", "")
                
                st.markdown(f'<div {attr}>', unsafe_allow_html=True)
                if st.button(label, key=f"conv_btn_{conv['id']}", use_container_width=True):
                    _select_conversation(conv)
                st.markdown("</div>", unsafe_allow_html=True)
                if preview:
                    st.markdown(f'<div style="font-size:11px; color:#475569; margin:-6px 0 6px 14px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{preview}</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="text-align:center; padding:24px 12px; color:#475569;">
<div style="font-size:28px; margin-bottom:8px;">💬</div>
<div style="font-size:13px; line-height:1.5;">Aucune conversation.<br><span style="color:#6366f1;">Commencez à chatter !</span></div>
</div>
""", unsafe_allow_html=True)

        st.divider()

        user_login = st.session_state.get("user", {}).get("login", "guest")
        st.markdown('<div data-logout="1">', unsafe_allow_html=True)
        if st.button("🚪  Déconnexion", key=f"logout_btn_{user_login}", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)