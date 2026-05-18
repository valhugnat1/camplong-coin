# CamplongCoin — MVP Setup

App custodial minimaliste pour échanger un token ERC-20 (CAMP) entre potes sur **Base Sepolia** (testnet, gratuit).

## Stack

- **Smart contract** : Solidity 0.8.20 + OpenZeppelin ERC20
- **Réseau** : Base Sepolia (Chain ID 84532)
- **Backend** : FastAPI + `web3.py` + `eth-account` + JWT
- **Frontend** : Vue 3 (single HTML file)
- **Storage** : `users.json` chiffré localement

## Structure du projet

```
camplong-coin/
├── README.md
├── .gitignore
├── contract/
│   └── CamplongCoin.sol         # Smart contract ERC-20
├── backend/
│   ├── main.py                  # API FastAPI
│   ├── setup_users.py           # Génère les wallets users
│   ├── requirements.txt
│   ├── .env.example             # Template du .env
│   ├── .env                     # (créé manuellement, NON commit)
│   ├── users.json               # (généré par setup_users, NON commit)
│   └── transactions.log         # (créé au runtime, NON commit)
└── frontend/
    └── index.html               # UI Vue 3
```

---

## Étape 1 — MetaMask + Base Sepolia

1. Installe **MetaMask** (extension Chrome/Brave/Firefox)
2. Crée un wallet "Dev Hugo" — note la seed dans un gestionnaire de mots de passe. **Ce wallet sera ta treasury.**
3. Ajoute le réseau **Base Sepolia** :
   - Va sur https://chainlist.org/?testnets=true&search=base+sepolia → "Add to MetaMask"
   - Ou manuellement :
     - Nom : `Base Sepolia`
     - RPC URL : `https://base-sepolia-rpc.publicnode.com` (plus stable que sepolia.base.org)
     - Chain ID : `84532`
     - Symbole : `ETH`
     - Explorer : `https://sepolia.basescan.org`

## Étape 2 — Récupérer des ETH Sepolia (gratuit)

Tu en as besoin pour : déployer le contrat + funder les wallets users.

Faucets recommandés (du plus simple au plus contraint) :
- **Coinbase Developer Platform** : https://portal.cdp.coinbase.com/products/faucet (jusqu'à 0.1 ETH/24h, compte CDP gratuit)
- **Chainstack** : 0.5 ETH/24h, inscription rapide
- **PoW faucet** : https://www.ethereum-ecosystem.com/faucets/base-sepolia (zéro inscription, "minage" navigateur)
- **Alchemy** / **QuickNode** : marchent bien mais demandent 0.001 ETH sur mainnet Ethereum

Demande **~0.1 ETH Sepolia** sur ton wallet "Dev Hugo". C'est largement suffisant.

## Étape 3 — Déployer le contrat ERC-20

1. Va sur https://remix.ethereum.org
2. Crée un fichier `CamplongCoin.sol` et colle le contenu de `contract/CamplongCoin.sol`
3. Onglet **Solidity Compiler** : version `0.8.20+` → **Compile**
4. Onglet **Deploy & Run Transactions** :
   - Environment : **Injected Provider - MetaMask** (vérifie que tu es sur Base Sepolia !)
   - Contract : `CamplongCoin`
   - Clique **Deploy** → signe la tx dans MetaMask
5. **Copie l'adresse du contrat** (clique sur le contrat déployé en bas, icône copier). C'est ton `CONTRACT_ADDRESS`.

À ce stade, ton wallet "Dev Hugo" possède **1 000 000 CAMP**. C'est la treasury.

> 💡 Tu peux vérifier le contrat sur https://sepolia.basescan.org en collant son adresse.

