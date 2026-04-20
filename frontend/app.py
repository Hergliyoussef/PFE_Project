# frontend/app.py
import streamlit as st
import json
from utils.cookies import cookie_manager

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    # Tentative de récupération depuis les cookies
    access_token = cookie_manager.get("access_token")
    
    if access_token:
        try:
            st.session_state["access_token"] = access_token
            st.session_state["refresh_token"] = cookie_manager.get("refresh_token")
            
            user_json = cookie_manager.get("user")

            if user_json:
                user_data = json.loads(user_json)
                st.session_state["user"] = user_data
                st.session_state["authenticated"] = True
                
                projects = user_data.get("authorized_projects", [])
                st.session_state["projects"] = projects
                st.session_state["active_project"] = projects[0] if projects else None
                
                # Succès -> Redirection vers le chat
                st.switch_page("pages/chat.py")
        except Exception:
            # En cas d'erreur de parsing ou autre, on laisse aller au login
            pass

# Si toujours pas authentifié
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.switch_page("pages/login.py") 
else:
    st.switch_page("pages/chat.py")