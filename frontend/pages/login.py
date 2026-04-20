"""
Page Login — Premium UX
frontend/pages/login.py
"""
import streamlit as st
import requests
from utils.cookies import cookie_manager
from utils.auth_guard import _try_restore_session
import json

FASTAPI_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="PM Assistant — Connexion",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

@keyframes fadeInUp {
    from { opacity:0; transform:translateY(24px); }
    to   { opacity:1; transform:translateY(0); }
}
@keyframes floatY {
    0%,100% { transform:translateY(0); }
    50%      { transform:translateY(-10px); }
}
@keyframes pulseRing {
    0%   { transform:translate(-50%,-50%) scale(0.85); opacity:0.8; }
    100% { transform:translate(-50%,-50%) scale(1.55); opacity:0; }
}
@keyframes gradShift {
    0%,100% { background-position:0% 50%; }
    50%      { background-position:100% 50%; }
}
@keyframes shine {
    0%   { left:-60%; }
    100% { left:160%; }
}

html, body {
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%) !important; 
    height: 100vh !important;
    min-height: 100vh !important;
    font-family: 'Inter', sans-serif !important;
    overflow: hidden !important;
}

[data-testid="stMain"] { 
    background:transparent !important; 
    height: 100vh !important;
    overflow: hidden !important;
}

[data-testid="stMain"] > div:first-child {
    height: 100vh !important;
    overflow: hidden !important;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stHeader"], [data-testid="stDecoration"], .stAppHeader { 
    display:none !important; 
    visibility: hidden !important;
    height: 0 !important;
}

.block-container { 
    max-width:380px !important; 
    padding: 0 1rem !important; 
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    margin-left: auto !important;
    margin-right: auto !important;
    transform: scale(0.9); 
    transform-origin: right center;
}

.stTextInput > label {
    color:#94a3b8 !important;
    font-size:11px !important;
    font-weight:600 !important;
    text-transform:uppercase;
    letter-spacing:1px;
}
.stTextInput > div > div > input {
    background:rgba(15, 23, 42, 0.4) !important;
    border:1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius:12px !important;
    color:#f8fafc !important;
    font-family:'Inter',sans-serif !important;
    font-size:14px !important;
    padding:12px 16px !important;
    transition:all 0.3s ease !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
}
.stTextInput > div > div > input:focus {
    border-color:#6366f1 !important;
    background:rgba(15, 23, 42, 0.6) !important;
    box-shadow:0 0 0 3px rgba(99,102,241,0.15), 0 4px 12px rgba(0,0,0,0.1) !important;
}
.stTextInput > div > div > input::placeholder { color:#475569 !important; }

.stButton > button {
    width:100% !important;
    position:relative !important;
    overflow:hidden !important;
    background: linear-gradient(135deg,#4f46e5,#7c3aed) !important;
    background-size:200% 200% !important;
    animation: gradShift 4s ease infinite !important;
    color:#fff !important;
    border:none !important;
    border-radius:12px !important;
    font-family:'Inter',sans-serif !important;
    font-size:14px !important;
    font-weight:600 !important;
    padding:13px 24px !important;
    letter-spacing:0.3px !important;
    box-shadow:0 6px 20px rgba(79,70,229,0.2) !important;
    transition:all 0.3s ease !important;
}
.stButton > button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 28px rgba(79,70,229,0.35) !important;
}
.stButton > button::after {
    content:'';
    position:absolute;
    top:0; left:-60%;
    width:40%; height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,0.15),transparent);
    animation: shine 3s ease-in-out infinite;
    transform:skewX(-15deg);
}

