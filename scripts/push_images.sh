#!/bin/bash
set -e

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi


# === CONFIGURATION ===
# Remplace "fr-par" par ta région si besoin
REGION="fr-par"
NAMESPACE="camplong-coin"
REGISTRY_URL="rg.$REGION.scw.cloud/$NAMESPACE"

# URL de ton backend en production (À MODIFIER avec ton URL Scaleway/Domaine)
VITE_API_URL=${BACKEND_URL:?"Erreur : BACKEND_URL est introuvable dans le .env"}

# Assure-toi d'être connecté au registre Scaleway avant de lancer ce script :
# docker login rg.fr-par.scw.cloud -u nologin -p $SCW_SECRET_KEY

echo "🚀 Préparation de Docker Buildx..."
# Crée et utilise un builder spécifique si le défaut ne supporte pas le multi-arch (échoue silencieusement s'il existe déjà)
docker buildx create --use --name scaleway-builder 2>/dev/null || docker buildx use scaleway-builder

echo "📦 Build & Push du BACKEND (linux/amd64)..."
docker buildx build \
  --platform linux/amd64 \
  -t $REGISTRY_URL/backend:latest \
  --push \
  ./backend

echo "📦 Build & Push du FRONTEND (linux/amd64)..."
docker buildx build \
  --platform linux/amd64 \
  --build-arg VITE_API_URL=$VITE_API_URL \
  -t $REGISTRY_URL/frontend:latest \
  --push \
  ./frontend

echo "✅ Images buildées et pushées avec succès sur $REGISTRY_URL !"