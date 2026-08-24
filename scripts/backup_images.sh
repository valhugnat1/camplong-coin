#!/bin/bash
# Sauvegarde les images actuellement en production sous un tag horodate,
# AVANT de pousser de nouvelles :latest.
#
#   sudo bash scripts/backup_images.sh
#
# Ne rebuild rien : `imagetools create` fait pointer un nouveau tag sur le
# manifeste deja present dans le registry, cote serveur. La sauvegarde est donc
# strictement identique a ce qui tourne (meme digest), pas une reconstruction.
#
# Ne touche pas aux containers : c'est juste un tag de plus dans le registry.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

REGISTRY="rg.fr-par.scw.cloud/camplong-coin"
STAMP=$(date +%Y%m%d-%H%M)
TAG="rollback-$STAMP"

SCW_SECRET_KEY=$(grep -E '^SCW_SECRET_KEY=' .env | cut -d= -f2-)
echo "$SCW_SECRET_KEY" | docker login rg.fr-par.scw.cloud -u nologin --password-stdin >/dev/null
echo "Registry OK."

digest_of() {
  docker manifest inspect "$1" 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'manifests' in d:
    print(next(m['digest'] for m in d['manifests']
               if m['platform'].get('architecture') == 'amd64'))
else:
    print('(manifeste simple)')
" || echo "(introuvable)"
}

echo
for img in backend frontend; do
  echo "── $img ──"
  before=$(digest_of "$REGISTRY/$img:latest")
  echo "   :latest actuel  $before"
  docker buildx imagetools create --tag "$REGISTRY/$img:$TAG" "$REGISTRY/$img:latest"
  after=$(digest_of "$REGISTRY/$img:$TAG")
  echo "   :$TAG  $after"
  if [ "$before" = "$after" ]; then
    echo "   ✓ sauvegarde identique a la prod"
  else
    echo "   ✗ DIGESTS DIFFERENTS — ne pousse pas tant que ce n'est pas compris"
    exit 1
  fi
done

echo
echo "════════════════════════════════════════════════════════════"
echo " Sauvegarde faite sous le tag :  $TAG"
echo
echo " Pour revenir a cet etat plus tard :"
echo "   bash scripts/rollback.sh $TAG"
echo "════════════════════════════════════════════════════════════"
