import streamlit as st
import requests
import time

FASTAPI_URL = "http://localhost:8000/api/v1"

def require_login():
    """Vérifie l'authentification et affiche la barre latérale."""
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        st.warning("Veuillez vous connecter.")
        st.switch_page("pages/login.py")
        st.stop()
    render_sidebar()

def render_sidebar():
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        if "user" in st.session_state:
            st.markdown(f"**Utilisateur :** {st.session_state['user']['full_name']}")
        
        st.divider()

        if "projects" in st.session_state:
            project_names = [p['name'] for p in st.session_state["projects"]]
            
            # Récupération du projet actif ou par défaut le premier
            if "active_project" not in st.session_state:
                st.session_state["active_project"] = st.session_state["projects"][0]
            
            current_project = st.session_state["active_project"]
            try:
                current_index = project_names.index(current_project['name'])
            except ValueError:
                current_index = 0

            # CALLBACK : Cette fonction s'exécute AVANT le rechargement de la page
            def on_project_change():
                new_name = st.session_state["project_selector_sidebar"]
                new_proj = next(p for p in st.session_state["projects"] if p['name'] == new_name)
                st.session_state["active_project"] = new_proj
                # On vide le chat car le contexte change
                st.session_state.messages = []

            st.selectbox(
                "📁 Choisir un projet", 
                options=project_names,
                index=current_index,
                key="project_selector_sidebar",
                on_change=on_project_change
            )

        st.divider()
        
        if st.button("🚪 Déconnexion", key="logout_btn_sidebar"):
            st.session_state.clear()
            st.switch_page("pages/login.py")

def get_active_project():
    """Récupère l'objet projet (ID et Nom) depuis la session unique."""
    return st.session_state.get("active_project")