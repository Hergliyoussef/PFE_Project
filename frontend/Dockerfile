FROM python:3.10-slim
WORKDIR /app

# ÉTAPE DE CACHE : Docker va voir que c'est la même chose que le backend 
# et va utiliser "CACHED" au lieu de télécharger.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade pip
# ÉTAPE DE CODE : Spécifique au frontend
COPY frontend/ .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]