"""
Garde d'authentification & Sidebar — frontend/utils/auth_guard.py
"""
import streamlit as st
import requests
from datetime import datetime
import json
from utils.cookies import cookie_manager

FASTAPI_URL = "http://localhost:8000/api/v1"

def _try_restore_session():
    """Tente de restaurer la session depuis les cookies si non authentifié."""
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        access_token = cookie_manager.get("access_token")
        if access_token:
            try:
                user_json = cookie_manager.get("user")
                if user_json:
                    user_data = json.loads(user_json)
                    st.session_state["access_token"]   = access_token
                    st.session_state["refresh_token"]  = cookie_manager.get("refresh_token")
                    st.session_state["user"]           = user_data
                    st.session_state["authenticated"]  = True
                    
                    projects = user_data.get("authorized_projects", [])
                    st.session_state["projects"]       = projects
                    st.session_state["active_project"] = projects[0] if projects else None
                    return True
            except Exception:
                pass
    return False

def _get_headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def _load_conversations() -> list:
    needs_refresh = st.session_state.get("refresh_conversations", True)
    if needs_refresh or "conversations_list" not in st.session_state:
        try:
            resp = requests.get(f"{FASTAPI_URL}/conversations", headers=_get_headers(), timeout=8)
            if resp.status_code == 200:
                data = resp.json().get("conversations", [])
                st.session_state["conversations_list"] = data
            else:
                st.session_state.setdefault("conversations_list", [])
        except Exception:
            st.session_state.setdefault("conversations_list", [])
        st.session_state["refresh_conversations"] = False
    return st.session_state.get("conversations_list", [])

def _select_conversation(conv: dict):
    project_list = st.session_state.get("projects", [])
    target = next((p for p in project_list if p.get("identifier") == conv["project_id"]), None)
    if target:
        st.session_state["active_project"] = target
        st.session_state["last_project_id"] = target["identifier"]
    st.session_state["active_conv_id"] = conv["id"]
    st.session_state.messages = []
    st.rerun()

def _new_conversation():
    st.session_state["active_conv_id"] = None
    st.session_state["is_new_session"] = True
    st.session_state.messages = []
    st.session_state["refresh_conversations"] = True
    st.rerun()

def require_login():
    # 1. Tentative de restauration auto via cookies si besoin
    _try_restore_session()
    
    # 2. Vérification finale
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        st.switch_page("pages/login.py")
        st.stop()
    render_sidebar()

def get_active_project():
    return st.session_state.get("active_project")

def render_sidebar():
    """Affiche le sidebar avec Top/Bottom fixés et Milieu scrollable (Version Slate Pro)."""
    with st.sidebar:
        # CSS Premium Slate Pro (Fixed Layout)
        st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Fond global sidebar Slate/Deep Blue */
[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}
[data-testid="stSidebarNav"] { display: none !important; }

/* Masquer le scroll padding de Streamlit */
[data-testid="stSidebarUserContent"] {
    padding: 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
}

/* Forcer le conteneur principal en Flexbox 100vh */
[data-testid="stSidebarUserContent"] > div {
    height: 100vh !important;
}
[data-testid="stSidebarUserContent"] > div > div[data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    overflow: hidden !important; 
    gap: 0 !important;
}

/* --- SECTION HAUT (HEADER) --- */
div[data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"] > div:has(div[data-sidebar-top="1"]) {
    flex-shrink: 0 !important;
    padding: 1rem 1rem 8px 1rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.05) !important;
    z-index: 10;
}

/* --- SECTION MILIEU (SCROLLABLE) --- */
div[data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"] > div:has(div[data-sidebar-middle="1"]) {
    flex-grow: 1 !important;
    overflow-y: auto !important; 
    overflow-x: hidden !important;
    padding: 8px 1rem !important;
    scrollbar-width: thin;
    scrollbar-color: rgba(99,102,241,0.2) transparent;
}
/* Style Scrollbar */
div[data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"] > div:has(div[data-sidebar-middle="1"])::-webkit-scrollbar {
    width: 5px;
}
div[data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"] > div:has(div[data-sidebar-middle="1"])::-webkit-scrollbar-thumb {
    background: rgba(99,102,241,0.15);
    border-radius: 10px;
}

/* --- SECTION BAS (FOOTER) --- */
div[data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"] > div:has(div[data-sidebar-bottom="1"]) {
    flex-shrink: 0 !important;
    margin-top: auto !important;
    padding: 8px 1rem 1rem 1rem !important;
    border-top: 1px solid rgba(255,255,255,0.05) !important;
    z-index: 10;
}

/* Force zero gaps in sidebar blocks */
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}

/* Remove Streamlit default top padding from sidebar section */
[data-testid="stSidebar"] section {
    padding-top: 0 !important;
}

