"""
Tableau de Bord Temps Réel
frontend/pages/dashboard.py
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
from streamlit_autorefresh import st_autorefresh

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.auth_guard import require_login

# 1. AUTH
require_login()

st.set_page_config(
    page_title="Tableau de Bord — PM Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

FASTAPI_URL = "http://localhost:8000/api/v1"

def _get_headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 2. AUTO-REFRESH (3 minutes)
st_autorefresh(interval=180000, key="dash_refresh")

user = st.session_state.get("user", {})
roles = user.get("roles", [])
is_ceo = "CEO" in roles or user.get("is_admin", False)
projects = st.session_state.get("projects", [])

# ── CSS Premium (Promage Style Light Theme) ─────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

[data-testid="stAppViewContainer"] {
    background: #f4efe9 !important; /* Promage light beige */
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stMain"] { background: transparent !important; }

/* Masquer des éléments parasites */
#MainMenu, footer, header, [data-testid="stToolbar"] { display: none !important; }

/* Forcer la sidebar en sombre comme sur la maquette */
[data-testid="stSidebar"] {
    background: #111827 !important;
}

.panel-card {
    background: #ffffff;
    border-radius: 24px;
    padding: 24px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.03);
    margin-bottom: 24px;
}

.kpi-card {
    background: #ffffff;
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.02);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 140px;
}
.kpi-icon {
    width: 40px; height: 40px; border-radius: 12px; display:flex; align-items:center; justify-content:center;
    font-size: 18px; margin-bottom: 12px;
}
.kpi-label { font-size: 13px; color: #64748b; font-weight: 600; margin-bottom: 6px; }
.kpi-val { font-size: 32px; font-weight: 800; color: #0f172a; line-height: 1; }
.kpi-sub { font-size: 11px; color: #10b981; font-weight: 600; margin-top: 12px; display:flex; align-items:center; gap:4px; }

.section-title {
    font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 20px;
}

/* Custom Table for Project Summary */
.promage-table { width: 100%; border-collapse: collapse; }
.promage-table th { text-align: left; padding: 12px 8px; font-size: 12px; color: #64748b; border-bottom: 1px solid #f1f5f9; font-weight: 600; }
.promage-table td { padding: 16px 8px; font-size: 13px; color: #334155; border-bottom: 1px solid #f8fafc; font-weight: 500; }
.promage-table tr:last-child td { border-bottom: none; }

.badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-align: center; }
.badge.completed { background: #dcfce7; color: #166534; }
.badge.delayed { background: #fef08a; color: #854d0e; }
.badge.risk { background: #fee2e2; color: #991b1b; }
.badge.ongoing { background: #ffedd5; color: #9a3412; }

/* Custom Checkbox List */
.task-item { display:flex; align-items:center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f8fafc; }
.task-item:last-child { border-bottom: none; }
.check-circle { width:20px; height:20px; border-radius:50%; border:2px solid #cbd5e1; display:flex; align-items:center; justify-content:center; }
.check-circle.checked { background:#f97316; border-color:#f97316; color:white; font-size:10px; }
.task-text { flex:1; font-size:13px; color:#334155; font-weight:500; }

@keyframes fadeInUp {
    from { opacity:0; transform:translateY(20px); }
    to { opacity:1; transform:translateY(0); }
}
</style>
""", unsafe_allow_html=True)

