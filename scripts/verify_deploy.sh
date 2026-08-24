#!/bin/bash
# Verifie qu'un deploiement s'est bien passe. A lancer apres redeploy.sh.
#
#   bash scripts/verify_deploy.sh
#
# SANS sudo. Lecture seule : rien n'est modifie.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

REGISTRY="rg.fr-par.scw.cloud/camplong-coin"
BACKEND_ID=$(grep -E '^BACKEND_CONTAINER_ID=' .env | cut -d= -f2-)
FRONT_ID=$(grep -E '^FRONT_CONTAINER_ID=' .env | cut -d= -f2-)
BACKEND_URL=$(grep -E '^BACKEND_URL=' .env | cut -d= -f2-)

# Digest de l'image qui tournait avant ce deploiement.
ANCIEN="sha256:2cc2cd710fbef72c15b82bbee653db3391b9fbf63b979280635161eb921bfd97"

ko=0
ok()  { echo "   ✓ $1"; }
bad() { echo "   ✗ $1"; ko=$((ko + 1)); }

echo "═══ 1. Images du registry ═══"
digest=$(docker manifest inspect "$REGISTRY/backend:latest" 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(next(m['digest'] for m in d['manifests']
           if m['platform'].get('architecture') == 'amd64'))
" 2>/dev/null)
echo "   backend:latest = ${digest:-introuvable}"
if [ -z "$digest" ]; then
  bad "digest illisible (droits registry ?)"
elif [ "$digest" = "$ANCIEN" ]; then
  bad "c'est encore l'ANCIENNE image : le push n'a pas abouti"
else
  ok "nouvelle image publiee"
fi

echo
echo "═══ 2. Etat des containers ═══"
for id in "$BACKEND_ID" "$FRONT_ID"; do
  scw container container get "$id" -o json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
mark = 'ok' if d['status'] == 'ready' else 'BAD'
print(f\"   [{mark}] {d['name']:44} {d['status']}\")
if d.get('error_message'):
    print('        erreur :', d['error_message'])
" || bad "container $id illisible"
done

echo
echo "═══ 3. API en ligne ═══"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BACKEND_URL/openapi.json")
[ "$code" = "200" ] && ok "openapi.json HTTP 200" || bad "openapi.json HTTP $code"

# Le `|| bad` doit couvrir le cas "routes manquantes", pas seulement le cas
# "json illisible" : d'ou le sys.exit(1) cote python.
curl -s "$BACKEND_URL/openapi.json" | python3 -c "
import sys, json
try:
    paths = json.load(sys.stdin)['paths']
except Exception as e:
    print('   ✗ openapi illisible :', e)
    sys.exit(1)
attendus = ['/me/stats', '/admin/analytics', '/admin/analytics/flows']
print(f'   {len(paths)} routes exposees')
manquantes = [p for p in attendus if p not in paths]
for p in attendus:
    print(('   ✓ ' if p in paths else '   ✗ MANQUANT ') + p)
sys.exit(1 if manquantes else 0)
" || bad "les nouvelles routes ne sont pas servies (redeploy pas fait ?)"

echo
echo "═══ 4. Front en ligne ═══"
code=$(curl -s -o /dev/null -w '%{http_code}' https://coin.camplong.eu/)
[ "$code" = "200" ] && ok "coin.camplong.eu HTTP 200" || bad "coin.camplong.eu HTTP $code"

# Le bundle doit pointer sur l'API de prod, pas sur localhost : c'est l'erreur
# classique quand on a build en local juste avant.
main=$(curl -s https://coin.camplong.eu/ | grep -oE '/assets/index-[^"]+\.js' | head -1)
urls=$(curl -s "https://coin.camplong.eu$main" \
  | grep -oE 'assets/[A-Za-z0-9_.-]+\.js' | sort -u \
  | while read -r c; do curl -s "https://coin.camplong.eu/$c"; done \
  | grep -ohE 'http://localhost:[0-9]+|https://[A-Za-z0-9.-]+functions\.fnc\.fr-par\.scw\.cloud' \
  | sort -u)
echo "   API ciblee par le bundle :"
echo "$urls" | sed 's/^/     /'
if echo "$urls" | grep -q localhost; then
  bad "le bundle pointe sur localhost — rebuild avec le bon BACKEND_URL"
else
  ok "le bundle pointe sur l'API de prod"
fi

# Test qui manquait et qui a laisse passer un front perime : pointer sur la
# bonne API ne prouve pas qu'on sert la BONNE VERSION (l'ancien bundle aussi
# pointait sur la prod). On verifie donc la presence des pages recentes.
# Scaleway resout :latest en digest au moment du deploiement : un redeploy
# lance avant la fin du push repart sur l'ancienne image, sans rien signaler.
if curl -s "https://coin.camplong.eu$main" | grep -q "MyStatsView"; then
  ok "le front sert bien la nouvelle version (page Mes stats presente)"
else
  bad "front PERIME : le bundle ne contient pas les nouvelles pages"
  echo "        -> relance ./scripts/redeploy.sh (l'image est bien dans le registry)"
fi

echo
echo "═══════════════════════════════════════════════"
if [ "$ko" -eq 0 ]; then
  echo " Deploiement OK."
  echo " Verifie a la main : connexion, /stats cote joueur, /admin/stats."
else
  echo " $ko probleme(s). Pour revenir en arriere :"
  echo "   bash scripts/rollback.sh            # liste les sauvegardes"
  echo "   bash scripts/rollback.sh <tag>"
fi
echo "═══════════════════════════════════════════════"
