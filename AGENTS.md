# AGENTS.md — Spec technique CamplongCoin

Document destiné aux développeurs (humains ou agents IA) qui veulent contribuer ou comprendre comment l'app fonctionne sous le capot. Le `README.md` couvre le "quoi" et "comment lancer". Ce fichier couvre le "comment c'est fait".

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Smart contract](#smart-contract)
3. [Base de données](#base-de-donnees)
4. [Backend](#backend)
5. [Frontend](#frontend)
6. [Module Paris (P2P bets)](#module-paris-p2p-bets)
7. [Module Casino (coinflip + roulette)](#module-casino-coinflip--roulette)
8. [Sécurité & secrets](#securite--secrets)
9. [Déploiement](#deploiement)
10. [Conventions & gotchas](#conventions--gotchas)

---

## Vue d'ensemble

CamplongCoin est une app **custodial** (le backend gère les clés privées des users) construite autour d'un token ERC-20 sur Base Sepolia. La caractéristique architecturale clé : **toutes les transactions on-chain sont signées par la treasury** (= le wallet owner du contrat), jamais par les users.

Concrètement :
- Quand Hugo envoie 50 CAMP à Alice, le backend appelle `contract.adminTransfer(addrHugo, addrAlice, 50)` signé par la treasury
- La treasury paie le gas, donc les users n'ont jamais besoin d'ETH
- La clé privée d'un user est chiffrée en base (Fernet) et **n'est jamais utilisée pour signer dans le flow custodial** — elle reste là uniquement pour un export self-custody volontaire

C'est très centralisé (l'owner peut bouger n'importe quel solde), assumé pour un produit "entre potes". À surtout pas faire en mainnet sans multi-sig.

### Flow complet d'un transfert user→user

```
[Vue]      Hugo clique "Envoyer 50 à Alice"
   │
   ▼
[FastAPI]  POST /transfer  { to_username: "Alice", amount: 50 }
   │       ↓ valide JWT, retrouve le User de Hugo en DB
   │       ↓ vérifie le solde de Hugo (balanceOf on-chain)
   │       ↓ réserve un nonce TREASURY en DB (SELECT FOR UPDATE)
   │       ↓ construit la tx : contract.adminTransfer(addr_Hugo, addr_Alice, 50e18)
   │       ↓ signe avec la clé privée de la TREASURY
   │       ↓ w3.eth.send_raw_transaction()
   │       ↓ attend la confirmation (~2s sur Base)
   │       ↓ insère une ligne dans la table transactions
   │
   ▼
[Réponse]  { tx_hash, new_balance }
```

La clé privée de Hugo n'intervient jamais. Le contrat exécute le transfert parce que la treasury est l'owner.

---

## Smart contract

Fichier : `contract/CamplongCoin.sol`.

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

- Hérite de l'`ERC20` standard et d'`Ownable` (OpenZeppelin)
- Au déploiement, le déployeur (la treasury) reçoit 1 000 000 CAMP et devient owner
- `adminTransfer` appelle l'internal `_transfer` (sans vérification d'allowance) — réservé à l'owner
- **Contrat immuable** : pour upgrade il faut redéployer. Trivial sur testnet, plus engageant en prod (pattern proxy UUPS si besoin)

Pour le déploiement, voir le pas-à-pas dans `README.md`. L'adresse du contrat déployé va dans `.env` côté backend (`CONTRACT_ADDRESS`) et frontend (`VITE_CONTRACT_ADDRESS`).

---

## Base de données

PostgreSQL (Scaleway Serverless ou local), une seule base, **deux schémas** `test` et `prod`.

Le switch se fait via la variable `DB_SCHEMA` (lue dans `config.py`). Tout le code SQLAlchemy est identique entre les deux schémas grâce à `__table_args__ = {"schema": DB_SCHEMA}` sur chaque modèle.

```
camplong (DB)
├── schema: test       ├── users               (user + comptes système)
│                      ├── transactions
│                      ├── nonces
│                      ├── market_orders
│                      ├── bets                (cf. § Module Paris)
│                      ├── app_settings        (clés/valeurs admin-tweakables)
│                      ├── rng_seeds           (commit-reveal provably fair)
│                      ├── coinflip_rounds     (cf. § Module Casino)
│                      └── roulette_spins      (cf. § Module Casino)
└── schema: prod       (mêmes tables)
```

Les tables `poker_*`, `milk_*` existent (préparées par `migrate_v4_extensions.py`) mais ne sont pas encore exploitées (cf. `EXTENSIONS.md`).

Garanties :
- Le code applique `SET search_path TO "<schema>", public` à chaque nouvelle connexion (ceinture)
- Les modèles déclarent leur schéma explicitement dans `__table_args__` (bretelles)
- Donc les requêtes ORM produisent du SQL qualifié `SELECT ... FROM test.users` au lieu de `SELECT ... FROM users`

### Tables

**`users`** — un user = un compte custodial.

| Colonne                   | Type         | Notes                                       |
|---------------------------|--------------|---------------------------------------------|
| `username` (PK)           | VARCHAR(64)  | = pseudo (ex: 'Hugo')                       |
| `password_hash`           | VARCHAR(128) | bcrypt                                       |
| `address`                 | VARCHAR(42)  | adresse Ethereum générée à la création      |
| `encrypted_private_key`   | TEXT         | clé privée chiffrée Fernet (MASTER_KEY)     |
| `email`                   | VARCHAR(256) | nullable, pour les notifs                   |
| `created_at`              | TIMESTAMP    |                                              |

**`transactions`** — log de toutes les tx CAMP qui passent par le backend (user↔user, treasury↔user).

| Colonne          | Type        | Notes                                          |
|------------------|-------------|------------------------------------------------|
| `id` (PK)        | INT auto    |                                                |
| `ts`             | TIMESTAMP   |                                                |
| `from_username`  | VARCHAR(64) | `__treasury__` pour les ops admin              |
| `to_username`    | VARCHAR(64) | idem                                            |
| `amount`         | BIGINT      | en CAMP entiers (pas wei)                      |
| `note`           | VARCHAR(256)| libre, ex: "raclette samedi"                   |
| `tx_hash` (UNQ)  | VARCHAR(66) | `0x` + 64 hex                                   |

**`nonces`** — compteur de tx par adresse, verrouillé en `SELECT ... FOR UPDATE`.

| Colonne        | Type        | Notes                                          |
|----------------|-------------|------------------------------------------------|
| `address` (PK) | VARCHAR(42) | en pratique, une seule ligne : la treasury     |
| `next_nonce`   | INT         |                                                 |
| `updated_at`   | TIMESTAMP   |                                                 |

Le nonce Ethereum doit être strictement séquentiel. Comme **toutes les tx sont signées par la treasury**, il y a une seule séquence à gérer. La fonction `_next_treasury_nonce()` dans `blockchain.py` :
1. Fait un `SELECT ... FOR UPDATE` sur la ligne du nonce treasury (verrou pessimiste Postgres)
2. Compare avec `eth_getTransactionCount(treasury, "pending")` au cas où une tx aurait été faite hors backend
3. Prend `max(db, chain)`, incrémente, commit (libère le verrou)

Garantie : deux requêtes parallèles ont des nonces strictement différents.

**`market_orders`** — demandes d'achat/vente de CAMP contre des EUR.

| Colonne        | Type         | Notes                                          |
|----------------|--------------|------------------------------------------------|
| `id` (PK)      | INT auto     |                                                 |
| `ts`           | TIMESTAMP    |                                                 |
| `username`     | VARCHAR(64)  | qui a fait la demande                          |
| `type`         | VARCHAR(8)   | `buy` ou `sell`                                |
| `amount_camp`  | BIGINT       |                                                 |
| `amount_eur`   | FLOAT        |                                                 |
| `handle`       | VARCHAR(128) | Wero/Revolut handle (obligatoire pour `sell`)  |
| `note`         | VARCHAR(512) | note du user                                   |
| `status`       | VARCHAR(16)  | `pending` / `done` / `cancelled`               |
| `admin_note`   | VARCHAR(512) | message admin visible dans l'email de confirm. |
| `done_at`      | TIMESTAMP    | nullable                                       |
| `tx_hash`      | VARCHAR(66)  | nullable, set quand l'order passe en `done`    |

Workflow :
1. User crée une demande via `POST /orders` → `status = pending` → email admin
2. Admin reçoit l'EUR, ouvre le backoffice, clique "Confirmer" → backend exécute la tx on-chain (`adminTransfer` dans le bon sens), set `tx_hash` et `done_at`, passe `status = done` → email user
3. Toute l'opération est atomique : si la tx on-chain échoue, l'order reste en `pending` (rien n'est commit)
4. Garde-fou contre le double-transfert : si on repasse une order de done → pending → done, le `tx_hash` étant déjà set, on ne refait pas le mouvement on-chain

**`app_settings`** — clés/valeurs admin-tweakables. Permet à l'admin de changer des paramètres à chaud depuis le backoffice (ex : l'edge maison du coinflip) sans redéploiement.

| Colonne        | Type         | Notes                                          |
|----------------|--------------|------------------------------------------------|
| `key` (PK)     | VARCHAR(64)  | ex: `coinflip_edge_pct`, `roulette_min_bet`    |
| `value`        | VARCHAR(256) | parsé à la lecture (int/float selon la clé)   |
| `description`  | TEXT         | message d'aide affiché dans le backoffice     |
| `updated_at`   | TIMESTAMP    | onupdate=now                                   |

La whitelist des clés autorisées en écriture (`WRITABLE_KEYS`) est dans `services/settings.py`. Validation par-clé dans `routers/admin.py::admin_update_setting` (bornes, types). Pas de cache : la table est petite et lue ~1×/play.

**`rng_seeds`** — commit-reveal pour les tirages aléatoires provably fair.

| Colonne        | Type         | Notes                                          |
|----------------|--------------|------------------------------------------------|
| `id` (PK)      | INT auto     |                                                |
| `purpose`      | VARCHAR(32)  | `coinflip`, `roulette`, …                      |
| `ref_id`       | INT          | id de la round/spin associée (lié après flush) |
| `seed_hash`    | VARCHAR(64)  | sha256(secret) — publié AVANT le tirage        |
| `seed_secret`  | VARCHAR(64)  | secret 32 bytes — publié APRÈS                 |
| `revealed`     | BOOLEAN      |                                                |
| `client_seed`  | VARCHAR(128) | contribution random du user                    |
| `created_at`   | TIMESTAMP    |                                                |
| `revealed_at`  | TIMESTAMP    | nullable                                       |

Flow (cf. `services/randomness.py`) :
1. `commit(db, purpose)` : génère un secret, retourne `(seed_hash, seed_id)`.
2. `reveal(db, seed_id, client_seed)` : marque revealed=True, retourne `(server_seed, combined_hash)` où `combined_hash = sha256(server_seed + ":" + client_seed)`.
3. `derive_int(combined_hash, modulo)` : convertit les 8 premiers chars hex en int et applique `% modulo`. Utilisé pour `% 2` (coinflip) ou `% 37` (roulette).

L'utilisateur peut vérifier a posteriori que `sha256(server_seed) == seed_hash`.

**`coinflip_rounds`** — historique des parties de pile/face. Settle dans la même requête HTTP que le play (commit + reveal en un seul aller-retour pour l'UX, le user peut vérifier après coup). Edge maison configurable via `app_settings.coinflip_edge_pct`. Payout gagnant = `int(bet × 2 × (1 - edge/100))` (= ~1.96× pour 2%).

**`roulette_spins`** — historique des spins de roulette européenne (37 cases). Un spin = N mises agrégées (numéros pleins 35:1, dozens/columns 2:1, even-money 1:1) → **1 lock unique** vers `casino_bank` (somme des mises), **1 payout net unique** si gain > 0. `bets_json` stocke la liste `[{spot, amount}, …]`. L'edge n'est pas configurable (mécanique : 1/37 ≈ 2.70%).

Voir § *Module Casino* pour le détail des flows.

### Migrations

`scripts/init_db.py` crée les tables au premier setup. Migrations successives (idempotentes, multi-schémas) :
- `migrate_v4_extensions.py` : tables paris + casino + poker + milk + `rng_seeds` + colonnes `account_type` / `system_role` sur users.
- `migrate_v5_bet_votes.py` : colonnes `creator_vote` / `opponent_vote` sur `bets` pour la résolution amiable.
- `migrate_v6_app_settings.py` : table `app_settings` + seed des paramètres casino par défaut (`coinflip_edge_pct=2`, `coinflip_min_bet=1`, `coinflip_max_bet=200`, `roulette_min_bet=1`, `roulette_max_bet=200`).

Chaque script s'applique aux deux schémas par défaut (`test`, puis `prod`) et est ré-exécutable sans effet de bord (CREATE IF NOT EXISTS, ON CONFLICT DO NOTHING, etc.). Lancer ensuite `seed_system_accounts.py` après v4 pour créer les wallets de `casino_bank`, `bets_escrow`, `poker_bank`, `milk_pool_lait_entier`.


---

## Backend

### Organisation

```
backend/
├── main.py              # FastAPI app, CORS, mount des routers
├── config.py            # lit .env, expose les constantes statiques (BETS, JWT, …)
├── database.py          # engine SQLAlchemy + session + search_path
├── models.py            # User, Transaction, Nonce, MarketOrder, Bet,
│                        # AppSetting, RngSeed, CoinflipRound, RouletteSpin
├── schemas.py           # tous les Pydantic In/Out
├── security.py          # JWT decode, deps current_user / require_admin, Fernet
├── blockchain.py        # web3 init, helpers admin_transfer / balanceOf / nonce
├── email_service.py     # SMTP best-effort (orders + bets notifs)
├── services/
│   ├── escrow.py        # lock/release vers comptes système (paris, casino, …)
│   ├── settings.py      # lecture/écriture des app_settings, defaults de secours
│   ├── randomness.py    # commit-reveal (sha256) + derive_int
│   ├── coinflip.py      # play() : lock → tirage → release si gain
│   └── roulette.py      # spin() : N mises agrégées → 1 lock + 1 payout net
├── routers/
│   ├── users.py         # /login, /me, /transfer, /history, /orders, /me/*
│   ├── admin.py         # /admin/login, /admin/users, /admin/credit|debit,
│   │                    # /admin/orders, /admin/bets/*,
│   │                    # /admin/settings/*, /admin/casino/stats
│   ├── bets.py          # /bets/*, /me/bets, vote/match/cancel/resolve
│   └── casino.py        # /casino/coinflip/*, /casino/roulette/*,
│                        # /me/coinflip, /me/roulette
└── scripts/
    ├── migrate_v4_extensions.py   # tables paris/casino/lait + comptes système
    ├── migrate_v5_bet_votes.py    # colonnes creator_vote / opponent_vote
    ├── migrate_v6_app_settings.py # table app_settings + seed casino defaults
    └── seed_system_accounts.py    # crée bets_escrow, casino_bank, poker_bank
```

### Modules clés

**`security.py`**
- `current_user(token)` : décode le JWT user, retrouve le User en DB, sinon 401
- `require_admin(token)` : vérifie le claim `role: "admin"` du JWT admin, sinon 401
- `fernet` : instance Fernet initialisée avec `MASTER_KEY`, utilisée pour chiffrer/déchiffrer les clés privées

**`blockchain.py`**
- Singleton `w3` (web3 instance) et `contract` (instance du contrat)
- `treasury` : instance `Account` depuis `TREASURY_PRIVATE_KEY`
- `admin_transfer(db, from_addr, to_addr, amount)` : construit la tx `adminTransfer`, réserve un nonce, signe, envoie, attend la confirmation, retourne le `tx_hash`
- `get_balance_camp(addr)` : appelle `contract.functions.balanceOf(addr).call()` et convertit en CAMP entiers
- `get_balance_eth(addr)` : pour la jauge gas

**`email_service.py`**
- `_send(to, subject, body)` : envoi SMTP best-effort (log warning si pas configuré, log error si échec, **jamais de raise**)
- `send_admin_new_order(order, user_email)` : notif admin sur nouvelle demande
- `send_user_order_done(order, user_email)` : confirmation user après "done"
- Toujours appelé via `BackgroundTasks` FastAPI pour ne pas bloquer la requête HTTP

### Endpoints

| Méthode | Route                        | Auth        | Description                                                |
|---------|------------------------------|-------------|------------------------------------------------------------|
| GET     | `/`                          | public      | Healthcheck + config                                       |
| POST    | `/login`                     | public      | Login user → JWT 7j                                        |
| GET     | `/me`                        | user        | Solde + infos                                              |
| POST    | `/me/password`               | user        | Change mot de passe (re-vérifie l'ancien)                  |
| POST    | `/me/email`                  | user        | Update email                                                |
| POST    | `/me/reveal-key`             | user + pwd  | Renvoie la clé privée déchiffrée (pour MetaMask)           |
| GET     | `/users`                     | user        | Annuaire des autres users (pour le dropdown destinataire)  |
| POST    | `/transfer`                  | user        | Envoi user → user                                          |
| GET     | `/history`                   | user        | 100 dernières tx où le user est expéditeur ou destinataire |
| POST    | `/orders`                    | user        | Crée une demande d'achat/vente                             |
| GET     | `/me/orders`                 | user        | Historique des demandes du user                            |
| POST    | `/admin/login`               | public      | Login admin → JWT 24h                                      |
| GET     | `/admin/treasury`            | admin       | Adresse + solde CAMP + ETH                                 |
| GET     | `/admin/users`               | admin       | Liste de tous les users avec solde                         |
| POST    | `/admin/users`               | admin       | Crée un user (génère wallet, fund optionnel)               |
| DELETE  | `/admin/users/{username}`    | admin       | Supprime (refuse si solde > 0)                             |
| POST    | `/admin/credit`              | admin       | `adminTransfer(treasury → user)`                           |
| POST    | `/admin/debit`               | admin       | `adminTransfer(user → treasury)`                           |
| GET     | `/admin/orders`              | admin       | Liste des demandes (filtre `?status=pending|done|cancelled|all`) |
| PATCH   | `/admin/orders/{id}`         | admin       | Change statut + admin_note. Si done → exécute tx + email   |
| DELETE  | `/admin/orders/{id}`         | admin       | Suppression définitive                                     |
| GET     | `/admin/settings`            | admin       | Liste les `app_settings` (key/value + description)         |
| PATCH   | `/admin/settings/{key}`      | admin       | Met à jour une setting (whitelist + validation par clé)    |
| GET     | `/admin/casino/stats`        | admin       | Solde `casino_bank`, PnL coinflip/roulette, RTP observé, derniers rounds/spins |
| GET     | `/casino/coinflip/config`    | user        | min_bet, max_bet, edge_pct, win_multiplier (lus en DB)     |
| POST    | `/casino/coinflip/play`      | user        | Joue 1 partie. Lock → tirage → release si gain             |
| GET     | `/me/coinflip`               | user        | Historique des derniers flips du user                      |
| GET     | `/casino/roulette/config`    | user        | min_bet, max_bet, house_edge_pct (2.70%, mécanique)        |
| POST    | `/casino/roulette/spin`      | user        | Joue 1 spin avec N mises agrégées                          |
| GET     | `/me/roulette`               | user        | Historique des derniers spins du user                      |

Doc auto-générée OpenAPI : `http://localhost:8000/docs`.

### Authentification

Deux types de tokens JWT, deux durées :
- **User** : 7 jours, claim `sub: <username>`
- **Admin** : 24 heures, claim `sub: "admin"` + `role: "admin"`

Les deux utilisent `JWT_SECRET` et l'algo HS256.

---

## Frontend

### Stack

- **Vue 3** (Composition API, `<script setup>`)
- **Vite 6** (dev server + bundler, alias `@` = `./src`)
- **Vue Router 4** (lazy loading par route)
- **Pinia** (state management)
- Single-file components, scoped CSS, pas de framework UI externe
- Responsive (mobile-first), tout marche jusqu'à 360px

### Organisation

```
frontend/src/
├── App.vue                      # shell minimal (juste router-view)
├── main.js                      # init Pinia + router + CSS global
├── config.js                    # ⭐ taux EUR↔CAMP, handles paiement, chain, token
│
├── api/
│   ├── client.js                # wrapper fetch avec auto-injection Bearer + handle 401 global
│   ├── bets.js                  # REST wrappers paris (user + admin)
│   └── casino.js                # REST wrappers coinflip + roulette + adminSettings
│
├── router/
│   └── index.js                 # routes + guard (needsUser / needsAdmin / guest)
│
├── stores/
│   ├── auth.js                  # userToken + adminToken, persistés localStorage
│   ├── wallet.js                # me, users, history (refresh centralisé)
│   ├── orders.js                # orders admin (partagé entre AdminView et AdminOrdersView pour le compteur pending)
│   ├── bets.js                  # state + actions paris (open/mine/detail + create/match/cancel/resolve/vote)
│   └── casino.js                # config + history + actions coinflip + roulette (lock/play/spin)
│
├── assets/styles/
│   └── main.css                 # variables CSS, primitives (boutons, inputs, alerts), grain noise en background
│
├── components/
│   ├── layout/
│   │   ├── AppLayout.vue        # shell user : TopBar + Ticker + TabNav
│   │   ├── TopBar.vue           # logo + balance pill + ProfileMenu
│   │   ├── ProfileMenu.vue      # dropdown profil (Mon profil, MetaMask, Acheter/Vendre, Mes demandes, Logout)
│   │   ├── Ticker.vue           # ticker scrollant infini (private jokes + market data)
│   │   └── TabNav.vue           # onglets Wallet/Paris/Casino/Lait
│   ├── wallet/
│   │   ├── BalanceCard.vue      # gros solde CAMP + EUR + conversions (baguettes/bières/raclettes)
│   │   ├── SendForm.vue
│   │   └── HistoryList.vue
│   └── admin/
│       ├── AdminTopBar.vue      # nav admin avec badge nombre de demandes pending
│       ├── TreasuryBox.vue      # treasury + CAMP en circulation + valeurs EUR
│       ├── CreateUserForm.vue   # création user avec email
│       └── UsersTable.vue       # table + modal credit/debit + modal delete (avec confirmation par typage)
│
└── views/
    ├── LoginView.vue            # avec coin 3D low-poly animé en background
    ├── WalletView.vue           # vue principale
    ├── CasinoView.vue           # hub casino : tuiles cliquables (coinflip + roulette jouables)
    ├── MilkView.vue             # placeholder Bourse du Lait (chart SVG)
    ├── ProfileView.vue          # email + mot de passe
    ├── SelfCustodyView.vue      # export clé + ajout MetaMask via wallet_addEthereumChain / watchAsset
    ├── BuyCampView.vue          # création de demandes achat/vente
    ├── OrdersView.vue           # historique des demandes du user
    ├── paris/
    │   ├── ParisListView.vue
    │   ├── ParisCreateView.vue
    │   └── ParisDetailView.vue
    ├── casino/
    │   ├── CoinflipView.vue     # pile/face + roue 3D CSS + provably fair
    │   └── RouletteView.vue     # tapis HTML/CSS + roue qui décélère sur le bon n°
    └── admin/
        ├── AdminLoginView.vue
        ├── AdminView.vue            # treasury + users + bandeau "demandes en attente"
        ├── AdminOrdersView.vue      # filtres + modal "Confirmer et transférer" → tx on-chain auto
        ├── AdminBetsView.vue        # liste + filtres + force-resolve/cancel
        └── AdminCasinoView.vue      # éditeur des app_settings (edge, limites) + PnL + RTP
```

### `config.js` — point central des paramètres

Toutes les constantes métier sont là pour ne pas avoir à chercher :

```js
export const RATES = {
  campPerEur: 100,    // 1 € = 100 CAMP
  feePctBuy: 5        // frais 5 % à l'ACHAT uniquement, vente sans frais
}

export const PAYMENT = {
  recipient: 'Hugo Philipp',
  wero: '+33 7 77 93 22 15',
  revolut: '@hugo1weu7'
}

export const CHAIN = { /* Base Sepolia */ }
export const TOKEN = { address: VITE_CONTRACT_ADDRESS, ... }
```

Helpers `campToEur(camp)`, `eurToCampNet(eur)`, `formatEur(n)`, `formatNum(n)` sont aussi exportés depuis ce fichier.

**Important** : le solde affiché à l'utilisateur (`X CAMP · Y €`) utilise `campToEur` (sans frais), parce que c'est la valeur de revente. Les frais 5 % ne s'appliquent qu'à l'achat. C'est cohérent : ce qu'on voit affiché est ce qu'on récupère si on vend.

### Router & guards

Trois flags de meta-route :
- `guest: 'user'` ou `'admin'` : routes login (`/login`, `/admin/login`)
- `needsUser: true` : routes user authentifié
- `needsAdmin: true` : routes admin authentifié

Le `beforeEach` :
1. Route protégée + pas de token → redirect vers login correspondant avec `?redirect=<url>`
2. Route login + token déjà présent → bypass vers dashboard (`/wallet` ou `/admin`)

Après login, la query `?redirect` est lue pour retourner sur la page initialement demandée.

### Gestion 401 globale

Dans `api/client.js`, toute réponse HTTP 401 déclenche :
1. Détection user vs admin (en comparant le token utilisé avec ceux du store auth)
2. Logout de la session concernée
3. Push vers le login correspondant avec `?redirect=<page courante>`

Donc pas besoin de gérer le 401 dans chaque store/vue.

---

## Module Paris (P2P bets)

Système de paris pair-à-pair sur une affirmation textuelle, avec deadline et résolution. Conserve le pattern custodial : aucun user ne signe quoi que ce soit, la treasury signe tous les mouvements via `adminTransfer`.

### Cycle de vie d'un pari

```
[creator] POST /bets
   │  (lock stake_creator → bets_escrow)
   ▼
 open ──[creator DELETE]──→ cancelled  (refund creator)
   │
   │ [opponent POST /bets/{id}/match]
   │  (lock stake_opponent → bets_escrow)
   ▼
 matched ──→ resolved
   ├── 1. Accord à deux : creator + opponent votent (POST /bets/{id}/vote)
   │       Quand les votes coïncident → settlement auto,
   │       resolved_by = '__both_players__'
   ├── 2. Arbitre désigné : POST /bets/{id}/resolve par arbiter_username
   └── 3. Admin override : POST /admin/bets/{id}/resolve (résout sans
          contrainte d'arbitre, sert quand pas d'arbitre / désaccord
          des votants), resolved_by = '__admin__'

  → resolved : payout au gagnant (pot - arbiter_fee) + arbiter_fee si arbitre
  → resolution = 'void' : refund intégral des deux côtés
```

L'ordre de priorité dans la UI : si tu es arbitre, la vue détail t'affiche le panneau "trancher" ; sinon (creator ou opponent), le panneau "voter pour valider l'issue".

### Comptes système

Les paris introduisent une notion de **compte système** dans `users` :
- Nouvelle colonne `account_type VARCHAR(16) NOT NULL DEFAULT 'user'` (`'user'` | `'system'`)
- Nouvelle colonne `system_role VARCHAR(64)` (ex: `'bets_escrow'`)
- `password_hash` et `email` deviennent nullable (les comptes système n'en ont pas)
- `/users` filtre `account_type = 'user'` pour ne pas exposer `bets_escrow` dans le dropdown arbitre

La treasury, elle, reste en `.env` (pas dans `users`). Seuls les autres comptes système (`bets_escrow`, etc.) vont en DB. Création via `python scripts/seed_system_accounts.py` (génère wallet + chiffre la clé privée + insère la ligne).

### Service `escrow`

`backend/services/escrow.py` expose deux primitives réutilisables (pour les futurs modules casino/lait) :

- `escrow.lock(db, user, role, amount, note)` : user → compte système. Vérifie le solde, appelle `admin_transfer`, journalise dans `transactions` (`from_username = user`, `to_username = '__<role>__'`).
- `escrow.release(db, role, user, amount, note)` : compte système → user. Vérifie le solde du compte système, appelle `admin_transfer`, journalise.

`EscrowError` est la classe d'exception métier ; les routers la convertissent en 400.

**Pattern atomique** (à conserver pour les futurs modules) : la tx on-chain (`lock`/`release`) se fait *avant* tout changement de statut DB. Sur échec, la route fait `db.rollback()` et le pari reste dans son état précédent.

### Schéma DB — `bets`

Voir `backend/scripts/migrate_v4_extensions.py` (table) et `migrate_v5_bet_votes.py` (colonnes de vote). Champs clés :
- `creator_username`, `opponent_username`, `arbiter_username` : 3 rôles, opponent et arbiter NULL tant que pas matché
- `stake_creator`, `stake_opponent` : dérivés de la cote `odds_num / odds_den`. Validation : `(stake_creator * odds_den) % odds_num == 0` pour éviter les mises fractionnaires.
- `creator_side` : `'yes'` | `'no'`
- `status` : `'open'` | `'matched'` | `'resolved'` | `'cancelled'` | `'expired'`
- `resolution`, `resolved_at`, `resolved_by` : remplis au settlement
- `creator_vote`, `opponent_vote` : pour la résolution amiable à deux
- 4 colonnes `tx_hash_*` pour tracer les 4 mouvements possibles (lock creator, lock opponent, payout winner, payout arbiter)

### Endpoints

| Méthode | Route                          | Auth   | Description                                                |
|---------|--------------------------------|--------|------------------------------------------------------------|
| POST    | `/bets`                        | user   | Créer un pari (lock fonds creator)                         |
| GET     | `/bets?status=...&category=`   | user   | Liste filtrable                                            |
| GET     | `/bets/{id}`                   | user   | Détail                                                     |
| POST    | `/bets/{id}/match`             | user   | Prendre le pari (lock fonds opponent)                      |
| DELETE  | `/bets/{id}`                   | user   | Annuler (creator only, status open uniquement)             |
| POST    | `/bets/{id}/vote`              | user   | Voter sur l'issue (creator/opponent). Accord → settlement  |
| POST    | `/bets/{id}/resolve`           | user   | Résolution arbitre (arbiter_username uniquement)           |
| GET     | `/me/bets`                     | user   | Tous mes paris (avec champ `my_role`)                      |
| GET     | `/admin/bets?status=...`       | admin  | Liste admin (tous statuts)                                 |
| POST    | `/admin/bets/{id}/resolve`     | admin  | Force-resolve (sans contrainte arbitre)                    |
| POST    | `/admin/bets/{id}/cancel`      | admin  | Force-cancel (refund creator + opponent si matched)        |
| DELETE  | `/admin/bets/{id}`             | admin  | Suppression DB (refusé si `matched` / `resolved`)          |

### Concurrence

Match, cancel, resolve, vote font `SELECT ... FOR UPDATE` sur la ligne `bets` : si deux users matchent en même temps, le second voit `status != 'open'` et reçoit une erreur claire.

### Notifications

Best-effort, via `BackgroundTasks` :
- Création avec arbitre désigné → email à l'arbitre
- Match → email au creator
- Résolution (arbitre, admin, ou accord) → email aux deux parties

### À faire (non bloquant pour v1)

- Cron 10 min : refund auto des paris `open` dont la deadline est passée → `expired`
- Cron 6h : alerte admin sur les paris `matched` dont la deadline + 24h est dépassée sans résolution

Tant que ces crons n'existent pas, l'admin peut faire `POST /admin/bets/{id}/cancel` à la main.

### Front

- `frontend/src/views/paris/{ParisListView, ParisCreateView, ParisDetailView}.vue`
- `frontend/src/stores/bets.js` (Pinia, expose `fetchOpen`, `fetchMine`, `fetchDetail`, `create`, `match`, `cancel`, `resolve`, `vote`)
- `frontend/src/api/bets.js` (wrapper REST)
- `frontend/src/config.js` → `BETS = { minStake, maxStake, maxOpenBetsPerUser, arbiterDefaultFeePct }` (à garder en sync avec `backend/config.py::BETS`)

Le username courant pour les vérifications de rôle (`isCreator`, `isOpponent`, `isArbiter`) se lit dans `wallet.me.username` — pas dans `auth` (qui n'expose que les tokens).

---

## Module Casino (coinflip + roulette)

Deux jeux "joueur vs banque" qui réutilisent les mêmes primitives : escrow vers le compte système `casino_bank`, RNG vérifiable commit-reveal, payouts on-chain agrégés en 1 release par partie.

### Patterns partagés

**Banque casino**. Compte système (`account_type='system'`, `system_role='casino_bank'`) créé par `seed_system_accounts.py`. Reçoit toutes les mises et paie tous les gains. À capitaliser depuis le backoffice (~10× la mise max recommandé pour absorber la variance).

**RNG vérifiable** (`services/randomness.py`). Pour chaque tirage :
1. `commit(db, purpose)` → publie `sha256(secret)` (le `seed_hash`), garde `secret` côté serveur.
2. `reveal(db, seed_id, client_seed)` → marque revealed et calcule `combined_hash = sha256(server_seed + ":" + client_seed)`. Le `client_seed` est généré côté front (crypto.getRandomValues) pour que le user puisse contribuer à l'aléa.
3. `derive_int(combined_hash, modulo)` → tire l'outcome (modulo 2 pour coinflip, modulo 37 pour roulette).

Commit + reveal se font dans la même requête HTTP (le user ne voit pas le hash *avant* de miser), mais le hash + le secret restent en DB pour vérification a posteriori — `sha256(server_seed)` doit matcher `seed_hash` annoncé.

**Paramètres tweakables à chaud**. Les limites de mise et l'edge du coinflip vivent dans la table `app_settings` (cf. §DB), pas dans `config.py`. L'admin peut les modifier depuis `/admin/casino` sans redéploiement : `services.settings.get_int/get_float` les relit à chaque play, pas de cache. Whitelist des clés autorisées dans `services/settings.py::WRITABLE_KEYS`, validation par-clé dans `routers/admin.py::admin_update_setting` (bornes, types, cohérence min≤max).

**Pattern atomique** (identique à l'escrow paris) :
1. Commit RNG (flush DB, pas de commit).
2. `escrow.lock(user → casino_bank, total_bet)` — tx on-chain ; sur échec, rollback session.
3. Reveal + calcul de l'outcome + payout théorique.
4. Si gain : `escrow.release(casino_bank → user, payout)`. Si la release échoue alors que le lock a réussi (banque casino vidée par exemple), on **raise sans rollback** : la mise est bloquée côté casino, le user gagne mais ne reçoit rien → l'admin règle à la main. Pas de "tx ghost".
5. Persiste la round + lie le seed à son id (`ref_id`).
6. Commit final.

### Coinflip (`services/coinflip.py`)

- Mise + choix `heads`/`tails` + `client_seed` → POST `/casino/coinflip/play`.
- `outcome = 'heads' if derive_int(combined, 2) == 0 else 'tails'`.
- Payout gagnant = `int(bet × 2 × (1 - edge_pct/100))`. Avec edge=2% → 1.96× ; edge=5% → 1.90× ; edge=0% → 2.00×.
- Edge clamp `[0, 50[` au moment du play (garde-fou même si l'admin entre une valeur folle).
- Table : `coinflip_rounds`. Réponse : `PlayResult` (id, outcome, win, payout, seed_hash, server_seed, combined_hash, tx_hash_lock, tx_hash_payout, new_balance).

### Roulette (`services/roulette.py`)

- N mises agrégées en un spin → POST `/casino/roulette/spin`. Body : `{ bets: [{spot, amount}, …], client_seed }`. Max 50 spots par spin.
- Spots supportés en V1 :
  - Numéro plein : `"n=0"` … `"n=36"` — payout 35:1 (mise × 36).
  - Couleur : `"red"` / `"black"` — 1:1 (×2). 0 = vert, ne paye ni rouge ni noir.
  - Pair / Impair : `"even"` / `"odd"` — 1:1 ; 0 ne paye ni l'un ni l'autre.
  - Manque / Passe : `"low"` (1-18) / `"high"` (19-36) — 1:1 ; 0 ne paye rien.
  - Douzaines : `"dozen=1"` / `"dozen=2"` / `"dozen=3"` — 2:1 (×3).
  - Colonnes : `"col=1"` / `"col=2"` / `"col=3"` — 2:1 (×3).
- `outcome = derive_int(combined, 37)` (0-36). Couleur dérivée de l'ensemble standard `RED_NUMBERS`.
- **Edge non configurable** : mécanique 1/37 ≈ 2.70% sur tous les spots — payout numéro plein 35:1 vs proba 1/37, etc. Seules les limites de mise totale (somme des spots) sont tweakables.
- **1 lock unique + 1 payout net unique** : pour éviter N tx on-chain pour N spots, on agrège. `total_bet = sum(amount)` → 1 `escrow.lock`. `total_payout = sum(evaluate_bet(b, outcome))` → 1 `escrow.release` (skip si 0).
- Table : `roulette_spins`. `bets_json` stocke la liste pour audit a posteriori. `winning_spots` est calculé à la résolution et renvoyé au front pour le glow doré.

### Front (`views/casino/`)

- `CoinflipView.vue` : pièce 3D CSS qui tourne, choix Pile/Face avec jetons codés couleur, panneau "Vérifier le tirage" qui affiche seed_hash/server_seed/combined_hash/formule.
- `RouletteView.vue` : tapis HTML/CSS (12 colonnes × 3 rangées + 2:1 en bout + dozens + outside), roue européenne SVG-like CSS qui décélère sur 7s en cubic-bezier `(0.04, 0.86, 0.12, 1)` (forward-only, calcul du delta sur la position actuelle). Après l'arrêt : reveal du panneau gain/perte + glow doré 3s sur les cases gagnantes, puis clear automatique du tapis.
- `stores/casino.js` : Pinia avec deux blocs distincts (coinflip + roulette), `loadConfig` au montage + `loadHistory`, action `play`/`rouletteSpin` qui rafraîchit le wallet après settle.

### Admin (`views/admin/AdminCasinoView.vue`)

- **Settings éditables** : `coinflip_edge_pct`, `coinflip_min_bet`, `coinflip_max_bet`, `roulette_min_bet`, `roulette_max_bet`. Sauvegarde par champ (bouton "Sauver" actif uniquement si la valeur a changé). Validation backend + preview live du nouveau multiplicateur côté coinflip.
- **Stats temps réel** : solde `casino_bank`, PnL coinflip et roulette séparément (`volume_bet - volume_payout`), RTP observé vs attendu (`100 - edge_configured` pour coinflip, `100 - edge_mechanical` pour roulette), 20 derniers rounds / spins.

### Concurrence

Pas de `SELECT FOR UPDATE` nécessaire — chaque round/spin est indépendant et créé en une seule transaction. Les éventuels conflits de nonce treasury entre deux plays parallèles sont déjà gérés par `blockchain.py::_next_treasury_nonce()` (verrou pessimiste sur la ligne nonce).

---

## Sécurité & secrets

### Variables sensibles (`.env`)

Backend :
- `MASTER_KEY` : clé Fernet, chiffre les clés privées en DB. **Si perdue, plus aucune clé privée n'est récupérable**.
- `JWT_SECRET` : signe les JWT user et admin. Si compromise, les tokens existants restent valides jusqu'à expiration.
- `TREASURY_PRIVATE_KEY` : clé privée du wallet owner. Si compromise = contrôle total du contrat sur Base Sepolia (= 0 € de risque, c'est du testnet). Mainnet = catastrophe.
- `ADMIN_PASSWORD` : pour le login admin.
- `SMTP_PASSWORD` : Gmail App Password.
- `DATABASE_URL` : contient le password Postgres.

Frontend :
- `VITE_CONTRACT_ADDRESS` : adresse publique du contrat, pas un secret.
- `VITE_API_URL` : URL publique du backend.

### Génération des secrets

```bash
openssl rand -hex 32      # JWT_SECRET (32 bytes hex)
openssl rand -hex 16      # ADMIN_PASSWORD ou autre

# MASTER_KEY : voir setup_users.py qui génère une Fernet key proprement
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Limites assumées du modèle custodial

1. **L'owner peut bouger n'importe quel solde** via `adminTransfer`. C'est volontaire (pour les achats/ventes admin), mais c'est aussi une faille si la clé est compromise.
2. **La clé privée du user reste chiffrée en base** même quand il ne s'en sert pas. Si la DB fuit + `MASTER_KEY` fuit, tous les wallets sont compromis.
3. **Pas de 2FA** ni rate limiting côté auth.

Tout ça est acceptable pour un produit entre potes sur testnet. Liste des mitigations à prévoir pour passer en mainnet dans le README.

---

## Déploiement

### Scripts

- `scripts/push_images.sh` : build & push les images Docker (back + front) vers Scaleway Container Registry. Charge `.env` racine pour récupérer `BACKEND_URL` et `CONTRACT_ADDRESS`.
- `scripts/redeploy.sh` : trigger un redéploiement des containers Scaleway.

### `.env` racine attendu

```bash
# Pour les scripts de build
BACKEND_URL=https://camplongcoin-back.example.com
CONTRACT_ADDRESS=0xAbC123...
SCW_SECRET_KEY=...   # pour docker login Scaleway
```

### Frontend Docker

Build multi-stage :
1. `node:20-alpine` → `npm ci` → `npm run build` (avec `ARG VITE_API_URL` et `ARG VITE_CONTRACT_ADDRESS`)
2. `nginx:alpine` → sert le dist statique avec `try_files $uri $uri/ /index.html` pour le routing SPA

Le port nginx s'adapte à `$PORT` au démarrage (utile pour Scaleway Serverless Containers).

### Backend Docker

Image Python classique, `uvicorn main:app --host 0.0.0.0 --port $PORT`.

---

## Conventions & gotchas

### CAMP vs wei

L'API et la DB stockent les montants **en CAMP entiers** (pas en wei). La conversion ×10^18 se fait uniquement dans `blockchain.py` au moment de construire/lire les tx. Donc dans tout le reste du code, raisonner en CAMP.

### Adresses

Toujours en format hex `0x...` 42 caractères. Pour les afficher tronqués dans l'UI : `0x1234…abcd`.

### Tx hashes

Format `0x...` 66 caractères. Liens BaseScan : `https://sepolia.basescan.org/tx/<hash>`.

### Schema test vs prod

- `DB_SCHEMA=test` par défaut. Toujours bien vérifier en prod que c'est `prod`.
- Les deux schémas ont les mêmes tables, code identique.
- Pour appliquer une migration aux deux : lancer le script avec `DB_SCHEMA=test` puis `DB_SCHEMA=prod`.

### Logs admin dans `transactions`

Les opérations admin (credit/debit, onboarding, achat/vente confirmés) créent des lignes dans `transactions` avec `from_username` ou `to_username = "__treasury__"`. Donc l'historique d'un user inclut ses transferts ET ses interactions avec l'admin.

### Erreurs SMTP

L'envoi d'email est **best-effort** : si SMTP n'est pas configuré ou échoue, on log mais on ne raise pas. Une demande peut être créée et traitée sans aucun email — c'est dégradé mais ça ne casse pas l'app. Tous les détails restent visibles dans le backoffice.

### Treasury gas

Sur Base Sepolia, faucet gratuit, illimité en pratique. Sur mainnet, prévoir un refund périodique. Le backoffice affiche le solde ETH de la treasury avec un warning si < 0.01 ETH.

### Pourquoi pas d'allowance ERC-20 classique ?

Le flow standard ERC-20 pour qu'Alice envoie 50 CAMP à Bob serait :
1. Alice appelle `approve(spender, 50)` (signée par Alice, paie le gas)
2. Spender appelle `transferFrom(Alice, Bob, 50)`

Ici on veut zéro friction côté user, donc on a fait un raccourci : `adminTransfer(from, to, amount)` réservé à l'owner, qui appelle directement l'internal `_transfer`. Pas d'approve, pas de signature user, pas de gas user.

### `user` dans le menu admin

Quand l'admin navigue dans `/admin/*`, le store wallet n'est PAS chargé (parce que c'est lié à la session user). Si l'admin n'a pas aussi un compte user, le `wallet.me` est vide, ce qui est attendu.
