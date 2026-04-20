"""
Page Chat — Premium UX Design
frontend/pages/chat.py
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from streamlit_autorefresh import st_autorefresh
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.auth_guard import require_login, get_active_project
from utils.api_client import _get_headers, ask_agent

# 1. AUTH
require_login()

# 2. PAGE CONFIG
st.set_page_config(
    page_title="PM Assistant — Chat",
    page_icon="🤖",
    layout="wide",
)

FASTAPI_URL = "http://localhost:8000/api/v1"

# 3. PROJET ACTIF
current_project = get_active_project()
if not current_project:
    st.error("⚠️ Aucun projet sélectionné. Choisissez-en un dans la barre latérale.")
    st.stop()

project_id   = current_project.get("identifier")
project_name = current_project.get("name", "Projet")

if not project_id or project_id in ["None", "inconnu"]:
    st.warning("⚠️ Identifiant de projet invalide. Veuillez vous déconnecter et vous reconnecter.")
    st.stop()

# 4. AUTO-REFRESH (10 min)
st_autorefresh(interval=600_000, key="monitor_refresh")

# ── CSS Premium ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

@keyframes fadeInUp {
    from { opacity:0; transform:translateY(16px); }
    to   { opacity:1; transform:translateY(0); }
}
@keyframes fadeIn {
    from { opacity:0; }
    to   { opacity:1; }
}
@keyframes slideInUp {
    from { opacity:0; transform:translateY(20px) scale(0.95); }
    to   { opacity:1; transform:translateY(0) scale(1); }
}
@keyframes slideInRight {
    from { opacity:0; transform:translateX(30px); }
    to   { opacity:1; transform:translateX(0); }
}
@keyframes slideInLeft {
    from { opacity:0; transform:translateX(-20px); }
    to   { opacity:1; transform:translateX(0); }
}
@keyframes pulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:0.6; transform:scale(0.95); }
}
@keyframes metricPop {
    0%   { transform:scale(0.85); opacity:0; }
    70%  { transform:scale(1.03); }
    100% { transform:scale(1); opacity:1; }
}
@keyframes dotBounce {
    0%,80%,100% { transform:translateY(0); opacity:0.4; }
    40%          { transform:translateY(-6px); opacity:1; }
}
@keyframes fadeOut {
    from { opacity:1; transform:translateX(0); max-height:150px; margin-bottom:10px; }
    to   { opacity:0; transform:translateX(20px); max-height:0; margin-bottom:0; padding:0; border:none; }
}

#notification-container {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-width: 340px;
    max-height: 70vh;
    overflow-y: auto;
    padding-right: 8px;
    pointer-events: none;
    scrollbar-width: thin;
}
#notification-container::-webkit-scrollbar { width: 4px; }
#notification-container::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.2); border-radius: 10px; }

.toast-alert {
    pointer-events: auto;
    background: rgba(15, 23, 42, 0.82);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px 14px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: flex-start;
    gap: 12px;
    animation: slideInRight 0.4s ease both, fadeOut 0.5s ease 5s forwards;
    position: relative;
}
.toast-bar { position: absolute; left: 0; top: 12px; bottom: 12px; width: 3px; border-radius: 0 2px 2px 0; }
.toast-icon { font-size: 18px; line-height: 1; }
.toast-content { flex: 1; font-size: 13px; color: #e2e8f0; line-height: 1.4; }

[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #07101f 0%, #0d1528 50%, #111827 100%) !important;
}
[data-testid="stMain"] { background: transparent !important; }

/* Supprimer absolument tout ce qui dépasse (barres noires) */
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stHeader"], [data-testid="stDecoration"], .stAppHeader {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
}

/* Fond uniforme pour la barre latérale également pour éviter les coupures */
[data-testid="stSidebar"] {
    background: #07101f !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}

/* Optimiser la zone de contenu (Retirer les marges Streamlit par défaut) */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 95% !important;
}

/* Ajuster l'espacement du chat pour qu'il ne laisse pas de vide en bas */
[data-testid="stBottom"] {
    background: transparent !important;
    padding-bottom: 20px !important;
}

[data-testid="stChatMessage"] {
    animation: slideInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
    background: transparent !important;
    margin-bottom: 8px !important;
}
@keyframes slideInUp {
    from { opacity:0; transform:translateY(30px) scale(0.97); }
    to   { opacity:1; transform:translateY(0) scale(1); }
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {
    background: rgba(99,102,241,0.15) !important;
    border: 1px solid rgba(99,102,241,0.2) !important;
    border-radius: 16px 4px 16px 16px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stChatMessageContent"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 4px 16px 16px 16px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

# ── Reset si changement de projet ───────────────────────────────
if "last_project_id" not in st.session_state:
    st.session_state["last_project_id"] = project_id
if st.session_state["last_project_id"] != project_id:
    st.session_state.messages = []
    st.session_state["active_conv_id"] = None
    st.session_state["last_project_id"] = project_id
    st.rerun()

# ── HEADER ──────────────────────────────────────────────────────
head_col1, head_col2 = st.columns([1.5, 1])
with head_col1:
    st.markdown(f"""
    <div style="animation: fadeInUp 0.4s ease both;">
    <div style="font-size:22px; font-weight:700; background: linear-gradient(135deg, #f1f5f9, #a5b4fc); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">🤖 PM Assistant</div>
    <div style="font-size:13px; color:#475569;">Projet : <span style="color:#818cf8; font-weight:600;">{project_name}</span></div>
    </div>
    """, unsafe_allow_html=True)
with head_col2:
    sub_col1, sub_col2 = st.columns([1.5, 1])
    with sub_col1:
        if st.button("📊 Dashboard Temps Réel", width='stretch'):
            st.switch_page("pages/dashboard.py")
    with sub_col2:
        st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:center; gap:8px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:6px 10px; min-height:40px;">
            <div style="width:8px; height:8px; border-radius:50%; background:#22c55e; box-shadow:0 0 8px rgba(34,197,94,0.6); animation: pulse 2s ease infinite;"></div>
            <span style="font-size:12px; color:#64748b;">Système actif</span>
        </div>
        """, unsafe_allow_html=True)

