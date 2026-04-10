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
    """Affiche la barre latérale de configuration avec gestion du contexte projet."""
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        # 1. Affichage du profil utilisateur
        if "user" in st.session_state:
            user = st.session_state.get('user', {})
            firstname = user.get('firstname', '')
            lastname = user.get('lastname', '')
            full_name = f"{firstname} {lastname}".strip() or user.get('login', 'Manager')
            st.markdown(f"👤 **Project Manager :** {full_name}")
        
        st.divider()

        # 2. Gestion du Sélecteur de Projet
        if "projects" in st.session_state and st.session_state["projects"]:
            project_names = [p['name'] for p in st.session_state["projects"]]
            
            # Initialisation du projet actif
            if "active_project" not in st.session_state:
                st.session_state["active_project"] = st.session_state["projects"][0]
            
            current_project = st.session_state["active_project"]
            try:
                current_index = project_names.index(current_project['name'])
            except ValueError:
                current_index = 0

            # CALLBACK : Gère le changement de projet
            def on_project_change():
                try:
                    new_name = st.session_state["project_selector_sidebar"]
                    new_proj = next(p for p in st.session_state["projects"] if p['name'] == new_name)
                    st.session_state["active_project"] = new_proj
                    # On vide le chat car le contexte change (Crucial pour la cohérence de l'IA)
                    if "messages" in st.session_state:
                        st.session_state.messages = []
                except StopIteration:
                    st.error("Projet non trouvé")
                except Exception as e:
                    st.error(f"Erreur changement projet: {e}")

            st.selectbox(
                "📁 Choisir un projet", 
                options=project_names,
                index=current_index,
                key="project_selector_sidebar",
                on_change=on_project_change
            )

        st.divider()
        
        # 3. Bouton de Déconnexion (Clé unique basée sur le login)
        user_login = st.session_state.get('user', {}).get('login', 'guest')
        if st.button("🚪 Déconnexion", key=f"logout_btn_{user_login}", use_container_width=True):
            st.session_state.clear()
            st.rerun() # Plus propre pour réinitialiser totalement l'application

def get_active_project():
    """Récupère l'objet projet (ID et Nom) depuis la session unique."""
    return st.session_state.get("active_project")