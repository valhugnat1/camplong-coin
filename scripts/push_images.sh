#!/bin/bash
set -e

# Charge le .env de la racine si présent
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# === CONFIGURATION ===
REGION="fr-par"
NAMESPACE="camplong-coin"
REGISTRY_URL="rg.$REGION.scw.cloud/$NAMESPACE"

# Variables nécessaires pour le build du front (injectées par Vite au build-time)
VITE_API_URL=${BACKEND_URL:?"Erreur : BACKEND_URL est introuvable dans le .env"}

# L'adresse du contrat ERC-20 déployé sur Base Sepolia.
# C'est la MÊME valeur que CONTRACT_ADDRESS dans le .env du backend.
# Si pas définie explicitement, on réutilise CONTRACT_ADDRESS.
VITE_CONTRACT_ADDRESS=${VITE_CONTRACT_ADDRESS:-${CONTRACT_ADDRESS:?"Erreur : CONTRACT_ADDRESS (ou VITE_CONTRACT_ADDRESS) est introuvable dans le .env"}}

echo "🚀 Préparation de Docker Buildx..."
docker buildx create --use --name scaleway-builder 2>/dev/null || docker buildx use scaleway-builder

echo "📦 Build & Push du BACKEND (linux/amd64)..."
docker buildx build \
  --platform linux/amd64 \
  -t $REGISTRY_URL/backend:latest \
  --push \
  ./backend

echo "📦 Build & Push du FRONTEND (linux/amd64)..."
echo "   VITE_API_URL=$VITE_API_URL"
echo "   VITE_CONTRACT_ADDRESS=$VITE_CONTRACT_ADDRESS"
docker buildx build \
  --platform linux/amd64 \
  --build-arg VITE_API_URL=$VITE_API_URL \
  --build-arg VITE_CONTRACT_ADDRESS=$VITE_CONTRACT_ADDRESS \
  -t $REGISTRY_URL/frontend:latest \
  --push \
  ./frontend

echo "✅ Images buildées et pushées avec succès sur $REGISTRY_URL !"
