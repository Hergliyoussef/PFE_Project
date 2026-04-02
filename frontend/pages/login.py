import streamlit as st
import requests

# ── CONFIGURATION ──
REDMINE_URL = "http://localhost:3000"

st.set_page_config(
    page_title="PM Assistant — Connexion",
    page_icon="🔐",
    layout="centered"
)

# ── CSS PERSONNALISÉ (Identique à ton code) ──
st.markdown("""
<style>
    .login-title { text-align: center; font-size: 28px; font-weight: 600; color: #1a1a2e; }
    .login-sub { text-align: center; font-size: 14px; color: #888; margin-bottom: 32px; }
    .stButton > button { width: 100%; background: #5c5fef; color: white; border-radius: 8px; }
    .error-msg { background: #fff0f0; border: 1px solid #ffcdd2; border-radius: 8px; padding: 10px; color: #c62828; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ── FONCTIONS LOGIQUES ──

def authenticate_redmine(login, password):
    """Vérifie les credentials via l'API Redmine."""
    try:
        r = requests.get(
            f"{REDMINE_URL}/users/current.json",
            auth=(login, password),
            timeout=8,
        )
        if r.status_code == 200:
            user = r.json().get("user", {})
            return {
                "id": user.get("id"),
                "full_name": f"{user.get('firstname','')} {user.get('lastname','')}".strip(),
                "api_key": user.get("api_key"),
            }
        return None
    except Exception:
        return None

def get_user_projects(api_key):
    """Récupère les projets accessibles."""
    try:
        r = requests.get(
            f"{REDMINE_URL}/projects.json",
            headers={"X-Redmine-API-Key": api_key},
            timeout=8,
        )
        return r.json().get("projects", []) if r.status_code == 200 else []
    except Exception:
        return []

# ── INTERFACE UTILISATEUR ──

# Redirection si déjà connecté
if st.session_state.get("authenticated"):
    st.switch_page("pages/chat.py")

st.markdown('<div class="login-title">PM Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="login-sub">Assistant IA pour chefs de projet</div>', unsafe_allow_html=True)

with st.container():
    st.write("### Connexion")
    login = st.text_input("Identifiant", placeholder="votre.nom")
    password = st.text_input("Mot de passe", type="password")
    
    login_btn = st.button("Se connecter")

    if login_btn:
        if login and password:
            with st.spinner("Vérification..."):
                user = authenticate_redmine(login, password)
                
                if user:
                    # On utilise la clé API récupérée pour les projets
                    projects = get_user_projects(user["api_key"])
                    
                    # Stockage Session
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.session_state["projects"] = projects
                    
                    if projects:
                        st.session_state["projet_actif"] = projects[0]["identifier"]
                        st.session_state["projet_name"] = projects[0]["name"]
                    
                    st.success(f"Bienvenue {user['full_name']} !")
                    st.rerun()
                else:
                    st.markdown('<div class="error-msg">Identifiant ou mot de passe incorrect.</div>', unsafe_allow_html=True)
        else:
            st.warning("Veuillez remplir tous les champs.")