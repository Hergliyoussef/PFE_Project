import streamlit as st
import sys, os

# Page Config
st.set_page_config(
    page_title="PM Assistant — Intelligence Artificielle pour Redmine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Masquer le menu de navigation par défaut de Streamlit
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; height: 0; }
.stAppHeader { display: none; }

/* Global Style */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', sans-serif;
    background: #0f172a !important;
    color: #f1f5f9;
}

/* Hero Section */
.hero-container {
    padding: 100px 0 60px 0;
    text-align: center;
    background: radial-gradient(circle at top, rgba(99, 102, 241, 0.15), transparent 70%);
}
.hero-title {
    font-size: 64px;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 24px;
    background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.hero-subtitle {
    font-size: 20px;
    color: #94a3b8;
    max-width: 800px;
    margin: 0 auto 40px auto;
}

/* Glass Card */
.feature-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 24px;
    padding: 40px;
    transition: all 0.3s ease;
    height: 100%;
}
.feature-card:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(99, 102, 241, 0.3);
    transform: translateY(-5px);
}
</style>
""", unsafe_allow_html=True)

# --- HERO SECTION ---
st.markdown("""
<div class="hero-container">
    <h1 class="hero-title">L'Intelligence Artificielle<br>au service de vos projets.</h1>
    <p class="hero-subtitle">Boostez votre productivité avec PM Assistant. Analysez vos métriques Redmine, générez des rapports intelligents et anticipez les risques en temps réel.</p>
</div>
""", unsafe_allow_html=True)

# --- CTA ---
c1, c2, c3 = st.columns([1, 1, 1])
with c2:
    if st.button("🚀 Accéder à l'Assistant", use_container_width=True):
        st.switch_page("pages/login.py")

st.markdown("<br><br>", unsafe_allow_html=True)

# --- FEATURES ---
f1, f2, f3 = st.columns(3)
with f1:
    st.markdown("""
    <div class="feature-card">
        <div style="font-size:40px; margin-bottom:20px;">📊</div>
        <h3 style="color:#818cf8;">Analyses Prédictives</h3>
        <p style="color:#94a3b8; font-size:14px;">Détectez automatiquement les retards et les goulots d'étranglement avant qu'ils ne deviennent critiques.</p>
    </div>
    """, unsafe_allow_html=True)

with f2:
    st.markdown("""
    <div class="feature-card">
        <div style="font-size:40px; margin-bottom:20px;">🤖</div>
        <h3 style="color:#818cf8;">Multi-Agents IA</h3>
        <p style="color:#94a3b8; font-size:14px;">Des agents spécialisés travaillent ensemble pour vous fournir des synthèses précises de vos données Redmine.</p>
    </div>
    """, unsafe_allow_html=True)

with f3:
    st.markdown("""
    <div class="feature-card">
        <div style="font-size:40px; margin-bottom:20px;">⚡</div>
        <h3 style="color:#818cf8;">Monitoring Live</h3>
        <p style="color:#94a3b8; font-size:14px;">Suivez l'avancement global et la charge de vos équipes via un dashboard interactif ultra-fluide.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; margin-top:80px; padding:40px; color:#475569; font-size:12px; border-top:1px solid rgba(255,255,255,0.05);">
    PM Assistant Chatbot PFE — 2024. Optimisé pour Redmine.
</div>
""", unsafe_allow_html=True)