# ── ALERTES & KPIs ───────────────────────────────────────────────
# ── ALERTES ──────────────────────────────────────────────────────
try:
    r_alerts = requests.get(f"{FASTAPI_URL}/alerts/{project_id}", headers=_get_headers(), timeout=10)
    if r_alerts.status_code == 200:
        alerts = r_alerts.json().get("alerts", [])
        if alerts:
            display_alerts = alerts[:3]
            count_extra = len(alerts) - 3
            alerts_html = '<div id="notification-container">'
            for alert in display_alerts:
                is_crit = alert.get("level") == "critique"
                color = "#ef4444" if is_crit else "#f59e0b"
                icon  = "🚨" if is_crit else "⚠️"
                alerts_html += f'<div class="toast-alert"><div class="toast-bar" style="background:{color};"></div><div class="toast-icon">{icon}</div><div class="toast-content">{alert.get("message","")}</div></div>'
            if count_extra > 0:
                alerts_html += f'<div style="text-align:right; font-size:11px; color:#475569; padding-right:10px; font-style:italic;">+ {count_extra} autres...</div>'
            alerts_html += '</div>'
            st.markdown(alerts_html, unsafe_allow_html=True)
except Exception as e:
    pass # Les alertes sont secondaires, on continue

st.markdown('<div style="height:1px; margin:16px 0;"></div>', unsafe_allow_html=True)

# ── GRAPHIQUES & LOGIQUE ────────────────────────────────────────
def _plotly_layout():
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"), margin=dict(l=10,r=10,t=40,b=10))

def render_component(dtype, data):
    if dtype == "gantt" and data.get("issues"):
        df = pd.DataFrame([{"T": i["subject"][:30], "D": i.get("start_date") or str(date.today()), "F": i.get("due_date") or str(date.today())} for i in data["issues"]])
        fig = px.timeline(df, x_start="D", x_end="F", y="T", title="📅 Planning")
        fig.update_layout(**_plotly_layout())
        st.plotly_chart(fig, width='stretch')
    elif dtype == "workload" and data.get("time_by_user"):
        fig = go.Figure(go.Bar(x=list(data["time_by_user"].values()), y=list(data["time_by_user"].keys()), orientation="h"))
        fig.update_layout(title="💪 Charge", **_plotly_layout())
        st.plotly_chart(fig, width='stretch')

# ── MESSAGES (Historique Multi-session) ─────────────────────────
if "active_conv_id" not in st.session_state:
    st.session_state["active_conv_id"] = None

if "messages" not in st.session_state: 
    st.session_state.messages = []

# Logique de chargement (seulement si pas une nouvelle session forcée)
if st.session_state.get("is_new_session"):
    st.session_state.messages = []
    st.session_state["active_conv_id"] = None
    st.session_state["is_new_session"] = False # Consommé
else:
    if not st.session_state.messages:
        try:
            cur_conv_id = st.session_state.get("active_conv_id")
            params = {"conversation_id": cur_conv_id} if cur_conv_id else {}
            r = requests.get(f"{FASTAPI_URL}/history/{project_id}", params=params, headers=_get_headers(), timeout=5)
            if r.status_code == 200:
                h_data = r.json()
                st.session_state.messages = h_data.get("history", [])
                st.session_state["active_conv_id"] = h_data.get("conversation_id")
        except Exception:
            pass

if not st.session_state.messages:
    user_name = st.session_state.get("user", {}).get("firstname", "PM")
    st.session_state.messages = [{"role":"assistant","content":f"Bonjour **{user_name}** ! 👋\n\nJe suis votre assistant IA pour **{project_name}**."}]

# Affichage
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("display_type") and msg["display_type"] != "text":
            render_component(msg["display_type"], msg.get("data", {}))

# ── INPUT ──────────────────────────────────────────────────────
q = st.chat_input(f"Question sur {project_name}...")
if q:
    st.session_state.messages.append({"role":"user","content":q})
    with st.chat_message("user"): st.markdown(q)
    
    with st.chat_message("assistant"):
        think = st.empty()
        think.markdown('<div style="font-size:12px;color:#6366f1;animation:pulse 1.5s infinite;">L\'IA réfléchit...</div>', unsafe_allow_html=True)
        try:
            r = ask_agent(
                question=q, 
                project_id=project_id, 
                project_name=project_name, 
                user_id=st.session_state["user"]["login"], 
                history=st.session_state.messages[-5:],
                conversation_id=st.session_state.get("active_conv_id")
            )
            think.empty()
            if r and r.get("answer"):
                st.markdown(r["answer"])
                if r.get("display_type", "text") != "text": render_component(r["display_type"], r["data"])
                
                # Mise à jour de l'ID conversation si c'était une nouvelle session
                if r.get("conversation_id"):
                    st.session_state["active_conv_id"] = r["conversation_id"]
                    st.session_state["refresh_conversations"] = True
                
                st.session_state.messages.append({
                    "role":"assistant",
                    "content":r["answer"],
                    "display_type":r.get("display_type"),
                    "data":r.get("data")
                })
        except Exception as e:
            think.empty()
            st.error(f"Erreur : {e}")
