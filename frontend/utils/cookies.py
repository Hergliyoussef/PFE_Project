# frontend/utils/cookies.py
import extra_streamlit_components as stx
import streamlit as st

# Instance unique initialisée au niveau du module.
# Comme Python met les modules en cache, cet appel n'a lieu qu'une seule fois par exécution.
cookie_manager = stx.CookieManager(key="pm_assistant_global_cookie_manager")


