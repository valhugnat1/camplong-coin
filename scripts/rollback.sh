#!/bin/bash
# Revient a une version precedente des containers de prod.
#
#   bash scripts/rollback.sh                      # liste les sauvegardes
#   bash scripts/rollback.sh rollback-20260824-1130
#
# SANS sudo : n'utilise que le CLI `scw` (qui lit la config de hugo) et curl.
# Pas de docker, pas de rebuild, pas de push.
#
# Methode : on repointe les containers sur le tag de sauvegarde, ce qui declenche
# un rollout progressif. On ne reecrit PAS :latest — l'image fautive reste dans
# le registry pour analyse, et un second rollback vers :latest est possible une
# fois le probleme corrige.
#
# ⚠️ Ne rejoue AUCUNE migration a l'envers. Les migrations de ce projet sont
# additives (v11 = un CREATE TABLE), donc l'ancien code tourne sans probleme
# avec le schema recent : il ignore simplement la table en trop.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

REGISTRY="rg.fr-par.scw.cloud/camplong-coin"
BACKEND_ID=$(grep -E '^BACKEND_CONTAINER_ID=' .env | cut -d= -f2-)
FRONT_ID=$(grep -E '^FRONT_CONTAINER_ID=' .env | cut -d= -f2-)
BACKEND_URL=$(grep -E '^BACKEND_URL=' .env | cut -d= -f2-)

TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  echo "Sauvegardes disponibles dans le registry :"
  echo
  for img in backend frontend; do
    echo "── $img ──"
    scw registry tag list image-id="$(scw registry image list -o json \
      | python3 -c "
import sys, json
print(next(i['id'] for i in json.load(sys.stdin) if i['name'] == '$img'))")" -o json \
      | python3 -c "
import sys, json
tags = [t for t in json.load(sys.stdin) if t['name'].startswith('rollback-')]
for t in sorted(tags, key=lambda t: t['name'], reverse=True):
    print(f\"   {t['name']:26} {t.get('created_at', '')[:19]}  [{t['status']}]\")
print('   (aucune)' if not tags else '')
"
  done
  echo
  echo "Usage : bash scripts/rollback.sh <tag>"
  exit 0
fi

echo "Etat actuel :"
for id in "$BACKEND_ID" "$FRONT_ID"; do
  scw container container get "$id" -o json | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"   {d['name']:42} {d['registry_image'].split('/')[-1]:28} [{d['status']}]\")
"
done

echo
read -rp "Revenir sur '$TARGET' pour les DEUX containers ? [y/N] " ans
[ "$ans" = "y" ] || { echo "Annule."; exit 0; }

wait_ready() {
  for _ in $(seq 1 72); do
    s=$(scw container container get "$1" -o json \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
    [ "$s" = "ready" ] && { echo "   -> ready"; return 0; }
    [ "$s" = "error" ] && { echo "   -> ERREUR"; return 1; }
    printf '   status=%s\n' "$s"
    sleep 5
  done
  echo "   -> TIMEOUT"; return 1
}

echo
echo "==> Backend sur :$TARGET"
scw container container update "$BACKEND_ID" \
  registry-image="$REGISTRY/backend:$TARGET" >/dev/null
wait_ready "$BACKEND_ID"

echo "==> Frontend sur :$TARGET"
scw container container update "$FRONT_ID" \
  registry-image="$REGISTRY/frontend:$TARGET" >/dev/null
wait_ready "$FRONT_ID"

echo
echo "==> Verification"
echo "   backend /openapi.json : HTTP $(curl -s -o /dev/null -w '%{http_code}' "$BACKEND_URL/openapi.json")"
echo "   front coin.camplong.eu : HTTP $(curl -s -o /dev/null -w '%{http_code}' https://coin.camplong.eu/)"
echo
echo "Rollback termine. Les containers tournent sur :$TARGET."
echo "Pour revenir a la derniere version poussee : bash scripts/rollback.sh latest"
