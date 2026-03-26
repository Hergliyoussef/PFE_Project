import requests
from config import settings

print("\n[3/3] Test connexion LLM (via Requests blindé)...")

# Extraction propre de la clé
api_key = settings.openrouter_api_key.strip() # .strip() pour enlever d'éventuels espaces invisibles

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:8501", # Obligatoire pour OpenRouter
    "X-Title": "PFE PM Assistant"
}

payload = {
    # On utilise la variable chargée depuis le .env au lieu du texte en dur
    "model": settings.llm_model_name, 
    "messages": [{"role": "user", "content": "Réponds juste 'OK'."}],
    "temperature": 0.1
}

print(f"DEBUG - Modèle utilisé pour ce test : {settings.llm_model_name}")

try:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        verify=False, # On garde le bypass SSL pour l'instant
        timeout=80
    )

    if response.status_code == 200:
        res_data = response.json()
        print(f"  ✓ LLM accessible ! Réponse : {res_data['choices'][0]['message']['content']}")
    else:
        print(f"  ✗ Erreur API {response.status_code} : {response.text}")
        # DEBUG : Affiche les headers envoyés (SANS LA CLÉ ENTIÈRE)
        print(f"  DEBUG Headers envoyés : Authorization: Bearer {api_key[:10]}...")

except Exception as e:
    print(f"  ✗ Erreur fatale : {e}")