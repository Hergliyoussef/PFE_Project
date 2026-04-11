"""
Page Login — Premium UX
frontend/pages/login.py
"""
import streamlit as st
import requests

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
@keyframes orbMove {
    0%,100% { transform:translate(0,0) scale(1); }
    50%      { transform:translate(30px,-20px) scale(1.08); }
}
@keyframes shine {
    0%   { left:-60%; }
    100% { left:160%; }
}

[data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at 20% 20%, rgba(79,70,229,0.15) 0%, transparent 55%),
                radial-gradient(ellipse at 80% 80%, rgba(139,92,246,0.10) 0%, transparent 55%),
                #060d1a !important;
    min-height: 100vh;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stMain"] { background:transparent !important; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none !important; }

.block-container { max-width:430px !important; padding:2rem 1.2rem !important; }

.stTextInput > label {
    color:#64748b !important;
    font-size:11px !important;
    font-weight:600 !important;
    text-transform:uppercase;
    letter-spacing:1px;
}
.stTextInput > div > div > input {
    background:rgba(255,255,255,0.035) !important;
    border:1px solid rgba(99,102,241,0.22) !important;
    border-radius:12px !important;
    color:#e2e8f0 !important;
    font-family:'Inter',sans-serif !important;
    font-size:14px !important;
    padding:12px 16px !important;
    transition:all 0.3s ease !important;
    caret-color:#6366f1;
}
.stTextInput > div > div > input:focus {
    border-color:#6366f1 !important;
    background:rgba(99,102,241,0.07) !important;
    box-shadow:0 0 0 3px rgba(99,102,241,0.15) !important;
}
.stTextInput > div > div > input::placeholder { color:#334155 !important; }

.stButton > button {
    width:100% !important;
    position:relative !important;
    overflow:hidden !important;
    background: linear-gradient(135deg,#4f46e5,#7c3aed,#9333ea) !important;
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
    box-shadow:0 4px 24px rgba(79,70,229,0.4) !important;
    transition:all 0.3s ease !important;
}
.stButton > button:hover {
    transform:translateY(-2px) !important;
    box-shadow:0 8px 32px rgba(79,70,229,0.55) !important;
}
.stButton > button::after {
    content:'';
    position:absolute;
    top:0; left:-60%;
    width:40%; height:100%;
    background:linear-gradient(90deg,transparent,rgba(255,255,255,0.18),transparent);
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
     background:linear-gradient(90deg,transparent,rgba(99,102,241,0.3),transparent) !important; }
</style>
""", unsafe_allow_html=True)

if st.session_state.get("authenticated"):
    st.switch_page("pages/chat.py")

st.markdown("""
<div style="text-align:center; padding:44px 0 32px 0; animation:fadeInUp 0.5s ease both;">
<div style="position:relative; width:96px; height:96px; margin:0 auto 20px auto;">
<div style="position:absolute; top:50%; left:50%; width:96px; height:96px; border:2px solid rgba(99,102,241,0.5); border-radius:28px; animation:pulseRing 2.5s ease-out infinite;"></div>
<div style="position:absolute; top:50%; left:50%; width:96px; height:96px; border:2px solid rgba(139,92,246,0.3); border-radius:28px; animation:pulseRing 2.5s ease-out 1.25s infinite;"></div>
<div style="position:relative; z-index:1; width:96px; height:96px; background:linear-gradient(135deg,rgba(79,70,229,0.25),rgba(139,92,246,0.2)); border:1px solid rgba(99,102,241,0.35); border-radius:28px; display:flex; align-items:center; justify-content:center; font-size:46px; line-height:1; box-shadow:0 0 50px rgba(99,102,241,0.2); animation:floatY 4s ease-in-out infinite;">🤖</div>
</div>
<div style="font-size:26px; font-weight:800; letter-spacing:-0.5px; margin-bottom:6px; background:linear-gradient(135deg,#f1f5f9 0%,#a5b4fc 45%,#8b5cf6 100%); background-size:200% 200%; animation:gradShift 5s ease infinite; -webkit-background-clip:text; -webkit-text-fill-color:transparent;">PM Assistant</div>
<div style="font-size:13px; color:#475569; letter-spacing:0.3px;">Chatbot IA d'Assistance à la Gestion de Projet</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:linear-gradient(135deg,rgba(15,23,42,0.85),rgba(20,28,48,0.9)); border:1px solid rgba(99,102,241,0.18); border-radius:20px; padding:28px 28px 20px; backdrop-filter:blur(30px); box-shadow:0 24px 64px rgba(0,0,0,0.5),inset 0 1px 0 rgba(255,255,255,0.04); animation:fadeInUp 0.65s ease both;">
<div style="font-size:15px; font-weight:600; color:#e2e8f0; margin-bottom:4px;">Connexion</div>
<div style="font-size:12px; color:#475569; margin-bottom:20px;">Utilisez vos identifiants Redmine</div>
""", unsafe_allow_html=True)

login    = st.text_input("Identifiant", placeholder="votre.login", key="login_input")
password = st.text_input("Mot de passe", type="password", placeholder="••••••••", key="pwd_input")

st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

if st.button("🔓  Se connecter", use_container_width=True, key="login_btn"):
    if not login or not password:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        with st.spinner("Vérification des accès..."):
            try:
                resp = requests.post(
                    f"{FASTAPI_URL}/auth/login",
                    json={"login": login, "password": password},
                    timeout=20,
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

                    st.success(f"✅ Bienvenue, {data['user']['firstname']} !")
                    st.rerun()

                elif resp.status_code == 403:
                    detail = resp.json().get("detail", "Accès refusé.")
                    st.error(f"🚫 {detail} Contactez votre administrateur.")

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