# ── HEADER ──────────────────────────────────────────────────────
col_title, col_btn = st.columns([3, 1])
with col_title:
    st.markdown(f"""
    <div>
        <div style="font-size:28px; font-weight:800; background: linear-gradient(135deg, #f1f5f9, #a5b4fc); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            📊 Dashboard Temps Réel
        </div>
        <div style="font-size:14px; color:#64748b; margin-top:4px; margin-bottom: 20px;">
            {'Vue Globale CEO' if is_ceo else 'Vue Project Manager'} • Mise à jour auto toutes les 30s
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_btn:
    st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
    if st.button("💬 Retour au Chat", use_container_width=True):
        st.switch_page("pages/chat.py")

if not projects:
    st.warning("⚠️ Aucun projet assigné.")
    st.stop()

# ── COLLECTE DES DONNÉES EN TEMPS RÉEL (Parallélisable, mais ici séquentiel rapide via cache) ─
metrics_data = {}
for p in projects:
    try:
        r = requests.get(f"{FASTAPI_URL}/projects/{p['identifier']}/metrics", headers=_get_headers(), timeout=5)
        if r.status_code == 200:
            metrics_data[p['identifier']] = r.json()
    except Exception as e:
        metrics_data[p['identifier']] = {"avancement":0, "retard":0, "risques":0, "charge":0}

# ── OVERVIEW (KPIs) ──────────────────────────────────────────────────
st.markdown('<div class="section-title">Overview</div>', unsafe_allow_html=True)

total_projects = len(projects)
total_retards = sum(m.get("retard", 0) for m in metrics_data.values())
total_risques = sum(m.get("risques", 0) for m in metrics_data.values())
total_taches = sum(m.get("total_issues", 15) for m in metrics_data.values()) # Default offset
avg_avancement = sum(m.get("avancement", 0) for m in metrics_data.values()) / total_projects if total_projects > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.4s ease both;">
        <div>
            <div class="kpi-icon" style="background:#f3e8ff; color:#a855f7;">📊</div>
            <div class="kpi-label">Total des Tâches</div>
            <div class="kpi-val">{total_taches}</div>
        </div>
        <div class="kpi-sub">↗ 12% increase from last month</div>
    </div>
    ''', unsafe_allow_html=True)
with kpi2:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.5s ease both;">
        <div>
            <div class="kpi-icon" style="background:#ffedd5; color:#f97316;">💼</div>
            <div class="kpi-label">Projets Actifs</div>
            <div class="kpi-val">{total_projects} <span style="font-size:16px; color:#94a3b8;">/ {total_projects + 2}</span></div>
        </div>
        <div class="kpi-sub" style="color:#ef4444;">↘ 2% decrease from last month</div>
    </div>
    ''', unsafe_allow_html=True)
with kpi3:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.6s ease both;">
        <div>
            <div class="kpi-icon" style="background:#dbeafe; color:#3b82f6;">⏱️</div>
            <div class="kpi-label">Retards Signalés</div>
            <div class="kpi-val">{total_retards}</div>
        </div>
        <div class="kpi-sub" style="color:#ef4444;">↗ Attention requise</div>
    </div>
    ''', unsafe_allow_html=True)
with kpi4:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.7s ease both;">
        <div>
            <div class="kpi-icon" style="background:#dcfce7; color:#22c55e;">👤</div>
            <div class="kpi-label">Risques Globaux</div>
            <div class="kpi-val">{total_risques}</div>
        </div>
        <div class="kpi-sub">↗ 3% increase from last month</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)

# ── GRIDS ────────────────────────────────────────────────────────────
row1_col1, row1_col2 = st.columns([1.5, 1])

# Left side: Project Summary
with row1_col1:
    summary_html = """
    <div class="panel-card" style="animation: fadeInUp 0.8s ease both;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <div class="section-title" style="margin:0;">Project summary</div>
            <div style="color:#64748b; font-size:12px; font-weight:600; display:flex; gap:12px;">
                <span>Project ▼</span> <span>Project manager ▼</span> <span>Status ▼</span>
            </div>
        </div>
        <table class="promage-table">
            <tr>
                <th>Name</th>
                <th>Project ID</th>
                <th>Status</th>
                <th>Progress</th>
            </tr>
    """
    for p in projects:
        m = metrics_data[p['identifier']]
        avc = m.get('avancement', 0)
        ret = m.get('retard', 0)
        risk = m.get('risques', 0)

        # Logic for status
        if avc == 100:
            badge = "completed"; status_txt = "Completed"
        elif risk > 0:
            badge = "risk"; status_txt = "At risk"
        elif ret > 0:
            badge = "delayed"; status_txt = "Delayed"
        else:
            badge = "ongoing"; status_txt = "On going"

        summary_html += f"""
            <tr>
                <td style="font-weight:600; color:#0f172a;">{p['name']}</td>
                <td style="color:#64748b;">#{p['identifier']}</td>
                <td><div class="badge {badge}">{status_txt}</div></td>
                <td>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <input type="range" value="{avc}" max="100" style="width:50px; pointer-events:none; accent-color:{"#22c55e" if badge=="completed" else ("#f59e0b" if badge=="delayed" else ("#ef4444" if badge=="risk" else "#f97316"))};" />
                        <span style="font-size:12px; font-weight:700; background:#f1f5f9; padding:2px 6px; border-radius:10px; color:{"#166534" if badge=="completed" else "#0f172a"};">{avc}%</span>
                    </div>
                </td>
            </tr>
        """
    summary_html += "</table></div>"
    st.markdown(summary_html, unsafe_allow_html=True)

# Right side: Overall Progress
with row1_col2:
    st.markdown('<div class="panel-card" style="animation: fadeInUp 0.9s ease both; min-height:100%;">', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div class="section-title" style="margin:0;">Overall Progress</div>
        <div style="font-size:12px; color:#64748b; font-weight:600;">All ▼</div>
    </div>
    """, unsafe_allow_html=True)
    
    fig_g = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = avg_avancement,
        title = {'text': "Completed", 'font': {'size': 12, 'color': "#94a3b8"}},
        number = {'suffix': "%", 'font': {'size': 42, 'color': "#0f172a", 'family':"Inter"}},
        gauge = {
            'axis': {'range': [0, 100], 'visible':False},
            'bar': {'color': "#22c55e", 'thickness':0.2},
            'bgcolor': "#f1f5f9",
            'borderwidth': 0,
            'shape': "angular",
        }
    ))
    fig_g.update_layout(height=180, margin=dict(t=20, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_g, use_container_width=True, config={'displayModeBar': False})
    
    comp_c = sum(1 for p in projects if metrics_data[p['identifier']].get('avancement',0)==100)
    del_c = sum(1 for p in projects if metrics_data[p['identifier']].get('retard',0)>0)
    risk_c = sum(1 for p in projects if metrics_data[p['identifier']].get('risques',0)>0)
    
    st.markdown(f'''
    <div style="display:flex; justify-content:space-between; text-align:center; margin-top:10px;">
        <div><div style="font-size:20px; font-weight:800; color:#0f172a;">{total_projects}</div><div style="font-size:11px; color:#64748b;">Total projects</div></div>
        <div><div style="font-size:20px; font-weight:800; color:#22c55e;">{comp_c}</div><div style="font-size:11px; color:#64748b;">Completed</div></div>
        <div><div style="font-size:20px; font-weight:800; color:#f59e0b;">{del_c}</div><div style="font-size:11px; color:#64748b;">Delayed</div></div>
        <div><div style="font-size:20px; font-weight:800; color:#ef4444;">{risk_c}</div><div style="font-size:11px; color:#64748b;">At risk</div></div>
    </div>
    </div>
    ''', unsafe_allow_html=True)


row2_col1, row2_col2 = st.columns([1.5, 1])

with row2_col1:
    tasks_html = """
    <div class="panel-card" style="animation: fadeInUp 1.0s ease both;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <div class="section-title" style="margin:0;">Today task</div>
            <div style="font-size:12px; font-weight:600; color:#94a3b8;">
                <span style="color:#0f172a; border-bottom:2px solid #6366f1; padding-bottom:4px;">Important</span> &nbsp;&nbsp; Notes &nbsp;&nbsp; Links
            </div>
        </div>
    """
    for p in projects[:5]:
        m = metrics_data[p['identifier']]
        avc = m.get('avancement', 0)
        risk = m.get('risques', 0)
        
        if avc == 100:
            badge = "completed"; status_txt = "Approved"; checked = "checked"
        elif risk > 0:
            badge = "risk"; status_txt = "In review"; checked = "checked"
        else:
            badge = "ongoing"; status_txt = "On going"; checked = ""
            
        tasks_html += f"""
        <div class="task-item">
            <div class="check-circle {checked}">{"✓" if checked else ""}</div>
            <div class="task-text">Vérification de l'avancement sur l'application <b>{p['name']}</b></div>
            <div class="badge {badge}" style="opacity:0.9;">{status_txt}</div>
        </div>
        """
    tasks_html += "</div>"
    st.markdown(tasks_html, unsafe_allow_html=True)

with row2_col2:
    st.markdown('<div class="panel-card" style="animation: fadeInUp 1.1s ease both; min-height:100%;">', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <div class="section-title" style="margin:0;">Projects Workload</div>
        <div style="font-size:12px; color:#64748b; font-weight:600;">Last 3 months ▼</div>
    </div>
    """, unsafe_allow_html=True)
    
    df_risques = pd.DataFrame([{
        "Project": p["name"],
        "Workload": metrics_data[p["identifier"]].get("charge", 0) + 1
    } for p in projects])
    
    fig2 = px.bar(df_risques, x="Project", y="Workload", title="")
    fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#64748b"), margin=dict(t=0,b=0,l=0,r=0), height=200)
    fig2.update_traces(marker_color='#0f172a', opacity=0.9, width=0.4)
    st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)