## Étape 4 — Installer les dépendances backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # (sur macOS/Linux)
pip install -r requirements.txt
```

## Étape 5 — Générer les wallets users

```bash
cd backend
python setup_users.py
```

Le script va :
1. **Afficher une MASTER_KEY** → garde-la sous le coude (à mettre dans `.env`)
2. Te demander un mot de passe pour `Hugo` puis `Alice`
3. Créer `users.json` avec les wallets chiffrés et les adresses générées
4. **Afficher les 2 adresses Ethereum** des users → note-les

> 💡 Pour ajouter d'autres potes plus tard : édite la liste `USERS_TO_CREATE` en haut de `setup_users.py` puis relance.

## Étape 6 — Créer le fichier `.env`

```bash
cd backend
cp .env.example .env
```

Édite `.env` :

```env
MASTER_KEY=<celle affichée par setup_users.py>
RPC_URL=https://base-sepolia-rpc.publicnode.com
CONTRACT_ADDRESS=<adresse de l'étape 3>
JWT_SECRET=<génère un secret avec: openssl rand -hex 32>
```

## Étape 7 — Funder les wallets users avec un peu d'ETH (pour le gas)

Chaque user signe ses propres transactions, donc chaque wallet doit avoir un peu d'ETH pour payer le gas.

Depuis MetaMask (wallet "Dev Hugo"), envoie **0.01 ETH Sepolia** à chaque adresse user (affichées à l'étape 5).

> Sur Base Sepolia, une tx coûte ~0.000001 ETH → 0.01 ETH = des dizaines de milliers de transferts.

## Étape 8 — Distribuer des CAMP initiaux aux users

Depuis **Remix**, dans le contrat déployé (panneau "Deployed Contracts" en bas à gauche) :

Pour donner **1000 CAMP** à Hugo :
- Trouve la fonction `transfer`
- `_to` : adresse de Hugo
- `_value` : `1000000000000000000000` (= 1000 × 10¹⁸)
- Clique sur **transact** → signe dans MetaMask

Idem pour Alice (ou plus, ou moins, comme tu veux).

> ⚠️ Les ERC-20 ont **18 décimales**. Donc 1 CAMP = `1000000000000000000` en interne. Toujours multiplier/diviser par `10**18`.

Vérifie sur https://sepolia.basescan.org : colle l'adresse de Hugo → onglet "Token Holdings" → tu dois voir tes CAMP.

## Étape 9 — Lancer le backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

Le backend tourne sur http://localhost:8000. Pour vérifier :
- Ouvre http://localhost:8000/docs (Swagger auto-généré par FastAPI)
- Ou http://localhost:8000/ → doit retourner `{"status": "ok", ...}`

## Étape 10 — Lancer le frontend

Le plus simple :

```bash
cd frontend
python3 -m http.server 8080
```

Ouvre http://localhost:8080.

## Étape 11 — Test end-to-end

1. **Login** en tant que `Hugo` avec le password choisi à l'étape 5 → tu vois ton solde (ex: 1000 CAMP)
2. **Envoie 50 CAMP à Alice** avec note "test"
3. Attends ~2-3s (confirmation Base Sepolia)
4. Solde passe à 950, l'historique affiche la tx avec un lien BaseScan
5. **Logout**, login en tant que `Alice` → solde reflète le transfert

🎉 Voilà, ta crypto fonctionne entre potes !

---

## Comment ça marche (résumé)

### Flow d'un transfert

```
[Vue]  user clique "Envoyer 50 à Alice"
   │
   ▼
[FastAPI]  POST /transfer
   │
   ├─ valider le JWT, retrouver le wallet de Hugo dans users.json
   ├─ déchiffrer la clé privée de Hugo avec MASTER_KEY (Fernet)
   ├─ vérifier le solde (balanceOf on-chain)
   ├─ construire la tx : contract.transfer(addr_Alice, 50e18)
   ├─ signer avec la clé privée de Hugo
   ├─ envoyer via w3.eth.send_raw_transaction()
   ├─ attendre la confirmation (~2s sur Base)
   ├─ logger dans transactions.log
   │
   ▼
[Réponse]  {tx_hash, new_balance}
   │
   ▼
[Vue]  affiche succès + refresh balance + historique
```

### Sécurité (niveau MVP)

| Aspect | Approche |
|---|---|
| Mots de passe | hashés bcrypt |
| Clés privées | chiffrées Fernet, `MASTER_KEY` en env var |
| Auth API | JWT HS256, expiration 7 jours |
| Secrets | `.env` + `users.json` dans `.gitignore` |
| HTTPS | À activer en prod (Scaleway le fait) |

**Ce qui n'est PAS dans le MVP** mais nécessaire avant mainnet : 2FA, secret manager pour la master key, audit du code de signing, monitoring de la treasury, multi-sig, rate limiting.

---

## Pour aller plus loin

- [ ] Migrer `users.json` + `transactions.log` vers Postgres (Scaleway Serverless)
- [ ] Page "Exporter mon wallet" (affiche la clé privée déchiffrée, avec warning) pour passer en self-custody
- [ ] Monitoring : alerte quand un wallet user descend sous 0.001 ETH
- [ ] Déployer sur Scaleway Serverless Containers
- [ ] Meta-transactions EIP-2771 : la treasury paie le gas pour les users

---

## Pièges courants

| Erreur | Cause / solution |
|---|---|
| `insufficient funds for gas` | Le wallet user n'a plus d'ETH Sepolia. Refunde depuis la treasury. |
| `nonce too low` | Plusieurs tx rapprochées : utilise `get_transaction_count(addr, "pending")` |
| Solde affiche 0 alors que tu viens d'envoyer | Pas attendu la confirmation. Refresh dans 2-3s. |
| Faucet vide / rate-limited | Essaie un autre faucet (CDP, Chainstack, PoW) |
| MetaMask : "wrong network" | Toujours vérifier qu'on est sur Base Sepolia avant Deploy/transfer dans Remix |
| `Unable to connect` côté MetaMask | Change le RPC pour `https://base-sepolia-rpc.publicnode.com` |
| `users.json` commité par erreur | Vérifier que `.gitignore` est en place **avant** le premier commit |