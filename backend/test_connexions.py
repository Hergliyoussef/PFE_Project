"""
Test des connexions — backend/test_connexions.py
Lance : python test_connexions.py
"""
import sys, os
sys.path.append(os.path.dirname(__file__))

print("\n" + "="*55)
print("  TEST CONNEXIONS — PM Assistant")
print("="*55 + "\n")

# ── 1. Config ─────────────────────────────────────────────────
print("[1/4] Configuration...")
try:
    from config import settings
    print(f"  ✓ OpenRouter key : {settings.openrouter_api_key[:20]}...")
    print(f"  ✓ Groq key       : {settings.groq_api_key[:20]}...")
    print(f"  ✓ Superviseur    : {settings.llm_supervisor}")
    print(f"  ✓ Analyse        : {settings.llm_analyse} (Groq)")
    print(f"  ✓ Rapporteur     : {settings.llm_rapporteur}")
    print(f"  ✓ Fallback       : {settings.llm_fallback}")
except Exception as e:
    print(f"  ✗ Erreur : {e}")
    sys.exit(1)

# ── 2. Redmine ────────────────────────────────────────────────
print("\n[2/4] Redmine...")
try:
    from services.redmine_client import redmine
    projects = redmine.get_projects()
    print(f"  ✓ {len(projects)} projet(s) trouvé(s)")
    for p in projects:
        print(f"    • {p['name']} ({p['identifier']})")
except Exception as e:
    print(f"  ✗ Redmine : {e}")

# ── 3. Groq (Agent Analyse) ───────────────────────────────────
print("\n[3/4] Groq — Agent Analyse...")
try:
    from services.llm_client import get_llm
    from langchain_core.messages import HumanMessage
    llm = get_llm("analyse")
    r   = llm.invoke([HumanMessage(content="Réponds uniquement 'OK'.")])
    print(f"  ✓ Groq accessible — réponse : {r.content[:30]}")
except Exception as e:
    print(f"  ✗ Groq : {e}")

# ── 4. OpenRouter (Superviseur + Rapporteur) ──────────────────
print("\n[4/4] OpenRouter — Superviseur & Rapporteur...")
try:
    llm = get_llm("supervisor")
    r   = llm.invoke([HumanMessage(content="Réponds uniquement 'OK'.")])
    print(f"  ✓ Superviseur accessible — réponse : {r.content[:30]}")
    llm2 = get_llm("rapporteur")
    r2   = llm2.invoke([HumanMessage(content="Réponds uniquement 'OK'.")])
    print(f"  ✓ Rapporteur accessible — réponse : {r2.content[:30]}")
except Exception as e:
    print(f"  ✗ OpenRouter : {e}")

print("\n" + "="*55)
print("  Tests terminés !")
print("="*55 + "\n")
