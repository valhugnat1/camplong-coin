#!/bin/bash
set -e


if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi


# === CONFIGURATION ===
SCW_SECRET_KEY=${SCW_SECRET_KEY:?"Erreur : SCW_SECRET_KEY est introuvable. Vérifie ton fichier .env !"}

REGION="fr-par"

# Serverless Container IDs
BACKEND_CONTAINER_ID=${BACKEND_CONTAINER_ID:?"Erreur : BACKEND_CONTAINER_ID est introuvable dans le .env"}
FRONT_CONTAINER_ID=${FRONT_CONTAINER_ID:?"Erreur : FRONT_CONTAINER_ID est introuvable dans le .env"}



echo "🔄 Redéploiement du BACKEND..."
curl -s -X POST "https://api.scaleway.com/containers/v1/regions/$REGION/containers/$BACKEND_CONTAINER_ID/redeploy" \
  -H "X-Auth-Token: $SCW_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' | grep -o '"id":"[^"]*"' || echo "Requête envoyée."

echo -e "\n🔄 Redéploiement du FRONTEND..."
curl -s -X POST "https://api.scaleway.com/containers/v1/regions/$REGION/containers/$FRONT_CONTAINER_ID/redeploy" \
  -H "X-Auth-Token: $SCW_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{}' | grep -o '"id":"[^"]*"' || echo "Requête envoyée."

echo -e "\n✅ Ordres de redéploiement envoyés ! Tes apps seront à jour dans quelques secondes."