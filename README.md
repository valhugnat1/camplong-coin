# CamplongCoin

App custodial pour échanger un token ERC-20 (**CAMP**) entre potes sur **Base Sepolia** (testnet Ethereum L2, gratuit), avec une interface qui ressemble à un site crypto/casino moderne.

L'app gère les wallets en backend (clés privées chiffrées), un backoffice admin permet de tout piloter, et toutes les opérations passent par de vraies transactions on-chain visibles sur BaseScan.

**Caractéristique clé** : la treasury (= ton wallet perso, owner du contrat) paie 100 % du gas via une fonction `adminTransfer`. Les users n'ont jamais besoin d'ETH, l'onboarding est instantané.

---

## Features

### Pour les users

- **Wallet** : solde CAMP affiché en gros + équivalent EUR à côté
- **Envoyer / recevoir** des CAMP entre membres du groupe
- **Historique on-chain** avec liens BaseScan
- **Acheter / vendre des CAMP** contre des EUR (Wero / Revolut), envoie une demande à l'admin qui traite manuellement → confirmation par email
- **Self-custody mode** : récupération de la clé privée + import dans MetaMask en deux clics
- **Profil** : email, changement de mot de passe
- **Onglets "soon"** placeholders pour les évolutions à venir : Paris (style Polymarket), Casino (slots/roulette/poker), Bourse du Lait (trading de produits laitiers titrisés)

### Pour l'admin

- **Backoffice** avec vue d'ensemble : treasury, total en circulation, valeur EUR de tout
- **Gestion des users** : création, crédit/débit, suppression (refusée si solde non nul)
- **Gestion des demandes d'achat/vente** : filtrer par statut (pending/done/cancelled), confirmer une demande **déclenche automatiquement le mouvement on-chain** (treasury → user pour achat, user → treasury pour vente) + email au user

### Email notifications

- Nouvelle demande → email à l'admin
- Demande confirmée → email au user (avec ton message optionnel)
- Configuration Gmail via App Password ([détails dans `backend/SETUP_EMAIL.md`](backend/SETUP_EMAIL.md))

---

## Architecture haut niveau

```
┌─────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  Frontend (Vue 3)   │ ──→ │  Backend (FastAPI)   │ ──→ │  Base Sepolia      │
│  user + admin SPA   │     │  custodial logic     │     │  CamplongCoin.sol  │
└─────────────────────┘     └──────────┬───────────┘     └────────────────────┘
                                       │
                            ┌──────────┴──────────┐
                            ▼                     ▼
                       ┌─────────┐         ┌──────────┐
                       │Postgres │         │  Gmail   │
                       │test/prod│         │  SMTP    │
                       └─────────┘         └──────────┘
```

- **Front** : Vue 3 + Vite + Vue Router + Pinia, déployé sur Scaleway Serverless Containers (image nginx)
- **Back** : FastAPI + SQLAlchemy + web3.py, signe toutes les tx avec la clé treasury
- **DB** : Postgres Scaleway Serverless, 2 schémas `test` et `prod` dans la même base
- **Chain** : Base Sepolia (testnet L2 Ethereum), contrat ERC-20 custom avec `adminTransfer` réservé à l'owner

Détails techniques complets dans [`AGENTS.md`](AGENTS.md).

---

## Structure du repo

```
camplong-coin/
├── README.md                # ce fichier
├── AGENTS.md                # spec technique détaillée
├── contract/                # smart contract Solidity (à déployer via Remix)
├── backend/                 # FastAPI + SQLAlchemy + web3
├── frontend/                # Vue 3 SPA (user + admin)
└── scripts/                 # build & push d'images Docker
```

---

## Lancer le projet en local

### Prérequis

- Python 3.11+, Node 20+, Docker (optionnel)
- Un wallet MetaMask avec quelques ETH sur Base Sepolia ([faucet Coinbase](https://portal.cdp.coinbase.com/products/faucet))
- Une base Postgres (Scaleway Serverless SQL ou local)
- Le contrat `CamplongCoin.sol` déployé via Remix → récupérer l'adresse

Setup complet pas-à-pas dans `AGENTS.md` (déploiement contrat, génération des clés, init DB, etc.).

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Édite .env : DATABASE_URL, CONTRACT_ADDRESS, TREASURY_PRIVATE_KEY,
#              MASTER_KEY, JWT_SECRET, ADMIN_PASSWORD, SMTP_*

python scripts/init_db.py            # crée les tables (schéma 'test' par défaut)
uvicorn main:app --reload            # http://localhost:8000
```

### Frontend

```bash
cd frontend
cp .env.example .env
# Édite .env : VITE_API_URL (http://localhost:8000), VITE_CONTRACT_ADDRESS

npm install
npm run dev                          # http://localhost:8080
```

L'app user est sur `/login`, le backoffice sur `/admin/login`.

---

## Déploiement (Scaleway)

```bash
# Depuis la racine du repo
./scripts/push_images.sh             # build & push les 2 images Docker
./scripts/redeploy.sh                # trigger redeploy des containers
```

Le script lit `BACKEND_URL` et `CONTRACT_ADDRESS` depuis un `.env` racine pour injecter les bonnes valeurs à la compilation du front.

---

## Stack

| Couche | Techno |
|---|---|
| Smart contract | Solidity 0.8.20 + OpenZeppelin (ERC20, Ownable) |
| Réseau | Base Sepolia (Chain ID 84532) |
| Backend | FastAPI · SQLAlchemy · web3.py · eth-account · JWT · bcrypt · Fernet |
| Email | SMTP (Gmail App Password par défaut) |
| Database | PostgreSQL (Scaleway Serverless), schémas `test` + `prod` |
| Frontend | Vue 3 (Composition API) · Vite · Vue Router · Pinia |
| Déploiement | Docker · Scaleway Serverless Containers · Scaleway Container Registry |
