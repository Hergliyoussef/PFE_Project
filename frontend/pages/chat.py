import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import sys, os

# Configuration des chemins
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.auth_guard import require_login, get_active_project

# 1. SÉCURITÉ & SIDEBAR (Doit être en premier)
require_login()

# 2. CONFIGURATION DE LA PAGE
st.set_page_config(
    page_title="PM Assistant",
    page_icon="🤖",
    layout="wide",
)

FASTAPI_URL = "http://localhost:8000/api/v1"

# 3. RÉCUPÉRATION UNIQUE ET DYNAMIQUE DU PROJET
# On utilise get_active_project() qui lit directement la sidebar
current_project = get_active_project()

if not current_project:
    st.error("Aucun projet sélectionné.")
    st.stop()

project_id = str(current_project['id'])
project_name = current_project['name']

# 4. LOGIQUE DE RESET (Si on change de projet dans la sidebar)
if "last_project_id" not in st.session_state:
    st.session_state["last_project_id"] = project_id

if st.session_state["last_project_id"] != project_id:
    # On vide le chat pour que l'IA change de contexte
    st.session_state.messages = [] 
    st.session_state["last_project_id"] = project_id
    st.rerun()

# 5. TITRE UNIQUE
st.title(f"🤖 PM Assistant — {project_name}")

# 6. MÉTRIQUES DYNAMIQUES (Appel au Backend avec le BON ID)
try:
    r = requests.get(f"{FASTAPI_URL}/projects/{project_id}/metrics", timeout=5)
    if r.status_code == 200:
        m = r.json()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avancement", f"{m['avancement']}%", f"+{m['delta']}%")
        c2.metric("Tâches en retard", m['retard'], delta_color="inverse")
        c3.metric("Risques", m['risques'])
        c4.metric("Charge équipe", f"{m['charge']}%")
except Exception:
    st.warning("Impossible de charger les métriques.")

st.divider()

# --- Garde tes fonctions render_component et la suite du chat ici ---

st.divider()

# 7. FONCTIONS D'AFFICHAGE (Composants Graphiques)
def render_component(display_type: str, data: dict):
    if display_type == "gantt":
        versions = data.get("versions", [])
        if versions:
            from datetime import timedelta
            rows = []
            for v in versions:
                due = v.get("due_date") or str(date.today())
                start = str(date.fromisoformat(due) - timedelta(days=30))
                rows.append({"Sprint": v["name"], "Début": start, "Fin": due, "Statut": v.get("status", "open")})
            df = pd.DataFrame(rows)
            fig = px.timeline(df, x_start="Début", x_end="Fin", y="Sprint", color="Statut", title="Planning des sprints")
            st.plotly_chart(fig, use_container_width=True)
    
    elif display_type == "workload":
        time_by_user = data.get("time_by_user", {})
        if time_by_user:
            names = list(time_by_user.keys())
            loads = [min((time_by_user[n] / 40) * 100, 100) for n in names]
            fig = go.Figure(go.Bar(x=loads, y=names, orientation="h", marker_color="#1D9E75"))
            fig.update_layout(title="Charge de l'équipe (%)", xaxis=dict(range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True)

# 8. GESTION DE L'HISTORIQUE DU CHAT
if "messages" not in st.session_state or len(st.session_state.messages) == 0:
    st.session_state.messages = [{
        "role": "assistant",
        "content": f"Bonjour ! Je suis votre assistant pour **{project_name}**.",
        "display_type": "text",
        "data": {}
    }]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("display_type") and msg["display_type"] != "text":
            render_component(msg["display_type"], msg.get("data", {}))

# 9. INPUT UTILISATEUR
question = st.chat_input("Posez votre question sur le projet…")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            try:
                resp = requests.post(
                    f"{FASTAPI_URL}/chat",
                    json={
                        "question": str(question),
                        "project_id": str(project_id),
                        "user_id": str(st.session_state["user"]["id"]),
                    },
                    timeout=60
                )
                if resp.status_code == 200:
                    res = resp.json()
                    st.markdown(res["answer"])
                    if res.get("display_type") != "text":
                        render_component(res["display_type"], res.get("data", {}))
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": res["answer"], 
                        "display_type": res.get("display_type"), 
                        "data": res.get("data")
                    })
                else:
                    st.error("Erreur serveur.")
            except Exception as e:
                st.error(f"Erreur : {e}")
    st.rerun()