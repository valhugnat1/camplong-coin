# backend/Dockerfile
FROM python:3.12-slim

# Évite que Python ne crée des fichiers .pyc et force les logs dans le terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Installation des dépendances
COPY requirements.txt .
# psycopg2-binary, bcrypt et fastapi s'installent bien sur l'image slim
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

# Scaleway Serverless passe le port via $PORT
ENV PORT=8080
EXPOSE $PORT

# Lancement de l'API avec Uvicorn
CMD ["sh", "-c", "uvicorn main:router --host 0.0.0.0 --port ${PORT}"]