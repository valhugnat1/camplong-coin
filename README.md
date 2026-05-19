# CamplongCoin

App custodial pour échanger un token ERC-20 (**CAMP**) entre potes sur **Base Sepolia** (testnet Ethereum L2, gratuit).

L'app gère le wallet de chacun en backend (clés privées chiffrées), un backoffice admin permet de créer des users et distribuer/récupérer des CAMP depuis ton portefeuille perso (treasury), et tout passe par de vraies transactions on-chain visibles sur BaseScan.

**Caractéristique clé** : la treasury paie 100% du gas via une fonction `adminTransfer` du contrat. Les users n'ont jamais besoin d'ETH, l'onboarding est instantané.

---

## Table des matières

1. [Stack](#stack)
2. [Structure du projet](#structure-du-projet)
3. [Setup initial : déployer le contrat + lancer l'app](#setup-initial)
4. [Backoffice admin](#backoffice-admin)
5. [Comment ça marche](#comment-ça-marche)
6. [API reference](#api-reference)
7. [Pour aller plus loin](#pour-aller-plus-loin)

---

## Stack

| Couche | Techno |
|---|---|
| Smart contract | Solidity 0.8.20 + OpenZeppelin ERC20 + Ownable |
| Réseau | Base Sepolia (Chain ID 84532) — L2 d'Ethereum, testnet |
| Backend | FastAPI + `web3.py` + `eth-account` + JWT |
| DB | PostgreSQL (Scaleway Serverless), 2 schémas `test` + `prod` |
| Frontend | Vue 3 (single HTML file, x2 : user et admin) |
| Crypto | Fernet pour chiffrer les clés privées, bcrypt pour les mots de passe |

---

## Structure du projet

```
camplong-coin/
├── README.md                       # Ce fichier
├── .gitignore                      # Protège .env, users.json, transactions.log
│
├── contract/
│   └── CamplongCoin.sol            # Smart contract ERC-20 avec adminTransfer
│
├── backend/
│   ├── .env.example                # Template .env (à copier en .env)
│   ├── .env                        # 🔒 secrets, NON commit
│   ├── requirements.txt            # Deps Python
│   │
│   ├── database.py                 # Connection Postgres + schema switch
│   ├── models.py                   # Modèles SQLAlchemy : User, Transaction, Nonce
│   │
│   ├── init_db.py                  # Crée les 2 schémas + les tables
│   ├── migrate_from_json.py        # One-shot : users.json + transactions.log → DB
│   ├── setup_users.py              # Génère des users en CLI (alternative au backoffice)
│   │
│   ├── main.py                     # FastAPI app, endpoints users
│   └── admin.py                    # Router FastAPI, endpoints /admin/*
│
└── frontend/
    ├── index.html                  # UI user (login, balance, transfer)
    └── admin.html                  # UI admin (backoffice)
```

---

## Setup initial

L'objectif : avoir le contrat déployé, la DB prête, et 2 users qui peuvent s'envoyer des CAMP.

### Étape 1 — MetaMask + Base Sepolia

1. Installe **MetaMask** (extension Chrome/Brave/Firefox)
2. Crée un wallet "Dev Hugo" — note la seed dans un gestionnaire de mots de passe. **Ce wallet sera ta treasury.**
3. Ajoute le réseau **Base Sepolia** :
   - Va sur https://chainlist.org/?testnets=true&search=base+sepolia → "Add to MetaMask"
   - Ou manuellement :
     - Nom : `Base Sepolia`
     - RPC URL : `https://base-sepolia-rpc.publicnode.com` (plus stable que `sepolia.base.org`)
     - Chain ID : `84532`
     - Symbole : `ETH`
     - Explorer : `https://sepolia.basescan.org`

### Étape 2 — Récupérer des ETH Sepolia (gratuit)

Tu en as besoin pour : déployer le contrat + payer le gas de toutes les opérations futures (la treasury paie tout).

Faucets (du plus simple au plus contraint) :
- **Coinbase Developer Platform** : https://portal.cdp.coinbase.com/products/faucet (jusqu'à 0.1 ETH/24h, compte CDP gratuit)
- **Chainstack** : 0.5 ETH/24h, inscription rapide
- **PoW faucet** : https://www.ethereum-ecosystem.com/faucets/base-sepolia (zéro inscription, "minage" navigateur)
- **Alchemy** / **QuickNode** : marchent bien mais demandent 0.001 ETH sur mainnet Ethereum

Demande **~0.05 ETH Sepolia** sur ton wallet "Dev Hugo". Largement suffisant pour des milliers de transferts (le gas Base est extrêmement bas).

### Étape 3 — Déployer le contrat ERC-20

1. Va sur https://remix.ethereum.org
2. Crée un fichier `CamplongCoin.sol` et colle le contenu de `contract/CamplongCoin.sol`
3. Onglet **Solidity Compiler** → version `0.8.20+` → **Compile**
4. Onglet **Deploy & Run Transactions** :
   - Environment : **Injected Provider - MetaMask** (vérifie que tu es sur Base Sepolia !)
   - Contract : `CamplongCoin` (pas `ERC20` ou `Ownable` qui apparaîtront aussi dans la liste)
   - Clique **Deploy** → signe la tx dans MetaMask
5. **Copie l'adresse du contrat** (icône copier à côté du contrat déployé en bas). C'est ton `CONTRACT_ADDRESS`.

À ce stade, ton wallet "Dev Hugo" possède **1 000 000 CAMP** et est l'**owner** du contrat. Seul l'owner peut appeler `adminTransfer(from, to, amount)` — c'est ce qui permet à la treasury de déplacer les tokens de n'importe quel user sans que celui-ci signe quoi que ce soit.

> ⚠️ Le contrat est **immuable** une fois déployé. Si tu veux faire évoluer la logique, il faut redéployer (et mettre à jour `CONTRACT_ADDRESS` dans `.env`). Trivial sur testnet, plus engageant sur mainnet — d'où le pattern proxy upgradeable pour une vraie prod.

> 💡 Importer le token CAMP dans MetaMask pour le voir : MetaMask → onglet "Tokens" → "Import tokens" → "Custom token" → colle l'adresse du contrat → Import.

### Étape 4 — Créer la DB Postgres (Scaleway Serverless)

1. Console Scaleway → **Serverless → Serverless SQL Databases**
2. Crée une database :
   - Region : `fr-par`
   - Engine : **PostgreSQL**
   - Nom : `camplong`
3. Onglet **Connect** : note **endpoint**, **database name**, **username**, **password**
4. Forme finale du `DATABASE_URL` :

   ```
   postgresql://USER:PASSWORD@ENDPOINT/DBNAME?sslmode=require
   ```

> 💡 Scaleway Serverless SQL facture à l'usage, la DB se suspend après inactivité. Parfait pour un MVP.

### Étape 5 — Installer les dépendances backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Étape 6 — Récupérer la clé privée de ta treasury

⚠️ **Étape sensible**. Cette clé donne le contrôle total de la treasury ET de l'ownership du contrat (donc le pouvoir de déplacer n'importe quel solde via `adminTransfer`).

Dans MetaMask :
1. Clique sur les 3 points à côté de "Dev Hugo"
2. **Account details** → **Show private key**
3. Tape ton mot de passe MetaMask, copie la clé (format `0x...` 64 hex)

Sur testnet : aucun risque financier (= 0€), mais **prends l'habitude d'être prudent** dès maintenant.

### Étape 7 — Créer le `.env`

```bash
cd backend
cp .env.example .env
```

Édite `.env` :

```env
# Secrets app
MASTER_KEY=                            # généré à l'étape 9 ci-dessous
JWT_SECRET=<openssl rand -hex 32>

# Blockchain
RPC_URL=https://base-sepolia-rpc.publicnode.com
CONTRACT_ADDRESS=<adresse de l'étape 3>

# Database
DATABASE_URL=postgresql://USER:PASS@HOST:PORT/DB?sslmode=require
DB_SCHEMA=test

# Treasury (signe TOUTES les tx, paie tout le gas)
TREASURY_PRIVATE_KEY=<clé de l'étape 6>
ADMIN_PASSWORD=<openssl rand -hex 16>
```

### Étape 8 — Initialiser la DB

```bash
python init_db.py
```

Le script crée les 2 schémas (`test` et `prod`) et les tables `users`, `transactions`, `nonces` dans le schéma actif (`test` par défaut). Il affiche un diagnostic pour confirmer.

> 💡 Pour initialiser aussi le schéma `prod` :
> ```bash
> DB_SCHEMA=prod python init_db.py
> ```

### Étape 9 — Générer la MASTER_KEY (si tu n'en as pas déjà une)

```bash
python setup_users.py
```

Au premier lancement (sans `MASTER_KEY` dans `.env`), le script affiche une clé fraîche. **Copie-la dans `.env`** sous `MASTER_KEY=` puis relance le script.

> Le script `setup_users.py` est une **alternative CLI au backoffice** pour créer les premiers users. Tu peux aussi sauter cette étape et créer tes users directement via l'UI admin (étape 11).

### Étape 10 — Lancer le backend

```bash
uvicorn main:app --reload
```

Vérifie http://localhost:8000/ → doit retourner :
```json
{"status":"ok","chain":"Base Sepolia","contract":"0x...","schema":"test"}
```

Doc auto-générée : http://localhost:8000/docs

### Étape 11 — Lancer le frontend

```bash
cd frontend
python3 -m http.server 8080
```

- UI users : http://localhost:8080/index.html
- UI admin : http://localhost:8080/admin.html

### Étape 12 — Test end-to-end

1. Ouvre le **backoffice** http://localhost:8080/admin.html
2. Login avec ton `ADMIN_PASSWORD`
3. Crée Hugo : pseudo `Hugo`, password au choix, **1000 CAMP initiaux** → création quasi instantanée (1 seule tx on-chain)
4. Crée Alice : pseudo `Alice`, password au choix, **1000 CAMP initiaux**
5. Ouvre http://localhost:8080/index.html dans un autre onglet
6. Login en tant que `Hugo` → tu vois 1000 CAMP
7. Envoie 50 CAMP à Alice → ~3s, solde devient 950, historique affiche la tx avec lien BaseScan
8. Logout, login en tant que `Alice` → tu vois 1050 CAMP

🎉 Ton MVP est fonctionnel end-to-end, sans qu'aucun user ait jamais eu d'ETH.

---

## Backoffice admin

UI admin pour gérer les users et déplacer des CAMP entre ta treasury et n'importe quel user. Accès via http://localhost:8080/admin.html avec `ADMIN_PASSWORD`.

### Ce que tu peux faire

| Action | Comment |
|---|---|
| Voir la treasury | Header noir en haut : adresse + solde CAMP + solde ETH (gas global) |
| Créer un user | Pseudo + password + montant CAMP initial → 1 clic |
| Voir tous les users | Tableau avec leur solde CAMP en temps réel |
| Créditer (+) | Bouton vert : `adminTransfer(treasury, user, amount)` |
| Débiter (−) | Bouton rouge : `adminTransfer(user, treasury, amount)` |

### Détails techniques

**Création de user** déclenche au maximum 2 opérations :
1. Insert en DB (génère un wallet, chiffre la clé privée, hash le password)
2. Si `initial_camp > 0` : `adminTransfer(treasury, user.address, initial_camp)` signée par la treasury

Plus de funding ETH à l'onboarding. Le wallet généré possède une clé privée, mais celle-ci **n'est jamais utilisée pour signer** dans le flow actuel — elle est conservée chiffrée au cas où tu voudrais permettre un export self-custody plus tard.

**Crédit et débit** sont symétriques : un appel à `adminTransfer(from, to, amount)` signé par la treasury. Plus besoin de déchiffrer la clé privée du user pour le débit (l'owner du contrat peut déplacer n'importe quel solde).

**Logs d'audit** : chaque opération admin crée une ligne dans `transactions` avec `from_username` ou `to_username = "__treasury__"`. Tu retrouves tout l'historique admin dans la même table que les transferts normaux.

**Surveillance treasury ETH** : c'est la treasury qui paie 100% du gas, donc surveille la jauge ETH dans le header noir. Sur Base Sepolia c'est gratuit (faucet). Sur mainnet ce serait à refunder périodiquement.

---

## Comment ça marche

### Flow d'un transfert user

```
[Vue]  Hugo clique "Envoyer 50 à Alice"
   │
   ▼
[FastAPI]  POST /transfer
   │
   ├─ valider le JWT, retrouver le User de Hugo en DB
   ├─ vérifier le solde de Hugo (balanceOf on-chain)
   ├─ réserver un nonce TREASURY en DB (SELECT FOR UPDATE)
   ├─ construire la tx : contract.adminTransfer(addr_Hugo, addr_Alice, 50e18)
   ├─ signer avec la clé privée de la TREASURY
   ├─ envoyer via w3.eth.send_raw_transaction()
   ├─ attendre la confirmation (~2s sur Base)
   ├─ enregistrer en table transactions
   │
   ▼
[Réponse]  {tx_hash, new_balance}
```

La clé privée de Hugo n'intervient **jamais**. C'est la treasury qui signe la tx (et donc paie le gas), et le contrat exécute le transfert parce que la treasury est l'owner.

### Le contrat en 1 minute

```solidity
contract CamplongCoin is ERC20, Ownable {
    constructor() ERC20("CamplongCoin", "CAMP") Ownable(msg.sender) {
        _mint(msg.sender, 1_000_000 * 10**decimals());
    }

    function adminTransfer(address from, address to, uint256 amount)
        external onlyOwner
    {
        _transfer(from, to, amount);
    }
}
```

- Hérite de `ERC20` (transferts standards) et `Ownable` (gestion d'un owner).
- L'owner est `msg.sender` du constructor, donc le wallet qui déploie = la treasury.
- `adminTransfer` appelle `_transfer` (la fonction interne d'OpenZeppelin qui ne vérifie pas d'allowance) — accessible uniquement par l'owner.
- Trade-off assumé : c'est **très** custodial. L'owner peut bouger n'importe quel solde à tout moment. Acceptable pour une app entre potes, jamais à faire sur mainnet sans multi-sig.

### Modèle de données (3 tables)

**users** : 1 ligne par user. `username` (pseudo) en PK, password hashé bcrypt, clé privée chiffrée Fernet (jamais utilisée pour signer aujourd'hui, gardée pour un éventuel export self-custody), adresse Ethereum.

**transactions** : log de toutes les tx CAMP qui passent par le backend (user→user, treasury→user, user→treasury). `tx_hash` unique.

**nonces** : 1 seule ligne réellement utilisée — celle de la treasury. Verrouillée en `SELECT ... FOR UPDATE` pendant chaque transfert pour éviter les collisions en cas de tx concurrentes.

### Schémas test et prod

Une seule DB Scaleway, **deux schémas Postgres** :

```
camplong (DB)
├── schema: test           ├── users
│                          ├── transactions
│                          └── nonces
└── schema: prod           ├── users
                           ├── transactions
                           └── nonces
```

Tout le code est identique entre les deux. Seule la variable d'env `DB_SCHEMA` change. Les modèles déclarent leur schéma explicitement via `__table_args__ = {"schema": DB_SCHEMA}`, ce qui produit du SQL qualifié (`SELECT FROM test.users` au lieu de `SELECT FROM users`).

> En prod tu utiliseras aussi : un autre `CONTRACT_ADDRESS` (Base mainnet ou autre testnet), une autre `MASTER_KEY`, un autre `JWT_SECRET`, un autre `TREASURY_PRIVATE_KEY`.

### Gestion des nonces

Le nonce Ethereum doit être strictement séquentiel. Comme **toutes les tx sont signées par la treasury**, il n'y a qu'une seule séquence de nonces à gérer (au lieu d'une par user dans la version précédente). C'est plus simple, mais le verrou est plus chargé : toutes les tx en parallèle passent par la même ligne `nonces`.

Solution : `_next_treasury_nonce()` dans `admin.py` (et appelé aussi depuis `main.py`) :
1. `SELECT ... FOR UPDATE` sur la ligne du nonce treasury → verrou pessimiste
2. Compare avec `eth_getTransactionCount(treasury, "pending")` pour resync si tx hors backend
3. Prend `max(db, chain)`, incrémente, commit (libère le verrou)

Garantie : deux requêtes parallèles ont des nonces strictement différents.

---

## API reference

### Endpoints users (auth JWT user, 7 jours)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/login` | Login user → `{token, address, username}` |
| `GET` | `/me` | Infos du user connecté + solde CAMP |
| `GET` | `/users` | Liste des autres users (pour le dropdown destinataire) |
| `POST` | `/transfer` | Envoie CAMP du user connecté vers un autre user (signé par la treasury) |
| `GET` | `/history` | Historique des tx (100 dernières) |

### Endpoints admin (auth JWT admin, 24h)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/admin/login` | Login admin → `{token}` |
| `GET` | `/admin/treasury` | Adresse + solde CAMP + solde ETH de la treasury |
| `GET` | `/admin/users` | Liste de tous les users avec leur solde CAMP |
| `POST` | `/admin/users` | Crée un user (génère wallet, fund CAMP optionnel — plus d'ETH) |
| `POST` | `/admin/credit` | `adminTransfer(treasury → user)` |
| `POST` | `/admin/debit` | `adminTransfer(user → treasury)` |

### Endpoint root

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Healthcheck + infos de config (chain, contract, schema) |

Doc interactive : http://localhost:8000/docs

---

## Pour aller plus loin

### Évolutions courtes

- [ ] Page "Exporter mon wallet" (affiche la clé privée déchiffrée avec warning) pour migrer en self-custody — la clé est toujours stockée chiffrée même si le flow custodial ne l'utilise plus
- [ ] Monitoring : alerte si le solde ETH de la treasury descend sous un seuil (ex: 0.01 ETH)
- [ ] `adminBatchTransfer` côté contrat + endpoint backend pour grouper plusieurs transferts en une seule tx (économise du gas)
- [ ] Backup chiffré régulier de la DB
- [ ] Vérifier le contrat sur BaseScan pour qu'il soit lisible publiquement (Etherscan-style)

### Évolutions plus ambitieuses 

- [ ] **Auto-onboarding** : page `/signup` publique avec captcha, validation admin a posteriori
- [ ] **Notifications** : email ou push quand un user reçoit un transfert
- [ ] **Déploiement Scaleway Serverless Containers** : `Dockerfile` + push image + DNS + HTTPS

### Passer en mainnet

Le pattern `onlyOwner adminTransfer` est inacceptable en mainnet : un compromis de la clé treasury vide tous les wallets users. Avant tout passage en prod :

- **Multi-sig** sur l'owner du contrat (Safe / Gnosis) — il faut N signatures pour exécuter une fonction admin
- **Hardware wallet** pour la clé treasury (Ledger / Trezor)
- **Secret manager** pour MASTER_KEY et JWT_SECRET (pas de `.env` en plain text)
- **Audit du code** du contrat et du backend
- **Pattern proxy upgradeable** (UUPS/Transparent) pour pouvoir patcher les bugs sans migration