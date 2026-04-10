"""
Page Login — frontend/login.py
Utilise JWT via FastAPI au lieu d'appeler Redmine directement.
"""
import streamlit as st
import requests

FASTAPI_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title = "PM Assistant — Connexion",
    page_icon  = "🔐",
    layout     = "centered",
    initial_sidebar_state = "collapsed",
)

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 420px; padding-top: 80px; }
.stButton > button {
    width: 100%; height: 44px;
    background: #5c5fef; color: white;
    border: none; border-radius: 8px;
    font-size: 15px; font-weight: 500;
}
.stButton > button:hover { background: #4547d4; }
</style>
""", unsafe_allow_html=True)

# Si déjà connecté → rediriger
if st.session_state.get("authenticated"):
    st.switch_page("pages/chat.py")

st.markdown('<div style="text-align:center;font-size:28px;font-weight:600;margin-bottom:4px">PM Assistant</div>', unsafe_allow_html=True)
st.markdown('<div style="text-align:center;font-size:14px;color:#888;margin-bottom:32px">Assistant IA pour chefs de projet</div>', unsafe_allow_html=True)

st.markdown("**Connexion**")
st.caption("Utilisez vos identifiants Redmine")

login    = st.text_input("Identifiant", placeholder="youssef.hergli")
password = st.text_input("Mot de passe", type="password", placeholder="••••••••")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("Se connecter", use_container_width=True):
    if not login or not password:
        st.error("Veuillez remplir tous les champs.")
    else:
        with st.spinner("Connexion en cours..."):
            try:
                # ── Appel FastAPI /auth/login → JWT ───────────
                resp = requests.post(
                    f"{FASTAPI_URL}/auth/login",
                    json={"login": login, "password": password},
                    timeout=10,
                )

                if resp.status_code == 200:
                    data = resp.json()

                    # Sauvegarder JWT dans session_state
                    st.session_state["authenticated"]  = True
                    st.session_state["access_token"]   = data["access_token"]
                    st.session_state["refresh_token"]  = data["refresh_token"]
                    st.session_state["user"]           = data["user"]

                    # Récupérer les projets (utiliser config du backend plutôt que hardcoder)
                    redmine_url = "http://localhost:3000"  # fallback
                    try:
                        import sys, os
                        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                        from backend.config import settings
                        redmine_url = settings.redmine_url
                    except:
                        pass  # utiliser le fallback
                    
                    projects_resp = requests.get(
                        f"{redmine_url}/projects.json",
                        headers={"X-Redmine-API-Key": data["user"]["api_key"]},
                        timeout=8,
                    )
                    projects = []
                    if projects_resp.status_code == 200:
                        projects = projects_resp.json().get("projects", [])

                    st.session_state["projects"]       = projects
                    st.session_state["projet_actif"]   = projects[0]["identifier"] if projects else ""
                    st.session_state["projet_name"]    = projects[0]["name"] if projects else ""

                    st.success(f"Bienvenue, {data['user']['firstname']} !")
                    st.rerun()

                elif resp.status_code == 401:
                    st.error("Identifiant ou mot de passe incorrect.")
                else:
                    st.error(f"Erreur serveur ({resp.status_code}).")

            except requests.exceptions.ConnectionError:
                st.error("❌ Impossible de contacter le serveur FastAPI (port 8000).")
            except Exception as e:
                st.error(f"Erreur : {e}")

st.divider()
st.caption("🔒 Authentification sécurisée via JWT — session valide 1 heure.")