import streamlit as st
import requests

# ── CONFIGURATION ──
REDMINE_URL = "http://localhost:3000"

st.set_page_config(
    page_title="PM chatbot — Connexion",
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
    """Vérifie les credentials ET force le rôle Manager."""
    try:
        # On demande explicitement les memberships (adhésions aux projets)
        r = requests.get(
            f"{REDMINE_URL}/users/current.json?include=memberships",
            auth=(login, password),
            timeout=8,
        )
        
        if r.status_code == 200:
            user_data = r.json().get("user", {})
            memberships = user_data.get("memberships", [])
            
            # Vérification : l'utilisateur doit avoir le rôle 'Manager'
            # dans au moins un projet actif.
            is_manager = False
            for m in memberships:
                # Récupère la liste des noms de rôles pour ce projet
                user_roles = [role.get("name") for role in m.get("roles", [])]
                
                if "Manager" in user_roles:
                    is_manager = True
                    break
            
            if not is_manager:
                return "ACCESS_DENIED" # Identifiants OK, mais pas Manager
                
            return {
                "id": user_data.get("id"),
                "full_name": f"{user_data.get('firstname','')} {user_data.get('lastname','')}".strip(),
                "api_key": user_data.get("api_key"),
            }
        return None
    except Exception as e:
        print(f"Erreur Auth: {e}")
        return None
def get_user_projects(api_key):
    """
    Récupère uniquement les projets où l'utilisateur est membre actif.
    """
    try:
        # On interroge l'utilisateur actuel avec ses adhésions (memberships)
        r = requests.get(
            f"{REDMINE_URL}/users/current.json?include=memberships",
            headers={"X-Redmine-API-Key": api_key},
            timeout=8,
        )
        
        if r.status_code == 200:
            user_data = r.json().get("user", {})
            memberships = user_data.get("memberships", [])
            
            # On extrait uniquement les projets où l'utilisateur a un rôle
            projects = []
            for m in memberships:
                project_info = m.get("project", {})
                # On ne récupère que les projets qui ne sont pas archivés
                if project_info:
                    projects.append({
                        "id": project_info.get("id"),
                        "name": project_info.get("name"),
                        "identifier": project_info.get("name").lower().replace(" ", "-") # Fallback
                    })
            return projects
        return []
    except Exception as e:
        print(f"Erreur récupération projets : {e}")
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
            with st.spinner("Vérification des accès..."):
                user = authenticate_redmine(login, password)
                
                if user == "ACCESS_DENIED":
                    st.error("❌ Accès refusé : Cette application est réservée seulement aux ProjectManagers.")
                
                elif isinstance(user, dict):  # Si c'est un dictionnaire, l'auth est réussie
                    # 1. Récupérer les projets avec la clé API de l'utilisateur
                    projects = get_user_projects(user["api_key"])
                    
                    # 2. Stocker les infos dans la session
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.session_state["projects"] = projects
                    
                    # 3. Initialiser le projet actif par défaut
                    if projects:
                        # On utilise l'ID pour être sûr de matcher avec ton backend
                        st.session_state["projet_actif"] = str(projects[0]["id"]) 
                        st.session_state["projet_name"] = projects[0]["name"]
                        st.success(f"Bienvenue Manager {user['full_name']} !")
                        st.rerun()
                    else:
                        st.warning("⚠️ Connexion réussie, mais aucun projet trouvé pour ce compte.")
                
                else:
                    st.error("❌ Identifiant ou mot de passe incorrect.")
        else:
            st.warning("Veuillez remplir tous les champs.")