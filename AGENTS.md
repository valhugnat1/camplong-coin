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
7. [Module Casino (coinflip + roulette + slots)](#module-casino-coinflip--roulette--slots)
8. [Module Bourse du Lait (AMM)](#module-bourse-du-lait-amm)
9. [Sécurité & secrets](#securite--secrets)
10. [Déploiement](#deploiement)
11. [Conventions & gotchas](#conventions--gotchas)

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
│                      ├── bet_options         (cf. § Module Paris)
│                      ├── bet_participations  (cf. § Module Paris)
│                      ├── bet_votes           (cf. § Module Paris)
│                      ├── app_settings        (clés/valeurs admin-tweakables)
│                      ├── rng_seeds           (commit-reveal provably fair)
│                      ├── coinflip_rounds     (cf. § Module Casino)
│                      ├── roulette_spins      (cf. § Module Casino)
│                      ├── slots_spins         (cf. § Module Casino)
│                      ├── milk_pools             (cf. § Module Bourse du Lait)
│                      ├── milk_positions         (cf. § Module Bourse du Lait)
│                      ├── milk_trades            (cf. § Module Bourse du Lait)
│                      ├── milk_chaos_events      (cf. § Module Bourse du Lait)
│                      └── milk_chaos_templates   (cf. § Module Bourse du Lait)
└── schema: prod       (mêmes tables)
```

Les tables `poker_*` existent (préparées par `migrate_v4_extensions.py`) mais ne sont pas encore exploitées (cf. `EXTENSIONS.md`).

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

**`slots_spins`** — historique des spins de machine à sous (3 rouleaux, single payline, paye sur 3-of-a-kind uniquement). `reels` = `"🍒|🍋|🍒"` (3 symboles séparés par `|`), `combo` = `"3xcherry"` ou `"no_match"`, `multiplier` = 0 si perdu sinon ×4/×14/×50/×100/×250 selon le symbole. RTP théorique ≈ 90.2 %, edge mécanique ≈ 9.8 % (baked dans les poids + payouts hardcoded). Pas d'edge_pct configurable.

Voir § *Module Casino* pour le détail des flows.

### Migrations

`scripts/init_db.py` crée les tables au premier setup. Migrations successives (idempotentes, multi-schémas) :
- `migrate_v4_extensions.py` : tables paris (v1) + casino + poker + milk + `rng_seeds` + colonnes `account_type` / `system_role` sur users.
- `migrate_v5_bet_votes.py` : colonnes `creator_vote` / `opponent_vote` sur `bets` v1 (obsolète après v8).
- `migrate_v6_app_settings.py` : table `app_settings` + seed des paramètres casino par défaut (`coinflip_edge_pct=2`, `coinflip_min_bet=1`, `coinflip_max_bet=200`, `roulette_min_bet=1`, `roulette_max_bet=200`).
- `migrate_v7_slots.py` : table `slots_spins` + seed `slots_min_bet=1`, `slots_max_bet=100`.
- `migrate_v8_bets_v2.py` : **refonte complète des paris**. DROP de l'ancienne table `bets` (les paris non résolus doivent être refundés manuellement AVANT, le script les liste). Recrée `bets` avec son nouveau schéma + crée `bet_options`, `bet_participations`, `bet_votes`. Voir § *Module Paris*.
- `migrate_v9_milk_chaos_templates.py` : table `milk_chaos_templates` + seed de ~33 templates (famine_mild, overstock_massive, gerard_depardieu, etc.) + seed des `app_settings` pour le bot chaos (`milk_chaos_tick_seconds=900`, `milk_chaos_proba_pct=25`, `milk_chaos_max_volatility_pct=20`).

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
│                        # AppSetting, RngSeed,
│                        # CoinflipRound, RouletteSpin, SlotsSpin,
│                        # MilkPool, MilkPosition, MilkTrade,
│                        # MilkChaosEvent, MilkChaosTemplate
├── schemas.py           # tous les Pydantic In/Out
├── security.py          # JWT decode, deps current_user / require_admin, Fernet
├── blockchain.py        # web3 init, helpers admin_transfer / balanceOf / nonce
├── email_service.py     # SMTP best-effort (orders + bets notifs)
├── services/
│   ├── escrow.py        # lock/release vers comptes système (paris, casino, lait, …)
│   ├── settings.py      # lecture/écriture des app_settings, defaults de secours
│   ├── randomness.py    # commit-reveal (sha256) + derive_int
│   ├── coinflip.py      # play() : lock → tirage → release si gain
│   ├── roulette.py      # spin() : N mises agrégées → 1 lock + 1 payout net
│   ├── slots.py         # spin() : 3 picks pondérés indépendants → release si 3-of-kind
│   ├── amm.py           # x·y=k : current_price, buy_quote, sell_quote
│   └── milk.py          # quote, swap (lock/release), pick_template,
│                        # apply_chaos, clamp_to_volatility,
│                        # chaos_analysis, position_dict, ...
├── routers/
│   ├── users.py         # /login, /me, /transfer, /history, /orders, /me/*
│   ├── admin.py         # /admin/login, /admin/users, /admin/credit|debit,
│   │                    # /admin/orders, /admin/bets/*,
│   │                    # /admin/settings/*, /admin/casino/stats,
│   │                    # /admin/milk/* (pools, templates, chaos analysis)
│   ├── bets.py          # /bets/*, /me/bets, vote/match/cancel/resolve
│   ├── casino.py        # /casino/{coinflip,roulette,slots}/*,
│   │                    # /me/{coinflip,roulette,slots}
│   └── milk.py          # /milk/pools/*, /me/milk/*
└── scripts/
    ├── migrate_v4_extensions.py   # tables paris/casino/lait + comptes système
    ├── migrate_v5_bet_votes.py    # colonnes creator_vote / opponent_vote
    ├── migrate_v6_app_settings.py # table app_settings + seed casino defaults
    ├── migrate_v7_slots.py        # table slots_spins + seed slots min/max bet
    ├── migrate_v8_bets_v2.py      # refonte des paris (drop + recrée + tables sous-jacentes)
    ├── migrate_v9_milk_chaos_templates.py  # table milk_chaos_templates + seeds
    └── seed_system_accounts.py    # crée bets_escrow, casino_bank, poker_bank, milk_pool_*
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
| GET     | `/casino/slots/config`       | user        | min_bet, max_bet, rtp_theoretical_pct, paytable             |
| POST    | `/casino/slots/spin`         | user        | Joue 1 spin (3 rouleaux). Lock → tirage → release si 3-of-kind |
| GET     | `/me/slots`                  | user        | Historique des derniers spins slots                        |

Tous les endpoints `GET /me/{coinflip,roulette,slots}` acceptent `?limit=` (défaut 20, max 100). Le front fetch 50 et pagine côté client (10/page).

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
- **qrcode** (^1.5.4) : génération des QR pour la page Échange. Scan via `BarcodeDetector` natif (zéro dep côté lecture).
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
│   ├── casino.js                # REST wrappers coinflip + roulette + adminSettings
│   └── milk.js                  # REST wrappers AMM lait (user + admin pools/templates/analysis)
│
├── router/
│   └── index.js                 # routes + guard (needsUser / needsAdmin / guest)
│
├── stores/
│   ├── auth.js                  # userToken + adminToken, persistés localStorage
│   ├── wallet.js                # me, users, history (refresh centralisé)
│   ├── orders.js                # orders admin (partagé entre AdminView et AdminOrdersView pour le compteur pending)
│   ├── bets.js                  # state + actions paris (open/mine/detail + create/match/cancel/resolve/vote)
│   ├── casino.js                # config + history + actions coinflip + roulette + slots (lock/play/spin)
│   └── milk.js                  # pools, pool courant, chart, trades, chaos, positions, myTrades
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
│   │   └── TabNav.vue           # onglets Wallet/Échange/Paris/Casino/Lait
│   ├── wallet/
│   │   ├── BalanceCard.vue      # gros solde CAMP + EUR + conversions ; adresse on-chain "tap to copy"
│   │   └── HistoryList.vue      # liste paginée (8 tx/page, prev/next)
│   ├── exchange/
│   │   ├── ShowQrLayer.vue      # layer plein écran : QR du handle (encode "camplong:<username>")
│   │   └── ScanQrLayer.vue      # layer plein écran : caméra → scan QR → saisie montant → POST /transfer
│   └── admin/
│       ├── AdminTopBar.vue      # nav admin avec badge nombre de demandes pending
│       ├── TreasuryBox.vue      # treasury + CAMP en circulation + valeurs EUR
│       ├── CreateUserForm.vue   # création user avec email
│       └── UsersTable.vue       # table + modal credit/debit + modal delete (avec confirmation par typage)
│
└── views/
    ├── LoginView.vue            # avec coin 3D low-poly animé en background
    ├── WalletView.vue           # solde + plan en 6 étapes + CTA "Envoyer des CAMP" → /exchange + historique paginé
    ├── ExchangeView.vue         # Recevoir (handle + QR) | Envoyer (scan QR ou pote + montant + note)
    ├── CasinoView.vue           # hub casino : tuiles cliquables (coinflip + roulette + slots)
    ├── MilkView.vue             # hub Bourse du Lait : grid pools + sparkline + prix
    ├── ProfileView.vue          # email + mot de passe
    ├── SelfCustodyView.vue      # export clé + ajout MetaMask via wallet_addEthereumChain / watchAsset
    ├── BuyCampView.vue          # création de demandes achat/vente
    ├── OrdersView.vue           # historique des demandes du user
    ├── paris/
    │   ├── ParisListView.vue
    │   ├── ParisCreateView.vue
    │   └── ParisDetailView.vue
    ├── casino/
    │   ├── CoinflipView.vue     # pile/face + pièce 3D CSS + provably fair
    │   ├── RouletteView.vue     # tapis HTML/CSS + roue qui décélère sur le bon n°
    │   └── SlotsView.vue        # 3 rouleaux (Web Animations API), 3 lignes visibles
    ├── lait/
    │   └── MilkTradeView.vue    # chart SVG + swap card + position réalisable + tape trades/chaos
    └── admin/
        ├── AdminLoginView.vue
        ├── AdminView.vue            # treasury + users + bandeau "demandes en attente"
        ├── AdminOrdersView.vue      # filtres + modal "Confirmer et transférer" → tx on-chain auto
        ├── AdminBetsView.vue        # liste + filtres + force-resolve/cancel
        ├── AdminCasinoView.vue      # éditeur des app_settings (edge, limites) + PnL + RTP
        └── AdminMilkView.vue        # pools + bot chaos freq + analyse banque + templates + historique chaos
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

## Module Paris (communautaires)

Système de paris communautaires sur une affirmation textuelle, avec deadline et résolution. Conserve le pattern custodial : aucun user ne signe quoi que ce soit, la treasury signe tous les mouvements via `adminTransfer`.

**Refonte (mai 2026)** : l'ancien modèle 1v1 (creator/opponent + cote `odds_num:odds_den` + side yes/no) a été abandonné. Le nouveau modèle :

- **Mise unique fixe** définie par le créateur (`bet.stake`). Tout participant pose exactement ce montant pour rejoindre.
- **2 à 6 options** par pari : soit `type='yes_no'` (Oui/Non auto-créés), soit `type='multi_choice'` (libellés custom).
- **Le créateur peut participer ou non**. S'il participe, c'est juste comme n'importe quel autre participant — il bloque sa mise en même temps que la création.
- **N participants par option**, 1 mise max par user par pari (UNIQUE(bet_id, username) sur `bet_participations`).
- **Résolution** : (a) arbitre désigné, (b) 2 votes communautaires concordants (n'importe quel user, 1 vote/pari, modifiable), ou (c) admin override.
- **Payout** : pot total réparti à parts égales entre les participants de l'option gagnante (`floor(pot / nb_gagnants)`, le reste de division reste dans `bets_escrow` — négligeable, c'est de la poussière).
- **Solo bet** : si une seule option a des participants au moment de la résolution, le pari est forcé en `void` (refund de tous). Personne ne "gagne tout seul".

### Cycle de vie d'un pari

```
[creator] POST /bets
   │  (si creator participe : lock stake → bets_escrow,
   │   row inseree dans bet_participations)
   ▼
 open ──[creator DELETE]──→ cancelled
   │      (refund de tous les participants, status=cancelled, void=true)
   │
   │ [anyone POST /bets/{id}/join {option_id}]
   │  (lock stake → bets_escrow, row dans bet_participations)
   ▼
 open + N participants ──→ resolved via :
   ├── 1. Arbitre :         POST /bets/{id}/resolve {option_id}
   │                         par arbiter_username (option_id=null → void)
   ├── 2. Communauté :      POST /bets/{id}/vote {option_id} par
   │                         n'importe quel user ; quand 2 votes pointent
   │                         vers la même option_id (ou tous les 2 vers
   │                         null=void) → settlement auto,
   │                         resolved_by='__community__'
   └── 3. Admin override :  POST /admin/bets/{bet_id}/resolve {option_id}
                             (sans contrainte arbitre), resolved_by='__admin__'

  → resolved : payout = floor(pot_total / nb_winners) pour chaque
                participant de l'option gagnante.
  → resolution_void = true : refund intégral de tous les participants.
```

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

### Schéma DB (tables paris)

Quatre tables, créées par `backend/scripts/migrate_v8_bets_v2.py` (qui DROP l'ancienne table `bets` avant recreate).

**`bets`** — métadonnées du pari :
- `id`, `creator_username`, `statement`, `deadline`
- `type` : `'yes_no'` | `'multi_choice'`
- `stake` (BIGINT) : mise unique fixe pour tous les participants
- `arbiter_username` (nullable)
- `status` : `'open'` | `'resolved'` | `'cancelled'` | `'expired'`
- `resolution_option_id` (FK `bet_options.id`, NULL si void ou pas encore résolu)
- `resolution_void` (BOOLEAN) : true si résolu en void (refund tous)
- `resolved_at`, `resolved_by` (sentinels possibles : `__community__`, `__admin__`, `__expired__`, ou un username)
- `created_at`

**`bet_options`** — 2 à 6 options par pari :
- `id`, `bet_id` (FK `bets.id` ON DELETE CASCADE), `label`, `position`

**`bet_participations`** — qui a misé quoi sur quelle option :
- `id`, `bet_id`, `option_id`, `username`, `amount`
- `tx_hash_lock` (lock du stake), `tx_hash_payout` (payout / refund)
- `joined_at`
- UNIQUE `(bet_id, username)` : un user n'a qu'une participation par pari

**`bet_votes`** — votes communautaires pour la résolution :
- `id`, `bet_id`, `voter_username`, `option_id` (NULL = vote pour `void`)
- `voted_at`
- UNIQUE `(bet_id, voter_username)` : un user n'a qu'un vote (modifiable)

Le payout = `floor(pot_total / nb_winners)`. Le reste de division (< nb_winners CAMP) reste dans `bets_escrow` comme poussière. À nettoyer périodiquement à la main via debit admin si ça s'accumule.

### Endpoints

| Méthode | Route                          | Auth   | Description                                                |
|---------|--------------------------------|--------|------------------------------------------------------------|
| POST    | `/bets`                        | user   | Créer un pari (+ lock du creator s'il participe)           |
| GET     | `/bets?status=...`             | user   | Liste filtrable (avec `my_role` sur chaque ligne)          |
| GET     | `/bets/{id}`                   | user   | Détail (options, participants, votes)                      |
| POST    | `/bets/{id}/join`              | user   | Rejoindre sur une `option_id` (lock du stake)              |
| DELETE  | `/bets/{id}`                   | user   | Annuler (creator only, refund tous si participants)        |
| POST    | `/bets/{id}/vote`              | user   | Vote communautaire `{option_id}` (NULL=void). 2 voix → settle |
| POST    | `/bets/{id}/resolve`           | user   | Résolution arbitre `{option_id}` (NULL=void)               |
| GET     | `/me/bets`                     | user   | Tous mes paris (creator / arbitre / participant)           |
| GET     | `/admin/bets?status=...`       | admin  | Liste admin                                                |
| POST    | `/admin/bets/{id}/resolve`     | admin  | Force-resolve `{option_id}` (NULL=void)                    |
| POST    | `/admin/bets/{id}/cancel`      | admin  | Force-cancel (refund tous les participants)                |
| DELETE  | `/admin/bets/{id}`             | admin  | Suppression DB (refusé si `resolved` ou `open` avec participants) |

### Concurrence

Join, cancel, resolve, vote font `SELECT ... FOR UPDATE` sur la ligne `bets` : si deux users joignent en même temps, ils sont sérialisés et le UNIQUE(bet_id, username) garantit qu'on ne peut pas miser 2 fois.

### Notifications

Best-effort, via `BackgroundTasks` :
- Création avec arbitre désigné → email à l'arbitre
- Quelqu'un rejoint → email au créateur (sauf s'il est le joiner)
- Résolution (arbitre, communauté, admin) → email à tous les participants avec leur résultat individuel

### À faire (non bloquant pour v1)

- Cron 10 min : void auto + refund des paris `open` dont la deadline est passée → `expired`
- Cron 6h : alerte admin sur les paris `open` dont la deadline + 24h est dépassée sans résolution

Tant que ces crons n'existent pas, l'admin peut faire `POST /admin/bets/{id}/cancel` à la main.

### Front

- `frontend/src/views/paris/{ParisListView, ParisCreateView, ParisDetailView}.vue`
- `frontend/src/stores/bets.js` (Pinia, expose `fetchOpen`, `fetchMine`, `fetchDetail`, `create`, `join`, `cancel`, `resolve`, `vote`)
- `frontend/src/api/bets.js` (wrapper REST)
- `frontend/src/config.js` → `BETS = { minStake, maxStake, maxOpenBetsPerUser, minOptions, maxOptions }` (à garder en sync avec `backend/config.py::BETS`)

Le username courant pour les vérifications de rôle (`isCreator`, `isArbiter`, `isParticipant`) se lit dans `wallet.me.username` — pas dans `auth` (qui n'expose que les tokens). Le backend renseigne aussi `my_role`, `my_option_id`, `my_vote_option_id`, `my_has_voted` directement dans les responses.

La vue détail affiche les barres de participation par option (largeur ∝ nombre de participants), et `commit-after-action` n'est pas nécessaire ici (pas d'animation à attendre).

---

## Module Casino (coinflip + roulette + slots)

Trois jeux "joueur vs banque" qui réutilisent les mêmes primitives : escrow vers le compte système `casino_bank`, RNG vérifiable commit-reveal, payouts on-chain agrégés en 1 release par partie.

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

### Slots (`services/slots.py`)

- POST `/casino/slots/spin` : `{ bet, client_seed }` → 3 rouleaux tirés sur le même `combined_hash` avec offsets distincts (`sha256(combined+":i") % TOTAL_WEIGHT` pour i ∈ [0,2]). Paye uniquement sur **3-of-a-kind**.
- Palette (poids / multiplicateur 3-of-a-kind) — hardcodés dans `SYMBOLS` :
  - 🍒 cherry  : w=8, ×4
  - 🍋 lemon   : w=4, ×14
  - 🍊 orange  : w=2, ×50
  - 🔔 bell    : w=1, ×100
  - ⭐ star    : w=1, ×250 (jackpot)
- Total weight = 16. `P(any win) ≈ 14.3 %` (≈ 1 spin sur 7), `RTP ≈ 90.2 %`, edge ≈ 9.8 %. Calculs vérifiables via `slots.theoretical_rtp_pct()`.
- **Edge non configurable** : pour le changer il faut éditer le tableau `SYMBOLS` dans `services/slots.py`. Seuls `slots_min_bet` / `slots_max_bet` sont tweakables à chaud via `app_settings`. ⚠ Attention : un jackpot ⭐⭐⭐ paye ×250 la mise → avec `slots_max_bet=100`, le payout maxi en cas de jackpot = 25 000 CAMP. Capitaliser `casino_bank` en conséquence.
- Table : `slots_spins`. Champ `reels` = `"🍒|🍋|🍒"` (3 emojis sep `|`), `combo` = `"3xcherry"` / `"no_match"`, `multiplier` snapshotté au moment du spin.

### Front (`views/casino/`)

- **`CoinflipView.vue`** : pièce 3D CSS qui tourne, choix Pile/Face avec jetons codés couleur, panneau "Vérifier le tirage" (seed_hash / server_seed / combined_hash / formule). Tailles 100 % dérivées d'une CSS var `--coin-size` (140 / 110 / 92 px selon viewport) — pas de cumul accidentel sur mobile.
- **`RouletteView.vue`** : tapis HTML/CSS (12 colonnes × 3 rangées + 2:1 en bout + dozens + outside), roue européenne CSS qui décélère sur 7 s en cubic-bezier `(0.04, 0.86, 0.12, 1)` (forward-only, calcul du delta sur la position visuelle actuelle). Sur viewport ≤ 520 px le tapis devient **scroll horizontal** (`min-width: 440px` sur la grille + mask fade-out à droite) — sinon les cellules tassent à ~14 px illisibles. Après l'arrêt : reveal du panneau gain/perte + glow doré 3 s sur les cases gagnantes, puis clear automatique du tapis.
- **`SlotsView.vue`** : 3 rouleaux verticaux animés via **Web Animations API** (`el.animate(...)`, *pas* de transition CSS persistante — sinon le 2e spin ne se rejoue pas). Fenêtre 3 lignes (haut / payline / bas), `--slot-h` CSS var qui descend de 72→62→54 px ; le JS mesure `getBoundingClientRect()` au moment du spin pour calculer le `targetTranslate` au pixel exact quel que soit le viewport. Cascade gauche→droite avec arrêts à 1.8 s / 2.6 s / 3.4 s. Glow doré 2.5 s sur les rouleaux si gain.

#### Pattern "commit-after-anim" (anti-spoiler)

Sans précaution, dès qu'on `await casino.{play,spin}()` la TopBar et la liste "derniers spins" se mettent à jour → ça **spoile** le résultat avant la fin de l'animation. Le store expose donc :

- `slotsSpin()` / `rouletteSpin()` : appel API pur, retourne le `result`. **Ne touche pas** à l'historique ni au wallet.
- `commitSlotsResult(result)` / `commitRouletteResult(result)` : helpers à appeler par la vue **après** la fin de l'anim → unshift dans l'historique local + `wallet.refresh()`.

Côté vue, on les appelle dans le `setTimeout` qui révèle le panneau de résultat (slots : ~3.6 s après l'API ; roulette : 7 s). Le coinflip suit la même idée mais inline (anim courte 1.4 s).

À chaque commit on remet aussi `historyPage.value = 1` pour que le nouveau résultat soit visible sans navigation manuelle.

#### Pagination historique

Le store fetch `limit=50` pour chaque historique (`/me/{coinflip,roulette,slots}`). Chaque vue tranche ensuite localement par pages de **10** :

```js
const HISTORY_PAGE_SIZE = 10
const historyPage = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(items.length / HISTORY_PAGE_SIZE)))
const pagedHistory = computed(() => items.slice(
  (historyPage.value - 1) * HISTORY_PAGE_SIZE,
  historyPage.value * HISTORY_PAGE_SIZE,
))
```

Widget Prev/Next 40×40 px (tap-friendly), affiché uniquement si `totalPages > 1`. Si on veut un jour dépasser 50 spins en mémoire, ajouter un param `offset` aux endpoints `/me/{game}` et renvoyer `{items, total}` au lieu de l'array brut.

### Admin (`views/admin/AdminCasinoView.vue`)

- **Settings éditables** : `coinflip_edge_pct`, `coinflip_min_bet`, `coinflip_max_bet`, `roulette_min_bet`, `roulette_max_bet`, `slots_min_bet`, `slots_max_bet`. Sauvegarde par champ (bouton "Sauver" actif uniquement si la valeur a changé). Validation backend + preview live du nouveau multiplicateur côté coinflip. **Pas de knob d'edge pour roulette/slots** (mécanique).
- **Stats temps réel** : solde `casino_bank`, PnL coinflip / roulette / slots séparément (`volume_bet - volume_payout`), RTP observé vs attendu pour chacun (`100 - edge_configured` côté coinflip, `100 - edge_mechanical` côté roulette/slots), 20 derniers rounds / spins par jeu.

### Concurrence

Pas de `SELECT FOR UPDATE` nécessaire — chaque round/spin est indépendant et créé en une seule transaction. Les éventuels conflits de nonce treasury entre deux plays parallèles sont déjà gérés par `blockchain.py::_next_treasury_nonce()` (verrou pessimiste sur la ligne nonce).

---

## Module Bourse du Lait (AMM)

AMM type Uniswap v1 (x · y = k), un pool par "produit" laitier (`LAIT-ENTIER`, et autres à créer côté admin). Les CAMP transitent on-chain via `escrow.lock/release` sur un compte système `milk_pool_<symbol>`. Le lait lui-même n'est PAS un token ERC-20 séparé : c'est un nombre off-chain dans `milk_positions.balance_milk`, indexé en milli-bouteilles (`MILK_UNIT = 1000`, soit 1 btl = 1000 unités internes).

Un **bot dieu (chaos)** tourne en boucle async dans `main.py::_chaos_loop` et modifie aléatoirement `reserve_milk` (jamais `reserve_camp`) selon un catalogue de templates pondérés. Le prix `reserve_camp / reserve_milk` bouge sans qu'aucun CAMP ne quitte le système. Templates et fréquence sont éditables à chaud depuis le backoffice.

### Tables

**`milk_pools`** — un pool = un produit. Le `system_role` pointe sur le wallet `users.system_role` qui détient les CAMP du pool.

| Colonne          | Type        | Notes                                                       |
|------------------|-------------|-------------------------------------------------------------|
| `id` (PK)        | INT auto    |                                                             |
| `symbol` (UNQ)   | VARCHAR(32) | ex: `LAIT-ENTIER`                                           |
| `name`           | VARCHAR(64) | libellé pour l'UI                                           |
| `reserve_camp`   | BIGINT      | CAMP entiers détenus par le pool                            |
| `reserve_milk`   | BIGINT      | milli-bouteilles (1 btl = 1000)                             |
| `fee_pct`        | FLOAT       | frais swap (défaut 0, en %, prélevé sur l'input)            |
| `status`         | VARCHAR     | `active` / `paused`                                         |
| `chaos_enabled`  | BOOLEAN     | un pool peut être exempté du bot                            |
| `system_role`    | VARCHAR(64) | `milk_pool_<slug>` — lié à `users.system_role`              |
| `initial_camp`   | BIGINT      | snapshot d'amorçage (pour calculer la dérive)               |
| `initial_milk`   | BIGINT      | idem                                                         |

**`milk_positions`** — stock de lait par user et par pool. `avg_cost` est le prix moyen pondéré d'achat (CAMP/btl) — utilisé pour la base de coût UI. Vendre **ne modifie pas** `avg_cost` ; seul un buy l'actualise.

**`milk_trades`** — tape de tous les swaps (`buy` ou `sell`). Garde `price_before`, `price_after`, `fee`, `tx_hash` pour audit.

**`milk_chaos_events`** — historique de chaque event chaos appliqué. `kind ∈ {famine, overstock, spoil, import}`, `delta_milk` signé (négatif = retrait), `narrative` est le texte affiché à l'UI (templated avec placeholders `{pct}/{abs_pct}/{n}/{abs_n}`), `triggered_by ∈ {bot, admin}`.

**`milk_chaos_templates`** — catalogue de scénarios tirables par le bot. Chaque template :
- `slug`, `kind`, `weight` (poids dans le tirage), `enabled`.
- `delta_type ∈ {pct, bottles}` : si `pct`, `delta_min/max` sont en % du `reserve_milk` ; si `bottles`, en bouteilles absolues.
- `narrative` avec placeholders. Ex: `🇨🇳 Boom export vers la Chine (-{abs_pct}% du stock local)`.

### Math AMM (`services/amm.py`)

```
buy_quote(reserve_camp, reserve_milk, fee_pct, camp_in):
    fee = camp_in * fee_pct / 100
    camp_in_net = camp_in - fee
    new_reserve_camp = reserve_camp + camp_in_net
    new_reserve_milk = (reserve_camp * reserve_milk) // new_reserve_camp   # k préservé via floor div
    milk_out = reserve_milk - new_reserve_milk

sell_quote(reserve_camp, reserve_milk, fee_pct, milk_in):
    new_reserve_milk = reserve_milk + milk_in
    new_reserve_camp = (reserve_camp * reserve_milk) // new_reserve_milk
    camp_out_gross = reserve_camp - new_reserve_camp
    fee = camp_out_gross * fee_pct / 100
    camp_out = camp_out_gross - fee
```

`k` peut dériver très légèrement vers le haut à cause du floor div + des fees qui restent dans le pool. C'est attendu. Le prix marginal est `reserve_camp / reserve_milk * MILK_UNIT` (CAMP par bouteille).

### Endpoints

| Méthode | Route                                       | Auth   | Description                                              |
|---------|---------------------------------------------|--------|----------------------------------------------------------|
| GET     | `/milk/pools`                               | user   | Liste pools actifs + prix courant                        |
| GET     | `/milk/pools/{symbol}`                      | user   | Détail d'un pool                                          |
| GET     | `/milk/pools/{symbol}/chart?minutes=`       | user   | Série temporelle (1..43200 min) à partir des trades + chaos |
| GET     | `/milk/pools/{symbol}/quote?side=&amount=`  | user   | Preview du swap (renvoie out, fee, price impact)          |
| POST    | `/milk/pools/{symbol}/swap`                 | user   | Exécute le swap (`SELECT FOR UPDATE` sur la row pool)     |
| GET     | `/milk/pools/{symbol}/trades`               | user   | Tape récente d'un pool                                    |
| GET     | `/milk/pools/{symbol}/chaos`                | user   | Historique chaos d'un pool                                |
| GET     | `/me/milk/positions`                        | user   | Mes positions (toutes pools)                              |
| GET     | `/me/milk/trades`                           | user   | Mes trades                                                 |
| GET     | `/admin/milk/pools`                         | admin  | Pools + balance CAMP on-chain du wallet pool              |
| POST    | `/admin/milk/pools`                         | admin  | Créer un pool (crée aussi le compte système associé)      |
| PATCH   | `/admin/milk/pools/{id}`                    | admin  | Update `fee_pct`, `chaos_enabled`, `status`               |
| POST    | `/admin/milk/pools/{id}/inject`             | admin  | Chaos manuel (`kind`, `delta_milk`, `narrative`)          |
| GET     | `/admin/milk/chaos`                         | admin  | Historique chaos (filtrable par pool, max 100)            |
| GET     | `/admin/milk/trades`                        | admin  | Tous les trades (filtrable par pool)                      |
| GET     | `/admin/milk/templates`                     | admin  | Liste des templates                                       |
| POST    | `/admin/milk/templates`                     | admin  | Créer un template                                          |
| PATCH   | `/admin/milk/templates/{id}`                | admin  | Update (slug, kind, delta_min/max, narrative, weight, enabled) |
| DELETE  | `/admin/milk/templates/{id}`                | admin  | Suppression                                                |
| POST    | `/admin/milk/templates/{id}/preview`        | admin  | Simulate un tirage + delta + narrative rendu              |
| GET     | `/admin/milk/chaos/analysis?reference_bottles=` | admin | Espérance de drift banque + bias stock + projection/jour, **cap de volatilité appliqué** (cf. infra) |

### Pattern swap

`POST /milk/pools/{symbol}/swap` (cf. `services/milk.py::swap`) :

1. `SELECT ... FOR UPDATE` sur la row pool (sérialise les swaps concurrents — sans ça, deux users qui swappent en même temps verraient la même réserve et créeraient des incohérences classiques type front-running / TOCTOU sur AMM).
2. `quote(pool, side, amount)` puis vérification `_check_slippage(q, expected_price, max_slippage_pct)`.
3. **Buy** : `escrow.lock(user → milk_pool_<slug>, amount)` → si OK, applique la quote (`reserve_camp`, `reserve_milk`, `MilkPosition.balance_milk +=`, `avg_cost` recalculé pondéré), persiste un `MilkTrade`.
4. **Sell** : on retire `amount` du `MilkPosition.balance_milk` **avant** la release (pour qu'un rollback côté tx remette tout d'aplomb), puis `escrow.release(milk_pool_<slug> → user, amount_out)`. Persiste un `MilkTrade`.

`avg_cost` est mis à jour **seulement aux buys** (moyenne pondérée). Les sells n'y touchent pas — le coût moyen des bouteilles restantes ne change pas quand on en vend.

### Position dict : valeur réalisable vs mark-to-market

`services/milk.py::position_dict` expose pour chaque position :
- `current_value_camp` : valeur mark-to-market (`balance_milk × prix_spot`). Théorique — surestime systématiquement parce qu'elle ne prend pas en compte le price impact qu'une vente totale provoquerait.
- `realisable_value_camp` : ce qu'on touche **vraiment** si on solde tout maintenant (= `amm.sell_quote(reserves, fee_pct, balance_milk).amount_out`). Honnête.
- `cost_basis_camp`, `pnl_camp` (mark-to-market), `realisable_pnl_camp` (réaliste), `price_impact_sell_all_pct`.

La vue `MilkTradeView.vue` utilise par défaut `realisable_value_camp` et `realisable_pnl_camp`, avec un `<details>` pour expliquer la différence si l'impact est notable.

### Bot chaos (`main.py::_chaos_loop`)

Boucle async lancée au démarrage de l'app. Chaque tick :
1. Relit `milk_chaos_tick_seconds` (60..86400, défaut 900s) et `milk_chaos_proba_pct` (0..100, défaut 25) dans `app_settings`.
2. Pour chaque pool `active` et `chaos_enabled` : tire à `proba_pct%` si un event tombe.
3. Si oui, `milk.pick_template()` (tirage pondéré sur `MilkChaosTemplate.enabled`), puis `apply_chaos()` :
   - `_delta_from_template()` calcule un delta brut (uniform sur `[delta_min, delta_max]`, interprété en `%` ou en btl selon `delta_type`).
   - `clamp_to_volatility(delta_milk, reserve_milk, max_vol_pct)` plafonne le delta à `±max_vol_pct%` de variation de **prix** (cap asymétrique côté lait : `-max/(100+max)` pour les famines, `+max/(100-max)` pour les overstocks — un cap de 20% sur prix = -16.67% / +25% sur lait). Le param `milk_chaos_max_volatility_pct` (défaut 20) vit dans `app_settings`.
   - Persiste un `MilkChaosEvent` (avec `triggered_by='bot'`) et update `pool.reserve_milk`.

Le bot ne touche **jamais** `reserve_camp` : la conservation des CAMP du système reste vraie. Seul le prix bouge.

### Analyse d'espérance banque (`chaos_analysis`)

`GET /admin/milk/chaos/analysis` calcule pour le catalogue actif :
- `weighted_avg_delta_milk_pct` (bias stock — positif = milk a tendance à grossir, donc prix à baisser),
- `weighted_avg_abs_delta_pct` (volatilité moyenne),
- `weighted_avg_bank_drift_pct` (espérance de drift de la banque, formule fermée sur `E[sqrt(milk_after/milk_before) − 1]`).

Le cap de volatilité (`max_vol_pct` lu depuis `app_settings`) **est appliqué** : chaque template est clampé sur `[cap_lo, cap_hi]` avant intégration, avec masse concentrée sur chaque borne pour la part qui dépasserait. Sans ça, les templates à gros range (ex: `milking_record [+100, +400 btl]` sur ref 200 btl = +50%..+200%) gonflaient artificiellement le drift attendu.

**Hypothèse importante** affichée dans l'UI : ce drift suppose que les holders rééquilibrent au prix d'avant choc (vendre après famine, racheter après overstock). Sans volume de trade, la banque garde exactement son CAMP — c'est un upper bound conditionnel, pas une rente.

### Front (`views/MilkView.vue` + `views/lait/MilkTradeView.vue`)

- **`MilkView.vue`** (hub) : grid des pools avec prix courant + sparkline + variation. Remplace l'ancien placeholder.
- **`MilkTradeView.vue`** : un pool sélectionné.
  - Chart SVG `viewBox="0 0 600 200"`, série de prix dérivée des trades + chaos events. Y-axis avec labels prix, X-axis avec ticks temps. Ranges sélectionnables `15min / 1h / 24h / 7j` (le bouton 30j a été retiré, pas utile à l'échelle de jeu).
  - **Mes markers buy/sell** uniquement (on filtre par `wallet.me.username`), tooltip HTML overlay (et pas `<title>` SVG, qui ne déclenche pas l'hover sur tous les navigateurs).
  - Card swap : buy/sell tabs, input avec Max button (sell), preview live debouncé (220ms), `<details>` "Avancé" qui contient le slippage tolérance (caché par défaut pour ne pas perdre les débutants).
  - Position : Stock, Valeur réalisable (avec badge `impact -X%` si notable), Performance, P&L. Un `<details>` "Pourquoi pas la valeur au prix affiché ?" explique le price impact.
  - Listes : trades récents + chaos récents avec narrative.

#### Pattern "Sell-all par bouteille pleine"

Subtilité : `formatBottles(balance_milk)` doit utiliser `Math.floor`, pas `toFixed(2)`. Sinon une balance à 999 milli s'affiche "1.00 btl" mais la vente de 1 btl (1000 milli) est refusée. Le bouton Max et l'input de quantité côté sell sont aussi clampés sur `balance_milk` exact (et la conversion bouteilles → milli utilise `Math.round` pour absorber la dust flottante).

### Admin (`views/admin/AdminMilkView.vue`)

- **Pools** : grid avec balance CAMP on-chain du wallet pool, contrôles `pause/resume`, `chaos enabled`, modal "Injecter chaos" (kind + delta + narrative custom).
- **Card "🤖 Bot chaos · fréquence"** : 3 tuiles `tick_seconds`, `proba_pct`, `max_volatility_pct` éditables (validation backend), + cadence estimée (`events/h` calculée depuis les settings et le nombre de pools actifs).
- **Card "💰 Espérance banque · catalogue chaos"** : 3 tuiles drift moyen / bias stock / projection jour, expliquées et avec un encart ⚠️ rappelant l'hypothèse "si rééquilibrage". Table collapsible par template (slug, kind, weight share, Δ moyen lait, E[banque]).
- **Templates** : tableau éditable (slug, kind, delta range, narrative avec placeholders, weight, enabled). Modal preview pour tester un template sans l'appliquer.
- **Historique chaos** : tape paginée (10/page, fetch limit 100), toutes pools confondues.

### Concurrence

`SELECT ... FOR UPDATE` sur la row `milk_pools` est obligatoire à chaque swap (sinon front-running entre deux swaps quasi-simultanés). Le bot chaos tourne en arrière-plan et n'utilise pas `FOR UPDATE` — il accepte qu'un swap user puisse passer "entre" la lecture et l'écriture de `reserve_milk`, parce qu'il commit son delta sur la valeur observée. L'invariant à préserver est juste : `reserve_milk` ne descend jamais sous `MIN_RESERVE_MILK = 1000` (1 btl), pour éviter une division par zéro / prix infini.

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

### Page Échange — QR send/receive

Pas de nouvel endpoint backend : la page `/exchange` réutilise `POST /transfer` existant pour l'envoi. Particularités frontend :

- **Format QR** : on encode `camplong:<username>` (et pas l'adresse on-chain), parce que `/transfer` prend un `to_username`. Le `ScanQrLayer` accepte aussi un username brut comme tolérance, et refuse net les QR qui ne matchent pas (pas d'envoi à un destinataire arbitraire scanné depuis n'importe où). Pour étendre plus tard (montant pré-rempli, mémo) : passer à un format URI plus riche, ex. `camplong:<username>?amount=10&note=biere`.
- **Scan** : utilise l'API native `BarcodeDetector` (Chrome Android, Safari iOS 17+). Pas de fallback type `jsqr` — sur navigateur non supporté on affiche un message clair et on désactive le scan. `getUserMedia({ facingMode: 'environment' })` pour la caméra arrière par défaut.
- **Self-send** : le scan refuse explicitement son propre username (compare avec `wallet.me.username`).
- Sur Wallet, l'adresse on-chain n'est plus un lien vers BaseScan : c'est une zone tactile qui copie au tap (feedback `✓ copié` 1.5 s). Les anciens boutons "Copier adresse" et "Rafraîchir" ont sauté — le refresh se fait au montage de chaque vue qui a besoin du solde.
- L'historique (`HistoryList.vue`) est paginé client-side, 8 tx par page. Pas de pagination serveur : `/history` renvoie déjà au max 100 entrées, ça tient en mémoire sans souci.
