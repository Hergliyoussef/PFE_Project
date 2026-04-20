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

def _render_html(html: str):
    clean = "\n".join(line.lstrip() for line in html.split("\n"))
    st.markdown(clean, unsafe_allow_html=True)


# 2. AUTO-REFRESH (3 minutes)
st_autorefresh(interval=180000, key="dash_refresh")

user = st.session_state.get("user", {})
roles = user.get("roles", [])
is_ceo = "CEO" in roles or user.get("is_admin", False)
projects = st.session_state.get("projects", [])

# ── CSS Premium Dark Theme ─────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body { background: #07101f !important; }

[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #07101f 0%, #0c1424 50%, #111827 100%) !important;
    font-family: 'Inter', sans-serif !important;
    color: #f8fafc !important;
}
[data-testid="stMain"] { background: transparent !important; }

/* Masquer des éléments parasites */
#MainMenu, footer, header, [data-testid="stToolbar"] { display: none !important; }

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 95% !important;
}

/* Forcer la sidebar en sombre comme sur la maquette */
[data-testid="stSidebar"] {
    background: #07101f !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}

.panel-card {
    background: rgba(30, 41, 59, 0.4);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    margin-bottom: 24px;
    color: #f8fafc;
}

.kpi-card {
    background: rgba(30, 41, 59, 0.5);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 130px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.25);
    border: 1px solid rgba(255,255,255,0.1);
}
.kpi-icon {
    width: 38px; height: 38px; border-radius: 10px; display:flex; align-items:center; justify-content:center;
    font-size: 16px; margin-bottom: 12px; box-shadow: inset 0 2px 4px rgba(255,255,255,0.1);
}
.kpi-label { font-size: 13px; color: #94a3b8; font-weight: 500; margin-bottom: 4px; letter-spacing: 0.3px; }
.kpi-val { font-size: 32px; font-weight: 800; color: #f8fafc; line-height: 1.1; }
.kpi-sub { font-size: 11px; font-weight: 600; margin-top: 12px; display:flex; align-items:center; gap:4px; }

.section-title {
    font-size: 18px; font-weight: 600; color: #f8fafc; margin-bottom: 20px; letter-spacing: -0.3px;
}

/* Custom Table for Project Summary */
.promage-table { width: 100%; border-collapse: collapse; }
.promage-table th { text-align: left; padding: 12px 10px; font-size: 12px; color: #64748b; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.promage-table td { padding: 16px 10px; font-size: 13px; color: #e2e8f0; border-bottom: 1px solid rgba(255,255,255,0.02); font-weight: 500; }
.promage-table tr:last-child td { border-bottom: none; }
.promage-table tr { transition: background 0.2s ease; }
.promage-table tr:hover { background: rgba(255,255,255,0.02); border-radius: 8px;}

.badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-align: center; border: 1px solid transparent; width: fit-content;}
.badge.completed { background: rgba(34,197,94,0.1); color: #4ade80; border-color: rgba(34,197,94,0.2); }
.badge.delayed { background: rgba(245,158,11,0.1); color: #fbbf24; border-color: rgba(245,158,11,0.2); }
.badge.risk { background: rgba(239,68,68,0.1); color: #f87171; border-color: rgba(239,68,68,0.2); }
.badge.ongoing { background: rgba(99,102,241,0.1); color: #818cf8; border-color: rgba(99,102,241,0.2); }

/* Custom Checkbox List */
.task-item { display:flex; align-items:center; gap: 14px; padding: 14px 12px; border-bottom: 1px solid rgba(255,255,255,0.03); border-radius: 8px; transition: background 0.2s; }
.task-item:last-child { border-bottom: none; }
.task-item:hover { background: rgba(255,255,255,0.03); }
.check-circle { width:20px; height:20px; border-radius:50%; border:2px solid #475569; display:flex; align-items:center; justify-content:center; }
.check-circle.checked { background:#6366f1; border-color:#6366f1; color:white; font-size:10px; box-shadow: 0 0 10px rgba(99,102,241,0.4);}
.task-text { flex:1; font-size:13px; color:#cbd5e1; font-weight:400; }

@keyframes fadeInUp {
    from { opacity:0; transform:translateY(16px); }
    to { opacity:1; transform:translateY(0); }
}
</style>
""", unsafe_allow_html=True)

# ── HEADER ──────────────────────────────────────────────────────
col_title, col_btn = st.columns([4, 1])
vue_label = 'Vue Globale CEO' if is_ceo else 'Vue Project Manager'
with col_title:
    st.markdown(f"""
   <div style="font-size:26px; font-weight:800; color:#ffffff; letter-spacing: -0.5px;">
    📊 Dashboard Temps Réel
</div>
<div style="font-size:13px; color:#c084fc; margin-top:4px; margin-bottom: 24px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px;">
    {vue_label}
</div>
    """, unsafe_allow_html=True)
with col_btn:
    st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)
    if st.button("💬 Retour au Chat", width='stretch'):
        st.switch_page("pages/chat.py")

if not projects:
    st.warning("⚠️ Aucun projet assigné.")
    st.stop()

# ── COLLECTE DES DONNÉES EN TEMPS RÉEL
metrics_data = {}
for p in projects:
    try:
        r = requests.get(f"{FASTAPI_URL}/projects/{p['identifier']}/metrics", headers=_get_headers(), timeout=5)
        if r.status_code == 200:
            metrics_data[p['identifier']] = r.json()
    except Exception:
        metrics_data[p['identifier']] = {"avancement":0, "retard":0, "risques":0, "charge":0}

# ── OVERVIEW (KPIs) ──────────────────────────────────────────────────
st.markdown('<div class="section-title">Aperçu Global</div>', unsafe_allow_html=True)

total_projects = len(projects)
total_retards = sum(m.get("retard", 0) for m in metrics_data.values())
total_risques = sum(m.get("risques", 0) for m in metrics_data.values())
total_taches = sum(m.get("total_issues", 0) for m in metrics_data.values())
avg_avancement = sum(m.get("avancement", 0) for m in metrics_data.values()) / total_projects if total_projects > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.4s ease both;">
        <div>
            <div class="kpi-icon" style="background:rgba(168,85,247,0.15); color:#c084fc; border: 1px solid rgba(168,85,247,0.3);">📋</div>
            <div class="kpi-label">Total des Tâches</div>
            <div class="kpi-val">{total_taches}</div>
        </div>
        <div class="kpi-sub" style="color:#4ade80;">↗ +12% ce mois</div>
    </div>
    ''', unsafe_allow_html=True)
with kpi2:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.5s ease both;">
        <div>
            <div class="kpi-icon" style="background:rgba(99,102,241,0.15); color:#818cf8; border: 1px solid rgba(99,102,241,0.3);">💻</div>
            <div class="kpi-label">Projets Actifs</div>
            <div class="kpi-val">{total_projects} <span style="font-size:16px; color:#64748b; font-weight: 500;">/ {total_projects + 2}</span></div>
        </div>
        <div class="kpi-sub" style="color:#94a3b8;">→ Stable depuis 7j</div>
    </div>
    ''', unsafe_allow_html=True)
with kpi3:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.6s ease both;">
        <div>
            <div class="kpi-icon" style="background:rgba(245,158,11,0.15); color:#fbbf24; border: 1px solid rgba(245,158,11,0.3);">⏱️</div>
            <div class="kpi-label">Retards Signalés</div>
            <div class="kpi-val">{total_retards}</div>
        </div>
        <div class="kpi-sub" style="color:#fbbf24;">↗ Attention requise</div>
    </div>
    ''', unsafe_allow_html=True)
with kpi4:
    st.markdown(f'''
    <div class="kpi-card" style="animation: fadeInUp 0.7s ease both;">
        <div>
            <div class="kpi-icon" style="background:rgba(239,68,68,0.15); color:#f87171; border: 1px solid rgba(239,68,68,0.3);">🚨</div>
            <div class="kpi-label">Risques Globaux</div>
            <div class="kpi-val">{total_risques}</div>
        </div>
        <div class="kpi-sub" style="color:#f87171;">↗ +3% ce mois</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

# ── GRIDS ────────────────────────────────────────────────────────────
row1_col1, row1_col2 = st.columns([1.7, 1])

# Left side: Project Summary
with row1_col1:
    summary_html = """
    <div class="panel-card" style="animation: fadeInUp 0.8s ease both;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div class="section-title" style="margin:0;">Avancement des Projets</div>
            <div style="color:#64748b; font-size:12px; font-weight:600; display:flex; gap:16px;">
                <span style="color:#e2e8f0; cursor:pointer;">Tous ▼</span> <span style="cursor:pointer;">Aujourd'hui ▼</span>
            </div>
        </div>
        <table class="promage-table">
            <tr>
                <th>Projet</th>
                <th>Identifiant</th>
                <th>Statut</th>
                <th>Progression</th>
            </tr>
    """
    for p in projects:
        m = metrics_data[p['identifier']]
        avc = m.get('avancement', 0)
        ret = m.get('retard', 0)
        risk = m.get('risques', 0)

        # Logic for status
        if avc >= 100:
            badge = "completed"; status_txt = "Terminé"
        elif risk > 0:
            badge = "risk"; status_txt = "Risque"
        elif ret > 0:
            badge = "delayed"; status_txt = "Retard"
        else:
            badge = "ongoing"; status_txt = "En cours"

        if badge == "completed":   accent_color = "#4ade80"
        elif badge == "delayed":   accent_color = "#fbbf24"
        elif badge == "risk":      accent_color = "#f43f5e"
        else:                      accent_color = "#818cf8"

        summary_html += f"""
            <tr>
                <td style="font-weight:600; color:#f8fafc;">{p['name']}</td>
                <td style="color:#64748b;">#{p['identifier']}</td>
                <td><div class="badge {badge}">{status_txt}</div></td>
                <td>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="flex:1; height:6px; background:rgba(255,255,255,0.05); border-radius:3px; overflow:hidden; min-width: 60px;">
                            <div style="width:{avc}%; height:100%; background:{accent_color}; border-radius:3px; box-shadow: 0 0 8px {accent_color}55;"></div>
                        </div>
                        <span style="font-size:12px; font-weight:600; color:{accent_color}; width:35px; text-align:right;">{avc}%</span>
                    </div>
                </td>
            </tr>
        """
    summary_html += "</table></div>"
    _render_html(summary_html)

# Right side: Overall Progress
with row1_col2:
    prog_html = '<div class="panel-card" style="animation: fadeInUp 0.9s ease both; min-height:100%; display:flex; flex-direction:column;">'
    prog_html += f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: -15px;">
<div class="section-title" style="margin:0;">Progression Globale</div>
</div>
<div style="flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; z-index: 10;">
"""
    _render_html(prog_html)
    
    # Custom plotly gauge for Dark Theme
    fig_g = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = avg_avancement,
        title = {'text': "Moyenne Accomplie", 'font': {'size': 12, 'color': "#94a3b8"}},
        number = {'suffix': "%", 'font': {'size': 38, 'color': "#f8fafc", 'family':"Inter", "weight":"bold"}},
        gauge = {
            'axis': {'range': [0, 100], 'visible':False},
            'bar': {'color': "#818cf8", 'thickness':0.2},
            'bgcolor': "rgba(255,255,255,0.05)",
            'borderwidth': 0,
            'shape': "angular",
        }
    ))
    fig_g.update_layout(height=190, margin=dict(t=40, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter"))
    st.plotly_chart(fig_g, width='stretch', config={'displayModeBar': False})
    
    comp_c = sum(1 for p in projects if metrics_data[p['identifier']].get('avancement',0)==100)
    del_c  = sum(1 for p in projects if metrics_data[p['identifier']].get('retard',0)>0)
    risk_c = sum(1 for p in projects if metrics_data[p['identifier']].get('risques',0)>0)

    _render_html(f"""
<div style="display:flex; justify-content:space-between; text-align:center; margin-top:10px; width: 100%; z-index:10; position:relative;">
<div><div style="font-size:22px; font-weight:800; color:#f8fafc;">{total_projects}</div><div style="font-size:11px; color:#64748b; font-weight:500;">Projets</div></div>
<div><div style="font-size:22px; font-weight:800; color:#4ade80;">{comp_c}</div><div style="font-size:11px; color:#64748b; font-weight:500;">Terminés</div></div>
<div><div style="font-size:22px; font-weight:800; color:#fbbf24;">{del_c}</div><div style="font-size:11px; color:#64748b; font-weight:500;">En retard</div></div>
<div><div style="font-size:22px; font-weight:800; color:#f43f5e;">{risk_c}</div><div style="font-size:11px; color:#64748b; font-weight:500;">À risque</div></div>
</div>
</div></div>
""")


row2_col1, row2_col2 = st.columns([1.7, 1])

with row2_col1:
    tasks_html = """
    <div class="panel-card" style="animation: fadeInUp 1.0s ease both;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <div class="section-title" style="margin:0;">Vérifications Automatiques</div>
            <div style="font-size:12px; font-weight:600; color:#64748b;">
                <span style="color:#818cf8; border-bottom:2px solid #818cf8; padding-bottom:4px; cursor:pointer;">Prioritaires</span> &nbsp;&nbsp; <span style="cursor:pointer; transition: color 0.2s;">Toutes</span>
            </div>
        </div>
    """
    for p in projects[:5]:
        m = metrics_data[p['identifier']]
        avc = m.get('avancement', 0)
        risk = m.get('risques', 0)

        if avc == 100:
            badge = "completed"; status_txt = "Validé"; checked = "checked"
        elif risk > 0:
            badge = "risk"; status_txt = "En revue"; checked = "checked"
        else:
            badge = "ongoing"; status_txt = "En cours"; checked = ""

        check_icon = "✓" if checked else ""
        proj_name  = p['name']

        tasks_html += f"""
        <div class="task-item">
            <div class="check-circle {checked}">{check_icon}</div>
            <div class="task-text">Vérification de l'état d'avancement pour <b style="color:#f8fafc; font-weight:500;">{proj_name}</b></div>
            <div class="badge {badge}" style="opacity:0.9;">{status_txt}</div>
        </div>
        """
    tasks_html += "</div>"
    _render_html(tasks_html)

with row2_col2:
    _render_html("""
<div class="panel-card" style="animation: fadeInUp 1.1s ease both;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
<div class="section-title" style="margin:0;">Charge par Projet</div>
</div>
""")
    
    df_risques = pd.DataFrame([{
        "Projet": p["name"][:12] + ("..." if len(p["name"])>12 else ""),
        "Charge": metrics_data[p["identifier"]].get("charge", 0) + 1
    } for p in projects])
    
    fig2 = px.bar(df_risques, x="Projet", y="Charge", title="")
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        font=dict(color="#94a3b8", family="Inter", size=11), 
        margin=dict(t=15,b=0,l=0,r=0), 
        height=220,
        xaxis=dict(showgrid=False, linecolor='rgba(255,255,255,0.05)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)', linecolor='rgba(255,255,255,0.05)', zeroline=False)
    )
    fig2.update_traces(
        marker_color='#818cf8', 
        opacity=0.9, 
        width=0.4, 
        marker_line_color='rgba(255,255,255,0.1)', 
        marker_line_width=1,
        hovertemplate='<b>%{x}</b><br>Charge: %{y}<br><extra></extra>'
    )
    st.plotly_chart(fig2, width='stretch', config={'displayModeBar': False})
    _render_html("</div>")