/* Boutons & Composants */
div[data-conv-new="1"] button {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: 12px 16px !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.3);
    transition: all 0.2s ease;
}
div[data-conv-new="1"] button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(99,102,241,0.4);
}
div[data-conv-item="1"] button, div[data-conv-active="1"] button {
    text-align: left !important;
    border-radius: 9px !important;
    padding: 10px 12px !important;
    font-size: 13px !important;
    border: 1px solid transparent !important;
    transition: all 0.15s ease;
}
div[data-conv-item="1"] button:hover {
    background: rgba(255,255,255,0.04) !important;
}
div[data-conv-active="1"] button {
    background: rgba(99,102,241,0.12) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    color: #a5b4fc !important;
}
.stExpander {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
}
[data-logout="1"] button {
    background: rgba(239,68,68,0.1) !important;
    border: 1px solid rgba(239,68,68,0.15) !important;
    color: #fca5a5 !important;
    font-size: 12px !important;
}
</style>
""", unsafe_allow_html=True)

        # ── 1. HAUT (FIXÉ) ──────────────────────────────────────────
        with st.container():
            st.markdown('<div data-sidebar-top="1"></div>', unsafe_allow_html=True)
            st.markdown("""
<div style="text-align:center; padding-bottom:15px;">
<div style="font-size:20px; margin-bottom:4px;">🤖</div>
<div style="font-size:20px; font-weight:800; color:#818cf8;">PM Assistant</div>
</div>
""", unsafe_allow_html=True)

            st.markdown('<div data-conv-new="1">', unsafe_allow_html=True)
            if st.button("💬  Nouvelle conversation", key="new_conv_btn", width='stretch'):
                _new_conversation()
            st.markdown("</div>", unsafe_allow_html=True)

            if "projects" in st.session_state and st.session_state["projects"]:
                project_names = [p["name"] for p in st.session_state["projects"]]
                if "active_project" not in st.session_state:
                    st.session_state["active_project"] = st.session_state["projects"][0]
                current_proj = st.session_state["active_project"]
                current_index = 0
                try: current_index = project_names.index(current_proj["name"])
                except: pass

                def on_project_change():
                    new_name = st.session_state["project_selector_sidebar"]
                    new_proj = next(p for p in st.session_state["projects"] if p["name"] == new_name)
                    st.session_state["active_project"] = new_proj
                    st.session_state["active_conv_id"] = None
                    st.session_state.messages = []
                    st.session_state["refresh_conversations"] = True

                st.markdown('<div style="font-size:9px; color:#475569; font-weight:700; margin:15px 0 5px 0;">📁 PROJET ACTIF</div>', unsafe_allow_html=True)
                st.selectbox("P", options=project_names, index=current_index, key="project_selector_sidebar", on_change=on_project_change, label_visibility="collapsed")

        # ── 2. MILIEU (SCROLLABLE) ──────────────────────────────────
        with st.container():
            st.markdown('<div data-sidebar-middle="1"></div>', unsafe_allow_html=True)
            st.markdown('<div style="margin-top:10px; font-size:10px; color:#475569; font-weight:700;">💬 DISCUSSIONS RÉCENTES</div>', unsafe_allow_html=True)
            
            conversations = _load_conversations()
            active_proj_id = st.session_state.get("active_project", {}).get("identifier", "")
            active_conv_id = st.session_state.get("active_conv_id")

            if conversations:
                for conv in conversations:
                    if conv["project_id"] != active_proj_id: continue
                    is_active = (conv["id"] == active_conv_id)
                    attr = 'data-conv-active="1"' if is_active else 'data-conv-item="1"'
                    try: c_date = datetime.fromisoformat(conv["created_at"].replace("Z", "+00:00")).strftime("%d/%m")
                    except: c_date = "--/--"
                    label = f"{'🟢' if is_active else '⚫'} {c_date} - {conv['title'][:25]}"
                    
                    st.markdown(f'<div {attr}>', unsafe_allow_html=True)
                    if st.button(label, key=f"conv_btn_{conv['id']}", width='stretch'):
                        _select_conversation(conv)
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Aucune discussion.")

        # ── 3. BAS (FIXÉ) ───────────────────────────────────────────
        if "user" in st.session_state:
            with st.container():
                st.markdown('<div data-sidebar-bottom="1"></div>', unsafe_allow_html=True)
                user = st.session_state["user"]
                fn, ln = user.get("firstname", ""), user.get("lastname", "")
                full_name = f"{fn} {ln}".strip() or "Utilisateur"
                initials  = (fn[:1] + ln[:1]).upper() if fn and ln else "U"
                role      = user.get("roles", ["Utilisateur"])[0]

                with st.expander(f"👤 {initials} - {full_name}"):
                    st.markdown(f"""
                    <div style="font-size:12px; color:#94a3b8; margin-bottom:25px; line-height:1.6;">
                    <b>Identifiant :</b> {user.get('login')}<br>
                    <b>Rôle :</b> {role}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown('<div data-logout="1">', unsafe_allow_html=True)
                    if st.button("🚪 Déconnexion", key="sidebar_logout_btn", width='stretch'):
                        # Suppression des cookies (Unique Keys required for .delete)
                        try:
                            cookie_manager.delete("access_token", key="del_at_logout")
                            cookie_manager.delete("refresh_token", key="del_rt_logout")
                            cookie_manager.delete("user", key="del_user_logout")
                        except Exception:
                            pass
                        
                        st.session_state.clear()
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)