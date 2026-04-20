# frontend/app.py
import streamlit as st
from utils.auth_guard import require_login

# require_login s'occupe de la restauration auto et de la redirection
require_login()

# Si on arrive ici, on est authentifié
st.switch_page("pages/chat.py")