[data-testid="stAlert"] {
    border-radius:12px !important;
    font-family:'Inter',sans-serif !important;
    font-size:13px !important;
}
.stSpinner > div { border-top-color:#6366f1 !important; }
hr { border:none !important; height:1px !important;
     background:linear-gradient(90deg,transparent,rgba(99,102,241,0.2),transparent) !important; }
</style>
""", unsafe_allow_html=True)

# AUTO-REDIRECT SI DÉJÀ CONNECTÉ (via Session ou Cookies)
if _try_restore_session() or st.session_state.get("authenticated"):
    st.switch_page("pages/chat.py")
    st.stop()

st.markdown("""
<div style="text-align:center; padding:10px 0 24px 0; animation:fadeInUp 0.5s ease both;">
<div style="position:relative; width:96px; height:96px; margin:0 auto 20px auto;">
<div style="position:absolute; top:50%; left:50%; width:96px; height:96px; border:2px solid rgba(99,102,241,0.4); border-radius:28px; animation:pulseRing 2.5s ease-out infinite;"></div>
<div style="position:absolute; top:50%; left:50%; width:96px; height:96px; border:2px solid rgba(139,92,246,0.25); border-radius:28px; animation:pulseRing 2.5s ease-out 1.25s infinite;"></div>
<div style="position:relative; z-index:1; width:96px; height:96px; background:linear-gradient(135deg,rgba(79,70,229,0.25),rgba(139,92,246,0.2)); border:1px solid rgba(99,102,241,0.35); border-radius:28px; display:flex; align-items:center; justify-content:center; font-size:46px; line-height:1; box-shadow:0 8px 32px rgba(99,102,241,0.15); animation:floatY 4s ease-in-out infinite;">🤖</div>
</div>
<div style="font-size:30px; font-weight:800; letter-spacing:-0.5px; margin-bottom:6px; background:linear-gradient(135deg,#f8fafc 0%,#a5b4fc 50%,#8b5cf6 100%); background-size:200% 200%; animation:gradShift 5s ease infinite; -webkit-background-clip:text; -webkit-text-fill-color:transparent;">PM Assistant</div>
<div style="font-size:20px; color:#94a3b8; letter-spacing:2.5px;">Chatbot IA d'Assistance à la Gestion de Projet</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:rgba(30, 41, 59, 0.4); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:2px 2px 2px; backdrop-filter:blur(24px);  inset 0 1px 0 rgba(255,255,255,0.05); animation:fadeInUp 0.65s ease both;">
<div style="font-size:20px; font-weight:700; color:#f8fafc; margin-bottom:4px;">Connexion</div>
<div style="font-size:15px; color:#94a3b8; margin-bottom:24px;">Utilisez vos identifiants Redmine</div>
""", unsafe_allow_html=True)

login    = st.text_input("Identifiant", placeholder="votre.identifiant", key="login_input")
password = st.text_input("Mot de passe", type="password", placeholder="••••••••", key="pwd_input")

st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

if st.button("🔓  Se connecter", width='stretch', key="login_btn"):
    if not login or not password:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        with st.spinner("Vérification des accès..."):
            try:
                resp = requests.post(
                    f"{FASTAPI_URL}/auth/login",
                    json={"login": login, "password": password},
                    timeout=30,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["authenticated"]  = True
                    st.session_state["access_token"]   = data["access_token"]
                    st.session_state["refresh_token"]  = data["refresh_token"]
                    st.session_state["user"]           = data["user"]

                    # Utilisation des projets autorisés fournis par le backend
                    projects = data["user"].get("authorized_projects", [])
                    st.session_state["projects"]     = projects
                    st.session_state["active_project"] = projects[0] if projects else None

                    # PERSISTENCE via Cookies (Clés uniques requises pour éviter les erreurs de duplication)
                    try:
                        cookie_manager.set("access_token", data["access_token"], key="set_at_login")
                        cookie_manager.set("refresh_token", data["refresh_token"], key="set_rt_login")
                        cookie_manager.set("user", json.dumps(data["user"]), key="set_user_login")
                    except Exception as e:
                        print(f"Erreur Cookie : {e}")

                    st.success(f"✅ Bienvenue, {data['user']['firstname']} !")
                    st.rerun()

                elif resp.status_code == 403:
                    detail = resp.json().get("detail", "Accès refusé.")
                    st.error(f"🚫 {detail}")

                elif resp.status_code == 401:
                    st.error("❌ Identifiant ou mot de passe incorrect.")
                else:
                    st.error(f"Erreur serveur ({resp.status_code}).")

            except requests.exceptions.ConnectionError:
                st.error("❌ Impossible de contacter le serveur (port 8000).")
            except Exception as e:
                st.error(f"Erreur inattendue : {e}")

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:16px; background:rgba(99,102,241,0.06); border:1px solid rgba(99,102,241,0.15); border-radius:12px; padding:12px 16px; font-size:12px; color:#475569; text-align:center; line-height:1.7; animation:fadeInUp 0.85s ease both;">
🔐 Accès réservé aux
<span style="color:#a5b4fc; font-weight:600;">Project Manager</span> et
<span style="color:#a5b4fc; font-weight:600;">CEO</span> uniquement<br>
<span style="font-size:11px; color:#334155;">
Authentification sécurisée JWT &middot; Session valide 1 heure
</span>
</div>
""", unsafe_allow_html=True)