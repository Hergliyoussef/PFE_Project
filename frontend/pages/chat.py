import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from streamlit_autorefresh import st_autorefresh
import sys
import os

# 1. CONFIGURATION DES CHEMINS & IMPORTS LOCAUX
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.auth_guard import require_login, get_active_project

# 2. SÉCURITÉ (Doit être la toute première action)
require_login()

# 3. CONFIGURATION DE LA PAGE
st.set_page_config(
    page_title="Chatbot PM - Assistant IA",
    page_icon="🤖",
    layout="wide",
)

FASTAPI_URL = "http://localhost:8000/api/v1"

# 4. RÉCUPÉRATION DU PROJET ACTIF
current_project = get_active_project()

if not current_project:
    st.error("⚠️ Aucun projet sélectionné. Veuillez en choisir un dans la barre latérale.")
    st.stop()

project_id = str(current_project['id'])
project_name = current_project['name']

# 🔄 AUTO-REFRESH (Toute 1 minute)
# Crucial pour faire "surgir" les alertes du monitor.py sans action manuelle
st_autorefresh(interval=60000, key="monitor_refresh")

# 5. LOGIQUE DE RESET (Changement de projet)
if "last_project_id" not in st.session_state:
    st.session_state["last_project_id"] = project_id

if st.session_state["last_project_id"] != project_id:
    st.session_state.messages = [] 
    st.session_state["last_project_id"] = project_id
    st.rerun()

# 6. TITRE ET ZONE D'ALERTES PROACTIVES
st.title(f"🤖 PM Assistant — {project_name}")

# --- BLOC DE MONITORING EN TEMPS RÉEL ---
try:
    # Récupération des alertes depuis le store du Backend (monitor.py)
    from utils.api_client import _get_headers
    r_alerts = requests.get(
        f"{FASTAPI_URL}/alerts/{project_id}",
        headers=_get_headers(),
        timeout=5
    )
    if r_alerts.status_code == 200:
        alerts_data = r_alerts.json().get("alerts", [])
        
        for alert in alerts_data:
            # Notification "Toast" (Petit popup en bas à droite)
            st.toast(alert["message"], icon="🚨" if alert["level"] == "critique" else "⚠️")
            
            # Affichage persistant en haut de page
            if alert["level"] == "critique":
                st.error(f"🚨 **ALERTE CRITIQUE** : {alert['message']}")
            else:
                st.warning(f"⚠️ **ATTENTION** : {alert['message']}")

    # Affichage des KPIs (Métriques)
    r_metrics = requests.get(
        f"{FASTAPI_URL}/projects/{project_id}/metrics",
        headers=_get_headers(),
        timeout=5
    )
    if r_metrics.status_code == 200:
        m = r_metrics.json()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avancement", f"{m['avancement']}%", f"+{m.get('delta', 0)}%")
        c2.metric("Tâches en retard", m['retard'], delta_color="inverse")
        c3.metric("Risques Critiques", m['risques'])
        c4.metric("Charge Équipe", f"{m['charge']}%")
except Exception:
    st.info("📊 Synchronisation avec le service de monitoring...")

st.divider()

# 7. FONCTION DE RENDU DES COMPOSANTS (Graphiques Plotly)
def render_component(display_type: str, data: dict):
    if display_type == "gantt":
        issues = data.get("issues", [])
        if issues:
            from datetime import timedelta
            rows = []
            for i in issues:
                due = i.get("due_date") or str(date.today())
                start = i.get("start_date") or str(date.fromisoformat(due) - timedelta(days=7))
                rows.append({
                    "Tâche": i["subject"][:30], 
                    "Début": start, 
                    "Fin": due, 
                    "Statut": i.get("status", {}).get("name", "Open")
                })
            df = pd.DataFrame(rows)
            fig = px.timeline(df, x_start="Début", x_end="Fin", y="Tâche", color="Statut", title="Planning détaillé")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
    
    elif display_type == "workload":
        time_by_user = data.get("time_by_user", {})
        if time_by_user:
            names = list(time_by_user.keys())
            loads = [round(min((hours / 40) * 100, 100), 1) for hours in time_by_user.values()]
            fig = go.Figure(go.Bar(x=loads, y=names, orientation="h", marker_color="#1D9E75"))
            fig.update_layout(title="Charge actuelle de l'équipe (%)", xaxis=dict(range=[0, 100]))
            st.plotly_chart(fig, use_container_width=True)

# 8. HISTORIQUE DU CHAT
if "messages" not in st.session_state or len(st.session_state.messages) == 0:
    st.session_state.messages = [{
        "role": "assistant",
        "content": f"Bonjour ! Je suis l'IA de gestion pour **{project_name}**. Que voulez-vous savoir ?",
        "display_type": "text",
        "data": {}
    }]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("display_type") and msg["display_type"] != "text":
            render_component(msg["display_type"], msg.get("data", {}))

# 9. ZONE DE SAISIE ET APPEL BACKEND
question = st.chat_input(f"Posez votre question sur {project_name}...")

if question:
    # Affichage immédiat du message utilisateur
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Appel au moteur Multi-Agents
    with st.chat_message("assistant"):
        with st.spinner("Analyse des données en cours..."):
            try:
                from utils.api_client import _get_headers, ask_agent
                
                # Utiliser la fonction api_client pour avoir les headers JWT
                resp_json = ask_agent(
                    question=question,
                    project_id=project_id,
                    project_name=project_name,
                    user_id=str(st.session_state["user"]["id"]),
                    history=st.session_state.get("messages", [])[-5:]
                )
                
                if resp_json.get("answer"):
                    res = resp_json
                    st.markdown(res["answer"])
                    
                    d_type = res.get("display_type", "text")
                    d_data = res.get("data", {})
                    
                    if d_type != "text":
                        render_component(d_type, d_data)
                    
                    # Sauvegarde
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": res["answer"], 
                        "display_type": d_type, 
                        "data": d_data
                    })
                else:
                    st.error("❌ Pas de réponse du serveur")
            except Exception as e:
                st.error(f"Connexion impossible : {e}")
    
    st.rerun()