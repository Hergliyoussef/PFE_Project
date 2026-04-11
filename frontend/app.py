# frontend/app.py
import streamlit as st

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    # AJOUTE BIEN "pages/" DEVANT
    st.switch_page("pages/login.py") 
else:
    st.switch_page("pages/chat.py")